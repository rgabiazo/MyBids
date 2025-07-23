"""\b
Generate or update a ``metadata.json`` manifest.

The command is detached from actual downloads: it derives the required
:class:`dicomatic.models.DownloadPlan` objects via the same planning
logic used by the *download* workflow, then writes or merges a manifest
without touching the underlying archives.
"""

from __future__ import annotations

import os

import click
from click import pass_context

from dicomatic.utils.metadata import write_metadata
from dicomatic.utils.plan_builder import build_download_plans
from dicomatic.utils.project_root import find_bids_root


@click.command("metadata")
# --------------------------------------------------------------------------- #
# CLI options                                                                 #
# --------------------------------------------------------------------------- #
@click.option(
    "-d",
    "--description",
    "desc",
    required=False,
    envvar="DICOMATIC_STUDY_DESCRIPTION",
    help="StudyDescription to match (defaults to $DICOMATIC_STUDY_DESCRIPTION).",
)
@click.option("--uid", "uids", multiple=True, help="StudyInstanceUID(s) to include.")
@click.option(
    "-o",
    "--output-dir",
    "output_dir",
    type=click.Path(file_okay=False, writable=True),
    help="Root directory of downloaded archives (defaults to detected BIDS root).",
)
@click.option("-p", "--participant", "subject_override", help="Override subject folder name.")
@click.option("-s", "--session", "session_override", help="Override session folder name.")
@click.option(
    "--no-session-dirs",
    is_flag=True,
    help="Set when archives were flattened (no ses-XX folders).",
)
@click.option(
    "--metadata-file",
    "metadata_file",
    type=click.Path(dir_okay=False, writable=True),
    help="Custom path to metadata JSON (default is <bids_root>/sourcedata/dicom/metadata.json).",
)
@click.option(
    "--cfmm2tar-version",
    "cfmm2tar_version",
    envvar="DICOMATIC_CFMM2TAR_VERSION",
    help="Version string recorded under 'cfmm2tar_version'.",
)
@pass_context
def metadata(
    ctx: click.Context,
    desc: str | None,
    uids: tuple[str, ...],
    output_dir: str | None,
    subject_override: str | None,
    session_override: str | None,
    no_session_dirs: bool,
    metadata_file: str | None,
    cfmm2tar_version: str | None,
):
    """Create or merge a DICOM metadata manifest.

    The helper reuses :func:`dicomatic.utils.plan_builder.build_download_plans`
    to avoid duplicating path rules. No data transfer is performed.

    Exit codes:
        * 0 – success
        * 1 – no plans could be generated (likely due to bad filters)

    Args:
        ctx: Click context carrying configuration.
        desc: ``StudyDescription`` filter.
        uids: ``StudyInstanceUID`` values to include.
        output_dir: Root directory of downloaded archives.
        subject_override: Override subject folder name.
        session_override: Override session folder name.
        no_session_dirs: Set when archives were flattened.
        metadata_file: Custom path to the metadata JSON file.
        cfmm2tar_version: Version string stored under ``cfmm2tar_version``.

    Returns:
        None
    """
    cfg = ctx.obj

    # ------------------------------------------------------------------ #
    # 1. Build DownloadPlan objects                                      #
    # ------------------------------------------------------------------ #
    plans = build_download_plans(
        ctx,
        desc=desc,
        uids=uids,
        output_dir=output_dir,
        subject_override=subject_override,
        session_override=session_override,
        no_session_dirs=no_session_dirs,
    )
    if not plans:
        click.echo("[ERROR] No download plans found; nothing to write.", err=True)
        ctx.exit(1)

    # ------------------------------------------------------------------ #
    # 2. Determine metadata.json path                                    #
    # ------------------------------------------------------------------ #
    if metadata_file:
        meta_path = metadata_file
    else:
        bids_root = cfg.bids.root
        if not bids_root:
            try:
                bids_root = find_bids_root()
            except RuntimeError as exc:
                click.echo(f"[ERROR] {exc}", err=True)
                ctx.exit(1)
        meta_dir = os.path.join(bids_root, "sourcedata", "dicom")
        meta_path = os.path.join(meta_dir, "metadata.json")

    # ------------------------------------------------------------------ #
    # 3. Write or merge manifest                                         #
    # ------------------------------------------------------------------ #
    write_metadata(plans, meta_path, cfmm2tar_version or "")

    click.echo(f"Wrote metadata for {len(plans)} studies to {meta_path}")
