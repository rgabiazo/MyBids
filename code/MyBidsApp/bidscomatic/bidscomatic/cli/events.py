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
  ``--response-cols``, ``--onset-cols`` and ``--rt-cols`` flags.
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
    infer_dir_tag,
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
from bidscomatic.utils.ops import (
    apply_ops,
    parse_kv_spec,
    parse_mapping,
)

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
    required=False,
)
# ───────── discovery options ────────────────────────────────────────────────
@click.option(
    "--pattern", default="*.csv", help="Filename glob when PATH is a directory."
)
@click.option("--filter-sub", "filter_sub", multiple=True, callback=split_commas)
@click.option("--filter-ses", "filter_ses", multiple=True, callback=split_commas)
# ───────── configuration file ──────────────────────────────────────────────
@click.option(
    "--config",
    type=click.Path(path_type=Path, exists=True, dir_okay=False),
    help="YAML configuration file replacing most CLI flags.",
)
# ───────── core input columns ───────────────────────────────────────────────
@click.option("--img-col", required=False, help="Filename / stimulus column.")
@click.option("--accuracy-col", required=False, help="Accuracy column (0/1 or similar).")
@click.option(
    "--response-cols",
    multiple=True,
    callback=split_commas,
    help="Candidate response columns to coalesce into 'response' (first non-empty per row wins).",
)
@click.option(
    "--onset-cols",
    "onset_specs",
    required=False,
    multiple=True,
    help="Onset column spec: 'col1,col2 duration=3'. Repeat for groups.",
)
@click.option(
    "--rt-cols",
    required=False,
    multiple=True,
    callback=split_commas,
    help="Reaction-time column(s) matching the onset columns.",
)
@click.option(
    "--duration",
    type=float,
    help="Default duration when an onset group omits 'duration='.",
)
@click.option(
    "--duration-col",
    type=str,
    help="Column containing per-row durations (overrides --duration when present).",
)
@click.option(
    "--trialtype-patterns",
    required=False,
    help="Semi-colon separated '<substring>=<label>' rules.",
)
@click.option(
    "--trialtype-col",
    "trialtype_col",
    required=False,
    help=(
        "Column containing pre-defined trial_type values. When supplied the "
        "values are copied (and optionally remapped via --trialtype-patterns)."
    ),
)
# ───────── BIDS entities ────────────────────────────────────────────────────
@click.option("--task", required=False, help="Task label (BIDS 'task' entity).")
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
@click.option("--regex-map", "regex_maps", multiple=True, help="Regex map spec")
@click.option("--regex-extract", "regex_extracts", multiple=True, help="Regex extract spec")
@click.option("--id-from", "id_from_specs", multiple=True, help="Identifier derive spec")
@click.option("--map-values", "map_values_specs", multiple=True, help="Value mapping spec")
@click.option("--join-membership", "join_membership_specs", multiple=True, help="Join membership spec")
@click.option("--join-value", "join_value_specs", multiple=True, help="Join value spec")
@click.option("--exists-to-flag", "exists_to_flag_specs", multiple=True, help="Exists to flag spec")
@click.option("--synth-rows", "synth_rows_specs", multiple=True, help="Synthetic rows spec")
@click.option("--flag", "flag_specs", multiple=True, help="Flag spec")
@click.option("--index", "index_specs", multiple=True, help="Index spec")
@click.option("--set", "set_specs", multiple=True, help="Conditional assignment spec")
@click.option("--drop", "drop_specs", multiple=True, help="Row drop spec")
@click.option(
    "--keep-cols-if-exist",
    "keep_cols_if_exist",
    default="",
    help="Comma-separated list of columns to keep if present.",
)
@click.option("--overwrite", is_flag=True, help="Overwrite existing files.")
@click.pass_obj
def cli(  # noqa: D401 – Click callback
    ctx_obj,
    paths: Tuple[Path, ...],
    pattern: str,
    filter_sub: Tuple[str, ...],
    filter_ses: Tuple[str, ...],
    config: Path | None,
    img_col: str | None,
    accuracy_col: str | None,
    response_cols: Tuple[str, ...],
    onset_specs: Tuple[str, ...],
    rt_cols: Tuple[str, ...],
    duration: float | None,
    duration_col: str | None,
    trialtype_patterns: str | None,
    trialtype_col: str | None,
    task: str | None,
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
    regex_maps: Tuple[str, ...],
    regex_extracts: Tuple[str, ...],
    id_from_specs: Tuple[str, ...],
    map_values_specs: Tuple[str, ...],
    join_membership_specs: Tuple[str, ...],
    join_value_specs: Tuple[str, ...],
    exists_to_flag_specs: Tuple[str, ...],
    synth_rows_specs: Tuple[str, ...],
    flag_specs: Tuple[str, ...],
    index_specs: Tuple[str, ...],
    set_specs: Tuple[str, ...],
    drop_specs: Tuple[str, ...],
    keep_cols_if_exist: str,
    overwrite: bool,
):
    """Convert raw behavioural sheets to BIDS `*_events.tsv` files.

    Args:
        ctx_obj:  Click context dictionary created in *bidscomatic.cli.main*.
        paths:    One or more input files/folders supplied on the CLI.
        pattern:  Glob pattern when an element of *paths* is a directory.
        filter_sub/filter_ses:  Subject/session filters identical to those in
            other bidscomatic commands.
        img_col / accuracy_col / response_cols / onset_cols / rt_cols:
            Column names required to construct the output TSVs.
        duration: Fixed event duration (in seconds).
        duration_col: Column containing per-row event durations.
        trialtype_patterns:  Semi-colon separated mapping used to derive the
            ``trial_type`` column from *img_col* or *trialtype_col* (example:
            ``'Face_Encoding=face_enc;Place_Encoding=place_enc'``).
        trialtype_col:  Column containing pre-defined ``trial_type`` values.
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

    # Load YAML configuration and merge with CLI flags
    cfg: dict = {}
    if config is not None:
        from bidscomatic.utils.events_config import load_events_config

        try:
            cfg = load_events_config(config)
        except Exception as exc:  # noqa: BLE001
            raise click.ClickException(str(exc)) from exc

    if not paths and cfg.get("paths"):
        paths = tuple(Path(p) for p in cfg["paths"])
    if not paths:
        raise click.ClickException("No input paths specified and config has no 'input.root'")

    pattern = cfg.get("pattern", pattern)
    img_col = img_col or cfg.get("img_col")
    accuracy_col = accuracy_col or cfg.get("accuracy_col")
    response_cols = response_cols or tuple(cfg.get("response_cols", []))
    rt_cols = rt_cols or tuple(cfg.get("rt_cols", []))
    trialtype_patterns = trialtype_patterns or cfg.get("trialtype_patterns")
    trialtype_col = trialtype_col or cfg.get("trialtype_col")
    duration_col = duration_col or cfg.get("duration_col")
    task = task or cfg.get("task")
    if not filter_sub:
        filter_sub = tuple(cfg.get("filter_sub", []))
    if not filter_ses:
        filter_ses = tuple(cfg.get("filter_ses", []))

    if cfg.get("keep_cols"):
        keep_cols = tuple(list(keep_cols) + cfg.get("keep_cols", []))

    keep_cols_if_exist = keep_cols_if_exist or ",".join(cfg.get("keep_cols_if_exist", []))
    create_stimuli_directory = create_stimuli_directory or cfg.get("create_stimuli_directory", False)
    create_events_json = create_events_json or cfg.get("create_events_json", False)

    desc_map = cfg.get("field_descriptions", {})
    desc_map.update(_parse_colval_specs(field_descriptions, "--field-description"))
    units_map = cfg.get("field_units", {})
    units_map.update(_parse_colval_specs(field_units, "--field-units"))
    levels_map = cfg.get("field_levels", {})
    levels_map.update(_parse_levels_specs(field_levels))

    # operations from config
    ops: list[tuple[str, dict]] = cfg.get("ops", [])

    missing: list[str] = []
    if accuracy_col is None and not response_cols:
        log.debug("[events] neither accuracy nor response columns provided; 'response' column will be omitted")
    if not trialtype_patterns and not trialtype_col and not img_col:
        log.debug("[events] trial_type column will be omitted (no patterns/column provided)")
    if task is None:
        missing.append("--task")
    if missing:
        raise click.ClickException("Missing required options: " + ", ".join(missing))

    if create_stimuli_directory and not img_col:
        raise click.ClickException(
            "--create-stimuli-directory requires --img-col to locate stimulus files"
        )

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

    default_stim_root = None
    if stim_root is None and len(paths) == 1 and paths[0].is_dir():
        default_stim_root = paths[0].expanduser().resolve()
    if stim_root is not None:
        default_stim_root = stim_root.expanduser().resolve()

    # ────────────────────────────── 2 — process sheets ─────────────────────
    written = 0
    stim_paths: list[Path] = []
    rename_map = _parse_rename_specs(rename_cols)

    # Parse onset column specifications with optional duration overrides
    onset_cols: list[str] = []
    duration_map: dict[str, float] = {}
    if onset_specs:
        for spec in onset_specs:
            tokens = spec.split()
            cols: list[str] = []
            dur: float | None = None
            for tok in tokens:
                if tok.startswith("duration="):
                    try:
                        dur = float(tok.split("=", 1)[1])
                    except ValueError as exc:  # noqa: BLE001
                        raise click.ClickException(
                            f"--onset-cols bad duration in '{spec}'"
                        ) from exc
                else:
                    cols.extend([c.strip() for c in tok.split(",") if c.strip()])
            if not cols:
                raise click.ClickException(f"--onset-cols bad spec '{spec}'")
            for col in cols:
                onset_cols.append(col)
                if dur is not None:
                    duration_map[col] = dur
    else:
        onset_cols = cfg.get("onset_cols", [])
        duration_map = cfg.get("duration_map", {})
        if duration is None:
            duration = cfg.get("duration")

    if (
        duration_col is None
        and duration is None
        and any(c not in duration_map for c in onset_cols)
    ):
        raise click.ClickException("--duration required when onset groups lack duration")
    if not onset_cols:
        raise click.ClickException("No onset columns specified")

    # ─────────────────────── Build DataFrame operations ────────────────────
    # IMPORTANT: id_from must come BEFORE any regex_extract that may depend on it
    # (e.g., novelty_type derived from 'stim_id'). This prevents warnings about
    # missing source columns during apply_ops().

    parsed_map_values = [parse_kv_spec(spec) for spec in map_values_specs]

    # Determine which map-values results are required before join operations.
    join_value_parsed: list[dict[str, str]] = []
    required_map_newcols: set[str] = set()
    for spec in join_value_specs:
        kv = parse_kv_spec(spec)
        join_value_parsed.append(kv)
        value_from = kv.get("value-from")
        if value_from:
            required_map_newcols.add(value_from)

    early_map_kvs: list[dict[str, str]] = []
    late_map_kvs: list[dict[str, str]] = []
    for kv in parsed_map_values:
        if kv.get("newcol") in required_map_newcols:
            early_map_kvs.append(kv)
        else:
            late_map_kvs.append(kv)

    def _map_values_params(kv: dict[str, str]) -> dict[str, object]:
        """Translate a map-values spec dictionary into operation parameters.

        Args:
            kv: Key-value mapping produced by :func:`parse_kv_spec`.

        Returns:
            Dictionary suitable for :func:`bidscomatic.utils.ops.op_map_values`.
        """
        mapping = parse_mapping(kv.get("map", ""), kv_sep="=")
        return {
            "newcol": kv.get("newcol"),
            "from_col": kv.get("from"),
            "mapping": mapping,
            "casefold": kv.get("casefold", "false").lower() == "true",
        }

    # ── 1) Derive base fields (phase/condition/stim_id/choice extracted early)
    for spec in regex_maps:
        kv = parse_kv_spec(spec)
        mapping = parse_mapping(kv.get("map", ""))
        ops.append((
            "regex_map",
            {
                "newcol": kv.get("newcol"),
                "from_col": kv.get("from"),
                "mapping": mapping,
                "casefold": kv.get("casefold", "false").lower() == "true",
            },
        ))

    # Place id_from BEFORE regex_extract so 'stim_id' exists for later extracts
    for spec in id_from_specs:
        kv = parse_kv_spec(spec)
        ops.append(("id_from", {
            "newcol": kv.get("newcol"),
            "from_col": kv.get("from"),
            "func": kv.get("func", "basename"),
        }))

    for spec in regex_extracts:
        kv = parse_kv_spec(spec)
        group = kv.get("group")
        if group is not None and str(group).isdigit():
            group = int(group)
        params = {
            "newcol": kv.get("newcol"),
            "from_col": kv.get("from"),
            "pattern": kv.get("pattern", ""),
            "group": group,
            "apply_to": kv.get("apply-to"),
            "casefold": kv.get("casefold", "false").lower() == "true",
            "default": kv.get("default", ""),
        }
        ops.append(("regex_extract", params))

    for kv in early_map_kvs:
        ops.append(("map_values", _map_values_params(kv)))

    # (NOTE) Postpone all map_values until after joins/sets so that dependent
    # columns (e.g. class_label from probe_type) are available.

    # ── 2) Structure rows (instruction rows)
    for spec in synth_rows_specs:
        kv = parse_kv_spec(spec)
        set_map = parse_mapping(kv.get("set", ""), kv_sep="=")
        params = {
            "when": kv.get("when", "block-start"),
            "groupby": [k.strip() for k in kv.get("groupby", "").split(",") if k.strip()],
            "onset": kv.get("onset", "first.onset"),
            "duration": float(kv.get("duration", 0)),
            "clamp_zero": kv.get("clamp-zero", "false").lower() == "true",
            "set_values": set_map,
        }
        ops.append(("synth_rows", params))

    # ── 3) Joins that only need keys (e.g., set probe_type)
    for spec in join_membership_specs:
        kv = parse_kv_spec(spec)
        params = {
            "newcol": kv.get("newcol"),
            "keys": [k.strip() for k in kv.get("keys", "").split(",") if k.strip()],
            "exists_in": kv.get("exists-in", ""),
            "apply_to": kv.get("apply-to", ""),
            "true_value": kv.get("true-value"),
            "false_value": kv.get("false-value"),
            "scope": kv.get("scope"),
        }
        ops.append(("join_membership", params))

    # ── 4) Then assign (compute acc_label etc.)
    for spec in set_specs:
        kv = parse_kv_spec(spec)
        set_map = parse_mapping(kv.get("set", ""), kv_sep="=")
        params = {"when": kv.get("when"), "set_values": set_map}
        ops.append(("set", params))

    # ── 5) Post‑set joins (now that acc_label exists)
    for kv in join_value_parsed:
        params = {
            "newcol": kv.get("newcol"),
            "value_from": kv.get("value-from"),
            "keys": [k.strip() for k in kv.get("keys", "").split(",") if k.strip()],
            "from_rows": kv.get("from-rows", ""),
            "to_rows": kv.get("to-rows", ""),
            "default": kv.get("default"),
            "scope": kv.get("scope"),
        }
        ops.append(("join_value", params))

    for spec in exists_to_flag_specs:
        kv = parse_kv_spec(spec)
        params = {
            "newcol": kv.get("newcol"),
            "keys": [k.strip() for k in kv.get("keys", "").split(",") if k.strip()],
            "from_rows": kv.get("from-rows", ""),
            "to_rows": kv.get("to-rows", ""),
            "true_val": kv.get("true", 1),
            "false_val": kv.get("false", 0),
            "scope": kv.get("scope"),
        }
        ops.append(("exists_to_flag", params))

    # ── 6) Indices (safe at any point after instruction rows exist)
    for spec in index_specs:
        kv = parse_kv_spec(spec)
        params = {
            "newcol": kv.get("newcol"),
            "groupby": [k.strip() for k in kv.get("groupby", "").split(",") if k.strip()],
            "orderby": kv.get("orderby", "onset"),
            "start": int(kv.get("start", 1)),
            "apply_to": kv.get("apply-to"),
        }
        ops.append(("index", params))

    # ── 7) Value recoding that may depend on earlier fields
    for kv in late_map_kvs:
        ops.append(("map_values", _map_values_params(kv)))

    # ── 8) Compute flags (depend on acc_label/enc_later_outcome)
    for spec in flag_specs:
        kv = parse_kv_spec(spec)
        params = {
            "newcol": kv.get("newcol"),
            "expr": kv.get("expr", ""),
            "true": kv.get("true", 1),
            "false": kv.get("false", 0),
        }
        ops.append(("flag", params))

    # ── 9) Finish
    for spec in drop_specs:
        kv = parse_kv_spec(spec)
        params = {"when": kv.get("when", "")}
        ops.append(("drop", params))

    if keep_cols_if_exist:
        cols = [c.strip() for c in keep_cols_if_exist.split(",") if c.strip()]
        ops.append(("keep_cols_if_exist", {"cols": cols}))

    for sheet, sheet_sub, sheet_ses in triples:
        # Command-line overrides beat path-derived entities.
        eff_sub = sub or sheet_sub
        eff_ses = ses or sheet_ses
        echo_subject_session(eff_sub, eff_ses)

        frames = make_events_frames(
            sheet=sheet,
            img_col=img_col,
            accuracy_col=accuracy_col,
            response_cols=response_cols,
            onset_cols=onset_cols,
            rt_cols=rt_cols,
            duration=duration,
            duration_col=duration_col,
            duration_map=duration_map,
            trialtype_patterns=trialtype_patterns,
            trialtype_col=trialtype_col,
            sub=eff_sub,
            ses=eff_ses,
            task=task,  # type: ignore[arg-type]
            keep_cols=keep_cols,
            rename_cols=rename_map,
            keep_raw_stim=keep_raw_stim,
        )

        if create_stimuli_directory and img_col:
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
            dir_tag = infer_dir_tag(dest_dir, fname)
            if dir_tag:
                fname = fname.replace("_run-", f"_{dir_tag}_run-")
            dst = dest_dir / fname
            if dst.exists() and not overwrite:
                log.info("[events] %s exists – skipped", dst.relative_to(root))
                continue
            if ops:
                df = apply_ops(df, ops)
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
