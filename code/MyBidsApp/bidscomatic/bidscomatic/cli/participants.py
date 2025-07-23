"""
Create or update *participants.tsv* (and optional JSON side-car).

This Click command merges subject IDs detected in the dataset with optional
metadata from an external sheet and manual ``--assign`` overrides.  Columns
can be filtered, renamed, and lower-cased.  Behaviour is aligned with other
bidscomatic sub-commands to preserve a consistent CLI experience.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Tuple

import click
import structlog

from bidscomatic.utils.participants import (
    collect_subject_ids,
    load_metadata,
    merge_participants,
    parse_assignments,
    tidy_columns,  # column-case/rename helper
    apply_value_map,
    write_participants,
)
from bidscomatic.utils.filters import split_commas
from bidscomatic.utils.display import echo_banner, echo_subject_session, echo_success

log = structlog.get_logger()


# ---------------------------------------------------------------------------
# helper – parse --rename-cols specs once
# ---------------------------------------------------------------------------
def _parse_rename_specs(specs: Tuple[str, ...]) -> Dict[str, str]:
    """Convert a sequence of ``old=new`` substrings into a mapping.

    Args:
        specs: Tuple of raw strings supplied via ``--rename-cols``.

    Returns:
        Mapping suitable for :func:`bidscomatic.utils.participants.tidy_columns`.

    Raises:
        click.ClickException: When a specification is malformed.
    """
    mapping: Dict[str, str] = {}
    for raw in specs:
        if "=" not in raw:
            raise click.ClickException(f"Bad --rename-cols spec '{raw}' (missing '=')")
        old, new = (s.strip() for s in raw.split("=", 1))
        if not old or not new:
            raise click.ClickException(f"Bad --rename-cols spec '{raw}'")
        mapping[old] = new
    return mapping


def _parse_value_maps(specs: Tuple[str, ...]) -> Dict[str, Dict[str, str]]:
    """Convert ``col=old:new,...`` substrings into a nested mapping.

    Args:
        specs: Tuple of raw strings supplied via ``--map-values``.
            Repeated specifications accumulate for the same column.

    Returns:
        Mapping suitable for :func:`bidscomatic.utils.participants.apply_value_map`.

    Raises:
        click.ClickException: When a specification is malformed.
    """
    mapping: Dict[str, Dict[str, str]] = {}
    for raw in specs:
        if "=" not in raw:
            raise click.ClickException(f"Bad --map-values spec '{raw}' (missing '=')")
        col, rest = (s.strip() for s in raw.split("=", 1))
        if not col or not rest:
            raise click.ClickException(f"Bad --map-values spec '{raw}'")

        val_map: Dict[str, str] = {}
        for chunk in rest.split(","):
            if not chunk.strip():
                continue
            if ":" not in chunk:
                raise click.ClickException(f"Bad old:new pair in '{raw}': '{chunk}'")
            old, new = (s.strip() for s in chunk.split(":", 1))
            if not old or not new:
                raise click.ClickException(f"Bad old:new pair in '{raw}': '{chunk}'")
            val_map[old] = new
        if not val_map:
            raise click.ClickException(f"No old:new pairs in '{raw}'")
        mapping.setdefault(col, {}).update(val_map)
    return mapping


# ---------------------------------------------------------------------------
# Click command definition
# ---------------------------------------------------------------------------
@click.command(
    name="participants",
    context_settings=dict(help_option_names=["-h", "--help"], show_default=True, max_content_width=120),
    help="Create or update participants.tsv (and optional participants.json).",
)
# --- external sheet ---------------------------------------------------------
@click.option(
    "--meta-file", type=click.Path(path_type=Path, exists=True, dir_okay=False)
)
@click.option("--id-col", default="participant_id", show_default=True)
# --- column filter ----------------------------------------------------------
@click.option(
    "--keep-cols",
    "keep_cols",
    multiple=True,
    callback=split_commas,
    metavar="<col>",
    help="Keep only these columns (besides participant_id) in participants.tsv.",
)
# --- rename option ----------------------------------------------------------
@click.option(
    "--rename-cols",
    "rename_cols",
    multiple=True,
    callback=split_commas,
    metavar="<old>=<new>",
    help="Rename column(s) after merging (repeatable or comma-separated).",
)
# --- value mapping ---------------------------------------------------------
@click.option(
    "--map-values",
    "map_values",
    multiple=True,
    metavar="<col>=<old>:<new>[,...]>",
    help="Replace cell values using comma-separated old:new pairs (repeatable).",
)
# --- manual overrides -------------------------------------------------------
@click.option("--assign", multiple=True, metavar="<spec>")
# --- JSON side-car ----------------------------------------------------------
@click.option(
    "--json-spec", type=click.Path(path_type=Path, exists=True, dir_okay=False)
)
@click.pass_obj
def cli(  # noqa: D401 – Click demands this callback name
    ctx_obj,
    meta_file: Path | None,
    id_col: str,
    keep_cols: Tuple[str, ...],
    rename_cols: Tuple[str, ...],
    map_values: Tuple[str, ...],
    assign: Tuple[str, ...],
    json_spec: Path | None,
) -> None:
    """Entry-point for ``bidscomatic-cli participants``.

    Args:
        ctx_obj:    Click context dictionary with ``root`` set by the main CLI.
        meta_file:  Optional metadata CSV/TSV/XLS(X) to merge with detected IDs.
        id_col:     Column containing participant IDs in *meta_file*.
        keep_cols:  Columns preserved in the final TSV besides *participant_id*.
        rename_cols: Tuple of ``old=new`` rename specifications.
        map_values:  ``--map-values`` replacements in ``col=old:new`` form.
            Multiple ``--map-values`` accumulate and old:new pairs may be
            comma-separated.
        assign:     ``--assign`` overrides in ``sub-XXX:col=value`` form.
        json_spec:  Optional JSON spec file copied verbatim as side-car.

    Raises:
        click.ClickException: For any validation or filesystem error.
    """
    dataset_root: Path = ctx_obj["root"]

    echo_banner("participants.tsv")

    # ------------------------------------------------------------------ 1. subject discovery
    subs = collect_subject_ids(dataset_root)
    if not subs:
        click.echo("No sub-* folders found – nothing to do.")
        return
    for sid in subs:
        echo_subject_session(sid, None)

    # ------------------------------------------------------------------ 2. optional metadata sheet
    meta_df = None
    if meta_file is not None:
        try:
            meta_df = load_metadata(meta_file, id_col=id_col)
        except Exception as exc:
            raise click.ClickException(str(exc)) from exc

    # ------------------------------------------------------------------ 3. manual --assign overrides
    try:
        manual = parse_assignments(list(assign)) if assign else None
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc

    # ------------------------------------------------------------------ 4. merge detected IDs + metadata + overrides
    df = merge_participants(subs, meta=meta_df, manual=manual)

    # ------------------------------------------------------------------ 5. keep-cols filter (optional)
    if keep_cols:
        keep_set = {c.strip() for c in keep_cols if c.strip()}
        missing = sorted(keep_set - set(df.columns))
        if missing:
            log.warning(
                "[participants] --keep-cols ignored unknown column(s): %s",
                ", ".join(missing),
            )
        ordered = ["participant_id"] + [c for c in keep_cols if c in df.columns]
        df = df.reindex(columns=ordered)

    # ------------------------------------------------------------------ 6. rename + lower-case
    rename_map = _parse_rename_specs(rename_cols)
    df = tidy_columns(df, rename=rename_map, lowercase=True)

    # ------------------------------------------------------------------ 7. value mapping (optional)
    if map_values:
        value_map = _parse_value_maps(map_values)
        df = apply_value_map(df, value_map)
    # ------------------------------------------------------------------ 8. optional JSON side-car
    json_meta = None
    if json_spec is not None:
        try:
            json_meta = json.loads(Path(json_spec).read_text())
        except Exception as exc:
            raise click.ClickException(f"Could not read {json_spec}: {exc}") from exc

    # ------------------------------------------------------------------ 9. write TSV (+ JSON) into dataset root
    write_participants(df, dataset_root=dataset_root, json_meta=json_meta)
    echo_success("participants.tsv updated.")
