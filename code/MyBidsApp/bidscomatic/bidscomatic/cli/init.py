"""
Create a minimal BIDS dataset and (optionally) rename its root folder.

This Click command is invoked through ``bidscomatic-cli init``.  It writes
``dataset_description.json`` and can emit the final dataset root on stdout
for shell scripting convenience (``--print-root``).

Key flags
---------
* ``--name``                 – study title placed in *dataset_description.json*
* ``--authors``              – list of author names
* ``--dataset-type``         – ``raw`` (default) or ``derivative``
* ``--force``                – overwrite an existing JSON
* ``--print-root``           – echo only the final root path
* ``--quiet``                – suppress the informational banner
* ``--[no-]rename-root``     – keep or change the folder name
"""

from __future__ import annotations

from pathlib import Path
from typing import Tuple

import click

from ..utils.logging import setup_logging
from .._init_dataset import initialise_dataset
from ..utils.display import echo_banner, echo_subject_session, echo_success

# ---------------------------------------------------------------------------
# Click command definition
# ---------------------------------------------------------------------------
@click.command(
    name="init",
    context_settings=dict(help_option_names=["-h", "--help"], show_default=True, max_content_width=120),
    help="Create a minimal BIDS dataset with dataset_description.json.",
)
@click.argument(
    "path",
    type=click.Path(file_okay=False, writable=True, path_type=Path),
)
@click.option("--name", help="Study title (Name field).")
@click.option(
    "--authors",
    multiple=True,
    help="One or more author names (option may be repeated).",
)
@click.option("--license", "license_", help="License identifier (License field).")
@click.option("--acknowledgements", help="Acknowledgements text.")
@click.option("--how-to-acknowledge", help="Instructions on how to cite the dataset.")
@click.option("--funding", multiple=True, help="Funding sources (repeatable).")
@click.option("--ethics-approval", "ethics_approvals", multiple=True, help="Ethics approval identifiers (repeatable).")
@click.option("--reference", "references_and_links", multiple=True, help="Related references or links (repeatable).")
@click.option("--dataset-doi", help="Dataset DOI string.")
@click.option(
    "--dataset-type",
    default="raw",
    show_default=True,
    type=click.Choice(["raw", "derivative"]),
    help="BIDS dataset category.",
)
@click.option("--force", is_flag=True, help="Overwrite if JSON already exists.")
# ─────────────────────────────────────────────────────────────────────────────
# Helper flags
# ─────────────────────────────────────────────────────────────────────────────
@click.option(
    "--print-root",
    is_flag=True,
    help="Echo only the final dataset root path.",
)
@click.option(
    "--quiet",
    is_flag=True,
    help="Suppress the standard banner lines.",
)
@click.option(
    "--rename-root/--no-rename-root",
    default=True,
    show_default=True,
    help="Rename dataset folder to match the study title.",
)
@click.pass_context
def cli(  # noqa: D401  – Click callback name semantic
    _ctx: click.Context,
    path: Path,
    name: str | None,
    authors: Tuple[str, ...],
    license_: str | None,
    acknowledgements: str | None,
    how_to_acknowledge: str | None,
    funding: Tuple[str, ...],
    ethics_approvals: Tuple[str, ...],
    references_and_links: Tuple[str, ...],
    dataset_doi: str | None,
    dataset_type: str,
    force: bool,
    print_root: bool,
    quiet: bool,
    rename_root: bool,
) -> None:
    """Entry-point for ``bidscomatic-cli init``.

    Args:
        _ctx:      Click context (unused, placeholder for symmetry).
        path:      Directory in which the dataset is created or detected.
        name:      Title placed in *dataset_description.json*.
        authors:   Tuple of author names supplied via repeated ``--authors``.
        license_:  Optional license identifier.
        acknowledgements: Optional acknowledgements text.
        how_to_acknowledge: Optional instructions for citing the dataset.
        funding:   Tuple of funding sources.
        ethics_approvals: Tuple of ethics approval identifiers.
        references_and_links: Tuple of related references or links.
        dataset_doi: DOI string for the dataset.
        dataset_type: ``raw`` or ``derivative`` as required by BIDS.
        force:     When *True*, overwrite an existing description file.
        print_root:  Echo the final root path for shell scripting.
        quiet:       Suppress informational output except mandatory messages.
        rename_root: Rename the dataset folder to match the title.
    """
    # Always enable pretty console logging even in --quiet mode
    setup_logging(dataset_root=None, verbose=not quiet)
    echo_banner("init dataset")

    # ------------------------------------------------------------------
    # Create / overwrite dataset_description.json and handle folder rename
    # ------------------------------------------------------------------
    try:
        new_root = initialise_dataset(
            root=path,
            name=name or path.name,
            authors=list(authors) if authors else None,
            license=license_,
            acknowledgements=acknowledgements or "",
            how_to_ack=how_to_acknowledge or "",
            funding=list(funding) if funding else None,
            ethics_approvals=list(ethics_approvals) if ethics_approvals else None,
            references_and_links=list(references_and_links) if references_and_links else None,
            dataset_doi=dataset_doi,
            dataset_type=dataset_type,
            force=force,
            rename_root=rename_root,
        )
    except FileExistsError as exc:
        raise click.ClickException(str(exc)) from exc

    # ------------------------------------------------------------------
    # Verbose banner unless --quiet
    # ------------------------------------------------------------------
    if not quiet:
        echo_subject_session(new_root.name, None)
        if new_root != path:
            click.secho(f"Dataset folder renamed to {new_root}", fg="yellow")
        echo_success(f"Created {new_root / 'dataset_description.json'}")

    # ------------------------------------------------------------------
    # Optional machine-readable output
    # ------------------------------------------------------------------
    if print_root:
        # Ensure this is printed last so command substitution captures it cleanly
        click.echo(new_root)
