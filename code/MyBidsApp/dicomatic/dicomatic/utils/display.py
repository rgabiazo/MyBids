"""
Presentation helpers for CLI commands.

The functions here format and print study information, tables, and
download summaries.  Pure string/console logic lives here so that
higher-level workflow code remains focused on orchestration rather than I/O.
"""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

import click
import tableprint as tp

from dicomatic.utils.bids_helpers import session_number, subject_number
from dicomatic.utils.naming import build_bids_basename  # noqa: F401 (re-export use)

# -----------------------------------------------------------------------------#
# Internal helpers                                                             #
# -----------------------------------------------------------------------------#
def _echo_count(kind: str, n: int) -> None:
    """Emit a one-line “Found N <kind>(s)” banner."""
    label = kind if n == 1 else kind + "s"
    click.echo(f"Found {n} {label}:")


# -----------------------------------------------------------------------------#
# Public study / patient listings                                              #
# -----------------------------------------------------------------------------#
def display_studies(studies: List[Dict[str, str]]) -> None:
    """Print a simple numbered list of studies to stdout.

    Args:
        studies: List of raw study dicts produced by the query parser.
    """
    _echo_count("study", len(studies))
    for i, st in enumerate(studies, start=1):
        click.echo(
            f"{i}. Date: {st.get('study_date') or 'N/A'}   "
            f"Patient: {st.get('patient_name')}   "
            f"Desc: {st.get('study_description')}   "
            f"UID: {st.get('study_uid')}"
        )


def display_patients(studies: List[Dict[str, str]]) -> None:
    """Print a unique, alphabetically sorted list of patient names."""
    patients = sorted({st["patient_name"] for st in studies if st.get("patient_name")})
    _echo_count("patient", len(patients))
    for p in patients:
        click.echo(f"- {p}")


# -----------------------------------------------------------------------------#
# BIDS-grouped display helpers                                                 #
# -----------------------------------------------------------------------------#
def format_session_block(
    ses_label: str,
    studies: List[Dict[str, str]],
    list_studies: bool = False,
) -> str:
    """Return a human-readable block summarising one BIDS session."""
    header = f"  {ses_label} ({len(studies)} studies)"
    if not list_studies:
        return header

    # Indent individual study lines underneath the session header
    lines = [
        f"    • Date: {st.get('study_date', 'N/A')}   "
        f"Patient: {st.get('patient_name', '')}   "
        f"UID: {st.get('study_uid', '')}"
        for st in studies
    ]
    return "\n".join([header] + lines)


def display_session_block(
    ses_label: str,
    studies: List[Dict[str, str]],
    list_studies: bool = False,
) -> None:
    """Print one session block."""
    click.echo(format_session_block(ses_label, studies, list_studies))


def display_subject_block(
    sub_label: str,
    sessions: Dict[str, List[Dict[str, str]]],
    list_studies: bool = False,
) -> None:
    """Print all sessions for a single subject."""
    click.echo(f"\nSubject: {sub_label}")
    for ses_label in sorted(sessions.keys(), key=session_number):
        display_session_block(ses_label, sessions[ses_label], list_studies)


def display_grouped_studies(
    grouped: Dict[str, Dict[str, List[Dict[str, str]]]],
    list_studies: bool = False,
) -> None:
    """Pretty-print ``{sub:{ses:[studies]}}`` structures in a tree layout."""
    for sub_label in sorted(grouped.keys(), key=subject_number):
        display_subject_block(sub_label, grouped[sub_label], list_studies)


