"""Extract study archives and optionally delete them or the DICOM folders they create.

The command is exposed as ``bidscomatic-cli unzip`` and is designed to run
before any conversion step. A confirmation prompt is displayed before
performing destructive deletions unless ``--yes`` is passed.

Key flags
------------
* ``--rm-archives``  – permanently remove each archive after extraction.
* ``--rm-dcm-dirs``  – delete the top-level DICOM folder produced by the archive.
* ``--dry-run``      – show what would be deleted without touching the file-system.
* ``--filter-sub`` / ``--filter-ses``  – subject/session filters.
"""

from __future__ import annotations

from pathlib import Path
import click
import structlog

from bidscomatic.utils.filters import (
    split_commas,
    filter_subject_session_paths,
    expand_session_roots,
)
from bidscomatic.utils.cleanup import delete_archives, delete_dcm_roots
from bidscomatic.utils.display import (
    echo_banner,
    echo_subject_session,
    echo_success,
)
from bidscomatic.cli.convert import _expand_subject_roots        # helper reused across CLI
from ..pipelines.unzip       import unzip_archives

log = structlog.get_logger()

# ---------------------------------------------------------------------------
# helper – confirmation prompt
# ---------------------------------------------------------------------------
def _ask_yes_no(msg: str) -> bool:
    """Interactive *Y/N* prompt.

    Args:
        msg: Prompt displayed before the ``[Y/N]`` suffix.

    Returns:
        ``True`` for an affirmative answer; ``False`` otherwise.
    """
    while True:
        ans = click.prompt(f"{msg} [Y/N]", default="", show_default=False).strip().lower()
        if ans in {"y", "yes"}:
            return True
        if ans in {"n", "no"}:
            return False
        click.echo("Please answer Y or N.", err=True)


# ---------------------------------------------------------------------------
# Click command
# ---------------------------------------------------------------------------
@click.command(
    name="unzip",
    help="Extract archives and optionally delete them or their DICOM folders.",
    context_settings=dict(help_option_names=["-h", "--help"], max_content_width=120),
)
@click.argument(
    "paths",
    type=click.Path(path_type=Path, exists=True),
    nargs=-1,
    required=True,
)
# ------------ filters -------------------------------------------------------
@click.option("--filter-sub", "filter_sub", multiple=True,
              callback=split_commas, metavar="<sub>")
@click.option("--filter-ses", "filter_ses", multiple=True,
              callback=split_commas, metavar="<ses>")
# ------------ cleanup flags -------------------------------------------------
@click.option("--rm-archives", is_flag=True,
              help="Delete each archive after a successful extract.")
@click.option("--rm-dcm-dirs", is_flag=True,
              help="Delete the top-level DICOM folder produced by the archive.")
@click.option("--dry-run", is_flag=True,
              help="Only show what would be deleted; do not modify the file-system.")
@click.option("--yes", is_flag=True,
              help="Skip the confirmation prompt.")
# ---------------------------------------------------------------------------
@click.pass_obj
def cli(  # noqa: D401 – Click callback naming rule
    ctx_obj,
    paths: tuple[Path, ...],
    filter_sub: tuple[str, ...],
    filter_ses: tuple[str, ...],
    rm_archives: bool,
    rm_dcm_dirs: bool,
    dry_run: bool,
    yes: bool,
) -> None:
    """Entry-point for ``bidscomatic-cli unzip``.

    Args:
        ctx_obj:      Click context with global flags already parsed.
        paths:        Files or directories supplied on the command line.
        filter_sub:   Subject filter (IDs without the ``sub-`` prefix).
        filter_ses:   Session filter (IDs without the ``ses-`` prefix).
        rm_archives:  When *True*, delete archives after extraction.
        rm_dcm_dirs:  When *True*, delete extracted DICOM directories.
        dry_run:      Perform a trial run without deleting anything.
        yes:          Skip the confirmation prompt.
    """
    verbose = bool(ctx_obj.get("verbose", False) or ctx_obj.get("debug", False))

    echo_banner("Unzip archives")

    # ---------------------------- path expansion -----------------------------
    paths = _expand_subject_roots(paths)        # dataset → sub-*
    paths = expand_session_roots(tuple(paths))  # sub-* → ses-* where present

    # ----------------------- subject/session filter --------------------------
    paths = filter_subject_session_paths(paths, filter_sub, filter_ses)
    paths = tuple(paths)
    if not paths:
        click.echo("Nothing left after --filter-sub / --filter-ses.")
        return

    # ------------------------------- unzip -----------------------------------
    all_archives: list[Path] = []
    all_dcm_roots: list[Path] = []

    for p in paths:
        log.info("Unzipping: %s", p)
        sub = next((x for x in p.parts if x.startswith("sub-")), str(p))
        ses = next((x for x in p.parts if x.startswith("ses-")), None)
        echo_subject_session(sub, ses)
        res = unzip_archives(p, logger=log, list_files=verbose)
        if res.archive_dirs:
            click.echo("Archives unpacked into:")
            for d in res.archive_dirs:
                click.echo(f"  {d}")
        else:
            click.echo(f"No archives found under {p}")

        all_archives.extend(res.archives)
        all_dcm_roots.extend(res.dcm_roots)

    # -------------------- optional destructive cleanup -----------------------
    if rm_archives or rm_dcm_dirs:
        if not yes and not dry_run:
            # Abort early if confirmation denied
            if not _ask_yes_no("\nDestructive cleanup requested – continue?"):
                raise click.Abort()

        if rm_archives:
            delete_archives(all_archives, dry=dry_run)
        if rm_dcm_dirs:
            delete_dcm_roots(all_dcm_roots, dry=dry_run)

    if all_archives:
        echo_success(f"{len(all_archives)} archive(s) unpacked")
    else:
        click.echo("No archives found.")
