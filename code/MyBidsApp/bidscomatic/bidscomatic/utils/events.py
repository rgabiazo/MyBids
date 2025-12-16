"""Behavioural-sheet helpers for BIDS-compatible ``*_events.tsv`` frames.

This module is deliberately pure: no files are written – only
:pyclass:`pandas.DataFrame` objects are returned. The separation keeps the
logic reusable in interactive notebooks and makes unit testing trivial.

Key responsibilities:
1. **Discovery** – locate CSV/TSV/Excel sheets underneath an arbitrary folder
   tree while respecting subject/session filters.
2. **Parsing** – convert a single sheet into one or more events DataFrames
   ready for saving.
3. **Validation** – raise explicit errors when mandatory columns are missing or
   no events can be generated (fail‑fast instead of silently producing empty
   files).
"""

from __future__ import annotations

import json
import logging
import re
from difflib import SequenceMatcher
from pathlib import Path
from typing import Dict, List, Mapping, Sequence, Tuple

import pandas as pd

from bidscomatic.utils.filters import (
    _sub_of,  # internal helper reused for discovery
    _ses_of,
    filter_subject_session_paths,
)
from bidscomatic.utils.participants import tidy_columns

# ---------------------------------------------------------------------------
# Default column handling                                                     #
# ---------------------------------------------------------------------------

# Columns that are always present in every events.tsv. Additional columns can
# be preserved via the ``keep_cols`` argument in :func:`make_events_frames`.
_MANDATORY_COLS = ["onset", "duration"]

log = logging.getLogger(__name__)

# ════════════════════════════════════════════════════════════════════════════
# 0. File I/O helpers
# ════════════════════════════════════════════════════════════════════════════


def _read_table(path: Path) -> pd.DataFrame:
    """Read *path* into a :class:`~pandas.DataFrame`.

    Supported formats are inferred from the file suffix.

    Args:
        path: Sheet file (CSV/TSV/XLS/XLSX).

    Returns:
        DataFrame with **all** columns read as string to avoid dtype issues.

    Raises:
        ValueError: When the file suffix is not recognised.
    """
    suffix = path.suffix.lower()
    if suffix == ".csv":
        return pd.read_csv(path, dtype=str)
    if suffix == ".tsv":
        return pd.read_csv(path, sep="\t", dtype=str)
    if suffix in {".xls", ".xlsx"}:
        return pd.read_excel(path, dtype=str)
    raise ValueError(f"Unsupported sheet {path.name} – use CSV, TSV, XLS or XLSX")


# ════════════════════════════════════════════════════════════════════════════
# 1. Sheet discovery helper (imported by the CLI)
# ════════════════════════════════════════════════════════════════════════════


def collect_sheets(
    root: Path,
    *,
    pattern: str = "*.csv",
    subs: Sequence[str] | None = None,
    sess: Sequence[str] | None = None,
) -> List[Tuple[Path, str, str | None]]:
    """Walk *root* and return tuples *(sheet, sub, ses)* for matching files.

    Args:
        root:    Directory to search recursively.
        pattern: Glob pattern evaluated via :pymeth:`Path.rglob`.
        subs:    Optional subject filter identical to other bidscomatic helpers.
        sess:    Optional session filter.

    Returns:
        Sorted list of tuples.  Each tuple contains the absolute sheet path and
        the *canonical* ``sub-XXX`` / ``ses-YYY`` identifiers detected in the
        path (prefixes added when absent).  Session can be *None* when the path
        lacks a ``ses-*`` component.
    """
    root = root.expanduser().resolve()
    if not root.is_dir():
        raise NotADirectoryError(root)

    hits: list[Path] = sorted(root.rglob(pattern))
    if not hits:
        log.info("[events] 0 files match %s under %s", pattern, root)
        return []

    # Narrow down by subject/session filters early for speed.
    hits = filter_subject_session_paths(hits, subs, sess)

    triples: list[Tuple[Path, str, str | None]] = []
    for sheet in hits:
        sub = _sub_of(sheet)
        if sub is None:
            log.warning("[events] %s ignored (no sub-* in path)", sheet)
            continue
        ses = _ses_of(sheet)
        triples.append((sheet, f"sub-{sub}", f"ses-{ses}" if ses else None))

    log.info("[events] discovered %d sheet(s) under %s", len(triples), root)
    return triples


