"""
Click wrapper for the ``bids`` sub-command.

The function defined below performs only argument parsing.  All
processing logic is delegated to
:func:`dicomatic.bids.planner.download_bids`.
"""

from __future__ import annotations

from typing import List, Optional  # Tuple no longer required

import click
from click import pass_context

from dicomatic.bids.planner import download_bids as _download_bids
from dicomatic.utils.cli_parse import parse_session_flags


@click.command("bids")
@pass_context
# --------------------------------------------------------------------------- #
# Global options – identical to the original implementation.                  #
# Only comments changed for clarity and style compliance.                     #
# --------------------------------------------------------------------------- #
@click.option(
    "-d",
    "--description",
    "desc",
    required=False,
    envvar="DICOMATIC_STUDY_DESCRIPTION",
    help="StudyDescription to search for (defaults to $DICOMATIC_STUDY_DESCRIPTION).",
)
@click.option(
    "-l",
    "--list-studies",
    is_flag=True,
    help="With grouped view: also print every study inside its session block.",
)
@click.option(
    "--numeric-sessions/--no-numeric-sessions",
    "numeric_sessions",
    default=True,
    help="Relabel sessions chronologically as ses-01, ses-02, …",
)
@click.option(
    "--reassign-session",
    "reassign_sessions",
    multiple=True,
    help="Reassign sessions: OLD_SUB:OLD_SES=NEW_SUB[:NEW_SES][,…].",
)
@click.option(
    "--exclude-subject",
    "exclude_subjects",
    multiple=True,
    help="Remove complete subject folders; accepts '001' or 'sub-001'.",
)
@click.option(
    "--exclude-session",
    "exclude_sessions",
    multiple=True,
    help="Remove specific sessions: SUB:SES (e.g. '001:baseline').",
)
@click.option(
    "--exclude-patient",
    "exclude_patients",
    multiple=True,
    help="Remove studies that match these PatientName values.",
)
@click.option("--exclude-uid", "exclude_uids", multiple=True, help="Remove specific StudyInstanceUIDs.")
@click.option(
    "--filter-subject",
    "include_subjects",
    multiple=True,
    help="Keep only these subjects; accepts '001' or 'sub-001'.",
)
@click.option(
    "--filter-session",
    "include_sessions",
    multiple=True,
    type=str,   # accept one raw token each time
    help=(
        "Session filter. Accepts '01', 'ses-01', or '064:01'. "
        "Legacy two-token form ('--filter-session 064 01') is also supported."
    ),
)
@click.option("--filter-patient", "include_patients", multiple=True, help="Keep only these PatientName values.")
@click.option(
    "--demographics/--no-demographics",
    "with_demographics",
    default=False,
    help="Add Age and Sex columns to the ASCII table output.",
)
@click.option(
    "--no-table",
    "no_table",
    is_flag=True,
    default=False,
    help="Disable ASCII table view; fall back to grouped listing.",
)
@click.option(
    "--dry-run",
    "dry_run",
    is_flag=True,
    help="Print destination paths without running cfmm2tar.",
)
@click.option(
    "--no-session-dirs",
    "no_session_dirs",
    is_flag=True,
    help="Flatten archives under sub-directory when subject has a single session.",
)
@click.option("--download", "download", is_flag=True, help="Execute cfmm2tar downloads.")
@click.option(
    "--create-metadata/--no-create-metadata",
    "create_metadata",
    default=None,
    help="Override YAML 'create_dicom_metadata' flag for this invocation.",
)
def bids(  # noqa: D401, C901 – complexity handled in planner
    ctx: click.Context,
    desc: Optional[str],
    list_studies: bool,
    numeric_sessions: bool,
    reassign_sessions: List[str],
    exclude_subjects: List[str],
    exclude_sessions: List[str],
    exclude_patients: List[str],
    exclude_uids: List[str],
    include_subjects: List[str],
    include_sessions: List[str],  # list of raw single-token flags
    include_patients: List[str],
    with_demographics: bool,
    no_table: bool,
    dry_run: bool,
    no_session_dirs: bool,
    download: bool,
    create_metadata: Optional[bool],
) -> None:
    """Dispatch the ``bids`` workflow.

    Args:
        ctx: Click context.
        desc: ``StudyDescription`` to search for.
        list_studies: Also print every study inside its session block.
        numeric_sessions: Relabel sessions chronologically as ``ses-01``.
        reassign_sessions: Session reassignment rules.
        exclude_subjects: Subject folders to remove.
        exclude_sessions: Session folders to remove.
        exclude_patients: Patient names to exclude.
        exclude_uids: ``StudyInstanceUID`` values to exclude.
        include_subjects: Subject folders to keep.
        include_sessions: Raw ``--filter-session`` flags.
        include_patients: Patient names to keep.
        with_demographics: Add age and sex columns to the table view.
        no_table: Disable the ASCII table view.
        dry_run: Print destination paths without running ``cfmm2tar``.
        no_session_dirs: Flatten archives when a subject has one session.
        download: Execute ``cfmm2tar`` downloads.
        create_metadata: Override the YAML ``create_dicom_metadata`` flag.

    Returns:
        None
    """
    # Convert single-token ``--filter-session`` flags to
    # ``(subject_label | None, session_label)`` tuples.
    parsed_sessions = parse_session_flags(include_sessions)

    _download_bids(
        ctx,
        desc=desc,
        list_studies=list_studies,
        numeric_sessions=numeric_sessions,
        reassign_sessions=list(reassign_sessions),
        exclude_subjects=list(exclude_subjects),
        exclude_sessions=list(exclude_sessions),
        exclude_patients=list(exclude_patients),
        exclude_uids=list(exclude_uids),
        include_subjects=list(include_subjects),
        include_sessions=parsed_sessions,          # patched argument
        include_patients=list(include_patients),
        with_demographics=with_demographics,
        no_table=no_table,
        dry_run=dry_run,
        no_session_dirs=no_session_dirs,
        download=download,
        create_metadata=create_metadata,
    )
