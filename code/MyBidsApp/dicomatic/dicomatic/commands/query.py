"""\b
List studies that match a *StudyDescription* and optionally trigger an
interactive download.

The flow is intentionally minimal:

1. Validate or prompt for *StudyDescription* and perform the PACS query.
2. Print an indexed study list.
3. Offer a guided download prompt that uses sensible defaults.
"""

from __future__ import annotations

import os

import click
from click import pass_context

from dicomatic.commands._shared import fetch_studies_interactive
from dicomatic.utils.display import display_studies
from dicomatic.utils.project_root import find_bids_root
from dicomatic.utils.prompts import prompt_for_downloads


@click.command("query")
# --------------------------------------------------------------------------- #
# Single option – description                                                 #
# --------------------------------------------------------------------------- #
@click.option(
    "-d",
    "--description",
    "desc",
    required=False,
    envvar="DICOMATIC_STUDY_DESCRIPTION",
    help="StudyDescription to match (defaults to $DICOMATIC_STUDY_DESCRIPTION).",
)
@pass_context
def query(ctx: click.Context, desc: str | None) -> None:
    """Display studies and offer interactive downloads.

    Args:
        ctx: Click context containing configuration in ``ctx.obj``.
        desc: Optional ``StudyDescription``. When ``None`` a prompt collects
            one.

    Returns:
        None
    """
    # ------------------------------------------------------------------ #
    # 1. Validate description and fetch studies                           #
    # ------------------------------------------------------------------ #
    _, studies = fetch_studies_interactive(ctx, desc)

    # ------------------------------------------------------------------ #
    # 2. Show study list (numbered)                                       #
    # ------------------------------------------------------------------ #
    display_studies(studies)

    # ------------------------------------------------------------------ #
    # 3. Offer guided download prompt                                     #
    # ------------------------------------------------------------------ #
    cfg = ctx.obj
    try:
        bids_root = cfg.bids.root or find_bids_root()
    except RuntimeError as e:  # No BIDS root detected
        click.echo(f"[ERROR] {e}", err=True)
        ctx.exit(1)
    default_output = os.path.join(bids_root, "sourcedata", cfg.dicom.container)

    prompt_for_downloads(
        ctx,
        studies,
        default_output=default_output,
        default_participant="",
        default_session="",
        default_no_session_dirs=True,
        default_create_meta=False,
    )
