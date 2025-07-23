"""
Interactive prompt flows used by the CLI entry points.

This module groups all text-user-interface (TUI) helpers.  High-level
Click commands call into these functions when run without fully scripted
arguments.  Each helper:

* Presents a series of questions via :pymod:`click`.
* Validates and normalises responses.
* Delegates back to Click sub-commands with concrete parameters.

The module does **not** perform network or filesystem I/O aside from
invoking other commands that handle those responsibilities.
"""

from __future__ import annotations

import os
import re
from typing import Dict, List, Tuple, Optional

import click
import tableprint as tp

from click import Context

from dicomatic.utils.input_helpers import prompt_input
from dicomatic.utils.download_helpers import extract_download_overrides
from dicomatic.utils.naming import sanitize_for_filename
from dicomatic.utils.project_root import find_bids_root
from dicomatic.utils.display import summarize_downloads

# -----------------------------------------------------------------------------#
# Utility helpers                                                               #
# -----------------------------------------------------------------------------#
def _truncate(text: str, max_len: int) -> str:
    """Return *text* shortened to *max_len* characters with ellipsis.

    Args:
        text: Arbitrary string or ``None``.  ``None`` returns an empty string.
        max_len: Maximum output length including the ellipsis.

    Returns:
        Possibly truncated string.  Length is guaranteed to be
        ``<= max_len``.
    """
    if not text:
        return ""
    text = str(text)
    return text if len(text) <= max_len else text[: max_len - 1] + "…"


def prompt_yes_no(question: str) -> bool:
    """Display *question* and return ``True`` for “y”, ``False`` for “n”."""
    return prompt_input(question, choices=["y", "n"]) == "y"


# -----------------------------------------------------------------------------#
# Main interactive menu                                                         #
# -----------------------------------------------------------------------------#
def _interactive_menu(ctx: Context) -> None:
    """Display the start-up menu when *dicomatic-cli* is invoked with no subcommand.

    Args:
        ctx: Click context forwarded from the CLI entry-point.
    """
    from dicomatic.commands.query import query as query_cmd
    from dicomatic.commands.bids import bids as bids_cmd
    from dicomatic.commands.patients import patients as patients_cmd

    choices = {
        "1": ("List & download studies (cfmm2tar)", query_cmd),
        "2": ("BIDS workflow: group / filter / download", bids_cmd),
        "3": ("Search by PatientName & custom download", patients_cmd),
    }

    while True:
        click.clear()
        click.echo("[==== DICOMATIC - DICOM Query & Download ====]\n")
        for key, (label, _) in choices.items():
            click.echo(f"{key}) {label}")

        sel = prompt_input("Choose an option", choices=list(choices.keys()))
        _, cmd = choices[sel]

        # Option “2” defaults to showing demographics in the table view.
        if sel == "2":
            ctx.invoke(cmd, with_demographics=True)
        else:
            ctx.invoke(cmd)

        if not prompt_yes_no("Return to main menu?"):
            click.echo("\nGoodbye!\n")
            break


