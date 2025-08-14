"""
Lightweight wrapper around the Node-based **bids-validator** CLI.

The helpers here locate the BIDS dataset root relative to a partial
path, invoke the external validator, and return a Boolean pass/fail
result.  This indirection keeps validation logic in one place and
avoids hard-coding dataset roots elsewhere in the code base.
"""

import logging
import os
import subprocess
from pathlib import Path
from typing import List, Optional

logger = logging.getLogger(__name__)


def bids_validator_cli(steps: List[str]) -> bool:
    """Run the Node bids-validator on the dataset containing *steps*.

    Args:
        steps: Sequence of path components (e.g. ``["sub-001", "ses-01", "anat"]``)
            pointing somewhere inside the BIDS dataset.  Wildcards are allowed.

    Returns:
        ``True`` if the validator completed without *critical* errors,
        otherwise ``False``.

    Notes:
        * This function does **not** raise on validation failure; it logs
          the outcome and returns ``False`` so callers can decide how to
          proceed.
        * The underlying executable **must** be discoverable on ``$PATH``.
          A helpful error is logged if it is missing.
    """
    if not steps:
        logger.error("No steps provided for bids-validator.")
        return False

    # Build an absolute path from the current working directory plus the
    # caller-supplied components.
    base_dir: Path = Path.cwd()
    partial_path: Path = base_dir.joinpath(*steps)
    if not partial_path.exists():
        # A missing path is not fatal for validation itself, so continue.
        logger.warning(
            "Partial path '%s' does not exist locally; searching upward for dataset root.",
            partial_path,
        )

    dataset_root: Optional[Path] = find_bids_root_upwards(partial_path)
    if dataset_root is None:
        logger.error("Could not locate dataset_description.json.")
        return False

    logger.info("Running bids-validator on: %s", dataset_root)
    cmd = ["bids-validator", str(dataset_root)]
    logger.debug("Node command: %s", cmd)

    try:
        proc = subprocess.run(cmd, capture_output=True, text=True)
    except FileNotFoundError:
        logger.error("'bids-validator' not found in PATH.  Install it with "
                     "'npm install -g bids-validator'.")
        return False
    except Exception as exc:  # Generic safeguard
        logger.error("Unexpected error while calling bids-validator: %s", exc)
        return False

    if proc.returncode == 0:
        logger.info("BIDS validator passed with no *critical* errors.")
        logger.debug("Validator output:\n%s", proc.stdout)
        return True

    # Non-zero exit → at least one critical error.
    logger.warning("BIDS validator reported issues:\n%s", proc.stdout or proc.stderr)
    return False


def find_bids_root_upwards(start_path: os.PathLike) -> Optional[Path]:
    """Walk upward from *start_path* until *dataset_description.json* is found.

    Args:
        start_path: File or directory inside (or below) a BIDS dataset.

    Returns:
        ``Path`` to the dataset root if found; otherwise ``None``.
    """
    current: Path = Path(start_path).resolve()
    if current.is_file():
        current = current.parent

    first_hit: Optional[Path] = None

    # Repeatedly ascend one directory level until reaching filesystem root.
    while True:
        dd_file = current / "dataset_description.json"
        logger.debug("Checking for BIDS root: %s", dd_file)
        if dd_file.is_file():
            if first_hit is None:
                first_hit = current
            if "derivatives" not in current.parts:
                return current

        parent = current.parent
        if parent == current:  # Reached filesystem root.
            break
        current = parent

    return first_hit