def display_grouped_studies_table(
    grouped: Dict[str, Dict[str, List[Dict[str, str]]]],
    show_demographics: bool = False,
) -> None:
    """Render grouped studies as an ASCII-boxed table.

    Args:
        grouped: Mapping produced by ``group_studies_by_bids``.
        show_demographics: When ``True`` include Age and Sex columns.
    """
    # Column width caps to keep tables narrow on typical terminals
    COL_CAPS = {"Patient": 24, "Age": 4, "Sex": 3}

    for sub_label in sorted(grouped.keys(), key=subject_number):
        click.echo(f"\n=== Subject: {sub_label} ===\n")
        for ses_label in sorted(grouped[sub_label].keys(), key=session_number):
            studies = grouped[sub_label][ses_label]
            click.echo(f"-- Session: {ses_label} --")

            headers = ["Date", "Patient"]
            if show_demographics:
                headers += ["Age", "Sex"]
            headers.append("UID")

            # Build row matrix
            rows: List[List[str]] = []
            for st in studies:
                row = [
                    st.get("study_date", "N/A"),
                    st.get("patient_name", ""),
                ]
                if show_demographics:
                    row += [
                        st.get("patient_age", ""),
                        st.get("patient_sex", ""),
                    ]
                row.append(st.get("study_uid", ""))
                rows.append(row)

            # Hard truncate long cells before width calculation
            rows = truncate_rows(rows, headers, COL_CAPS)

            widths = [
                max(len(h), *(len(r[i]) for r in rows))
                for i, h in enumerate(headers)
            ]

            sep = "+" + "+".join("-" * (w + 2) for w in widths) + "+"
            hdr = "|" + "|".join(f" {h.ljust(w)} " for h, w in zip(headers, widths)) + "|"

            click.echo(sep)
            click.echo(hdr)
            click.echo(sep)
            for row in rows:
                line = "|" + "|".join(
                    f" {row[i].ljust(widths[i])} " for i in range(len(headers))
                ) + "|"
                click.echo(line)
            click.echo(sep)
            click.echo("")  # trailing blank line for readability


# -----------------------------------------------------------------------------#
# Download-summary helpers                                                     #
# -----------------------------------------------------------------------------#
def summarize_downloads(plans: List[Any], include_session: bool = True) -> None:
    """Print an overview table for a batch of :class:`DownloadPlan` objects.

    Args:
        plans: Arbitrary objects implementing ``.path`` and ``.study`` attrs
               (the dataclass from ``dicomatic.models`` fits this contract).
        include_session: Hide the *Session* column when working with flattened
                         directory layouts.
    """
    if not plans:
        click.echo("\n[INFO] No studies to download.\n")
        return

    click.echo(f"\n=== Downloading {len(plans)} studies ===")
    rows: List[List[str]] = []
    for plan in plans:
        # Derive subject / session folder names from the plan path when the
        # attributes are missing (backwards-compat for legacy objects).
        sub_dir = (
            plan.sub_label
            if getattr(plan, "sub_label", None)
            else os.path.basename(os.path.dirname(os.path.dirname(plan.path)))
        )
        uid = plan.study.get("study_uid", "") or ""
        uid_disp = uid if len(uid) <= 30 else uid[:27] + "…"

        if include_session:
            ses_dir = (
                plan.ses_label
                if getattr(plan, "ses_label", None)
                else os.path.basename(os.path.dirname(plan.path))
            )
            rows.append([sub_dir, ses_dir, uid_disp])
        else:
            rows.append([sub_dir, uid_disp])

    headers = ["Subject", "Session", "UID"] if include_session else ["Subject", "UID"]
    tp.table(rows, headers=headers)


# -----------------------------------------------------------------------------#
# Pure utility                                                                 #
# -----------------------------------------------------------------------------#
def truncate_rows(
    rows: List[List[str]],
    headers: List[str],
    caps: Dict[str, int],
) -> List[List[str]]:
    """Return a copy of *rows* with overly long cells truncated.

    Args:
        rows:     2-D list of text cells.
        headers:  Header names aligned with row indices.
        caps:     Per-header maximum length.

    Returns:
        List of new, possibly truncated, rows.
    """
    out: List[List[str]] = []
    for row in rows:
        new_row = []
        for i, cell in enumerate(row):
            limit = caps.get(headers[i])
            if limit and len(cell) > limit:
                new_row.append(cell[: limit - 1] + "…")
            else:
                new_row.append(cell)
        out.append(new_row)
    return out