def extract_stim_paths(sheet: Path, img_col: str) -> list[Path]:
    """Return stimulus file paths referenced in *sheet*.

    Args:
        sheet: Behavioural sheet to read.
        img_col: Name of the column containing stimulus file names.

    Returns:
        list[pathlib.Path]: List of paths exactly as referenced in the sheet.
        Values that are missing or empty are skipped.
    """
    df = _read_table(sheet)
    if img_col not in df.columns:
        raise RuntimeError(f"Column '{img_col}' missing in {sheet}")
    return [Path(p) for p in df[img_col].dropna() if str(p).strip()]


# ════════════════════════════════════════════════════════════════════════════
# 2. Column‑level parsing helpers
# ════════════════════════════════════════════════════════════════════════════

_RUN_RE = re.compile(r"[Rr]un(\d+)")


def _col_signature(col_name: str) -> str:
    """Return a normalised signature for a column name.

    Args:
        col_name: Raw column name containing optional run tokens.

    Returns:
        Lower-case characters preceding the run token, suitable for comparison.

    The signature is used to choose the most appropriate reaction-time column
    for a given onset column when multiple candidates share the same run
    number. It strips the ``RunXX`` suffix (and everything after it) and keeps
    only lower-cased alphabetic characters so that tokens such as ``recog`` or
    ``encode`` can be compared reliably.
    """
    m = _RUN_RE.search(col_name)
    prefix = col_name[: m.start()] if m else col_name
    return re.sub(r"[^a-z]", "", prefix.lower())


def _rt_similarity(onset_col: str, rt_col: str) -> float:
    """Compute how well *rt_col* matches *onset_col* for tie-breaking.

    Args:
        onset_col: Candidate onset column name.
        rt_col: Candidate reaction-time column name.

    Returns:
        Score where larger values indicate a better match.

    Scores are biased so that direct prefix matches beat generic string
    similarity. This keeps backwards compatibility with datasets that only
    provide a single RT column per run while correctly handling layouts where
    both encoding and recognition RT columns share the same run number.
    """
    onset_sig = _col_signature(onset_col)
    rt_sig = _col_signature(rt_col)
    if not onset_sig or not rt_sig:
        return 0.0
    if onset_sig == rt_sig:
        return 3.0
    if onset_sig in rt_sig or rt_sig in onset_sig:
        return 2.0
    return SequenceMatcher(None, onset_sig, rt_sig).ratio()


def _detect_run_id(col_name: str) -> int:
    """Extract the run number from *col_name*.

    Accepted forms include ``Run1``, ``run02`` or embedded variants such as
    ``Onset_Run3``.

    Args:
        col_name: Column name containing a run indicator.

    Returns:
        int: Detected run number.

    Raises:
        ValueError: If the pattern does not match.
    """
    m = _RUN_RE.search(col_name)
    if not m:
        raise ValueError(f"Cannot parse run number from column '{col_name}'")
    return int(m.group(1))