# -----------------------------------------------------------------------------#
# Generic download prompt                                                       #
# -----------------------------------------------------------------------------#
def prompt_for_downloads(
    ctx: Context,
    studies: List[Dict[str, str]],
    *,
    default_output: str = "",
    default_participant: str = "",
    default_session: str = "",
    default_no_session_dirs: bool = True,
    default_create_meta: bool = True,
) -> None:
    """Ask which studies to download, then invoke the *download* command.

    Args:
        ctx: Click context with loaded configuration.
        studies: Full list of study dicts displayed earlier.
        default_output: Pre-filled output directory shown in the prompt.
        default_participant: Baseline subject label when empty input is given.
        default_session: Baseline session label when empty input is given.
        default_no_session_dirs: Default flattening flag.
        default_create_meta: Default metadata creation flag.
    """
    from dicomatic.commands.download import download as download_cmd

    # Question 1: perform any download?
    if prompt_input("Would you like to download any studies", choices=["y", "n"]) != "y":
        return

    # Question 2: choose by indices or “all”
    while True:
        idx_str = click.prompt(
            "\nPlease enter number IDs to download or press enter to download all",
            default="",
            show_default=False,
            prompt_suffix="\n> ",
            type=str,
        ).strip()

        if idx_str == "":
            indices = list(range(len(studies)))
            break

        try:
            picks = [int(tok) for tok in idx_str.split()]
        except ValueError:
            click.echo("[ERROR] Please enter only integer indices.", err=True)
            continue

        if any(p < 1 or p > len(studies) for p in picks):
            click.echo(
                f"[ERROR] Selection out of range. Pick numbers between 1 and {len(studies)}.",
                err=True,
            )
            continue

        indices = [p - 1 for p in picks]
        break

    # Question 3: metadata manifest update?
    create_meta = (
        prompt_input("Would you like to update/create metadata", choices=["y", "n"])
        == "y"
    )

    # Iterate over selected studies and invoke the dedicated command once per UID.
    for idx in indices:
        study = studies[idx]
        uid = study.get("study_uid") or ""
        if not uid:
            click.echo(f"[ERROR] Study at index {idx + 1} missing UID; skipping.", err=True)
            continue

        participant = study.get("patient_name", "").strip() or default_participant

        # Derive session folder heuristically.  Fallback: “01”.
        try:
            _, session, no_session_dirs = extract_download_overrides(
                study, studies, ctx.obj
            )
        except Exception:
            session = default_session or "01"
            no_session_dirs = default_no_session_dirs

        ctx.invoke(
            download_cmd,
            desc=None,
            uids=[uid],
            output_dir=default_output,
            subject_override=participant,
            session_override=session,
            no_session_dirs=no_session_dirs,
            dry_run=False,
            create_metadata=create_meta,
        )


# -----------------------------------------------------------------------------#
# BIDS download prompt                                                          #
# -----------------------------------------------------------------------------#
def prompt_for_bids_downloads(
    ctx: Context,
    desc: str,
    grouped: Dict[str, Dict[str, List[Dict[str, str]]]],
) -> None:
    """Interactive filtering and download prompt for the *bids* workflow.

    Args:
        ctx: Click context with configuration.
        desc: StudyDescription that was queried earlier.
        grouped: Mapping ``{sub:{ses:[studies]}}`` displayed to the console.
    """
    from dicomatic.commands.bids import bids as bids_cmd

    # Question 1: any download at all?
    if prompt_input("Would you like to download any studies", choices=["y", "n"]) != "y":
        return

    # ---------------- Subject filter ----------------
    all_subs = set(grouped.keys())
    if prompt_input("Would you like to download all subjects", choices=["y", "n"]) == "y":
        subject_filters: List[str] = []
    else:
        while True:
            subs_str = prompt_input(
                "Please enter subject IDs to download (space-separated)",
                show_choices=False,
            ).strip()
            toks = subs_str.split()
            if not toks:
                click.echo("[ERROR] Please enter at least one subject ID.", err=True)
                continue

            norm_ids = []
            bad = []
            for tok in toks:
                m = re.fullmatch(r"(?:sub-)?0*(\d+)", tok)
                if not m:
                    bad.append(tok)
                else:
                    full = f"sub-{int(m.group(1)):03d}"
                    if full not in all_subs:
                        bad.append(tok)
                    else:
                        norm_ids.append(m.group(1))

            if bad:
                click.echo(
                    f"[ERROR] Invalid subject ID(s): {', '.join(bad)}. "
                    f"The following subjects are available: {', '.join(sorted(all_subs))}",
                    err=True,
                )
                continue

            subject_filters = norm_ids
            break

    # ---------------- Session filter ----------------
    available_sessions = {ses for subs in grouped.values() for ses in subs.keys()}

    if prompt_input("Would you like to download all sessions", choices=["y", "n"]) == "y":
        session_filters: List[str] = []
    else:
        while True:
            ses_str = prompt_input(
                "Please enter sessions to download (space-separated)",
                show_choices=False,
            ).strip()
            toks = ses_str.split()
            if not toks:
                click.echo("[ERROR] Please enter at least one session.", err=True)
                continue

            norm_sess = []
            bad = []
            for tok in toks:
                # Normalise to ses-XX for membership test
                if tok.isdigit():
                    full = f"ses-{int(tok):02d}"
                elif tok.startswith("ses-"):
                    full = tok
                else:
                    full = f"ses-{tok}"
                if full not in available_sessions:
                    bad.append(tok)
                else:
                    norm_sess.append(full)

            if bad:
                click.echo(
                    f"[ERROR] Invalid session(s): {', '.join(bad)}. "
                    f"Available: {', '.join(sorted(available_sessions))}",
                    err=True,
                )
                continue

            # Keep canonical session labels for CLI invocation
            # ``bids`` accepts both numeric tokens ("01") and ``ses-XX``
            # style labels.  Removing the prefix breaks descriptive
            # tags like ``ses-baseline``, so forward the values verbatim.
            session_filters = list(norm_sess)
            break

    # ---------------- Metadata? ----------------
    create_meta = (
        prompt_input("Would you like to update/create metadata", choices=["y", "n"])
        == "y"
    )

    # Invoke *bids* command with filters and download flag
    # ``bids`` expects raw session strings (e.g. "01" or "ses-01") which will
    # be normalised by ``parse_session_flags``.  Forward the list directly
    # instead of constructing subject/session tuples.
    include_sessions = session_filters
    ctx.invoke(
        bids_cmd,
        desc=desc,
        include_subjects=subject_filters,
        include_sessions=include_sessions,
        download=True,
        create_metadata=create_meta,
    )


