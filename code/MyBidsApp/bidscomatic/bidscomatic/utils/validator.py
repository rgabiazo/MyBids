"""Tools for locating a BIDS root directory and running the BIDS validator."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Optional

import structlog

log = structlog.get_logger()


def find_bids_root_upwards(start: Path) -> Optional[Path]:
    """Return the nearest ancestor containing ``dataset_description.json``.

    Args:
        start: Path inside or below the dataset.

    Returns:
        ``Path`` to the dataset root if found, otherwise ``None``.
    """
    cur = start.resolve()
    if cur.is_file():
        cur = cur.parent
    for parent in (cur, *cur.parents):
        if (parent / "dataset_description.json").is_file():
            return parent
    return None


def run_bids_validator(root: Path) -> bool:
    """Invoke the external ``bids-validator`` CLI for *root*.

    The command output is streamed directly to the console. The return value
    indicates whether the validator exited without critical errors.

    Args:
        root: Path to the BIDS dataset root.

    Returns:
        ``True`` if validation finishes without critical errors, otherwise
        ``False``.
    """
    cmd = ["bids-validator", str(root)]
    log.debug("Node command: %s", cmd)
    try:
        proc = subprocess.run(cmd)
    except FileNotFoundError:
        log.error("'bids-validator' not found in PATH. Install it with 'npm install -g bids-validator'.")
        return False
    if proc.returncode == 0:
        log.info("BIDS validator passed with no critical errors.")
        return True
    log.error("bids-validator reported issues (exit code %s)", proc.returncode)
    return False