def _parse_patterns(raw: str) -> Dict[str, str]:
    """Convert *raw* spec into a mapping usable for trial‑type detection.

    The *raw* string encodes substring → label pairs separated by semicolons,
    for example ``'Face_Encoding=face_enc;Place_Encoding=place_enc'``.

    Args:
        raw: Semi-colon separated ``substring=label`` pairs.

    Returns:
        Dict mapping the *substring* that should be searched for in the
        stimulus file name to the *label* to assign when the substring is
        found.

    Raises:
        ValueError: If *raw* contains malformed segments.
    """
    mapping: Dict[str, str] = {}
    for chunk in raw.split(";"):
        if not chunk.strip():
            continue
        if "=" not in chunk:
            raise ValueError(f"Bad substring=label spec in '{raw}': '{chunk}'")
        substring, label = (s.strip() for s in chunk.split("=", 1))
        if not substring or not label:
            raise ValueError(f"Bad substring=label spec '{chunk}'")
        mapping[substring] = label
    return mapping


def _guess_trial_type(fname: str, patterns: Mapping[str, str]) -> str:
    """Return the *label* whose *substring* is present in *fname*.

    Args:
        fname: Stimulus file name.
        patterns: Mapping from substring to label.

    Returns:
        Label associated with the first matching substring or ``'unknown'`` when
        no match is found.
    """
    for substring, label in patterns.items():
        if substring in fname:
            return label
    return "unknown"


# ════════════════════════════════════════════════════════════════════════════
# 3. Public API – single‑sheet → DataFrames
# ════════════════════════════════════════════════════════════════════════════


