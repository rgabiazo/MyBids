"""
CLI front-end for utilities in :pymod:`bidscomatic.utils.events`.

The command discovers behavioural CSV/TSV/XLS(X) sheets, converts each one into
BIDS‐compatible `*_events.tsv` files (one per *run*) and writes them either
into the BIDS dataset structure or an explicit output directory.

Notes
------------
* Accepts individual files **and** directory trees (``--pattern`` glob).
* Offers subject/session filters that match other bidscomatic sub-commands.
* Handles arbitrary column names through ``--img-col``, ``--accuracy-col``,
  ``--onset-cols`` and ``--rt-cols`` flags.
* Supports additional column retention, renaming, and idempotent overwriting.
"""

from __future__ import annotations

from pathlib import Path
from typing import Tuple

import json

import click
import structlog

from bidscomatic.utils.events import (
    make_events_frames,
    collect_sheets,
    extract_stim_paths,
)
from bidscomatic.utils.events_json import (
    build_metadata,
    apply_overrides,
    write_json,
)
from bidscomatic.cli.phenotype_json import _parse_colval_specs
from bidscomatic.utils.stimuli import copy_stimuli
from bidscomatic.utils.filters import split_commas
from bidscomatic.utils.display import echo_banner, echo_subject_session, echo_success

log = structlog.get_logger()


