"""
Behavioural‑sheet helpers for producing BIDS‑compatible ``*_events.tsv``
frames.

This module is deliberately **pure**: no files are written – only
:pyclass:`pandas.DataFrame` objects are returned.  The separation keeps the
logic reusable in interactive notebooks and makes unit‑testing trivial.

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

import logging
import re
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
    img_col: str,
    accuracy_col: str,
    onset_cols: Sequence[str],
    rt_cols: Sequence[str],
    duration: float | int,
    trialtype_patterns: str,
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
        img_col:            Column containing the stimulus file name.
        accuracy_col:       Column indicating the correctness of the response.
        onset_cols:         Ordered list of onset‑time columns (one per run).
        rt_cols:            Ordered list of reaction‑time columns (one per run).
        duration:           Constant trial duration (seconds).
        trialtype_patterns: Semi‑colon separated ``substring=label`` pairs.
        sub:                Canonical ``sub-XXX`` identifier.
        ses:                Canonical ``ses-YYY`` identifier or *None*.
        task:               BIDS *TaskName* entity.
        keep_cols:          Optional additional columns to retain.  The
                            ``onset`` and ``duration`` columns are always
                            included.
        rename_cols:        Optional mapping ``{old: new}`` applied *before*
                            lower‑casing via :func:`tidy_columns`.
        keep_raw_stim:      When ``True`` the ``stim_file`` column retains the
                            original value from *img_col*.  By default only the
                            basename relative to the ``stimuli`` directory is
                            kept.

    Returns:
        Mapping of filename → DataFrame.  A sheet that contains multiple runs
        yields multiple frames.

    Raises:
        RuntimeError: When mandatory columns are missing or no events can be
            produced after filtering.
    """
    df = _read_table(sheet)

    # ── column presence checks ------------------------------------------
    for req in (img_col, accuracy_col, *onset_cols, *rt_cols):
        if req not in df.columns:
            raise RuntimeError(f"Column '{req}' missing in {sheet}")

    # ── pair onset & RT columns -----------------------------------------
    pairs = [
        (o, r)
        for o, r in zip(onset_cols, rt_cols)
        if o in df.columns and r in df.columns
    ]
    if not pairs:
        raise RuntimeError("No valid onset/RT column pairs – nothing to do.")

    tt_map = _parse_patterns(trialtype_patterns)
    events: list[pd.DataFrame] = []

    # Iterate over (onset, RT) column pairs – each represents one run.
    for onset_col, rt_col in pairs:
        try:
            run_id = _detect_run_id(onset_col)
        except ValueError as err:
            log.warning("[events] %s – skipped column '%s'", err, onset_col)
            continue

        rows = df.loc[~df[onset_col].isna()].copy()
        if rows.empty:
            log.debug("[events] %s – no rows for run %02d", sheet.name, run_id)
            continue

        # Construct mandatory BIDS columns.
        rows["onset"] = rows[onset_col].astype(float)
        rows["duration"] = float(duration)
        rows["trial_type"] = (
            rows[img_col].astype(str).apply(lambda f: _guess_trial_type(f, tt_map))
        )
        rows["stim_file"] = rows[img_col].astype(str)
        if not keep_raw_stim:
            rows["stim_file"] = rows["stim_file"].apply(lambda p: Path(str(p)).name)
        rows["response_time"] = pd.to_numeric(rows[rt_col], errors="coerce")
        rows["response"] = rows[accuracy_col]
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