def make_events_frames(  # noqa: C901 – data‑munging is inherently busy
    *,
    sheet: Path,
    img_col: str | None,
    accuracy_col: str | None,
    response_cols: Sequence[str] | None = None,
    onset_cols: Sequence[str],
    rt_cols: Sequence[str] | None = None,
    duration: float | int | None,
    duration_col: str | None = None,
    duration_map: Mapping[str, float] | None = None,
    trialtype_patterns: str | None,
    trialtype_col: str | None = None,
    sub: str,
    ses: str | None,
    task: str,
    keep_cols: Sequence[str] | None = None,
    rename_cols: Mapping[str, str] | None = None,
    keep_raw_stim: bool = False,
) -> Dict[str, pd.DataFrame]:
    """Convert *sheet* into a mapping ``{filename: DataFrame}``.

    The caller is expected to write each frame to disk as ``*_events.tsv``.

    Args:
        sheet:              Path to the behavioural sheet.
        img_col:            Optional column containing the stimulus file name.
        accuracy_col:       Column indicating the correctness of the response.
                            Optional when *response_cols* is provided.
        response_cols:      Candidate columns to coalesce into ``response`` –
                            first non-empty value per row wins.
        onset_cols:         Ordered list of onset-time columns (one per run).
        rt_cols:            Optional ordered list of reaction-time columns
                            (one per run).
        duration:           Constant trial duration (seconds).
        duration_col:       Optional column containing per-row durations.
        trialtype_patterns: Semi-colon separated ``substring=label`` pairs.
        trialtype_col:      Optional column containing pre-defined trial type
                            values.  When provided the values are copied and
                            optionally mapped through *trialtype_patterns*.
        sub:                Canonical ``sub-XXX`` identifier.
        ses:                Canonical ``ses-YYY`` identifier or *None*.
        task:               BIDS *TaskName* entity.
        keep_cols:          Optional additional columns to retain.  The
                            ``onset`` and ``duration`` columns are always
                            included.
        rename_cols:        Optional mapping ``{old: new}`` applied *before*
                            lower-casing via :func:`tidy_columns`.
        keep_raw_stim:      When ``True`` the ``stim_file`` column retains the
                            original value from *img_col*.  By default only the
                            basename relative to the ``stimuli`` directory is
                            kept.

    Returns:
        Mapping of filename → DataFrame.  A sheet that contains multiple runs
        yields multiple frames.

    Raises:
        RuntimeError: When mandatory columns are missing or no events can be
            produced after filtering.
    """
    df = _read_table(sheet)

    # ── column presence checks ------------------------------------------
    # accuracy_col becomes optional when response_cols is used
    required = [*onset_cols]
    if img_col:
        required.append(img_col)
    for req in required:
        if req not in df.columns:
            raise RuntimeError(f"Column '{req}' missing in {sheet}")
    if response_cols:
        if not any(c in df.columns for c in response_cols):
            raise RuntimeError(
                f"None of the --response-cols are present in {sheet}: {response_cols}"
            )
    elif accuracy_col:
        if accuracy_col not in df.columns:
            raise RuntimeError(f"Column '{accuracy_col}' missing in {sheet}")

    if trialtype_col and trialtype_col not in df.columns:
        raise RuntimeError(f"Column '{trialtype_col}' missing in {sheet}")

    if trialtype_patterns and not (trialtype_col or img_col):
        raise RuntimeError(
            "'trialtype_patterns' requires either 'trialtype_col' or 'img_col'"
        )

    tt_map = _parse_patterns(trialtype_patterns) if trialtype_patterns else None
    events: list[pd.DataFrame] = []

    for onset_col in onset_cols:
        try:
            run_id = _detect_run_id(onset_col)
        except ValueError:
            run_id = 1
        rt_col = None
        if rt_cols:
            candidates: list[tuple[float, int, str]] = []
            for idx, rc in enumerate(rt_cols):
                try:
                    if _detect_run_id(rc) != run_id:
                        continue
                except ValueError:
                    continue
                score = _rt_similarity(onset_col, rc)
                candidates.append((score, -idx, rc))
            if candidates:
                _, _, rt_col = max(candidates)

        rows = df.loc[~df[onset_col].isna()].copy()
        if rows.empty:
            log.debug("[events] %s – no rows for %s", sheet.name, onset_col)
            continue

        rows["onset"] = rows[onset_col].astype(float)
        default_dur: float | None = None
        if duration_map and onset_col in duration_map:
            default_dur = float(duration_map[onset_col])
        elif duration is not None:
            default_dur = float(duration)

        if duration_col and duration_col in rows.columns:
            per_row = pd.to_numeric(rows[duration_col], errors="coerce")
            if default_dur is not None:
                per_row = per_row.fillna(default_dur)
            rows["duration"] = per_row.astype(float)
        else:
            if default_dur is None:
                rows["duration"] = pd.Series([pd.NA] * len(rows), dtype="float64")
            else:
                rows["duration"] = float(default_dur)
        if trialtype_col:
            rows["trial_type"] = rows[trialtype_col].astype(str)
            if tt_map:
                rows["trial_type"] = rows["trial_type"].apply(
                    lambda value: _guess_trial_type(value, tt_map)
                )
        elif tt_map:
            if not img_col:
                raise RuntimeError(
                    "trialtype_patterns requires --img-col when --trialtype-col is absent"
                )
            rows["trial_type"] = rows[img_col].astype(str).apply(
                lambda f: _guess_trial_type(f, tt_map)
            )
        if img_col:
            rows["stim_file"] = rows[img_col].astype(str)
            if not keep_raw_stim:
                rows["stim_file"] = rows["stim_file"].apply(lambda p: Path(str(p)).name)
        if rt_col and rt_col in df.columns:
            rows["response_time"] = pd.to_numeric(rows[rt_col], errors="coerce")
        else:
            rows["response_time"] = pd.NA

        # Build 'response': coalesce first non-empty across response_cols (if given),
        # otherwise mirror the accuracy column for backward compatibility.
        if response_cols:
            resp = pd.Series(pd.NA, index=rows.index, dtype="object")
            for col in response_cols:
                if col in df.columns:
                    vals = df.loc[rows.index, col]
                    # Fill where 'resp' is NA/blank and source 'vals' is non-empty
                    mask_empty = resp.isna() | (resp.astype(str).str.strip() == "")
                    src_ok = vals.notna() & (vals.astype(str).str.strip() != "")
                    resp = resp.mask(mask_empty & src_ok, vals)
            rows["response"] = resp
        elif accuracy_col:
            rows["response"] = rows[accuracy_col]  # type: ignore[index]

        rows["run"] = run_id
        events.append(rows)

    if not events:
        raise RuntimeError("No events produced – check filters / columns.")

    full = pd.concat(events, ignore_index=True)

    # ── tidy columns -----------------------------------------------------
    full = tidy_columns(full, rename=rename_cols, lowercase=True)

    # ``onset`` and ``duration`` are always kept.  Additional columns can be
    # requested via ``keep_cols``.
    wanted_cols = list(_MANDATORY_COLS)
    if keep_cols:
        wanted_cols += [c for c in keep_cols if c in full.columns]
    wanted_cols = [c for c in wanted_cols if c in full.columns] + ["run"]
    full = full[wanted_cols]

    # ── split by run & assemble return mapping ---------------------------
    frames: Dict[str, pd.DataFrame] = {}
    for run_id, frame in full.groupby("run"):
        frame = frame.drop(columns=["run"]).sort_values("onset")
        ses_part = f"_{ses}" if ses else ""
        fname = f"{sub}{ses_part}_task-{task}_run-{int(run_id):02d}_events.tsv"
        frames[fname] = frame.reset_index(drop=True)

    log.info(
        "[events] %s → %d run(s) × %d row(s)",
        sheet.name,
        len(frames),
        len(full),
    )
    return frames


