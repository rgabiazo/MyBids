"""
Filtering utilities for grouped DICOM study dictionaries.

The helpers operate on the nested mapping produced by
:func:`dicomatic.utils.bids_helpers.group_studies_by_bids`::

    {
        "sub-001": {
            "ses-01": [study_dict, …],
            "ses-02": [study_dict, …],
        },
        "sub-002": { … },
    }

Each function returns a **new** dictionary; the original object is
never modified in place.
"""

from __future__ import annotations

import copy
import re
from typing import Dict, List, Optional, Tuple

# ------------------------------------------------------------------------- #
# _subject_number / _session_number                                          #
# ------------------------------------------------------------------------- #
# Helper functions for natural sorting of BIDS labels.                       #
# They return large sentinel values when digits are absent, ensuring that    #
# non-standard labels are pushed to the end of any sorting operation.        #
# ------------------------------------------------------------------------- #


def _subject_number(sub_label: str) -> int:
    """Return the integer part of ``sub-XXX`` for sorting purposes."""
    m = re.search(r"\d+", sub_label)
    return int(m.group()) if m else 999_999


def _session_number(ses_label: str) -> int:
    """Return the integer part of ``ses-XX`` for sorting purposes."""
    m = re.search(r"\d+", ses_label)
    return int(m.group()) if m else 999_999


# ------------------------------------------------------------------------- #
# Public helpers                                                             #
# ------------------------------------------------------------------------- #


def numeric_session_grouping(
    grouped: Dict[str, Dict[str, List[dict]]]
) -> Dict[str, Dict[str, List[dict]]]:
    """Relabel sessions chronologically as ``ses-01``, ``ses-02`` …

    Args:
        grouped: Mapping of subject → session → list[study_dict].

    Returns
    -------
    dict
        New mapping with sessions renamed in date order for every subject.
    """
    out: Dict[str, Dict[str, List[dict]]] = {}
    for sub, sessions in grouped.items():
        order = sorted(sessions.keys(), key=_session_number)
        out[sub] = {f"ses-{idx:02d}": sessions[old] for idx, old in enumerate(order, 1)}
    return out


def prune_grouped_studies(
    grouped: Dict[str, Dict[str, List[dict]]],
    exclude_subjects: List[str],
    exclude_sessions: List[Tuple[str, str]],
    exclude_patients: List[str],
    exclude_uids: List[str] | None = None,
) -> Dict[str, Dict[str, List[dict]]]:
    """Remove subjects, sessions, patient names or UIDs from a grouping.

    Args:
        grouped: Original subject/session mapping.
        exclude_subjects: Subject identifiers to drop (numeric or *sub-###*).
        exclude_sessions: Pairs of ``(subject, session)`` to drop.
        exclude_patients: DICOM *PatientName* strings to drop.
        exclude_uids: StudyInstanceUID values to drop.

    Returns
    -------
    dict
        Deep-copied mapping with the requested entries removed.
    """
    out = copy.deepcopy(grouped)

    # -- 1. Drop entire subjects -------------------------------------
    for s in exclude_subjects:
        if m := re.fullmatch(r"(?:sub-)?0*(\d+)", s):
            out.pop(f"sub-{int(m.group(1)):03d}", None)

    # -- 2. Drop specific subject/session pairs ----------------------
    for sub, ses in exclude_sessions:
        if not (m := re.fullmatch(r"(?:sub-)?0*(\d+)", sub)):
            continue
        sub_key = f"sub-{int(m.group(1)):03d}"
        ses_key = (
            f"ses-{int(ses):02d}"
            if ses.isdigit()
            else (ses if ses.startswith("ses-") else f"ses-{ses}")
        )
        out.get(sub_key, {}).pop(ses_key, None)
        if not out.get(sub_key):
            out.pop(sub_key, None)

    # -- 3. Drop studies by patient name -----------------------------
    if exclude_patients:
        for sub_key, sessions in list(out.items()):
            for ses_key, lst in list(sessions.items()):
                kept = [st for st in lst if st.get("patient_name") not in exclude_patients]
                if kept:
                    sessions[ses_key] = kept
                else:
                    sessions.pop(ses_key)
            if not sessions:
                out.pop(sub_key)

    # -- 4. Drop studies by UID --------------------------------------
    drop_uids = set(exclude_uids or [])
    if drop_uids:
        for sub_key, sessions in list(out.items()):
            for ses_key, lst in list(sessions.items()):
                kept = [st for st in lst if st.get("study_uid") not in drop_uids]
                if kept:
                    sessions[ses_key] = kept
                else:
                    sessions.pop(ses_key)
            if not sessions:
                out.pop(sub_key)

    return out


def filter_grouped_studies(
    grouped: Dict[str, Dict[str, List[dict]]],
    include_subjects: List[str],
    include_sessions: List[Tuple[Optional[str], str]],
    include_patients: List[str],
) -> Dict[str, Dict[str, List[dict]]]:
    """Return a subset of *grouped* that matches subject, session, and patient filters.

    Args:
        grouped: Mapping produced by
            :func:`dicomatic.utils.bids_helpers.group_studies_by_bids`.
        include_subjects: Subject identifiers to keep. Accepts either plain
            numbers (``"064"``) or canonical labels (``"sub-064"``). An empty
            list preserves all subjects.
        include_sessions: Sequence of ``(subject, session)`` tuples. The
            subject element may be ``None`` to act as a wildcard; session
            strings may be numeric (``"01"``), BIDS-style (``"ses-01"``), or
            descriptive tokens normalised elsewhere.
        include_patients: Patient-name strings to keep. An empty list disables
            patient-level filtering.

    Returns:
        dict: Deep-copied mapping containing only studies that satisfy every
        filter.
    """
    # Canonicalise subject filters to BIDS form.
    wanted_subs = {
        f"sub-{int(m.group(1)):03d}"
        for s in include_subjects
        if (m := re.fullmatch(r"(?:sub-)?0*(\d+)", s))
    }

    def _norm_ses(tok: str) -> str:
        """Return a canonical ``ses-XX`` label for *tok*."""
        return (
            f"ses-{int(tok):02d}"
            if tok.isdigit()
            else tok if tok.startswith("ses-")
            else f"ses-{tok}"
        )

    # Pre-compute normalised session filters.
    include_sess: List[Tuple[Optional[str], str]] = []
    for sub, ses in include_sessions:
        if sub is None:
            sub_key = None  # wildcard
        else:
            m = re.fullmatch(r"(?:sub-)?0*(\d+)", sub)
            sub_key = f"sub-{int(m.group(1)):03d}" if m else None
        include_sess.append((sub_key, _norm_ses(ses)))

    out: Dict[str, Dict[str, List[dict]]] = {}
    for sub_key, sessions in grouped.items():
        # Subject-level filtering.
        if wanted_subs and sub_key not in wanted_subs:
            continue

        kept: Dict[str, List[dict]] = {}
        for ses_key, lst in sessions.items():
            # Session-level filtering.
            if include_sess:
                allowed = any(
                    (inc_sub is None or inc_sub == sub_key) and inc_ses == ses_key
                    for inc_sub, inc_ses in include_sess
                )
                if not allowed:
                    continue

            # Patient-level filtering.
            if include_patients:
                lst = [st for st in lst if st.get("patient_name") in include_patients]

            if lst:
                kept[ses_key] = lst

        if kept:
            out[sub_key] = kept

    return out
