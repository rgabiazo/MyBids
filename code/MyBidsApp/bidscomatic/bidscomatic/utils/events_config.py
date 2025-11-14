"""YAML-driven configuration loader for the :mod:`bidscomatic.cli.events` command.

The loader converts a nested YAML document into a dictionary containing the
parameters expected by :mod:`bidscomatic.cli.events`.  Only a subset of the
command line options are supported – just enough for tests and typical usage.

The structure mirrors the example in the project README::

    version: 1
    command: events
    task: demo
    input:
      root: sourcedata/behavioural_task
      pattern: "*.csv"
    ingest:
      img_col: image_file
      accuracy_col: response
      onset_groups:
        - onset_cols: [InstructionText.started]
          duration: 10
        - onset_cols: [onset_Run1]
          duration: 3
      rt_cols: [rt_Run1]
      trialtype_patterns:
        Pair_Encoding: encoding_pair
    derive:
      flags:
        - newcol: is_instruction
          expr: 'trial_type=="instruction"'
          true: 1
          false: 0
    output:
      keep_cols_if_exist: [onset, duration, trial_type]

The caller receives a dictionary with flattened keys that map directly onto the
arguments consumed by :func:`bidscomatic.cli.events.cli`.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

import yaml


# ---------------------------------------------------------------------------
# parsing helpers
# ---------------------------------------------------------------------------

def _as_list(val: Any) -> List[Any]:
    """Return *val* as a list, treating ``None`` as empty."""
    if val is None:
        return []
    if isinstance(val, list):
        return val
    return [val]


def _parse_onset_groups(cfg: Dict[str, Any]) -> Tuple[List[str], Dict[str, float], float]:
    """Parse onset group configuration into columns and duration map."""
    onset_cols: List[str] = []
    duration_map: Dict[str, float] = {}
    durations = cfg.get("durations", {})
    default_duration = float(durations.get("trial", 1.0))
    for group in cfg.get("onset_groups", []):
        cols = _as_list(group.get("onset_cols"))
        dur = float(group.get("duration", default_duration))
        for col in cols:
            onset_cols.append(col)
            duration_map[col] = dur
    return onset_cols, duration_map, default_duration


def _collect_ops(derive: Dict[str, Any]) -> List[Tuple[str, Dict[str, Any]]]:
    """Convert a YAML 'derive' block into a sequenced list of ops.

    Ordering is important:

    - regex_map / **id_from** / regex_extract: make base fields early and ensure
      IDs (e.g., `stim_id`) exist *before* any regex extracts that depend on them
      (such as deriving `novelty_type` from `stim_id`).
    - synth_rows: add instruction rows (if any)
    - join_membership: make 'probe_type' before 'set' rules that depend on it
    - indices: trial numbering etc.
    - set + set_after_indices: compute acc_label, tweak trial_n, etc.
    - join_value + exists_to_flag: transfer recognition outcomes / tested flags AFTER acc_label
    - map_values / recode / optional novelty: late recoding once inputs exist
    - flags: final booleans (analysis_include, is_error…)
    - drop: pruning rows if requested
    """
    ops: List[Tuple[str, Dict[str, Any]]] = []

    # Keep a local copy of flags; append them at the very end.
    flag_specs = derive.get("flags", [])

    # ---- helpers ---------------------------------------------------------
    def _re_extract(spec: Dict[str, Any]) -> Dict[str, Any]:
        """Translate a regex-extract spec into operator parameters."""
        out = {"newcol": spec["newcol"], "from_col": spec["from"], "pattern": spec["pattern"]}
        if "group" in spec:
            out["group"] = spec["group"]
        if "apply_to" in spec:
            out["apply_to"] = spec["apply_to"]
        if "casefold" in spec:
            out["casefold"] = spec["casefold"]
        if "default" in spec:
            out["default"] = spec["default"]
        return out

    def _map_values(spec: Dict[str, Any]) -> Dict[str, Any]:
        """Translate a map-values spec into operator parameters."""
        out = {"newcol": spec["newcol"], "from_col": spec["from"], "mapping": spec["map"]}
        if "casefold" in spec:
            out["casefold"] = spec["casefold"]
        return out

    map_specs = list(derive.get("map_values", []) or [])
    joins = derive.get("joins", {}) or {}
    value_join = joins.get("value") or {}
    required_newcols = {value_join.get("value_from")} if value_join.get("value_from") else set()

    early_map_specs = [spec for spec in map_specs if spec.get("newcol") in required_newcols]
    late_map_specs = [spec for spec in map_specs if spec not in early_map_specs]

    # ---- 1) Early derivations -------------------------------------------
    for spec in derive.get("regex_map", []):
        params = {"newcol": spec["newcol"], "from_col": spec["from"], "mapping": spec["map"]}
        if "casefold" in spec:
            params["casefold"] = spec["casefold"]
        ops.append(("regex_map", params))

    # Place id_from BEFORE regex_extract so derived IDs exist for later extracts
    for spec in derive.get("id_from", []):
        ops.append(("id_from", {
            "newcol": spec["newcol"],
            "from_col": spec["from"],
            "func": spec.get("func", "basename"),
        }))

    for spec in derive.get("regex_extract", []):
        ops.append(("regex_extract", _re_extract(spec)))

    for spec in early_map_specs:
        ops.append(("map_values", _map_values(spec)))

    # ---- 2) Structural rows (instructions etc.) -------------------------
    for spec in derive.get("synth_rows", []):
        set_vals = {
            k: (str(v) if not isinstance(v, str) else v)
            for k, v in (spec.get("set", {}) or {}).items()
        }
        ops.append(("synth_rows", {
            "when": spec.get("when"),
            "groupby": _as_list(spec.get("groupby")),
            "onset": spec["onset"],
            "duration": spec["duration"],
            "clamp_zero": spec.get("clamp_zero", False),
            "set_values": set_vals,
        }))

    # (Optional) Early drops to avoid affecting later indices.
    for spec in derive.get("drop", []):
        ops.append(("drop", spec))

    # ---- 3) Joins (membership FIRST so probe_type exists for 'set') -----
    mem = joins.get("membership")
    if mem:
        params = {
            "newcol": mem["newcol"],
            "keys": _as_list(mem.get("keys")),
            "exists_in": mem["exists_in"],
            "apply_to": mem["apply_to"],
            "true_value": mem["true_value"],
            "false_value": mem["false_value"],
        }
        if mem.get("scope"):
            params["scope"] = mem["scope"]
        ops.append(("join_membership", params))

    # ---- 4) Indices before sets (trial_n etc.) --------------------------
    for spec in derive.get("indices", []):
        params = {
            "newcol": spec["newcol"],
            "groupby": _as_list(spec.get("groupby")),
            "orderby": spec["orderby"],
            "start": spec.get("start", 1),
        }
        if spec.get("apply_to"):
            params["apply_to"] = spec["apply_to"]
        ops.append(("index", params))

    # ---- 5) Set rules (compute acc_label, blank trial_n on instruction…) -
    for spec in derive.get("set", []):
        ops.append(("set", {"when": spec.get("when"), "set_values": spec.get("set", {})}))

    for spec in derive.get("set_after_indices", []):
        ops.append(("set", {"when": spec.get("when"), "set_values": spec.get("set", {})}))

    # ---- 6) VALUE/EXISTS joins AFTER acc_label is available -------------
    if value_join:
        params = {
            "newcol": value_join["newcol"],
            "value_from": value_join["value_from"],
            "keys": _as_list(value_join.get("keys")),
            "from_rows": value_join["from_rows"],
            "to_rows": value_join["to_rows"],
            "default": value_join.get("default"),
        }
        if value_join.get("scope"):
            params["scope"] = value_join["scope"]
        ops.append(("join_value", params))

    ex_flag = joins.get("exists_to_flag")
    if ex_flag:
        params = {
            "newcol": ex_flag["newcol"],
            "keys": _as_list(ex_flag.get("keys")),
            "from_rows": ex_flag["from_rows"],
            "to_rows": ex_flag["to_rows"],
            "true_val": ex_flag.get("true"),
            "false_val": ex_flag.get("false"),
        }
        if ex_flag.get("scope"):
            params["scope"] = ex_flag["scope"]
        ops.append(("exists_to_flag", params))

    # ---- 7) Late recoding/mapping (now that inputs exist) ---------------
    for spec in late_map_specs:
        ops.append(("map_values", _map_values(spec)))

    for spec in derive.get("recode", []):
        ops.append(("map_values", {"newcol": spec["newcol"], "from_col": spec["from"], "mapping": spec["map"]}))

    optional = derive.get("optional", {})
    novelty = optional.get("novelty")
    if novelty and novelty.get("enabled"):
        rex = novelty.get("regex_extract")
        if rex:
            ops.append(("regex_extract", _re_extract(rex)))
        mv = novelty.get("map_values")
        if mv:
            ops.append(("map_values", _map_values(mv)))

    # ---- 8) Flags last ---------------------------------------------------
    for spec in flag_specs:
        ops.append(("flag", spec))

    return ops


def load_events_config(path: Path) -> Dict[str, Any]:
    """Load an events YAML *path* and return a flattened parameter mapping."""
    data = yaml.safe_load(Path(path).read_text()) or {}
    if data.get("command") not in {None, "events"}:
        raise RuntimeError("Config 'command' must be 'events'")

    out: Dict[str, Any] = {}
    out["task"] = data.get("task")

    input_cfg = data.get("input", {})
    root = input_cfg.get("root")
    if root:
        out["paths"] = [root]
    if "pattern" in input_cfg:
        out["pattern"] = input_cfg["pattern"]

    # Optional subject/session filters mirroring ``--filter-sub``/``--filter-ses``
    subs = input_cfg.get("subjects") or input_cfg.get("sub") or input_cfg.get("filter_sub")
    sess = input_cfg.get("sessions") or input_cfg.get("ses") or input_cfg.get("filter_ses")
    out["filter_sub"] = _as_list(subs)
    out["filter_ses"] = _as_list(sess)

    ingest = data.get("ingest", {})
    out["img_col"] = ingest.get("img_col")
    out["accuracy_col"] = ingest.get("accuracy_col")
    out["response_cols"] = ingest.get("response_cols", [])
    out["trialtype_col"] = ingest.get("trialtype_col")
    out["duration_col"] = ingest.get("duration_col")
    out["rt_cols"] = ingest.get("rt_cols", [])
    patt = ingest.get("trialtype_patterns")
    if isinstance(patt, dict):
        out["trialtype_patterns"] = ";".join(f"{k}={v}" for k, v in patt.items())
    else:
        out["trialtype_patterns"] = patt
    onset_cols, duration_map, default_dur = _parse_onset_groups(ingest)
    out["onset_cols"] = onset_cols
    out["duration_map"] = duration_map
    out["duration"] = default_dur

    derive = data.get("derive", {})
    out["ops"] = _collect_ops(derive)

    output = data.get("output", {})
    out["keep_cols_if_exist"] = output.get("keep_cols_if_exist", [])
    out["keep_cols"] = output.get("keep_cols", [])
    out["create_stimuli_directory"] = bool(output.get("create_stimuli_directory", False))
    out["create_events_json"] = bool(output.get("create_events_json", False))
    sidecar = output.get("sidecar", {})
    out["field_descriptions"] = sidecar.get("field_descriptions", {})
    out["field_units"] = sidecar.get("field_units", {})
    out["field_levels"] = sidecar.get("field_levels", {})
    return out