# ---------------------------------------------------------------------------
# Click command definition
# ---------------------------------------------------------------------------
@click.command(
    name="events",
    context_settings=dict(
        help_option_names=["-h", "--help"], show_default=True, max_content_width=120
    ),
)
@click.argument(
    "paths",
    type=click.Path(path_type=Path, exists=True),
    nargs=-1,
    required=True,
)
# ───────── discovery options ────────────────────────────────────────────────
@click.option(
    "--pattern", default="*.csv", help="Filename glob when PATH is a directory."
)
@click.option("--filter-sub", "filter_sub", multiple=True, callback=split_commas)
@click.option("--filter-ses", "filter_ses", multiple=True, callback=split_commas)
# ───────── core input columns ───────────────────────────────────────────────
@click.option("--img-col", required=True, help="Filename / stimulus column.")
@click.option("--accuracy-col", required=True, help="Accuracy column (0/1 or similar).")
@click.option(
    "--onset-cols",
    required=True,
    multiple=True,
    callback=split_commas,
    help="One or more onset columns, typically one per run.",
)
@click.option(
    "--rt-cols",
    required=True,
    multiple=True,
    callback=split_commas,
    help="Reaction-time column(s) matching the onset columns.",
)
@click.option(
    "--duration",
    required=True,
    type=float,
    help="Fixed duration applied to all events (seconds).",
)
@click.option(
    "--trialtype-patterns",
    required=True,
    help="Semi-colon separated '<substring>=<label>' rules.",
)
# ───────── BIDS entities ────────────────────────────────────────────────────
@click.option("--task", required=True, help="Task label (BIDS 'task' entity).")
@click.option("--sub", default="", help="Override subject (e.g. sub-002).")
@click.option("--ses", default="", help="Override session (e.g. ses-01).")
@click.option(
    "--data-type",
    "data_type",
    default="func",
    show_default=True,
    help="Destination datatype folder (func/anat/…); default 'func'.",
)
# ───────── destination tweaks ───────────────────────────────────────────────
@click.option("-o", "--output-dir", type=click.Path(path_type=Path, file_okay=False))
# ───────── misc grooming ────────────────────────────────────────────────────
@click.option(
    "--keep-cols",
    multiple=True,
    callback=split_commas,
    help=(
        "Additional columns to keep in the output TSVs besides 'onset' and "
        "'duration'."
    ),
)
@click.option(
    "--rename-cols",
    multiple=True,
    callback=split_commas,
    metavar="<old>=<new>",
    help="Rename columns after extraction.",
)
@click.option(
    "--keep-raw-stim",
    is_flag=True,
    help="Preserve original stimulus paths in 'stim_file'.",
)
@click.option(
    "--create-stimuli-directory",
    is_flag=True,
    help="Copy stimulus files into <BIDS_ROOT>/stimuli/",
)
@click.option(
    "--stim-root",
    type=click.Path(path_type=Path, exists=True, file_okay=False),
    help="Base directory for stimulus files when paths are relative."
    " Defaults to the event path when a single directory is supplied.",
)
@click.option(
    "--create-events-json",
    is_flag=True,
    help="Write JSON side-car(s) next to each events.tsv",
)
@click.option(
    "--json-spec",
    type=click.Path(path_type=Path, exists=True, dir_okay=False),
    help="JSON snippet merged into each side-car.",
)
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
@click.option(
    "--field-levels",
    "field_levels",
    multiple=True,
    metavar="col=val:desc[,val:desc...]",
    help="Override level descriptions (repeatable).",
)
@click.option("--overwrite", is_flag=True, help="Overwrite existing files.")
@click.pass_obj
def cli(  # noqa: D401 – Click callback
    ctx_obj,
    paths: Tuple[Path, ...],
    pattern: str,
    filter_sub: Tuple[str, ...],
    filter_ses: Tuple[str, ...],
    img_col: str,
    accuracy_col: str,
    onset_cols: Tuple[str, ...],
    rt_cols: Tuple[str, ...],
    duration: float,
    trialtype_patterns: str,
    task: str,
    sub: str,
    ses: str,
    data_type: str,
    output_dir: Path | None,
    keep_cols: Tuple[str, ...],
    rename_cols: Tuple[str, ...],
    keep_raw_stim: bool,
    create_stimuli_directory: bool,
    stim_root: Path | None,
    create_events_json: bool,
    json_spec: Path | None,
    field_descriptions: Tuple[str, ...],
    field_units: Tuple[str, ...],
    field_levels: Tuple[str, ...],
    overwrite: bool,
):
    """Convert raw behavioural sheets to BIDS `*_events.tsv` files.

    Args:
        ctx_obj:  Click context dictionary created in *bidscomatic.cli.main*.
        paths:    One or more input files/folders supplied on the CLI.
        pattern:  Glob pattern when an element of *paths* is a directory.
        filter_sub/filter_ses:  Subject/session filters identical to those in
            other bidscomatic commands.
        img_col / accuracy_col / onset_cols / rt_cols:  Column names required
            to construct the output TSVs.
        duration: Fixed event duration (in seconds).
        trialtype_patterns:  Semi-colon separated mapping used to derive the
            ``trial_type`` column from *img_col* (example:
            ``'Face_Encoding=face_enc;Place_Encoding=place_enc'``).
        task:     BIDS *task* entity.
        sub/ses:  Optional overrides when processing individual files.
        data_type: Destination datatype folder (usually ``func``).
        output_dir: Custom destination path.  Falls back to the BIDS dataset
            derived from *ctx_obj* when not supplied.
        keep_cols: Additional columns to keep besides ``onset`` and ``duration``.
        rename_cols: Column rename specifications in ``old=new`` form.
        keep_raw_stim: Preserve original paths from *img_col* in ``stim_file``.
        create_stimuli_directory: Copy stimulus files referenced by *img_col*
            into ``<BIDS_ROOT>/stimuli``.
        stim_root: Base directory used when stimulus paths are relative.  Falls
            back to each sheet's location when omitted.
        create_events_json: Write ``*.json`` side-cars for each events TSV.
        json_spec: Optional JSON snippet merged into each side-car.
        field_descriptions/field_units: Column overrides in ``col=value`` form.
        overwrite: Overwrite behaviour for existing output files.
    """
    root: Path = ctx_obj["root"]

    echo_banner("events.tsv")

    # ────────────────────────────── 1 — discover sheets ────────────────────
    triples = []  # (sheet_path, sub-id, ses-id|None)

    for p in paths:
        p = p.expanduser().resolve()
        if p.is_file():
            # Single-file mode – subject/session guessed from path unless
            # explicit overrides are given.
            found_sub = sub or f"sub-{_guess_sub_from_path(p)}"
            found_ses = ses or _guess_ses_from_path(p)
            triples.append((p, found_sub, found_ses))
        else:
            # Directory mode – recurse and collect sheets.
            triples.extend(
                collect_sheets(p, pattern=pattern, subs=filter_sub, sess=filter_ses)
            )

    if not triples:
        raise click.ClickException("No matching sheets after filters / pattern.")

    custom = None
    if json_spec is not None:
        try:
            custom = json.loads(Path(json_spec).read_text())
        except Exception as exc:  # noqa: BLE001
            raise click.ClickException(f"Could not read {json_spec}: {exc}") from exc

    desc_map = _parse_colval_specs(field_descriptions, "--field-description")
    units_map = _parse_colval_specs(field_units, "--field-units")
    levels_map = _parse_levels_specs(field_levels)

    default_stim_root = None
    if stim_root is None and len(paths) == 1 and paths[0].is_dir():
        default_stim_root = paths[0].expanduser().resolve()
    if stim_root is not None:
        default_stim_root = stim_root.expanduser().resolve()

    # ────────────────────────────── 2 — process sheets ─────────────────────
    written = 0
    stim_paths: list[Path] = []
    rename_map = _parse_rename_specs(rename_cols)

    for sheet, sheet_sub, sheet_ses in triples:
        # Command-line overrides beat path-derived entities.
        eff_sub = sub or sheet_sub
        eff_ses = ses or sheet_ses
        echo_subject_session(eff_sub, eff_ses)

        frames = make_events_frames(
            sheet=sheet,
            img_col=img_col,
            accuracy_col=accuracy_col,
            onset_cols=onset_cols,
            rt_cols=rt_cols,
            duration=duration,
            trialtype_patterns=trialtype_patterns,
            sub=eff_sub,
            ses=eff_ses,
            task=task,
            keep_cols=keep_cols,
            rename_cols=rename_map,
            keep_raw_stim=keep_raw_stim,
        )

        if create_stimuli_directory:
            try:
                for path in extract_stim_paths(sheet, img_col):
                    if not path.is_absolute():
                        base = default_stim_root or sheet.parent
                        path = (base / path).resolve()
                    stim_paths.append(path)
            except Exception as exc:  # noqa: BLE001
                log.error("[events] failed to parse %s: %s", sheet, exc)

        # Destination directory -------------------------------------------------
        if output_dir is None:
            dest_dir = root / eff_sub / (eff_ses or "") / data_type
        else:
            dest_dir = Path(output_dir).expanduser().resolve()
        dest_dir.mkdir(parents=True, exist_ok=True)

        # Write every *_events.tsv* produced by make_events_frames()
        for fname, df in frames.items():
            dst = dest_dir / fname
            if dst.exists() and not overwrite:
                log.info("[events] %s exists – skipped", dst.relative_to(root))
                continue
            df.to_csv(dst, sep="\t", index=False, na_rep="n/a")
            log.info("[events] wrote %s", dst.relative_to(root))
            if create_events_json:
                try:
                    meta = build_metadata(dst, custom=custom)
                    meta = apply_overrides(
                        meta,
                        field_description=desc_map,
                        field_units=units_map,
                        field_levels=levels_map,
                    )
                except Exception as exc:  # noqa: BLE001
                    raise click.ClickException(str(exc)) from exc
                write_json(dst, metadata=meta, overwrite=overwrite, root=root)
            written += 1

    if create_stimuli_directory and stim_paths:
        count = copy_stimuli(stim_paths, root / "stimuli")
        echo_success(f"{count} stimulus file(s) copied to stimuli/")

    echo_success(f"{written} events.tsv file(s) written.")


