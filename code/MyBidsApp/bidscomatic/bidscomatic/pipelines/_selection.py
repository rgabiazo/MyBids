"""
Shared heuristics for selecting the best NIfTI run(s) out of a set of
candidates that belong to the same phase-encode direction.

Selection rules
---------------
1. Prefer runs with **more 4-D volumes**.
2. Break ties using the **SeriesNumber** encoded in the filename
   (higher number wins).
3. If still tied, prefer the **newer modification-time**.
4. As a last resort, prefer the **larger gzip size**.

Keeping this logic in one place ensures identical behaviour across all
pipelines (anatomical, functional, diffusion, and any future additions).
"""
from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Iterable, List, Sequence

import nibabel as nib

log = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Regular expressions
# ─────────────────────────────────────────────────────────────────────────────
_SER_RE = re.compile(r"(?:[_-]i|[_-](?:AP|PA|LR|RL|SI)[_-])(?P<num>\d{2,})")


# ─────────────────────────────────────────────────────────────────────────────
# Tiny reusable helpers
# ─────────────────────────────────────────────────────────────────────────────
def _n_vols(path: Path) -> int:
    """Return the number of 4-D volumes in *path* (fallback to 1 for 3-D)."""
    img = nib.load(path)
    return img.shape[3] if img.ndim == 4 else 1


def _series_index(path: Path) -> int:
    """Extract the numeric SeriesNumber from *path* or ``-1`` when absent."""
    match = _SER_RE.search(path.stem)
    return int(match.group("num")) if match else -1


# ─────────────────────────────────────────────────────────────────────────────
# Internal sort helpers
# ─────────────────────────────────────────────────────────────────────────────
def _sort_key(p: Path) -> tuple[int, int, float, int]:
    """Return a tuple that captures the full ranking logic."""
    return (
        _n_vols(p),                 # 1) volume count
        _series_index(p),           # 2) SeriesNumber
        p.stat().st_mtime,          # 3) modification time
        p.stat().st_size,           # 4) gzip size
    )


def _stable_sort(paths: Iterable[Path]) -> List[Path]:
    """Return *paths* sorted **descending** using :func:`_sort_key`."""
    return sorted(paths, key=_sort_key, reverse=True)


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────
def best_runs(
    paths: Sequence[Path],
    *,
    wanted_vols: int | None = None,
    max_runs: int | None = None,
) -> List[Path]:
    """Return the best subset of *paths* according to the ranking rules.

    Args:
        paths: All candidate NIfTI files for a single PE-direction bucket.
        wanted_vols: Require an exact volume count. If no match exists,
            the generic ranking rules are applied.
        max_runs: Optional upper bound on the number of runs returned.

    Returns:
        A list containing the selected NIfTI paths, sorted by preference.
    """
    if not paths:
        return []

    vols = {p: _n_vols(p) for p in paths}

    # Honour an explicit volume filter first.
    if wanted_vols is not None:
        exact = [p for p, v in vols.items() if v == wanted_vols]
        selected = exact or []
        if not selected:
            log.info(
                "No run has %d volumes → falling back to generic ranking rule",
                wanted_vols,
            )
    else:
        selected = []

    # Generic ranking when the explicit filter did not match.
    if not selected:
        best_vol = max(vols.values())
        selected = [p for p, v in vols.items() if v == best_vol]

    selected = _stable_sort(selected)

    # Optionally cap the number of returned runs.
    if max_runs is not None:
        selected = selected[: max_runs]

    log.debug(
        "best_runs() chose %d/%d candidate(s) [wanted=%s max=%s]",
        len(selected),
        len(paths),
        wanted_vols,
        max_runs,
    )
    return selected


# ─────────────────────────────────────────────────────────────────────────────
__all__ = [
    "best_runs",
    "_n_vols",          # exposed for unit-tests & other helpers
    "_series_index",    # ditto
]
