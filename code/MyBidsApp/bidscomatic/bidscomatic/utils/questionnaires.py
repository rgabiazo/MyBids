"""Transform questionnaire sheets into tidy BIDS-compatible tables.

The module operates purely in memory, simplifying unit tests.
"""

from __future__ import annotations

import json
import logging
import re
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Mapping, MutableMapping, Sequence

import pandas as pd

from bidscomatic.utils.participants import _canon_pid, tidy_columns

log = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# 0  Loading helpers
# ─────────────────────────────────────────────────────────────────────────────
def _read_table(path: Path) -> pd.DataFrame:
    """Read *path* into a :class:`pandas.DataFrame`.

    Args:
        path: Path to a questionnaire sheet. Supported extensions are
            ``.csv``, ``.tsv``, ``.xls`` and ``.xlsx``.

    Returns:
        A **str-typed** DataFrame.  Values are kept un-coerced so that the
        calling code can decide on numeric conversion later.

    Raises:
        ValueError: If *path* has an unsupported extension.
    """
    suf = path.suffix.lower()
    if suf == ".csv":
        return pd.read_csv(path, dtype=str)
    if suf == ".tsv":
        return pd.read_csv(path, sep="\t", dtype=str)
    if suf in {".xls", ".xlsx"}:
        return pd.read_excel(path, dtype=str)
    raise ValueError(f"Unsupported questionnaire sheet {path.name!s}")


# ─────────────────────────────────────────────────────────────────────────────
# 1  Public I/O façade
# ─────────────────────────────────────────────────────────────────────────────
def load_questionnaire_csv(
    path: Path,
    *,
    id_col: str = "participant_id",
    subjects: Sequence[str] | None = None,
    omit: Sequence[str] | None = None,
) -> pd.DataFrame:
    """Load a raw questionnaire CSV/TSV/XLS(X) file and apply first-pass filters.

    Args:
        path: File to read.
        id_col: Column containing the participant identifier.  The values are
            canonicalised via :pyfunc:`bidscomatic.utils.participants._canon_pid`.
        subjects: Optional white-list of subject IDs (with or without the
            ``sub-`` prefix).  When provided, only matching rows are kept.
        omit: Sequence of **case-insensitive substrings**.  Columns whose
            *name* contains any of these tokens are dropped.

    Returns:
        A cleaned DataFrame **indexed** by ``participant_id``.  The order of
        the remaining columns is preserved.

    Raises:
        ValueError: If *id_col* is missing from *path*.
        RuntimeError: If the subject-filter removes all rows.
    """
    df = _read_table(path)
    if id_col not in df.columns:
        raise ValueError(f"Column '{id_col}' missing in {path}")

    # ---- canonicalise IDs --------------------------------------------------
    df[id_col] = df[id_col].astype(str).apply(_canon_pid)
    df = df.set_index(id_col)

    # ---- optional subject subset -------------------------------------------
    if subjects:
        keep = {_canon_pid(s) for s in subjects}
        df = df.loc[df.index.intersection(keep)]

    if df.empty:
        raise RuntimeError("No rows left after subject filter.")

    # ---- optional column omission ------------------------------------------
    omit_toks = [t.lower() for t in (omit or [])]

    def _keep(col: str) -> bool:
        """Return ``True`` when *col* does not contain any omit token."""
        cl = col.lower()
        return not any(tok in cl for tok in omit_toks)

    df = df[[c for c in df.columns if _keep(c)]].copy()

    log.info(
        "[questionnaires] %s → %d row(s) × %d column(s) after filtering",
        path.name,
        len(df),
        df.shape[1],
    )
    return df


# ─────────────────────────────────────────────────────────────────────────────
# 2  Column-name parsing utilities
# ─────────────────────────────────────────────────────────────────────────────
_LAST_UNDERSCORE = re.compile(r"^(.*)_(.+)$")