# ════════════════════════════════════════════════════════════════════════════
# 4. Helper – infer dir entity from existing BOLD files
# ════════════════════════════════════════════════════════════════════════════

# Mapping PhaseEncodingDirection values to BIDS ``dir-`` tags.
# For RAS-oriented NIfTI, BIDS uses:
#   j  = posterior→anterior  => PA
#   j- = anterior→posterior  => AP
_PED_MAP_TO_DIR_FOR_RAS: Dict[str, str] = {
    "i": "LR",   # Left→Right
    "i-": "RL",  # Right→Left
    "j": "PA",   # Posterior→Anterior
    "j-": "AP",  # Anterior→Posterior
    "k": "IS",   # Inferior→Superior
    "k-": "SI",  # Superior→Inferior
}

def infer_dir_tag(dest_dir: Path, events_fname: str) -> str | None:
    """Return a ``dir-`` entity for *events_fname* based on BOLD metadata.

    Args:
        dest_dir: Directory containing BOLD JSON sidecars and NIfTI files.
        events_fname: Filename produced by :func:`make_events_frames`.

    Returns:
        ``dir-XYZ`` string when inferable, otherwise ``None``.

    The helper searches *dest_dir* for a matching ``*_bold.json`` or
    ``*_bold.nii.gz``. When a side-car JSON is found and contains a valid
    ``PhaseEncodingDirection`` entry it takes precedence. Otherwise the
    function falls back to parsing ``dir-`` from the BOLD filename. When no
    information is available, ``None`` is returned and the caller should omit
    the ``dir`` entity.
    """
    # Construct glob pattern with optional ``dir-`` entity before ``run-``
    stem = events_fname.replace("_events.tsv", "")
    pattern = stem.replace("_run-", "*_run-")

    # 1) Look for a JSON sidecar with PhaseEncodingDirection
    for sidecar in dest_dir.glob(f"{pattern}_bold.json"):
        try:
            meta = json.loads(sidecar.read_text() or "{}")
        except Exception as exc:  # pragma: no cover - log and continue
            log.debug("[events] could not read %s: %s", sidecar, exc)
            continue
        ped = meta.get("PhaseEncodingDirection")
        if ped:
            tag = _PED_MAP_TO_DIR_FOR_RAS.get(str(ped))
            if tag:
                return f"dir-{tag}"

    # 2) Fallback to BOLD filenames containing ``dir-``
    for bold in dest_dir.glob(f"{pattern}_bold.nii.gz"):
        m = re.search(r"_dir-([A-Za-z0-9]+)_", bold.name)
        if m:
            return f"dir-{m.group(1)}"

    return None
