"""Utilities to build, override, and write JSON sidecars for events TSV files."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Mapping

import pandas as pd

from bidscomatic import __version__
from .phenotype_json import _deep_update

log = logging.getLogger(__name__)

__all__ = ["build_metadata", "apply_overrides", "write_json"]


def _read_table(path: Path) -> pd.DataFrame:
    """Load ``path`` into a DataFrame with string typed columns.

    Args:
        path: Events file to read.

    Returns:
        DataFrame with all columns read as strings.
    """
    return pd.read_csv(path, sep="\t", dtype=str)


def build_metadata(tsv: Path, custom: Mapping[str, Any] | None = None) -> dict:
    """Create metadata for ``tsv`` optionally merged with ``custom``.

    Args:
        tsv: Path to an ``*_events.tsv`` file.
        custom: Optional mapping with user-supplied metadata entries.

    Returns:
        Dictionary in BIDS events JSON format.
    """
    df = _read_table(tsv)

    meta: dict[str, dict[str, Any]] = {}
    for col in df.columns:
        info: dict[str, Any] = {"Description": "", "Units": ""}
        if col == "onset":
            info["Description"] = "Event onset relative to run start"
            info["Units"] = "seconds"
        elif col == "duration":
            info["Description"] = "Event duration"
            info["Units"] = "seconds"
        # Determine categorical columns and enumerate levels
        uniq = [v for v in sorted(df[col].dropna().unique()) if str(v).strip()]
        if col in {"trial_type", "response"}:
            if uniq:
                info["Levels"] = {str(v): "" for v in uniq}
        meta[col] = info

    meta["GeneratedBy"] = {
        "Name": "bidscomatic",
        "Version": __version__,
        "CodeURL": "https://github.com/rgabiazo/MyBidsTest/tree/main/code/MyBidsApp/bidscomatic",
    }

    if custom:
        meta = _deep_update(meta, dict(custom))

    return meta


def apply_overrides(
    meta: Mapping[str, Any],
    field_description: Mapping[str, str] | None = None,
    field_units: Mapping[str, str] | None = None,
    field_levels: Mapping[str, Mapping[str, str]] | None = None,
) -> dict:
    """Return copy of ``meta`` with command-line overrides applied.

    Args:
        meta: Base metadata mapping.
        field_description: Optional mapping of column descriptions.
        field_units: Optional mapping of column units.
        field_levels: Optional mapping of column levels.

    Returns:
        Updated metadata dictionary.
    """
    updated = dict(meta)

    if field_description:
        for col, desc in field_description.items():
            if col not in updated:
                log.warning(
                    "[events-json] --field-description ignored unknown column '%s'", col
                )
                continue
            updated[col] = _deep_update(
                dict(updated.get(col, {})), {"Description": desc}
            )

    if field_units:
        for col, unit in field_units.items():
            if col not in updated:
                log.warning(
                    "[events-json] --field-units ignored unknown column '%s'", col
                )
                continue
            updated[col] = _deep_update(dict(updated.get(col, {})), {"Units": unit})

    if field_levels:
        for col, levels in field_levels.items():
            if col not in updated:
                log.warning(
                    "[events-json] --field-levels ignored unknown column '%s'",
                    col,
                )
                continue
            info = dict(updated.get(col, {}))
            cur = dict(info.get("Levels", {}))
            cur.update(levels)
            info["Levels"] = cur
            updated[col] = info

    return updated


def write_json(
    tsv: Path,
    metadata: Mapping[str, Any],
    overwrite: bool = False,
    root: Path | None = None,
) -> bool:
    """Write ``*.json`` next to ``tsv`` respecting ``overwrite``.

    Args:
        tsv: Source events file.
        metadata: Structured metadata to write.
        overwrite: Whether to overwrite an existing JSON file.
        root: Base path used when reporting the saved file.

    Returns:
        ``True`` if a new file was written, ``False`` otherwise.
    """
    json_path = tsv.with_suffix(".json")
    if json_path.exists() and not overwrite:
        log.info(
            "[events-json] %s exists \u2013 skipped",
            json_path.relative_to(root or json_path.parent),
        )
        return False
    json_path.write_text(json.dumps(metadata, indent=2, ensure_ascii=False))
    log.info(
        "[events-json] wrote %s",
        json_path.relative_to(root or json_path.parent),
    )
    return True
