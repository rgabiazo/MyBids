"""
Utility helpers for logging differences between local and remote file sets.

This module contains lightweight helpers that compare the set of filenames
found *locally* with those present on a *remote* SFTP location that mirrors a
Brain Imaging Data Structure (BIDS)‑compatible layout.  The comparison is
strictly filename‑based – no checksum or timestamp validation is performed –
and is intended to provide quick feedback when synchronising derivatives or
raw data between a workstation and CBRAIN‑registered storage.

Typical usage inside a download / upload workflow::

    compare_local_remote_files(
        local_path  = "/path/to/sub‑01/ses‑01/anat",
        local_files = ["sub‑01_ses‑01_T1w.nii.gz", "sub‑01_ses‑01_T1w.json"],
        remote_path = "sub‑01/ses‑01/anat",
        remote_files= ["sub‑01_ses‑01_T1w.nii.gz"]
    )

The function logs four separate INFO‑level messages:

* files present on **both** sides
* files present **only locally**
* files present **only remotely**
* a final notice when *no* files exist on either side

The caller decides how to act on these differences; the helper keeps a clear
separation of *reporting* from *synchronisation logic*, in line with the
single‑responsibility principle.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Iterable, List, Sequence

logger = logging.getLogger(__name__)

# -----------------------------------------------------------------------------
# Public helpers
# -----------------------------------------------------------------------------

def compare_local_remote_files(
    local_path: str | Path,
    local_files: Sequence[str] | Iterable[str],
    remote_path: str | Path,
    remote_files: Sequence[str] | Iterable[str],
) -> None:
    """Log the intersection and differences between two filename sequences.

    Args:
        local_path: Absolute or relative path to the local directory being
            inspected.  Used *only* for clearer log messages; the path is not
            touched on disk.
        local_files: Filenames found under *local_path* (no directory part).
        remote_path: Remote directory in CBRAIN / SFTP space.  Again, this is
            logged verbatim – the function performs no remote I/O.
        remote_files: Filenames reported under *remote_path*.

    Returns:
        ``None`` – the function has side‑effects only (``logger.info`` calls).

    Notes:
        *Empty* sequences are allowed; the helper will emit a single summary
        message when neither side contains files.  This keeps log output
        concise while still signalling that the comparison took place.
    """
    # Convert to *sets* for efficient membership tests and to ignore order &
    # duplicates that may arise from sloppy upstream collection logic.
    local_set = set(local_files)
    remote_set = set(remote_files)

    both: List[str] = sorted(local_set & remote_set)
    only_local: List[str] = sorted(local_set - remote_set)
    only_remote: List[str] = sorted(remote_set - local_set)

    # ------------------------------------------------------------------
    # Emit human‑readable summaries.  Messages are deliberately short so
    # that downstream CLI tools can remain uncluttered while still giving
    # analysts enough context to act (e.g. re‑sync, investigate, ignore).
    # ------------------------------------------------------------------
    if both:
        logger.info(
            "[CHECK] Files present on *both* local (%s) and remote (%s): %s",
            local_path,
            remote_path,
            both,
        )

    if only_local:
        logger.info(
            "[CHECK] Files present *only locally* (missing on remote %s): %s",
            remote_path,
            only_local,
        )

    if only_remote:
        logger.info(
            "[CHECK] Files present *only remotely* (missing in %s): %s",
            local_path,
            only_remote,
        )

    # A dedicated message helps distinguish an *empty directory* from a case
    # where *all* files match – both are valid states that may require
    # different decisions in a data‑transfer pipeline.
    if not both and not only_local and not only_remote:
        logger.info(
            "[CHECK] No files found in either %s or %s.",
            local_path,
            remote_path,
        )
