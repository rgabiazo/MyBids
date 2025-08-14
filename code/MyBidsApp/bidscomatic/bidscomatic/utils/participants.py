"""Helper functions for generating and maintaining participants files.

The module is split into five logical sections:

1. **Column utilities** – renaming and case-normalisation.
2. **Folder discovery** – extracting subject IDs from the directory tree.
3. **Metadata loading** – reading external CSV/TSV/XLS(X) sheets.
4. **Manual overrides** – parsing ``--assign`` key/value CLI arguments.
5. **Merge + write** – combining all sources and writing the final files.

Only the public API is imported by :pymod:`bidscomatic.cli.participants`;
private helpers remain confined to this file to minimise coupling.
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Dict, List, Mapping, Optional

import pandas as pd

__all__ = [
    "collect_subject_ids",
    "load_metadata",
    "parse_assignments",
    "merge_participants",
    "tidy_columns",
    "apply_value_map",
    "write_participants",
]

log = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Configuration constants
# ─────────────────────────────────────────────────────────────────────────────
_PAD_WIDTH = 3  # Zero-padding width for purely numeric IDs such as “7” → “007”.

# Pre-compiled regular expressions are cheaper in tight loops.
_SUB_DIR_RE = re.compile(r"^sub-[A-Za-z0-9]+$")
_NUMERIC_RE = re.compile(r"^(0*(?P<num>\d+))$")


# ─────────────────────────────────────────────────────────────────────────────
# Column utilities
# ─────────────────────────────────────────────────────────────────────────────
def tidy_columns(
    df: pd.DataFrame,
    *,
    rename: Mapping[str, str] | None = None,
    lowercase: bool = True,
) -> pd.DataFrame:
    """Return a copy of *df* with column names tidied.

    The helper performs two optional, independent operations:

    1. **Renaming** – apply the explicit ``old → new`` mapping in *rename*.
       Keys are matched case-insensitively.  Unknown keys generate a warning.
    2. **Lower-casing** – convert every column name (except
       ``participant_id``) to lower-case.  This matches the style used
       throughout the BIDS examples and avoids accidental duplicates due to
       case differences.

    Args:
        df: Input :class:`pandas.DataFrame`.
        rename: Mapping *old* → *new*. Use an empty mapping to disable
            renaming.
        lowercase: When *True* (default) apply the lower-case
            transformation.

    Returns:
        pandas.DataFrame: A **new** DataFrame with the requested changes
        applied.
    """
    df = df.copy()

    # ――― explicit renames (case-insensitive matching) ―――
    if rename:
        applied: Dict[str, str] = {}
        for old_raw, new_raw in rename.items():
            old = old_raw.strip()
            new = new_raw.strip()

            # Find all columns that match *old* ignoring case.
            matches = [c for c in df.columns if c.lower() == old.lower()]
            if not matches:
                log.warning(
                    "[participants] --rename-cols ignored unknown column '%s'", old
                )
                continue
            if len(matches) > 1:
                log.warning(
                    "[participants] --rename-cols column '%s' matched >1 columns (%s) – "
                    "using first hit",
                    old,
                    ", ".join(matches),
                )
            applied[matches[0]] = new  # Use the first match only.

        if applied:
            log.info(
                "[participants] renamed column(s): %s",
                ", ".join(f"{o}→{n}" for o, n in applied.items()),
            )
            df = df.rename(columns=applied)

    # ――― optional lower-case pass ―――
    if lowercase:
        df = df.rename(
            columns={
                c: c.lower()
                for c in df.columns
                if c != "participant_id" and c != c.lower()
            }
        )

    return df


# ─────────────────────────────────────────────────────────────────────────────
# Value mapping
# ─────────────────────────────────────────────────────────────────────────────
def apply_value_map(
    df: pd.DataFrame, mapping: Mapping[str, Mapping[str, str]]
) -> pd.DataFrame:
    """Return a copy of *df* with value replacements applied.

    Args:
        df: Input DataFrame.
        mapping: Nested mapping ``{column: {old: new}}`` applied per column.

    Returns:
        pandas.DataFrame: New DataFrame with replacements applied. Unknown
        columns are ignored with a warning.
    """
    df = df.copy()
    for col, replace_map in mapping.items():
        if col not in df.columns:
            log.warning(
                "[participants] value map ignored unknown column '%s'",
                col,
            )
            continue
        df[col] = df[col].replace(replace_map)
    return df


# ─────────────────────────────────────────────────────────────────────────────
# Folder discovery
# ─────────────────────────────────────────────────────────────────────────────
def _is_sub_dir(p: Path) -> bool:
    """Return *True* when *p* is a ``sub-*`` directory."""
    return p.is_dir() and _SUB_DIR_RE.match(p.name) is not None


def _canon_pid(raw: str | int) -> str:
    """Canonicalise a participant identifier while preserving case.

    * Numeric IDs are zero-padded to ``*_PAD_WIDTH*`` digits.
    * Non-numeric IDs have non-alphanumeric characters stripped **without**
      forcing lower-case.
    * The ``sub-`` prefix is ensured for every output.

    Args:
        raw: Participant identifier which may be numeric or a string.

    Returns:
        Canonical identifier in ``sub-XXX`` form.

    Examples:
        >>> _canon_pid("7")
        'sub-007'
        >>> _canon_pid("Sub-ABC")
        'sub-ABC'
    """
    txt = str(raw).strip()
    if txt.lower().startswith("sub-"):
        txt = txt[4:]

    if m := _NUMERIC_RE.fullmatch(txt):
        num = int(m.group("num"))
        return f"sub-{num:0{_PAD_WIDTH}d}"

    txt = re.sub(r"[^A-Za-z0-9]+", "", txt)
    return f"sub-{txt}" if not txt.startswith("sub-") else txt


def collect_subject_ids(dataset_root: Path) -> List[str]:
    """Scan *dataset_root* and return canonical subject IDs.

    Args:
        dataset_root: Path containing one or more ``sub-*`` directories.

    Returns:
        list[str]: Sorted list of subject identifiers in canonical
        ``sub-XXX`` form.
    """
    subs = sorted(
        _canon_pid(p.name) for p in dataset_root.glob("sub-*") if _is_sub_dir(p)
    )
    log.info("[participants] discovered %d subject folder(s)", len(subs))
    return subs


# ─────────────────────────────────────────────────────────────────────────────
# Metadata loading
# ─────────────────────────────────────────────────────────────────────────────
def _read_table(path: Path) -> pd.DataFrame:
    """Load ``path`` into a DataFrame based on its suffix.

    Args:
        path: Metadata sheet in CSV, TSV or Excel format.

    Returns:
        DataFrame with all columns read as strings.
    """
    suf = path.suffix.lower()
    if suf == ".csv":
        return pd.read_csv(path, dtype=str)
    if suf == ".tsv":
        return pd.read_csv(path, sep="\t", dtype=str)
    if suf in {".xls", ".xlsx"}:
        return pd.read_excel(path, dtype=str)
    raise ValueError(f"Unsupported sheet {path.name} – use CSV, TSV, XLS or XLSX")


def load_metadata(path: Path, *, id_col: str = "participant_id") -> pd.DataFrame:
    """Read an external metadata sheet and index it by ``participant_id``.

    Args:
        path: CSV/TSV/XLS(X) file containing participant information.
        id_col: Column that holds the participant identifier.

    Returns:
        pandas.DataFrame: DataFrame indexed by canonicalised
        ``participant_id``.

    Raises:
        FileNotFoundError: If *path* does not exist.
        ValueError: If *id_col* is missing in the sheet.
    """
    if not path.exists():
        raise FileNotFoundError(path)

    df_in = _read_table(path)
    if id_col not in df_in.columns:
        raise ValueError(f"Column '{id_col}' missing in {path}")

    df_in[id_col] = df_in[id_col].astype(str).apply(_canon_pid)
    df_out = df_in.set_index(id_col)
    log.info("[participants] loaded %d row(s) from %s", len(df_out), path.name)
    return df_out


# ─────────────────────────────────────────────────────────────────────────────
# Manual overrides
# ─────────────────────────────────────────────────────────────────────────────
_ASSIGN_ROW_RE = re.compile(r"^(?P<sub>[^:]+):(?P<kvpairs>.+)$")


def parse_assignments(assignments: List[str]) -> Mapping[str, Dict[str, str]]:
    """Parse ``--assign`` CLI specs into a nested mapping.

    Each element in *assignments* must follow::

        sub-<ID>:key1=val1,key2=val2,…

    The function is intentionally strict to fail fast on typos.

    Args:
        assignments: Raw CLI strings.

    Returns:
        dict[str, dict[str, str]]: Mapping ``participant_id → { column →
        value }``.

    Raises:
        ValueError: If an assignment string is malformed or lacks key=value
            pairs.
    """
    out: Dict[str, Dict[str, str]] = {}
    for raw in assignments:
        m = _ASSIGN_ROW_RE.fullmatch(raw.strip())
        if not m:
            raise ValueError(
                f"Bad --assign spec '{raw}' – expected 'sub-XXX:key=val,…'"
            )

        subj = _canon_pid(m.group("sub"))
        kvpairs = m.group("kvpairs")

        fields: Dict[str, str] = {}
        for chunk in kvpairs.split(","):
            if not chunk.strip():
                continue
            k, _, v = chunk.partition("=")
            if not k or not v:
                raise ValueError(f"Bad key=value in '{raw}': '{chunk}'")
            fields[k.strip()] = v.strip()

        if not fields:
            raise ValueError(f"No key=value pairs in '{raw}'")
        out[subj] = fields
    return out


# ─────────────────────────────────────────────────────────────────────────────
# Merge logic
# ─────────────────────────────────────────────────────────────────────────────
def merge_participants(
    subject_ids: List[str],
    *,
    meta: Optional[pd.DataFrame] = None,
    manual: Optional[Mapping[str, Dict[str, str]]] = None,
) -> pd.DataFrame:
    """Combine folder IDs, external metadata, and manual overrides.

    The merge strategy is *left-join* on ``participant_id`` so that every
    subject folder ends up with a row, even when no metadata are available.

    Args:
        subject_ids: List of discovered subject IDs (already canonicalised).
        meta: Optional metadata DataFrame produced by :func:`load_metadata`.
        manual: Optional mapping from :func:`parse_assignments`.

    Returns:
        pandas.DataFrame: Participants DataFrame ready to be written.
    """
    # Start with a DataFrame that has exactly one row per subject folder.
    df = pd.DataFrame({"participant_id": sorted(map(_canon_pid, subject_ids))})
    df = df.set_index("participant_id")

    # 1) External sheet – joined *once* so that CLI overrides win later.
    if meta is not None:
        df = df.join(meta, how="left")
        unmatched = sorted(set(meta.index) - set(df.index))
        if unmatched:
            log.warning(
                "[participants] %d sheet row(s) ignored – no matching folder: %s",
                len(unmatched),
                ", ".join(unmatched[:8]) + (" …" if len(unmatched) > 8 else ""),
            )

    # 2) Manual CLI overrides – highest precedence.
    for subj, fields in (manual or {}).items():
        subj_id = _canon_pid(subj)
        for col, val in fields.items():
            df.loc[subj_id, col] = val

    # 3) Convert NaNs (from pandas) to empty strings for clean TSV output.
    for c in df.columns:
        df[c] = df[c].astype(str).replace({"nan": ""})

    return df.reset_index()


# ─────────────────────────────────────────────────────────────────────────────
# Writer
# ─────────────────────────────────────────────────────────────────────────────
def write_participants(
    df: pd.DataFrame,
    *,
    dataset_root: Path,
    json_meta: Optional[Mapping[str, dict]] = None,
) -> None:
    """Write *participants.tsv* and, optionally, *participants.json*.

    Args:
        df: DataFrame returned by :func:`merge_participants`.
        dataset_root: BIDS dataset root directory.
        json_meta: Optional JSON side-car content. When *None*, no JSON is
            written.
    """
    tsv_path = dataset_root / "participants.tsv"
    df.to_csv(tsv_path, sep="\t", index=False, na_rep="n/a")
    log.info(
        "[participants] wrote %s (%d row(s))",
        tsv_path.relative_to(dataset_root),
        len(df),
    )

    if json_meta:
        json_path = dataset_root / "participants.json"
        json_path.write_text(json.dumps(json_meta, indent=2, ensure_ascii=False))
        log.info("[participants] wrote %s", json_path.relative_to(dataset_root))
