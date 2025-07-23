"""\b
Direct download command for *dicomatic*.

The sub-command supports three main scenarios:

1. Download by explicit ``StudyInstanceUID`` (``--uid`` flag).
2. Download all studies matching a *StudyDescription* (``--description``).
3. Download the intersection of 1 and 2.

Optionally, a metadata manifest (``metadata.json``) can be created or
updated in the destination tree.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import List, Optional

import click
from click import pass_context

from dicomatic.models import DownloadPlan
from dicomatic.commands._shared import fetch_studies, fetch_studies_by_uids
from dicomatic.utils.display import summarize_downloads
from dicomatic.utils.download_helpers import download_study
from dicomatic.utils.metadata import write_metadata
from dicomatic.utils.planning import build_plans


@click.command("download")
@pass_context
# --------------------------------------------------------------------------- #
# CLI options                                                                 #
# --------------------------------------------------------------------------- #
@click.option(
    "-d",
    "--description",
    "desc",
    envvar="DICOMATIC_STUDY_DESCRIPTION",
    help="StudyDescription to search for (defaults to $DICOMATIC_STUDY_DESCRIPTION).",
)
@click.option("--uid", "uids", multiple=True, help="StudyInstanceUID(s) to download.")
@click.option(
    "-o",
    "--output-dir",
    "output_dir",
    type=click.Path(file_okay=False, writable=True),
    help="Destination root (defaults to the detected BIDS root).",
)
@click.option("-p", "--participant", "subject_override", help="Override subject folder name.")
@click.option(
    "-s",
    "--session",
    "session_override",
    help="Override session folder name, e.g. '01' or 'ses-01'.",
)
@click.option("--no-session-dirs", is_flag=True, help="Flatten archives (no ses-XX folder).")
@click.option("--dry-run", is_flag=True, help="Show destination paths but skip Docker execution.")
@click.option(
    "--create-metadata/--no-create-metadata",
    "create_metadata",
    default=None,
    help="Override YAML create_dicom_metadata flag for this invocation.",
)
def download(  # noqa: C901 – orchestration requires multiple branches
    ctx: click.Context,
    desc: Optional[str],
    uids: List[str],
    output_dir: Optional[str],
    subject_override: Optional[str],
    session_override: Optional[str],
    no_session_dirs: bool,
    dry_run: bool,
    create_metadata: Optional[bool],
):
    """Download studies via ``cfmm2tar`` and optionally update metadata.

    The command performs these steps:
    1. Resolve the output directory.
    2. Fetch the study list according to ``desc`` and/or ``uids``.
    3. Build :class:`dicomatic.models.DownloadPlan` objects.
    4. Execute downloads unless ``--dry-run`` is active.
    5. Update or create ``metadata.json`` when requested.

    Args:
        ctx: Click runtime context with configuration in ``ctx.obj``.
        desc: ``StudyDescription`` filter. Ignored when empty.
        uids: Sequence of explicit ``StudyInstanceUID`` strings.
        output_dir: Destination root. When ``None``, the function resolves
            the BIDS root and writes into ``sourcedata/dicom``.
        subject_override: Override subject folder name when both overrides
            are provided with ``session_override``.
        session_override: Override session folder name when paired with
            ``subject_override``.
        no_session_dirs: Flatten archives directly under ``sub-XXX`` when
            ``True``.
        dry_run: Skip Docker execution and print intended paths instead.
        create_metadata: Override the YAML ``create_dicom_metadata`` flag.

    Returns:
        None
    """
    cfg = ctx.obj

    # ------------------------------------------------------------------ #
    # 1. Resolve base output directory                                   #
    # ------------------------------------------------------------------ #
    if output_dir:
        base_root = Path(output_dir).resolve()
    else:
        from dicomatic.utils.project_root import find_bids_root

        bids_root = cfg.bids.root or ""
        if not bids_root:
            try:
                bids_root = find_bids_root()
            except RuntimeError as exc:
                click.echo(f"[ERROR] {exc}", err=True)
                ctx.exit(1)

        base_root = Path(bids_root).resolve()

    # ------------------------------------------------------------------ #
    # 2. Fetch study dictionaries                                        #
    # ------------------------------------------------------------------ #
    if uids and not desc:
        studies = fetch_studies_by_uids(ctx, list(uids))
    else:
        studies = fetch_studies(ctx, desc) if desc else []
        if uids:
            studies = [s for s in studies if s.get("study_uid") in uids]

    if not studies:
        click.echo("[ERROR] No studies to download.", err=True)
        ctx.exit(1)

    # ------------------------------------------------------------------ #
    # 3. Build DownloadPlan objects                                      #
    # ------------------------------------------------------------------ #
    overrides = None
    if subject_override and session_override:
        overrides = {"sub": subject_override, "ses": session_override}

    plans: List[DownloadPlan] = build_plans(
        studies=studies,
        bids_root=base_root,
        overrides=overrides,
        flatten=no_session_dirs,
    )

    # ------------------------------------------------------------------ #
    # 4. Dry-run mode                                                    #
    # ------------------------------------------------------------------ #
    if dry_run:
        for p in plans:
            click.echo(str(p.path))
        return

    # ------------------------------------------------------------------ #
    # 5. Execute downloads                                               #
    # ------------------------------------------------------------------ #
    summarize_downloads(plans, include_session=not no_session_dirs)

    total = len(plans)
    for i, plan in enumerate(plans, 1):
        header = f"\n-- [{i}/{total}] {plan.sub_label}"
        if not no_session_dirs:
            header += f" | {plan.ses_label}"
        click.echo(header)

        download_study(
            study=plan.study,
            cfg=cfg,
            target_dir=plan.path.parent,
            dry_run=False,
            verbose=getattr(cfg, "verbose", False),
        )

    # ------------------------------------------------------------------ #
    # 6. Update metadata manifest                                        #
    # ------------------------------------------------------------------ #
    write_meta = create_metadata if create_metadata is not None else getattr(cfg, "create_dicom_metadata", False)
    if write_meta:
        meta_dir = Path(output_dir) if output_dir else base_root / "sourcedata" / "dicom"
        meta_path = meta_dir / "metadata.json"
        cfmm2tar_ver = os.getenv("DICOMATIC_CFMM2TAR_VERSION", "")
        write_metadata(plans, str(meta_path), cfmm2tar_ver)
        click.echo(f"\n↳ metadata manifest updated → {meta_path}")