def split_by_prefix(cols: Sequence[str]) -> Dict[str, Dict[str, List[str]]]:
    """Group column names by questionnaire prefix and session suffix.

    A *prefix* is everything **before** the final underscore, while the *session
    suffix* is the remainder.  The returned mapping therefore looks like::

        {
            "MMQ_SAT": {"baseline": [colA, colB], "followup": [colC]},
            "GDS":     {"baseline": [colD], …},
        }

    Args:
        cols: Iterable of column names.

    Returns:
        Nested dictionary ``{prefix → {session_suffix → [columns]}}``.
    """
    out: Dict[str, Dict[str, List[str]]] = defaultdict(lambda: defaultdict(list))
    for col in cols:
        m = _LAST_UNDERSCORE.match(col)
        if m:
            pfx, sess = m.group(1), m.group(2)
            out[pfx][sess].append(col)
    return out


# ─────────────────────────────────────────────────────────────────────────────
# 3  Frame generator – public API
# ─────────────────────────────────────────────────────────────────────────────
def _merge_session_maps(
    master: MutableMapping[str, List[str]],
    incoming: Mapping[str, List[str]],
) -> None:
    """Append values from *incoming* into *master* without overwriting keys."""
    for sess, cols in incoming.items():
        master.setdefault(sess, []).extend(cols)


def make_tsv_frames(
    df: pd.DataFrame,
    *,
    prefixes: Sequence[str] | None = None,
    session_mode: str = "multi",
    lowercase_cols: bool = True,
    rename_cols: Mapping[str, str] | None = None,
) -> Dict[str, pd.DataFrame]:
    """Create BIDS-ready ``DataFrame`` objects for questionnaire data.

    Args:
        df: Cleaned DataFrame as returned by :pyfunc:`load_questionnaire_csv`.
        prefixes: Specific questionnaire names to export.  ``None`` or
            ``["all"]`` means *every* detected questionnaire is included.
            Matching is **case-insensitive** and supports partial prefixes, e.g.
            ``["MMQ"]`` captures both *MMQ_SAT* and *MMQ_ABILITY*.
        session_mode: ``"single"`` collapses every questionnaire into
            *ses-01* (useful when the sheet has no true longitudinal dimension);
            ``"multi"`` keeps one output per detected session suffix.
        lowercase_cols: When *True* (default) all column names except
            ``participant_id`` are lower-cased after optional renaming.
        rename_cols: Mapping ``old → new`` applied **before** the case pass.

    Returns:
        Mapping ``filename → DataFrame``.  Filenames follow the BIDS convention
        and **do not** include directory components.

    Raises:
        ValueError: If *session_mode* is not ``"single"`` or ``"multi"``.
    """
    if session_mode not in {"single", "multi"}:
        raise ValueError("session_mode must be 'single' or 'multi'")

    prefix_map = split_by_prefix(df.columns)

    use_all = not prefixes or (len(prefixes) == 1 and prefixes[0].lower() == "all")
    wanted: Dict[str, Dict[str, List[str]]] = {}

    # ------------------------------------------------------------------ prefix selection
    for pref, sess_map in prefix_map.items():
        if use_all or pref in prefixes:
            wanted[pref] = sess_map
            continue

        # partial-match support (e.g. MMQ → MMQ_SAT, MMQ_ABILITY …)
        for req in prefixes or []:
            if pref.lower().startswith(req.lower() + "_"):
                bucket = wanted.setdefault(req, {})
                _merge_session_maps(bucket, sess_map)

    if not wanted:
        return {}

    # ------------------------------------------------------------------ build output frames
    frames: Dict[str, pd.DataFrame] = {}
    for pref, sess_map in wanted.items():
        if session_mode == "single":
            first_sess = sorted(sess_map)[0]
            cols = sess_map[first_sess]
            fname = f"{pref.lower()}_ses-01.tsv"
            frames[fname] = df[cols].rename_axis("participant_id").reset_index()
        else:
            for idx, sess in enumerate(sorted(sess_map), start=1):
                cols = sess_map[sess]
                fname = f"{pref.lower()}_ses-{idx:02d}.tsv"
                frames[fname] = df[cols].rename_axis("participant_id").reset_index()

    # ------------------------------------------------------------------ tidy column names
    for k, frame in frames.items():
        frames[k] = tidy_columns(
            frame,
            rename=rename_cols,
            lowercase=lowercase_cols,
        )

    return frames
