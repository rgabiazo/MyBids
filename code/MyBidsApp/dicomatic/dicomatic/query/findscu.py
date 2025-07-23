"""Execute dcm4che ``findscu`` via Docker and return the output.

This module only runs the command and performs logging. Argument
construction is handled by :mod:`dicomatic.query.builder`.
"""

from __future__ import annotations

import logging
import subprocess
from typing import List, Optional

log = logging.getLogger(__name__)


def run_findscu(cmd: List[str], debug: bool = False) -> Optional[str]:
    """Run ``findscu`` and capture its output.

    Args:
        cmd: Full command-line token list, for example
            ``["docker", "run", "--rm", "--entrypoint", "/opt/dcm4che/bin/findscu", …]``.
        debug: When ``True``, emit verbose logging.

    Returns:
        str | None: Raw stdout on success or ``None`` on error.
    """
    if debug:
        log.debug("Running findscu: %s", " ".join(cmd))

    try:
        # Capture stdout/stderr in text mode; allow non-zero exit codes.
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    except Exception as exc:  # Broad except is intentional for subprocess failure
        if debug:
            log.debug("Subprocess execution failed: %s", exc)
        return None

    # Non-zero exit code indicates an error; return None for caller handling
    if result.returncode != 0:
        if debug:
            log.debug("findscu exited with code %d", result.returncode)
            log.debug("STDERR:\n%s", result.stderr)
        return None

    if debug:
        log.debug("Raw output (%d bytes)", len(result.stdout))
        for i, line in enumerate(result.stdout.splitlines(), start=1):
            log.debug("%04d: %r", i, line)

    return result.stdout
