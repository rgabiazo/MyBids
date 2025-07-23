"""
Utility functions for filesystem-safe naming.

Functions here transform arbitrary free-text values (DICOM fields,
UIDs, etc.) into strings that are safe for POSIX filenames and that
conform to the naming rules enforced elsewhere in dicomatic.
"""

from __future__ import annotations

import re
from typing import Dict

__all__ = ["sanitize_for_filename", "build_bids_basename"]


# -----------------------------------------------------------------------------#
# Public helpers                                                                #
# -----------------------------------------------------------------------------#
def sanitize_for_filename(s: str) -> str:
    """Return *s* transformed into a portable filename token.

    Steps applied in order:

    1. Strip leading/trailing whitespace.
    2. Collapse internal whitespace into a single underscore.
    3. Replace characters outside ``[A-Za-z0-9_]`` with underscores.
    4. Collapse consecutive underscores.
    5. Remove leading/trailing underscores.

    Args:
        s: Raw text to normalise.

    Returns:
        Sanitised string suitable for use as a path component.
    """
    # Remove surrounding whitespace
    s = s.strip()
    # Replace any run of whitespace with one underscore
    s = re.sub(r"\s+", "_", s)
    # Substitute non-alphanumeric characters
    s = re.sub(r"[^A-Za-z0-9_]+", "_", s)
    # Collapse multiple underscores inserted by previous substitutions
    s = re.sub(r"_+", "_", s)
    # Final trim of underscores that might sit at either edge
    return s.strip("_")


def build_bids_basename(study: Dict[str, str]) -> str:
    """Construct the canonical ``*.tar`` filename for one study.

    Composition rules:

    * Study description → sanitised (see :func:`sanitize_for_filename`).
    * Study date → kept verbatim.
    * Patient name → stripped but otherwise preserved (spaces allowed).
    * UID → sanitised.

    Empty components are dropped, and remaining parts join with a single
    underscore.  The ``.tar`` extension is always appended.

    Args:
        study: Raw study dictionary containing at least
            ``study_description``, ``study_date``, ``patient_name``,
            and ``study_uid`` keys.

    Returns:
        Filename string, **without** directory path.
    """
    desc = sanitize_for_filename(study.get("study_description", ""))
    date = study.get("study_date", "").strip()
    patient = study.get("patient_name", "").strip()
    uid = sanitize_for_filename(study.get("study_uid", ""))

    parts = [desc, date, patient, uid]
    parts = [p for p in parts if p]  # discard empty chunks
    return "_".join(parts) + ".tar"
