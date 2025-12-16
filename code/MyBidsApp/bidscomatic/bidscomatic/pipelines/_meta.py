"""
Lightweight helpers for reading dcm2niix JSON sidecars.

This module is intentionally tiny and dependency-free (stdlib only). It is used
by multiple pipelines (functional, fieldmap, events) to avoid duplicated JSON
parsing and to centralise heuristics such as SBRef detection.

Design goals
------------
* Pure functions (no I/O beyond reading JSON).
* Fast repeated lookups via an in-memory cache.
* Conservative heuristics: prefer explicit metadata fields over filename guesses.
"""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

log_re_sbref = re.compile(r"\bsbref\b|single[- ]band reference", re.I)

# For **RAS-oriented NIfTI**, map BIDS PhaseEncodingDirection (i/j/k) to a human
# dir label commonly used in BIDS filenames (AP/PA/LR/RL/SI/IS).
#
# Note: This is a convenience mapping. In general, mapping i/j/k to anatomical
# labels depends on orientation; many modern dcm2niix outputs are RAS, but not all.
_PED_TO_DIR_FOR_RAS: dict[str, str] = {
    "i": "LR",   # +i axis (Left→Right in RAS)
    "i-": "RL",  # -i axis (Right→Left)
    "j": "PA",   # +j axis (Posterior→Anterior)
    "j-": "AP",  # -j axis (Anterior→Posterior)
    "k": "IS",   # +k axis (Inferior→Superior)
    "k-": "SI",  # -k axis (Superior→Inferior)
}

_DIR_ENTITY_RE = re.compile(r"(?:^|_)dir-(?P<dir>[A-Za-z0-9]+)(?:_|$)", re.I)
_DIR_TOKEN_RE = re.compile(r"_(AP|PA|LR|RL|SI|IS)_", re.I)


@lru_cache(maxsize=4096)
def _read_json(path: str) -> dict[str, Any]:
    """Read JSON file at *path* and return a dict (cached)."""
    p = Path(path)
    if not p.exists() or p.stat().st_size == 0:
        return {}
    try:
        return json.loads(p.read_text() or "{}") or {}
    except Exception:
        # Corrupt JSON should not crash the pipeline; treat as empty metadata.
        return {}


def clear_meta_cache() -> None:
    """Clear the internal JSON cache (useful between subjects)."""
    _read_json.cache_clear()  # type: ignore[attr-defined]


def sidecar_json_of(nifti: Path) -> Path:
    """Return the expected sidecar JSON path for *nifti*."""
    return nifti.with_suffix("").with_suffix(".json")


def task_name_of(nifti: Path) -> str | None:
    """Return TaskName (lowercased) from sidecar JSON, or None."""
    meta = _read_json(str(sidecar_json_of(nifti)))
    v = meta.get("TaskName")
    if isinstance(v, str) and v.strip():
        return v.strip().lower()
    return None


def phase_encoding_direction_of(nifti: Path) -> str | None:
    """Return PhaseEncodingDirection (e.g. 'j'/'j-') from sidecar JSON."""
    meta = _read_json(str(sidecar_json_of(nifti)))
    v = meta.get("PhaseEncodingDirection")
    if isinstance(v, str) and v.strip():
        return v.strip()
    return None


def dir_label_from_ped(ped: str) -> str | None:
    """Map PhaseEncodingDirection (e.g. 'j-') to a dir label (e.g. 'AP').

    Returns None when *ped* is missing/unknown.

    This mapping assumes RAS-oriented NIfTI axes.
    """
    if not isinstance(ped, str):
        return None
    return _PED_TO_DIR_FOR_RAS.get(ped.strip())


def dir_label_from_name(name: str) -> str | None:
    """Infer dir label from a filename.

    Supports:
      - BIDS-style `..._dir-AP_...`
      - token style `..._AP_...`
    """
    if not isinstance(name, str) or not name:
        return None

    if (m := _DIR_ENTITY_RE.search(name)):
        return m.group("dir").upper()

    if (m := _DIR_TOKEN_RE.search(name)):
        return m.group(1).upper()

    return None


def dir_label_of(nifti: Path) -> str | None:
    """Infer dir label for *nifti* from filename first, then JSON PED."""
    # 1) Prefer explicit filename encoding (most reliable)
    d = dir_label_from_name(nifti.name)
    if d:
        return d

    # 2) Fallback to PhaseEncodingDirection (convenience; assumes RAS)
    ped = phase_encoding_direction_of(nifti)
    if ped:
        return dir_label_from_ped(ped)

    return None


def _norm_str(v: Any) -> str:
    return v.strip().lower() if isinstance(v, str) else ""


def is_sbref_meta(meta: dict[str, Any]) -> bool:
    """Heuristic: return True if metadata indicates this is an SBRef image."""
    series_desc = _norm_str(meta.get("SeriesDescription"))
    protocol = _norm_str(meta.get("ProtocolName"))
    img_comments = _norm_str(meta.get("ImageComments"))
    bids_guess = meta.get("BidsGuess")

    # 1) strong signal: explicit SBRef markers in common fields
    hay = " ".join([series_desc, protocol, img_comments])
    if log_re_sbref.search(hay):
        return True

    # 2) dcm2niix sometimes provides BidsGuess (string or dict)
    if isinstance(bids_guess, str) and "sbref" in bids_guess.lower():
        return True
    if isinstance(bids_guess, dict):
        suf = bids_guess.get("suffix")
        if isinstance(suf, str) and suf.lower() == "sbref":
            return True

    return False


def is_sbref_nifti(nifti: Path) -> bool:
    """Return True if *nifti* sidecar suggests SBRef."""
    meta = _read_json(str(sidecar_json_of(nifti)))
    return is_sbref_meta(meta)