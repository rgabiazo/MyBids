# ────────────────────────────────────────────────
# File: dicomatic/utils/session_map.py
# ────────────────────────────────────────────────
"""
Session-mapping utilities.

These helpers convert loosely formatted ``PatientName`` postfixes
(e.g., “baseline”, “endpoint”) into reproducible BIDS session labels
(``ses-01``, ``ses-02`` …).  All heuristics centralised here so that
session numbering logic stays consistent across the code-base.
"""

from __future__ import annotations

import re
from collections import Counter
from typing import Dict, List, Optional

# -----------------------------------------------------------------------------#
# Internal helpers                                                             #
# -----------------------------------------------------------------------------#
def _extract_trailing(name: str) -> Optional[str]:
    """Return the substring after the subject token inside *name*.

    A *PatientName* often follows the pattern::

        YYYY_MM_DD_<SUBJ>_<TRAILING_TAG>

    This function strips the optional leading date and subject ID,
    then joins the remaining tokens with underscores.

    Args:
        name: Raw DICOM *PatientName* string.

    Returns:
        Lower-case trailing tag or ``None`` when nothing follows the
        subject identifier.
    """
    tokens = re.split(r"[\s_\-]+", name.strip())

    # Drop a leading date chunk when present (YYYY MM DD).
    if len(tokens) >= 3 and all(re.fullmatch(r"\d{2,4}", t) for t in tokens[:3]):
        tokens = tokens[3:]

    # Skip until first numeric subject token, then return the rest.
    for i, tok in enumerate(tokens):
        if re.fullmatch(r"[Pp]?0*\d+", tok):
            return "_".join(tokens[i + 1 :]) or None

    return None


# -----------------------------------------------------------------------------#
# Public API                                                                    #
# -----------------------------------------------------------------------------#
def detect_trailing_tags(studies: List[Dict[str, str]]) -> List[str]:
    """Identify the two most frequent trailing tags in *studies*.

    Args:
        studies: List of raw study dicts.

    Returns:
        List containing up to two tags sorted by descending frequency.
    """
    trails = []
    for st in studies:
        tag = _extract_trailing(st.get("patient_name", ""))
        if tag:
            trails.append(tag.lower())

    common = Counter(trails).most_common(2)
    return [tag for tag, _ in common]


def build_session_map(
    studies: List[Dict[str, str]],
    *,
    explicit: Optional[Dict[str, str]] = None,
) -> Dict[str, str]:
    """Create a mapping ``trailing_tag → two-digit session number``.

    Priority rules:

    1. When *explicit* is provided, return it verbatim.
    2. Otherwise, auto-detect the two most common tags and map
       first→``"01"``, second→``"02"``.

    Args:
        studies: Study dictionaries used for automatic detection.
        explicit: Predefined mapping that overrides auto-detection.

    Returns:
        Dictionary such as ``{"baseline": "01", "endpoint": "02"}``.
    """
    if explicit:
        return explicit

    top_two = detect_trailing_tags(studies)
    return {tag: f"{idx + 1:02d}" for idx, tag in enumerate(top_two)}


def assign_session_label(
    trailing: Optional[str],
    session_map: Dict[str, str],
) -> Optional[str]:
    """Translate *trailing* into a BIDS ``ses-XX`` label using *session_map*.

    Args:
        trailing: Raw trailing tag extracted from *PatientName*.
        session_map: Mapping produced by :func:`build_session_map`.

    Returns:
        ``ses-##`` string or ``None`` when *trailing* is not recognised.
    """
    if not trailing:
        return None

    key = trailing.lower()
    if key not in session_map:
        return None

    return f"ses-{session_map[key]}"
