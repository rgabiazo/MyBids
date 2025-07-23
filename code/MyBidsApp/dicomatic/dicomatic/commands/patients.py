"""\b
List unique patients for a given *StudyDescription* and optionally launch
a guided download for one of them.

The command follows a simple three-step interaction:

1. Prompt (if necessary) for a valid *StudyDescription* and fetch studies.
2. Optionally display the full patient list (suppressed by default).
3. Pass control to an interactive helper that asks which patient to
   download and gathers per-study overrides.
"""

from __future__ import annotations

import click
from click import pass_context

from dicomatic.commands._shared import fetch_studies_interactive
from dicomatic.utils.display import display_patients


@click.command("patients")
# --------------------------------------------------------------------------- #
# CLI options                                                                 #
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
    "--list/--no-list",
    "show_list",
    default=False,  # default hides list
    help="Print patient list before prompting.",
)
@pass_context
def patients(ctx: click.Context, desc: str | None, show_list: bool) -> None:
    """Entry point for the ``patients`` workflow.

    Args:
        ctx: Click context containing the merged configuration.
        desc: Optional ``StudyDescription``. When ``None`` an interactive
            prompt collects the value.
        show_list: When ``True`` print the full patient list before prompting.

    Returns:
        None
    """
    # --------------------------------------------------------------- #
    # 1. Fetch studies for a validated StudyDescription               #
    # --------------------------------------------------------------- #
    _, studies = fetch_studies_interactive(ctx, desc)

    # --------------------------------------------------------------- #
    # 2. Display patient names when --list is supplied                #
    # --------------------------------------------------------------- #
    if show_list:
        display_patients(studies)

    # --------------------------------------------------------------- #
    # 3. Launch download-by-patient helper                            #
    # --------------------------------------------------------------- #
    from dicomatic.utils.prompts import prompt_for_patient_downloads

    prompt_for_patient_downloads(ctx, studies)
