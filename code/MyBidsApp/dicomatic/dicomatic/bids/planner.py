"""
Workflow orchestrator for the *bids* command.

The Click wrapper defined in :pymod:`dicomatic.commands.bids` performs
only argument parsing; all heavy-lifting occurs in this module.

Key design notes
----------------
* The destination root for downloads remains
  ``<BIDS_ROOT>/sourcedata/dicom``.
* After every filter or transformation, each study dictionary is stamped
  with ``sub_label`` and ``ses_label`` so that downstream helpers
  (chiefly :func:`dicomatic.utils.planning.build_plans`) cannot lose
  track of re-assignments.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import click
from click import Context

from dicomatic.models import DownloadPlan as MetaPlan
from dicomatic.utils.bids_helpers import group_studies_by_bids
from dicomatic.utils.display import (
    display_grouped_studies,
    display_grouped_studies_table,
    summarize_downloads,
)
from dicomatic.utils.download_helpers import download_study, generate_dry_run_paths
from dicomatic.utils.metadata import write_metadata
from dicomatic.utils.planning import build_plans
from dicomatic.utils.project_root import find_bids_root
from dicomatic.utils.prompts import prompt_for_bids_downloads
from dicomatic.utils.reassign import normalize_label, parse_reassign_specs
from dicomatic.utils.session_map import build_session_map
from dicomatic.commands._shared import fetch_studies_interactive

# Filtering helpers live in a separate module to avoid circular imports
from dicomatic.bids.filters import (
    filter_grouped_studies,
    numeric_session_grouping,
    prune_grouped_studies,
)

# --------------------------------------------------------------------------- #
# Public API                                                                  #
# --------------------------------------------------------------------------- #
def download_bids(  # noqa: C901 – function is inherently busy as an orchestrator
    ctx: Context,
    *,
    desc: Optional[str],
    list_studies: bool,
    numeric_sessions: bool,
    reassign_sessions: List[str],
    exclude_subjects: List[str],
    exclude_sessions: List[str],
    exclude_patients: List[str],
    exclude_uids: List[str],
    include_subjects: List[str],
    include_sessions: List[Tuple[Optional[str], str]],
    include_patients: List[str],
    with_demographics: bool,
    no_table: bool,
    dry_run: bool,
    no_session_dirs: bool,
    download: bool,
    create_metadata: Optional[bool],
):
    """End-to-end workflow for the ``bids`` sub-command.

    Args
    ----
    ctx:
        Click context carrying the merged configuration in ``ctx.obj``.
    desc:
        Optional *StudyDescription* used for the initial PACS query.
        If *None*, an interactive prompt fetches the value.
    list_studies:
        When *True* and table output is disabled, also print every study
        under its session group.
    numeric_sessions:
        If *True*, sessions are relabelled chronologically as
        ``ses-01``, ``ses-02``, … before any filtering.
    reassign_sessions:
        Strings of the form ``OLD_SUB:OLD_SES=NEW_SUB[:NEW_SES]`` used
        to move studies between subject/session buckets.
    exclude_subjects / exclude_sessions / exclude_patients / exclude_uids:
        Negative filters applied before inclusion filters.
    include_subjects / include_sessions / include_patients:
        Positive filters applied after exclusions.
    with_demographics:
        Include *Age* and *Sex* columns in the ASCII table view.
    no_table:
        Disable table output; fall back to the original grouped view.
    dry_run:
        Show file paths only; skip Docker download execution.
    no_session_dirs:
        Flatten archives directly under ``sub-XXX`` when a subject has
        only one session.
    download:
        Execute downloads when *True*.  When *False*, the function acts
        as a display-only command.
    create_metadata:
        Override YAML ``create_dicom_metadata`` when not *None*.

    Returns
    -------
    None
        The function exits early via ``ctx.exit`` when configuration
        errors occur; otherwise it completes silently.
    """
    # ------------------------------------------------------------------ #
    # 1. Query PACS and retrieve raw study dictionaries                  #
    # ------------------------------------------------------------------ #
    desc, studies = fetch_studies_interactive(ctx, desc)

    # Early UID exclusion speeds up subsequent grouping operations
    if exclude_uids:
        studies = [s for s in studies if s.get("study_uid") not in exclude_uids]

    # ------------------------------------------------------------------ #
    # 2. Build session map and group studies by subject/session          #
    # ------------------------------------------------------------------ #
    explicit_map = getattr(ctx.obj, "session_map", {}) or {}
    sess_map: Dict[str, str] = build_session_map(studies, explicit=explicit_map)
    grouped = group_studies_by_bids(studies, session_map=explicit_map)

    # ------------------------------------------------------------------ #
    # 3. Re-assign sessions as requested via --reassign-session          #
    # ------------------------------------------------------------------ #
    for old_sub, old_ses, new_sub, new_ses in parse_reassign_specs(reassign_sessions):
        try:
            old_sub_lbl, old_ses_lbl = normalize_label(old_sub, old_ses, sess_map)
            new_sub_lbl, new_ses_lbl = normalize_label(new_sub, new_ses, sess_map)
        except ValueError as exc:
            click.echo(f"Ignoring invalid --reassign-session spec: {exc}", err=True)
            continue

        moved = grouped.get(old_sub_lbl, {}).pop(old_ses_lbl, None)
        if moved:
            grouped.setdefault(new_sub_lbl, {}).setdefault(new_ses_lbl, []).extend(moved)
        if not grouped.get(old_sub_lbl):
            grouped.pop(old_sub_lbl, None)

    # ------------------------------------------------------------------ #
    # 4. Apply negative filters (exclude-*)                              #
    # ------------------------------------------------------------------ #
    parsed_excl: List[Tuple[str, str]] = [
        tuple(spec.split(":", 1)) for spec in exclude_sessions if ":" in spec
    ]
    grouped = prune_grouped_studies(
        grouped,
        exclude_subjects=list(exclude_subjects),
        exclude_sessions=parsed_excl,
        exclude_patients=list(exclude_patients),
        exclude_uids=list(exclude_uids),
    )

    # ------------------------------------------------------------------ #
    # 5. Optional chronological renumbering                              #
    # ------------------------------------------------------------------ #
    if numeric_sessions:
        grouped = numeric_session_grouping(grouped)

    # ------------------------------------------------------------------ #
    # 6. Apply positive filters (include-*)                              #
    # ------------------------------------------------------------------ #
    grouped = filter_grouped_studies(
        grouped,
        include_subjects=list(include_subjects),
        include_sessions=list(include_sessions),
        include_patients=list(include_patients),
    )

    # ------------------------------------------------------------------ #
    # 7. Stamp every study with its final sub / ses labels               #
    # ------------------------------------------------------------------ #
    for sub_key, sessions in grouped.items():
        for ses_key, lst in sessions.items():
            for st in lst:
                st["sub_label"] = sub_key
                st["ses_label"] = ses_key

    # ------------------------------------------------------------------ #
    # 8. Determine BIDS and data roots                                   #
    # ------------------------------------------------------------------ #
    bids_root = getattr(ctx.obj, "bids", {}).root or ""
    if not bids_root:
        try:
            bids_root = find_bids_root()
        except RuntimeError as exc:
            click.echo(f"[ERROR] {exc}", err=True)
            ctx.exit(1)

    data_root = Path(bids_root) / "sourcedata" / "dicom"
    use_session_dirs = not no_session_dirs

    # ------------------------------------------------------------------ #
    # 9. Pure dry-run mode                                               #
    # ------------------------------------------------------------------ #
    if dry_run and not download:
        for p in generate_dry_run_paths(grouped, str(data_root), use_session_dirs):
            click.echo(p)
        return

    # ------------------------------------------------------------------ #
    # 10. Download studies and optionally write metadata                 #
    # ------------------------------------------------------------------ #
    if download:
        all_studies = [s for subs in grouped.values() for sess in subs.values() for s in sess]
        plans = build_plans(studies=all_studies, bids_root=data_root, flatten=not use_session_dirs)

        summarize_downloads(plans, include_session=use_session_dirs)

        for i, plan in enumerate(plans, 1):
            click.echo(f"\n-- [{i}/{len(plans)}] {plan.sub_label} | {plan.ses_label}")
            download_study(
                study=plan.study,
                cfg=ctx.obj,
                target_dir=plan.path.parent,
                dry_run=False,
                verbose=getattr(ctx.obj, "verbose", False),
            )

        # Metadata manifest update (conditional)
        write_meta = (
            create_metadata
            if create_metadata is not None
            else getattr(ctx.obj, "create_dicom_metadata", False)
        )
        if write_meta:
            cfmm2tar_ver = os.getenv("DICOMATIC_CFMM2TAR_VERSION", "")
            meta_path = data_root / "metadata.json"

            meta_plans: List[MetaPlan] = [
                MetaPlan(study=p.study, path=p.path, sub_label=p.sub_label, ses_label=p.ses_label)
                for p in plans
            ]
            write_metadata(meta_plans, str(meta_path), cfmm2tar_ver)
            click.echo(f"\n↳ metadata manifest updated → {meta_path}")
        return

    # ------------------------------------------------------------------ #
    # 11. Display-only modes                                             #
    # ------------------------------------------------------------------ #
    if no_table:
        display_grouped_studies(grouped, list_studies)
    else:
        display_grouped_studies_table(grouped, with_demographics)

    # Offer interactive download prompt at the end of a listing session
    prompt_for_bids_downloads(ctx, desc or "", grouped)
