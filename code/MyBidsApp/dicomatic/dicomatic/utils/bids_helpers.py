"""
Pure utilities for mapping raw DICOM study dictionaries onto a BIDS‑compatible
*subject*/ *session* directory hierarchy.  Filtering logic is intentionally
re‑exported from :pymod:`dicomatic.bids.filters` to keep concerns separated while
preserving the original public API.
"""

from __future__ import annotations

import os
import re
from collections import Counter
from typing import Dict, List, Optional, Tuple

from dicomatic.utils.session_map import (
    _extract_trailing,
    assign_session_label,
    build_session_map,
)

# -----------------------------------------------------------------------------
# Re‑export filter helpers so callers do not break after the refactor
# -----------------------------------------------------------------------------
from dicomatic.bids.filters import (  # noqa: F401  – re‑export is intentional
    numeric_session_grouping,
    prune_grouped_studies,
    filter_grouped_studies,
)

# -----------------------------------------------------------------------------
# BIDS‑folder discovery
# -----------------------------------------------------------------------------


def list_subject_folders(bids_root: str) -> Dict[str, List[str]]:
    """Return the ``sub‑*/ses‑*`` directory structure under *bids_root*.

    Args:
        bids_root: Absolute or relative path to the dataset root containing a
            valid ``dataset_description.json`` file.

    Returns:
        Dict[str, list[str]]: Mapping of subject labels to their session labels,
        e.g. ``{"sub-001": ["ses-01", "ses-02"]}``.  Only directories that
        match the BIDS naming pattern are included; non‑directory entries are
        ignored silently.
    """
    subjects: Dict[str, List[str]] = {}
    if not os.path.isdir(bids_root):  # Nothing to scan – return empty mapping
        return subjects

    for entry in os.listdir(bids_root):
        if not entry.startswith("sub-"):
            continue  # Skip non‑subject folders early
        sub_path = os.path.join(bids_root, entry)
        if not os.path.isdir(sub_path):
            continue  # Guard against symbolic links or files

        sessions = [
            ses
            for ses in os.listdir(sub_path)
            if ses.startswith("ses-")
            and os.path.isdir(os.path.join(sub_path, ses))
        ]
        subjects[entry] = sessions

    return subjects


# -----------------------------------------------------------------------------
# Subject / session parsing helpers
# -----------------------------------------------------------------------------


def parse_subject_digits(dicom_patient_name: str) -> Optional[str]:
    """Extract a numeric subject identifier from *PatientName*.

    The helper supports various separator conventions used on the scanner
    console.  A leading date chunk (``YYYY_MM_DD``) is discarded to avoid
    collisions when technologists prepend acquisition dates.

    Args:
        dicom_patient_name: Raw *PatientName* DICOM attribute.

    Returns:
        Normalised subject label (e.g. ``"sub-007"``) or *None* when the token
        cannot be located.
    """
    clean = dicom_patient_name.strip()
    tokens = re.split(r"[\s_\-]+", clean)

    # Skip ISO‑like date prefix if present ------------------------------------
    if (
        len(tokens) >= 3
        and re.fullmatch(r"\d{4}", tokens[0])
        and re.fullmatch(r"\d{2}", tokens[1])
        and re.fullmatch(r"\d{2}", tokens[2])
    ):
        tokens = tokens[3:]

    for tok in tokens:
        if m := re.fullmatch(r"[Pp]?0*(\d+)", tok):
            return f"sub-{int(m.group(1)):03d}"
    return None


def parse_trailing_substring(dicom_patient_name: str) -> Optional[str]:
    """Return anything after the subject ID token.

    Args:
        dicom_patient_name: Raw *PatientName* DICOM attribute.

    Returns:
        The trailing substring joined by underscores, or *None* when no token is
        found.
    """
    clean = dicom_patient_name.strip()
    tokens = re.split(r"[\s_\-]+", clean)

    # Drop leading date "YYYY_MM_DD" if present ------------------------------
    if (
        len(tokens) >= 3
        and re.fullmatch(r"\d{4}", tokens[0])
        and re.fullmatch(r"\d{2}", tokens[1])
        and re.fullmatch(r"\d{2}", tokens[2])
    ):
        tokens = tokens[3:]

    for i, tok in enumerate(tokens):
        if re.fullmatch(r"[Pp]?\d+", tok):  # Subject token located
            rest = tokens[i + 1 :]
            return "_".join(rest) if rest else None
    return None


