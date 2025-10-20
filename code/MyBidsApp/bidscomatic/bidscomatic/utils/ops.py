"""Light‑weight DataFrame transformation helpers used by the events CLI.

The operators implemented here are intentionally small and generic so that they
can be re-used in other parts of bidscomatic.  Each operator accepts a
:class:`pandas.DataFrame` and returns a modified copy.  Functions generally try
hard not to raise exceptions – missing columns simply result in a logged warning
and a no-op transformation.

The module exposes :func:`apply_ops` which sequentially applies a list of
``(op_name, params)`` tuples to a frame.  ``op_name`` is the name of one of the
functions defined below without the ``op_`` prefix (e.g. ``("regex_map",
{...})`` calls :func:`op_regex_map`).
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Sequence

import pandas as pd

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# parsing helpers
# ---------------------------------------------------------------------------

def _split_spec_tokens(spec: str) -> List[str]:
    """Split *spec* into whitespace separated tokens while honouring quotes."""

    tokens: List[str] = []
    buf: List[str] = []
    quote: str | None = None

    for ch in spec:
        if quote:
            buf.append(ch)
            if ch == quote:
                quote = None
            continue

        if ch in {'"', "'"}:
            quote = ch
            buf.append(ch)
        elif ch.isspace():
            if buf:
                tokens.append("".join(buf))
                buf.clear()
        else:
            buf.append(ch)

    if buf:
        tokens.append("".join(buf))

    return tokens


def parse_kv_spec(spec: str) -> Dict[str, str]:
    """Parse key=value tokens from *spec* robustly.

    Only tokens that *begin* with a plausible key are treated as key=value.
    This prevents expressions like ``acc_label=="miss"`` from being split into
    fake pairs. Tokens that are not key=value are appended to the previous
    key's value with a separating space.

    Notes
    -----
    * Quotes around values are preserved by the tokenizer above and stripped
      after the key is identified.
    * Accepts keys comprised of letters, digits, underscores and hyphens,
      starting with a letter or underscore (e.g., newcol, apply-to, true-value).
    """
    out: Dict[str, str] = {}
    last_key: str | None = None

    # A "real" key must start with a letter/underscore and may contain letters,
    # digits, '_' or '-' followed by a single '='.
    key_prefix = re.compile(r"^[A-Za-z_][A-Za-z0-9_-]*=")

    for token in _split_spec_tokens(spec):
        if "=" in token:
            key_part, _, remainder = token.partition("=")
            if not remainder.startswith("=") and key_prefix.match(f"{key_part}="):
                key = key_part.strip()
                val = remainder.strip()
                if len(val) >= 2 and val[0] == val[-1] and val[0] in {'"', "'"}:
                    val = val[1:-1]
                out[key] = val
                last_key = key
                continue

        if last_key is not None:
            out[last_key] = (out[last_key] + " " + token).strip()
        else:
            log.warning("[ops] token '%s' not a key=value and no previous key – ignored", token)
    return out


def parse_mapping(raw: str, item_sep: str = ";", kv_sep: str = ":") -> Dict[str, str]:
    """Parse semi-colon separated ``key:val`` strings into a mapping."""

    mapping: Dict[str, str] = {}
    for chunk in raw.split(item_sep):
        if not chunk.strip():
            continue
        if kv_sep not in chunk:
            log.warning("[ops] bad mapping chunk '%s'", chunk)
            continue
        k, v = (c.strip() for c in chunk.split(kv_sep, 1))
        mapping[k] = v
    return mapping


_ONSET_RE = re.compile(r"^first\.(?P<col>\w+)(?P<off>[+-]\d+(?:\.\d+)?)?$")


def _parse_onset_expr(expr: str) -> tuple[str, float]:
    """Parse onset expressions like ``first.onset-10`` or ``first.onset+5``."""

    match = _ONSET_RE.fullmatch(expr.strip())
    if not match:
        raise ValueError(expr)
    col = match.group("col")
    off = match.group("off")
    return col, (float(off) if off is not None else 0.0)


# ---------------------------------------------------------------------------
# operators
# ---------------------------------------------------------------------------

def op_regex_map(
    df: pd.DataFrame,
    *,
    newcol: str,
    from_col: str,
    mapping: Dict[str, str],
    casefold: bool = False,
) -> pd.DataFrame:
    """Populate *newcol* by matching regex patterns against *from_col*.

    Args:
        df: Input frame.
        newcol: Name of the destination column.
        from_col: Source column evaluated against the regex mapping.
        mapping: Mapping of output labels to regex patterns.
        casefold: Lower-case values before matching when ``True``.

    Returns:
        DataFrame with the mapped column appended.
    """
    if from_col not in df.columns:
        log.warning("[ops] regex-map source column '%s' missing", from_col)
        return df
    col = df[from_col].astype(str)
    if casefold:
        col = col.str.lower()
    result = pd.Series("", index=df.index)
    for label, pattern in mapping.items():
        mask = col.str.contains(pattern, regex=True, na=False)
        result = result.mask(mask & (result == ""), label)
    df[newcol] = result
    return df


def op_regex_extract(
    df: pd.DataFrame,
    *,
    newcol: str,
    from_col: str,
    pattern: str,
    group: str | int | None = None,
    apply_to: str | None = None,
    casefold: bool = False,
    default: str = "",
) -> pd.DataFrame:
    """Extract regex groups from *from_col* into *newcol* with fallbacks.

    Args:
        df: Input frame.
        newcol: Destination column name.
        from_col: Source column to match.
        pattern: Regular expression pattern used for extraction.
        group: Named or positional group to select from the match.
        apply_to: Optional boolean expression limiting rows to update.
        casefold: Lower-case the source values before matching when ``True``.
        default: Value inserted when the match fails.

    Returns:
        Frame with *newcol* populated from regex matches.
    """
    if from_col not in df.columns:
        log.warning("[ops] regex-extract source column '%s' missing", from_col)
        return df
    mask = pd.Series(True, index=df.index)
    if apply_to:
        try:
            mask = df.eval(apply_to, engine="python")  # ← add engine="python"
        except Exception as exc:
            log.error("[ops] regex-extract apply-to '%s' failed: %s", apply_to, exc)
            return df
    series = df[from_col].astype(str)
    if casefold:
        series = series.str.lower()
    extracted = series.str.extract(pattern)
    if group is not None:
        try:
            extracted = extracted[group]
        except Exception:  # noqa: BLE001
            log.error("[ops] regex-extract group '%s' missing", group)
            extracted = pd.Series(default, index=df.index)
    extracted = extracted.fillna(default)
    df.loc[mask, newcol] = extracted[mask]
    if not apply_to:
        df[newcol] = extracted
    return df


def op_id_from(
    df: pd.DataFrame,
    *,
    newcol: str,
    from_col: str,
    func: str = "basename",
) -> pd.DataFrame:
    """Derive identifiers from path-like columns.

    Args:
        df: Input frame.
        newcol: Destination column.
        from_col: Source column containing path-like strings.
        func: Extraction strategy: ``basename``, ``stem`` or ``dirname``.

    Returns:
        Frame with *newcol* populated from transformed paths.
    """
    if from_col not in df.columns:
        log.warning("[ops] id-from source column '%s' missing", from_col)
        return df
    series = df[from_col].astype(str)
    if func == "basename":
        df[newcol] = series.apply(lambda p: Path(p).name)
    elif func == "stem":
        df[newcol] = series.apply(lambda p: Path(p).stem)
    elif func == "dirname":
        df[newcol] = series.apply(lambda p: Path(p).parent.as_posix())
    else:
        log.error("[ops] id-from unknown func '%s'", func)
    return df


def op_map_values(
    df: pd.DataFrame,
    *,
    newcol: str,
    from_col: str,
    mapping: Dict[str, str],
    casefold: bool = False,
) -> pd.DataFrame:
    """Map string values with optional case folding.

    Args:
        df: Input frame.
        newcol: Destination column.
        from_col: Source column to transform.
        mapping: Mapping of source values to replacement text.
        casefold: Lower-case values before matching when ``True``.

    Returns:
        Frame with the mapped column appended.
    """
    if from_col not in df.columns:
        log.warning("[ops] map-values source column '%s' missing", from_col)
        return df
    series = df[from_col].astype(str)
    original = series.copy()
    if casefold:
        series = series.str.lower()
        # Ensure mapping keys match the lower-cased values
        mapping = {str(k).lower(): v for k, v in mapping.items()}
    mapped = series.map(mapping)
    fallback = original if not casefold else original
    df[newcol] = mapped.fillna(fallback)
    return df


def _key_tuples(df: pd.DataFrame, keys: Sequence[str]) -> Sequence[tuple]:
    """Return key tuples for *keys* preserving NA alignment.

    Rows containing ``NaN`` in any of the key columns yield ``None`` to allow
    callers to keep alignment with the original frame while skipping such rows
    from join lookups.
    """

    tuples: List[tuple | None] = []
    for row in df[list(keys)].itertuples(index=False, name=None):
        if any(pd.isna(val) for val in row):
            tuples.append(None)
        else:
            tuples.append(tuple(row))
    return tuples


def op_join_membership(
    df: pd.DataFrame,
    *,
    newcol: str,
    keys: Sequence[str],
    exists_in: str,
    apply_to: str,
    true_value: Any,
    false_value: Any,
    scope: str | None = None,
) -> pd.DataFrame:
    """Flag rows when key tuples exist in the queried subset.

    Args:
        df: Input frame.
        newcol: Destination column name.
        keys: Columns composing the join key.
        exists_in: Query selecting rows that form the lookup set.
        apply_to: Expression selecting rows that should receive the result.
        true_value: Value written when the key exists.
        false_value: Value written when the key is absent.
        scope: Optional grouping column evaluated recursively.

    Returns:
        Frame with *newcol* filled based on membership tests.
    """
    if scope and scope in df.columns:
        result = df.copy()
        for _, group in df.groupby(scope):
            sub = op_join_membership(
                group,
                newcol=newcol,
                keys=keys,
                exists_in=exists_in,
                apply_to=apply_to,
                true_value=true_value,
                false_value=false_value,
                scope=None,
            )
            result.loc[sub.index, newcol] = sub[newcol]
        return result
    scope = None
    missing = [k for k in keys if k not in df.columns]
    if missing:
        log.warning("[ops] join-membership missing key column(s) %s", missing)
        return df
    try:
        source = df.query(exists_in)
        target_mask = df.eval(apply_to, engine="python")
    except Exception as exc:  # noqa: BLE001
        log.error("[ops] join-membership failed: %s", exc)
        return df
    source = source.dropna(subset=list(keys))
    if source.duplicated(subset=list(keys), keep=False).any():
        log.warning("[ops] join-membership duplicate key(s) for %s", keys)
    exists = {k for k in _key_tuples(source, keys) if k is not None}
    vals: list[Any] = []
    for tup in _key_tuples(df, keys):
        vals.append(true_value if tup is not None and tup in exists else false_value)
    series = pd.Series(vals, index=df.index)
    df.loc[target_mask, newcol] = series[target_mask]
    return df


def op_join_value(
    df: pd.DataFrame,
    *,
    newcol: str,
    value_from: str,
    keys: Sequence[str],
    from_rows: str,
    to_rows: str,
    default: Any,
    scope: str | None = None,
) -> pd.DataFrame:
    """Join scalar values from matching rows into a new column.

    Args:
        df: Input frame.
        newcol: Destination column name.
        value_from: Source column copied from the matching row.
        keys: Columns composing the join key.
        from_rows: Query selecting source rows.
        to_rows: Expression selecting rows that receive the value.
        default: Value used when a key is missing.
        scope: Optional grouping column evaluated recursively.

    Returns:
        Frame with *newcol* populated from the lookup results.
    """
    if scope and scope in df.columns:
        result = df.copy()
        for _, group in df.groupby(scope):
            sub = op_join_value(
                group,
                newcol=newcol,
                value_from=value_from,
                keys=keys,
                from_rows=from_rows,
                to_rows=to_rows,
                default=default,
                scope=None,
            )
            result.loc[sub.index, newcol] = sub[newcol]
        return result
    scope = None
    missing = [k for k in keys if k not in df.columns]
    if missing:
        log.warning("[ops] join-value missing key column(s) %s", missing)
        return df
    try:
        source = df.query(from_rows)
        target_mask = df.eval(to_rows, engine="python")
    except Exception as exc:  # noqa: BLE001
        log.error("[ops] join-value failed: %s", exc)
        return df
    source = source.dropna(subset=list(keys))
    if source.duplicated(subset=list(keys), keep=False).any():
        log.warning("[ops] join-value duplicate key(s) for %s", keys)
    lookup = {
        k: v for k, v in zip(_key_tuples(source, keys), source[value_from]) if k is not None
    }
    vals = [lookup.get(k, default) if k is not None else default for k in _key_tuples(df, keys)]
    series = pd.Series(vals, index=df.index)
    df.loc[target_mask, newcol] = series[target_mask]
    return df


def op_exists_to_flag(
    df: pd.DataFrame,
    *,
    newcol: str,
    keys: Sequence[str],
    from_rows: str,
    to_rows: str,
    true_val: Any,
    false_val: Any,
    scope: str | None = None,
) -> pd.DataFrame:
    """Convert existence checks into literal true/false values.

    Args:
        df: Input frame.
        newcol: Destination column name.
        keys: Columns composing the join key.
        from_rows: Query selecting source rows to test for existence.
        to_rows: Expression selecting rows to annotate.
        true_val: Value assigned when the key exists.
        false_val: Value assigned when the key does not exist.
        scope: Optional grouping column evaluated recursively.

    Returns:
        Frame with *newcol* populated based on existence checks.
    """
    if scope and scope in df.columns:
        result = df.copy()
        for _, group in df.groupby(scope):
            sub = op_exists_to_flag(
                group,
                newcol=newcol,
                keys=keys,
                from_rows=from_rows,
                to_rows=to_rows,
                true_val=true_val,
                false_val=false_val,
                scope=None,
            )
            result.loc[sub.index, newcol] = sub[newcol]
        return result
    scope = None
    missing = [k for k in keys if k not in df.columns]
    if missing:
        log.warning("[ops] exists-to-flag missing key column(s) %s", missing)
        return df
    try:
        source = df.query(from_rows)
        target_mask = df.eval(to_rows, engine="python")
    except Exception as exc:  # noqa: BLE001
        log.error("[ops] exists-to-flag failed: %s", exc)
        return df
    source = source.dropna(subset=list(keys))
    if source.duplicated(subset=list(keys), keep=False).any():
        log.warning("[ops] exists-to-flag duplicate key(s) for %s", keys)
    exists = {k for k in _key_tuples(source, keys) if k is not None}
    vals: list[Any] = []
    for tup in _key_tuples(df, keys):
        vals.append(true_val if tup is not None and tup in exists else false_val)
    series = pd.Series(vals, index=df.index)
    df.loc[target_mask, newcol] = series[target_mask]
    return df


def op_synth_rows(
    df: pd.DataFrame,
    *,
    when: str,
    groupby: Sequence[str],
    onset: str,
    duration: float,
    clamp_zero: bool,
    set_values: Dict[str, str],
) -> pd.DataFrame:
    """Synthesise rows per group with templated values.

    Args:
        df: Input frame.
        when: Boolean expression gating row synthesis.
        groupby: Columns defining each group to process.
        onset: Onset expression such as ``first.onset+2``.
        duration: Duration assigned to the synthetic row.
        clamp_zero: Clip negative onset values to zero when ``True``.
        set_values: Mapping of additional column assignments.

    Returns:
        Frame with synthetic rows prepended when conditions are satisfied.
    """
    if when != "block-start":
        log.error("[ops] synth-rows only supports when='block-start'")
        return df
    new_rows: List[Dict[str, Any]] = []
    for _, group in df.groupby(list(groupby)):
        if group.empty:
            continue
        first_vals = group.iloc[0]
        try:
            onset_col, offset = _parse_onset_expr(onset)
        except ValueError:
            log.error("[ops] synth-rows onset expression '%s' malformed", onset)
            return df
        if onset_col not in group.columns:
            log.error("[ops] synth-rows onset column '%s' missing", onset_col)
            return df
        base = float(group[onset_col].min())
        onset_val = base + offset
        if clamp_zero and onset_val < 0:
            onset_val = 0.0
        row = {col: first_vals.get(col) for col in groupby}
        row.update({"onset": onset_val, "duration": duration})
        context = {c: first_vals.get(c) for c in groupby}
        for k, v in set_values.items():
            if v.startswith("fmt(") and v.endswith(")"):
                template = v[4:-1].strip("'\"")
                row[k] = template.format(**context)
            elif "{" in v and "}" in v:  # allow bare brace templates too
                row[k] = v.format(**context)
            else:
                row[k] = v
        new_rows.append(row)
    if not new_rows:
        return df
    df = pd.concat([pd.DataFrame(new_rows), df], ignore_index=True, sort=False)
    df = df.sort_values("onset").reset_index(drop=True)
    return df


def op_flag(
    df: pd.DataFrame,
    *,
    newcol: str,
    expr: str,
    true: Any,
    false: Any,
) -> pd.DataFrame:
    """Create a boolean flag from a pandas.eval expression.

    Behaviour
    ---------
    * Evaluates the expression with engine="python".
    * Any NA/NaN results are treated as False (so the output is always set).
    * Writes the column with explicit {True: true, False: false} mapping.
    """
    try:
        mask = df.eval(expr, engine="python")
    except Exception as exc:  # noqa: BLE001
        log.error("[ops] flag expression '%s' failed: %s", expr, exc)
        return df

    # Ensure NA-safe boolean logic: treat NA as False by default.
    try:
        mask = mask.astype("boolean").fillna(False)
    except Exception:
        # Fallback for older pandas versions where .astype("boolean") may fail.
        mask = mask.where(mask.notna(), False)

    df[newcol] = mask.map({True: true, False: false})
    return df


def op_index(
    df: pd.DataFrame,
    *,
    newcol: str,
    groupby: Sequence[str],
    orderby: str,
    start: int,
    apply_to: str | None = None,
) -> pd.DataFrame:
    """Assign incremental indices grouped by *groupby* sorted by *orderby*.

    Args:
        df: Input frame.
        newcol: Destination column for the index.
        groupby: Columns used to partition the data.
        orderby: Column determining the ordering within each group.
        start: Starting index value.
        apply_to: Optional expression restricting rows that receive the index.

    Returns:
        Frame with the index column applied.
    """
    if apply_to:
        try:
            mask = df.eval(apply_to, engine="python")
        except Exception as exc:  # noqa: BLE001
            log.error("[ops] index apply-to '%s' failed: %s", apply_to, exc)
            return df
        order = df[mask].sort_values(orderby)
        seqs = (
            order.groupby(list(groupby)).cumcount() + start
            if groupby
            else pd.Series(range(start, start + len(order)), index=order.index)
        )
        df.loc[mask, newcol] = seqs.sort_index()
    else:
        order = df.sort_values(orderby)
        seqs = (
            order.groupby(list(groupby)).cumcount() + start
            if groupby
            else pd.Series(range(start, start + len(order)), index=order.index)
        )
        df[newcol] = seqs.sort_index()
    return df


def op_set(
    df: pd.DataFrame,
    *,
    when: str | None,
    set_values: Dict[str, Any],
) -> pd.DataFrame:
    """Assign columns based on an optional boolean expression."""
    mask = pd.Series(True, index=df.index)
    if when:
        try:
            mask = df.eval(when, engine="python")
        except Exception as exc:  # noqa: BLE001
            log.error("[ops] set when '%s' failed: %s", when, exc)
            return df
    for col, val in set_values.items():
        df.loc[mask, col] = val
    return df


def op_drop(df: pd.DataFrame, *, when: str) -> pd.DataFrame:
    """Drop rows where *when* evaluates to ``True``."""
    try:
        mask = df.eval(when, engine="python")
    except Exception as exc:  # noqa: BLE001
        log.error("[ops] drop expression '%s' failed: %s", when, exc)
        return df
    return df.loc[~mask].reset_index(drop=True)


def op_keep_cols_if_exist(df: pd.DataFrame, *, cols: Sequence[str]) -> pd.DataFrame:
    """Return a frame restricted to the subset of existing columns.

    Args:
        df: Input frame.
        cols: Candidate columns to preserve.

    Returns:
        Frame containing only the columns that were present.
    """
    cols = [c for c in cols if c in df.columns]
    return df[cols]


# ---------------------------------------------------------------------------
# dispatcher
# ---------------------------------------------------------------------------

OPS: Dict[str, Callable[..., pd.DataFrame]] = {
    "regex_map": op_regex_map,
    "regex_extract": op_regex_extract,
    "id_from": op_id_from,
    "map_values": op_map_values,
    "join_membership": op_join_membership,
    "join_value": op_join_value,
    "exists_to_flag": op_exists_to_flag,
    "synth_rows": op_synth_rows,
    "flag": op_flag,
    "index": op_index,
    "set": op_set,
    "drop": op_drop,
    "keep_cols_if_exist": op_keep_cols_if_exist,
}


def apply_ops(df: pd.DataFrame, ops: Iterable[tuple[str, Dict[str, Any]]]) -> pd.DataFrame:
    """Sequentially apply *ops* to *df*.

    Unknown operators are skipped with a warning.  Each operator receives the
    frame and keyword arguments extracted from the corresponding spec.
    """

    for name, params in ops:
        fn = OPS.get(name)
        if fn is None:
            log.warning("[ops] unknown operator '%s'", name)
            continue
        try:
            df = fn(df, **params)
        except Exception as exc:  # noqa: BLE001
            log.error("[ops] %s failed: %s", name, exc)
    return df

