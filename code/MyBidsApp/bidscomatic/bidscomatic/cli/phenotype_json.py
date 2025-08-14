"""CLI helpers for generating phenotype JSON metadata."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Tuple

import click
import structlog
from bidscomatic.utils.display import echo_banner, echo_success
from bidscomatic.utils.phenotype_json import (apply_overrides, build_metadata,
                                              write_json)

log = structlog.get_logger()


def _parse_colval_specs(specs: Tuple[str, ...], flag: str) -> dict[str, str]:
    """Return mapping parsed from ``col=value`` substrings."""
    mapping: dict[str, str] = {}
    for raw in specs:
        if "=" not in raw:
            raise click.ClickException(f"{flag} bad spec '{raw}'")
        col, val = (s.strip() for s in raw.split("=", 1))
        mapping[col] = val
    return mapping


@click.command(
    name="phenotype-json",
    context_settings=dict(
        help_option_names=["-h", "--help"], show_default=True, max_content_width=120
    ),
    help="Create or update questionnaire JSON side-cars for TSV files.",
)
@click.argument(
    "tsv_paths",
    type=click.Path(path_type=Path, exists=True, dir_okay=False),
    nargs=-1,
    required=True,
)
@click.option(
    "--json-spec",
    type=click.Path(path_type=Path, exists=True, dir_okay=False),
    help="JSON snippet merged into each side-car.",
)
@click.option("--tool-description")
@click.option("--tool-term-url")
@click.option(
    "--field-description",
    "field_descriptions",
    multiple=True,
    metavar="col=value",
    help="Override column description (repeatable).",
)
@click.option(
    "--field-units",
    "field_units",
    multiple=True,
    metavar="col=value",
    help="Override column units (repeatable).",
)
@click.option("--overwrite", is_flag=True, help="Overwrite existing JSON files.")
@click.pass_obj
def cli(
    ctx_obj,
    tsv_paths: Tuple[Path, ...],
    json_spec: Path | None,
    tool_description: str | None,
    tool_term_url: str | None,
    field_descriptions: Tuple[str, ...],
    field_units: Tuple[str, ...],
    overwrite: bool,
) -> None:
    """Create or update ``*.json`` files for phenotype TSVs.

    Args:
        ctx_obj: Click context populated in ``bidscomatic.cli.main``.
        tsv_paths: One or more TSV paths relative to the dataset root.
        json_spec: Optional JSON snippet merged into each output file.
        tool_description: Optional description of the questionnaire tool.
        tool_term_url: Optional ontology reference for the tool.
        field_descriptions: Column description overrides in ``col=value`` form.
        field_units: Column unit overrides in ``col=value`` form.
        overwrite: Replace existing JSON files when ``True``.

    Raises:
        click.ClickException: When inputs are invalid or metadata cannot be
            generated.
    """
    root: Path = ctx_obj["root"]
    echo_banner("phenotype json")

    custom = None
    if json_spec is not None:
        try:
            custom = json.loads(Path(json_spec).read_text())
        except Exception as exc:  # noqa: BLE001
            raise click.ClickException(f"Could not read {json_spec}: {exc}") from exc

    desc_map = _parse_colval_specs(field_descriptions, "--field-description")
    units_map = _parse_colval_specs(field_units, "--field-units")

    written = 0
    for tsv in tsv_paths:
        tsv = tsv if tsv.is_absolute() else root / tsv
        try:
            meta = build_metadata(tsv, custom=custom)
            meta = apply_overrides(
                meta,
                tool_description=tool_description,
                tool_term_url=tool_term_url,
                field_description=desc_map,
                field_units=units_map,
            )
        except Exception as exc:  # noqa: BLE001
            raise click.ClickException(str(exc)) from exc
        if write_json(tsv, metadata=meta, overwrite=overwrite, root=root):
            written += 1

    echo_success(f"{written} JSON file(s) written.")


__all__ = ["cli"]