def find_session_label(
    trailing: Optional[str], session_map: Optional[Dict[str, str]] = None
) -> Optional[str]:
    """Map a trailing token to a canonical ``ses-XX`` label.

    Args:
        trailing: Substring returned by
            :func:`parse_trailing_substring` / :pyfunc:`_extract_trailing`.
        session_map: Lookup table from trailing tokens to two‑digit session
            numbers (e.g. ``{"baseline": "01"}``).  When *None*, only the
            implicit rules are applied.

    Returns:
        Normalised session label or *None* when the token cannot be resolved.
    """
    if not trailing:
        return None

    t = trailing.lower().strip()

    # Explicit "ses-##" marker present ---------------------------------------
    if m := re.search(r"ses[-_]?(\d+)", t):
        return f"ses-{int(m.group(1)):02d}"

    # Pure numeric token ------------------------------------------------------
    if re.fullmatch(r"\d+", t):
        return f"ses-{int(t):02d}"

    # Custom tag resolved via session_map -------------------------------------
    if session_map and t in session_map:
        val = session_map[t]
        return val if val.startswith("ses-") else f"ses-{val}"

    return None


# -----------------------------------------------------------------------------
# Study grouping helpers
# -----------------------------------------------------------------------------


def subject_number(sub_label: str) -> int:
    """Return an integer key for natural sorting of subject labels."""
    m = re.search(r"\d+", sub_label)
    return int(m.group()) if m else 999_999


def session_number(ses_label: str) -> int:
    """Return an integer key for natural sorting of session labels."""
    m = re.search(r"\d+", ses_label)
    return int(m.group()) if m else 999_999


def group_studies_by_bids(
    studies: List[Dict[str, str]],
    session_map: Optional[Dict[str, str]] = None,
) -> Dict[str, Dict[str, List[Dict[str, str]]]]:
    """Bucket a flat list of studies into a two‑level BIDS mapping.

    The algorithm:
        1. Build or merge a ``session_map`` via
           :func:`dicomatic.utils.session_map.build_session_map`.
        2. Parse each *PatientName* into a canonical subject label using
           :func:`parse_subject_digits`.
        3. Derive a session label from the trailing tag (via
           :func:`assign_session_label`).
        4. Return a nested mapping ``{sub‑XXX: {ses‑YY: [study, …]}}``.

    Args:
        studies: Output of
            :func:`dicomatic.query.parser.parse_studies_with_demographics`.
        session_map: Optional pre‑computed mapping overriding the auto‑detected
            one.

    Returns:
        Dict[str, Dict[str, List[dict]]]: BIDS‑style grouping suitable for
        downstream planning helpers.
    """
    # 1) Construct or merge session mapping -----------------------------------
    sess_map = build_session_map(studies, explicit=session_map)

    # 2) Bucket studies by subject -------------------------------------------
    by_sub: Dict[str, List[Dict[str, str]]] = {}
    for st in studies:
        if sub := parse_subject_digits(st.get("patient_name", "")):
            by_sub.setdefault(sub, []).append(st)

    grouped: Dict[str, Dict[str, List[Dict[str, str]]]] = {}

    # 3) Assign each study to a session bucket --------------------------------
    for sub, slist in by_sub.items():
        # Sort chronologically so earliest scan dictates first session ---------
        slist_sorted = sorted(slist, key=lambda x: int(x.get("study_date", "0") or "0"))
        for st in slist_sorted:
            raw = st.get("patient_name", "").strip()
            trailing = _extract_trailing(raw)
            ses_lbl = assign_session_label(trailing, sess_map)
            if not ses_lbl:
                continue  # Skip unknown session tags silently
            grouped.setdefault(sub, {}).setdefault(ses_lbl, []).append(st)

    # 4) Natural sort order for pretty CLI output -----------------------------
    sorted_grouped: Dict[str, Dict[str, List[Dict[str, str]]]] = {}
    for sub in sorted(grouped.keys(), key=subject_number):
        sessions = grouped[sub]
        sorted_sessions = {s: sessions[s] for s in sorted(sessions.keys(), key=session_number)}
        sorted_grouped[sub] = sorted_sessions

    return sorted_grouped