# ---------------------------------------------------------------------------
# Helper utilities – kept private to this module
# ---------------------------------------------------------------------------
import re  # noqa: E402

_SUB_RE = re.compile(r"sub-[A-Za-z0-9]+")
_SES_RE = re.compile(r"ses-[A-Za-z0-9]+")


def _guess_sub_from_path(p: Path) -> str | None:
    """Return the first ``sub-*`` component found in *p* or *None*."""
    for part in p.parts:
        if _SUB_RE.fullmatch(part):
            return part
    return None


def _guess_ses_from_path(p: Path) -> str | None:
    """Return the first ``ses-*`` component found in *p* or *None*."""
    for part in p.parts:
        if _SES_RE.fullmatch(part):
            return part
    return None


def _parse_rename_specs(specs: Tuple[str, ...]) -> dict[str, str]:
    """Convert a sequence of ``old=new`` substrings into a mapping."""
    mapping: dict[str, str] = {}
    for raw in specs:
        if "=" not in raw:
            raise click.ClickException(f"--rename-cols bad spec '{raw}'")
        old, new = (s.strip() for s in raw.split("=", 1))
        mapping[old] = new
    return mapping


def _parse_levels_specs(specs: Tuple[str, ...]) -> dict[str, dict[str, str]]:
    """Convert ``col=val:desc,...`` substrings into a nested mapping."""
    mapping: dict[str, dict[str, str]] = {}
    for raw in specs:
        if "=" not in raw:
            raise click.ClickException(f"--field-levels bad spec '{raw}'")
        col, rest = (s.strip() for s in raw.split("=", 1))
        if not col or not rest:
            raise click.ClickException(f"--field-levels bad spec '{raw}'")

        level_map: dict[str, str] = {}
        for chunk in rest.split(","):
            if not chunk.strip():
                continue
            if ":" not in chunk:
                raise click.ClickException(
                    f"--field-levels bad val:desc pair in '{raw}': '{chunk}'"
                )
            val, desc = (s.strip() for s in chunk.split(":", 1))
            if not val:
                raise click.ClickException(
                    f"--field-levels bad val:desc pair in '{raw}': '{chunk}'"
                )
            level_map[val] = desc
        if not level_map:
            raise click.ClickException(f"--field-levels no val:desc pairs in '{raw}'")
        mapping.setdefault(col, {}).update(level_map)
    return mapping