# -----------------------------------------------------------------------------#
# Patient-centric prompt                                                        #
# -----------------------------------------------------------------------------#
def prompt_for_patient_downloads(ctx: Context, studies: List[Dict[str, str]]) -> None:
    """Prompt for a single PatientName or UID, then perform a guided download.

    Args:
        ctx: Active Click context.
        studies: List of previously fetched study dictionaries.
    """
    from dicomatic.commands.download import download as download_cmd

    cfg = ctx.obj

    # Question 1: identify a patient or UID
    while True:
        val = click.prompt(
            "\nEnter Patient Name or UID (or blank to return)",
            default="",
            show_default=False,
            prompt_suffix="\n> ",
        ).strip()
        if not val:
            return

        matches = [s for s in studies if s.get("patient_name") == val] or [
            s for s in studies if s.get("study_uid") == val
        ]
        if not matches:
            click.echo(f"[WARNING] '{val}' not found. Try again.", err=True)
            continue

        study = matches[0]
        click.echo(f"[INFO] Found '{val}'.")
        break

    # Question 2: confirmation
    if not prompt_yes_no("Would you like to download this study"):
        return

    # Question 3: subject override
    default_sub = sanitize_for_filename(study["patient_name"])
    subject_override = click.prompt(
        "\nEnter subject ID (press enter to use PatientName)",
        default=default_sub,
        show_default=False,
        prompt_suffix="\n> ",
    ).strip() or default_sub

    # Question 4: session folder preference
    create_session = prompt_yes_no("Would you like to create session folder?")
    no_session_dirs = not create_session

    # Question 5: metadata preference
    create_meta = prompt_yes_no("Would you like to update/create metadata")

    # Question 6: output directory with error checking
    try:
        bids_root = cfg.bids.root or find_bids_root()
    except RuntimeError as exc:
        click.echo(f"[ERROR] {exc}", err=True)
        return

    default_output = os.path.join(
        bids_root,
        "sourcedata",
        cfg.dicom.container,
    )
    while True:
        output_dir = click.prompt(
            f"\nPlease enter output directory (enter to use '{default_output}')",
            default=default_output,
            show_default=False,
            prompt_suffix="\n> ",
        ).strip() or default_output

        try:
            os.makedirs(output_dir, exist_ok=True)
        except Exception as exc:  # noqa: BLE001
            click.echo(f"[ERROR] Cannot use output directory '{output_dir}': {exc}", err=True)
            continue
        break

    # Build path preview for confirmation
    ses_lbl = "ses-01" if create_session else ""
    target_dir = (
        os.path.join(output_dir, subject_override, ses_lbl)
        if create_session
        else os.path.join(output_dir, subject_override)
    )

    # Final confirmation
    click.echo("\n=== Confirm Download ===")
    click.echo(f"Date             : {study.get('study_date', 'N/A')}")
    click.echo(f"Description      : {study.get('study_description', '')}")
    click.echo(f"Patient          : {study.get('patient_name', '')}")
    click.echo(f"Output directory : {target_dir}\n")

    if not prompt_yes_no("Proceed with download"):
        return

    # Invoke actual download sub-command
    ctx.invoke(
        download_cmd,
        desc=None,
        uids=[study["study_uid"]],
        output_dir=output_dir,
        subject_override=subject_override,
        session_override=(ses_lbl.replace("ses-", "") if create_session else "01"),
        no_session_dirs=no_session_dirs,
        dry_run=False,
        create_metadata=create_meta,
    )
