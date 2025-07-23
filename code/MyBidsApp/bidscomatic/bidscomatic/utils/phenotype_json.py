"""Helpers to generate and modify phenotype metadata JSON for TSV files."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Mapping, Sequence

import pandas as pd

from bidscomatic import __version__

log = logging.getLogger(__name__)


def _deep_update(dst: dict, src: Mapping[str, Any]) -> dict:
    """Recursively merge *src* into *dst* and return *dst*."""
    for key, val in src.items():
        if isinstance(val, Mapping) and isinstance(dst.get(key), dict):
            dst[key] = _deep_update(dst[key], val)
        else:
            dst[key] = val
    return dst


def _read_columns(path: Path) -> Sequence[str]:
    """Return column names from a TSV file without loading all rows."""
    return list(pd.read_csv(path, sep="\t", nrows=0).columns)


def minimal_metadata(columns: Sequence[str]) -> dict:
    """Return the base metadata structure for *columns*."""
    meta = {
        "MeasurementToolMetadata": {"Description": "", "TermURL": ""},
        "participant_id": {
            "Description": "Unique participant label matching participants.tsv"
        },
    }
    for col in columns:
        if col == "participant_id":
            continue
        meta[col] = {"Description": "", "Units": ""}
    meta["GeneratedBy"] = {
        "Name": "bidscomatic",
        "Version": __version__,
        "CodeURL": "https://github.com/rgabiazo/MyBidsTest/tree/main/code/MyBidsApp/bidscomatic",
    }
    return meta


def build_metadata(tsv: Path, *, custom: Mapping[str, Any] | None = None) -> dict:
    """Create metadata for *tsv* optionally merged with *custom* mapping.

    Args:
        tsv: Path to a ``*_phenotype.tsv`` file.
        custom: Optional mapping with user-supplied metadata entries.

    Returns:
        Dictionary describing the TSV columns for a sidecar JSON.
    """
    cols = _read_columns(tsv)
    meta = minimal_metadata(cols)
    if custom:
        meta = _deep_update(meta, dict(custom))
    return meta


def apply_overrides(
    meta: Mapping[str, Any],
    *,
    tool_description: str | None = None,
    tool_term_url: str | None = None,
    field_description: Mapping[str, str] | None = None,
    field_units: Mapping[str, str] | None = None,
) -> dict:
    """Return copy of *meta* with CLI overrides applied.

    Args:
        meta: Existing metadata mapping.
        tool_description: Optional description of the measurement tool.
        tool_term_url: Optional ontology URL for the measurement tool.
        field_description: Mapping of per-column descriptions.
        field_units: Mapping of per-column units.

    Returns:
        Updated metadata dictionary.
    """
    updated = dict(meta)

    mtm = updated.setdefault("MeasurementToolMetadata", {})
    if tool_description is not None:
        mtm["Description"] = tool_description
    if tool_term_url is not None:
        mtm["TermURL"] = tool_term_url

    if field_description:
        for col, desc in field_description.items():
            if col not in updated:
                log.warning(
                    "[phenotype-json] --field-description ignored unknown column '%s'",
                    col,
                )
                continue
            info = dict(updated.get(col, {}))
            info["Description"] = desc
            updated[col] = info

    if field_units:
        for col, unit in field_units.items():
            if col not in updated:
                log.warning(
                    "[phenotype-json] --field-units ignored unknown column '%s'",
                    col,
                )
                continue
            info = dict(updated.get(col, {}))
            info["Units"] = unit
            updated[col] = info

    return updated


def write_json(
    tsv: Path,
    *,
    metadata: Mapping[str, Any],
    overwrite: bool = False,
    root: Path | None = None,
) -> bool:
    """Write ``*.json`` next to *tsv* respecting *overwrite*.

    Args:
        tsv: Source TSV file.
        metadata: Metadata dictionary to write.
        overwrite: Whether to overwrite an existing sidecar.
        root: Base path used when reporting the saved file.

    Returns:
        ``True`` if a new file was written, ``False`` otherwise.
    """
    json_path = tsv.with_suffix(".json")
    if json_path.exists() and not overwrite:
        log.info(
            "[phenotype-json] %s exists \u2013 skipped",
            json_path.relative_to(root or json_path.parent),
        )
        return False
    json_path.write_text(json.dumps(metadata, indent=2, ensure_ascii=False))
    log.info(
        "[phenotype-json] wrote %s",
        json_path.relative_to(root or json_path.parent),
    )
    return True
