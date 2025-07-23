"""Create or update dataset_description.json."""

from __future__ import annotations

from pathlib import Path

import click
import structlog

from .._init_dataset import initialise_dataset, update_dataset_description
from ..utils.display import echo_banner, echo_success

log = structlog.get_logger()


@click.command(
    name="dataset-description",
    context_settings=dict(
        help_option_names=["-h", "--help"], show_default=True, max_content_width=120
    ),
    help="Create or update dataset_description.json at the dataset root.",
)
@click.option(
    "--create", is_flag=True, help="Create dataset_description.json if missing."
)
@click.option(
    "--update", is_flag=True, help="Update existing dataset_description.json."
)
@click.option("--name", help="Study title (Name field).")
@click.option("--authors", multiple=True, help="Author names (repeatable).")
@click.option("--license", "license_", help="License identifier (License field).")
@click.option("--acknowledgements", help="Acknowledgements text.")
@click.option("--how-to-acknowledge", help="Instructions on how to cite the dataset.")
@click.option("--funding", multiple=True, help="Funding sources (repeatable).")
@click.option(
    "--ethics-approval",
    "ethics_approvals",
    multiple=True,
    help="Ethics approval identifiers (repeatable).",
)
@click.option(
    "--reference",
    "references_and_links",
    multiple=True,
    help="Related references or links (repeatable).",
)
@click.option("--dataset-doi", help="Dataset DOI string.")
@click.option(
    "--dataset-type",
    default="raw",
    show_default=True,
    type=click.Choice(["raw", "derivative"]),
    help="BIDS dataset category.",
)
@click.pass_obj
def cli(
    ctx_obj,
    create: bool,
    update: bool,
    name: str | None,
    authors: tuple[str, ...],
    license_: str | None,
    acknowledgements: str | None,
    how_to_acknowledge: str | None,
    funding: tuple[str, ...],
    ethics_approvals: tuple[str, ...],
    references_and_links: tuple[str, ...],
    dataset_doi: str | None,
    dataset_type: str,
) -> None:
    """Handle ``bidscomatic-cli dataset-description`` requests.

    Args:
        ctx_obj: Click context populated in ``bidscomatic.cli.main``.
        create: Create ``dataset_description.json`` when it does not exist.
        update: Update an existing ``dataset_description.json``.
        name: Study title used as the Name field.
        authors: Tuple of author names.
        license_: License identifier.
        acknowledgements: Optional acknowledgements text.
        how_to_acknowledge: Instructions for citing the dataset.
        funding: Funding sources.
        ethics_approvals: Ethics approval identifiers.
        references_and_links: Related references or URLs.
        dataset_doi: Dataset DOI string.
        dataset_type: ``raw`` or ``derivative`` dataset category.

    Raises:
        click.ClickException: When the file cannot be created or updated.
    """
    root: Path = ctx_obj["root"]
    dd_file = root / "dataset_description.json"

    if create:
        echo_banner("create dataset_description")
        try:
            initialise_dataset(
                root=root,
                name=name or root.name,
                authors=list(authors) if authors else None,
                license=license_,
                acknowledgements=acknowledgements or "",
                how_to_ack=how_to_acknowledge or "",
                funding=list(funding) if funding else None,
                ethics_approvals=list(ethics_approvals) if ethics_approvals else None,
                references_and_links=(
                    list(references_and_links) if references_and_links else None
                ),
                dataset_doi=dataset_doi,
                dataset_type=dataset_type,
                force=False,
                rename_root=False,
            )
        except FileExistsError as exc:
            raise click.ClickException(str(exc)) from exc
        echo_success(f"Created {dd_file}")
        return

    if update:
        echo_banner("update dataset_description")
        if not dd_file.exists():
            raise click.ClickException(f"{dd_file} does not exist.")
        try:
            update_dataset_description(
                root=root,
                name=name,
                authors=list(authors) if authors else None,
                license=license_,
                acknowledgements=acknowledgements,
                how_to_ack=how_to_acknowledge,
                funding=list(funding) if funding else None,
                ethics_approvals=list(ethics_approvals) if ethics_approvals else None,
                references_and_links=(
                    list(references_and_links) if references_and_links else None
                ),
                dataset_doi=dataset_doi,
                dataset_type=dataset_type,
            )
        except Exception as exc:  # noqa: BLE001
            raise click.ClickException(str(exc)) from exc
        echo_success(f"Updated {dd_file}")
        return

    raise click.ClickException("No action requested. Use --create or --update.")


__all__ = ["cli"]
