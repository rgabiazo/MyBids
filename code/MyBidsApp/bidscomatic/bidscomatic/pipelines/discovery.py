"""Helpers shared across multiple pipelines.

* Subject / session guessing from arbitrary paths.
* Series enumeration and output-directory helpers.
* Cheap heuristics to decide whether a folder is a DICOM image series.

All functions are stateless, free of I/O side effects (apart from simple
``Path`` queries), and therefore easy to unit test.
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pydicom

# ─────────────────────────────────────────────────────────────────────────────
# Regular expressions
# ─────────────────────────────────────────────────────────────────────────────
_SUB_RE = re.compile(r"sub-[A-Za-z0-9]+")
_SES_RE = re.compile(r"ses-[A-Za-z0-9]+")
_DATE_RE = re.compile(r"\d{4}_\d{2}_\d{2}")   # e.g. 2024_05_24

# ─────────────────────────────────────────────────────────────────────────────
# Subject / session discovery
# ─────────────────────────────────────────────────────────────────────────────
def guess_sub_ses(path: Path) -> Tuple[str, Optional[str]]:
    """Return the first ``sub-*`` and ``ses-*`` components found in *path*.

    Args:
        path: A path that potentially contains ``sub-XXX`` and
            ``ses-YYY`` components.

    Returns:
        Tuple ``(sub, ses)`` where *ses* may be ``None`` if no match exists.

    Raises:
        RuntimeError: When *path* contains no ``sub-*`` component.
    """
    sub = ses = None
    for part in path.parts:
        if sub is None and _SUB_RE.fullmatch(part):
            sub = part
        if ses is None and _SES_RE.fullmatch(part):
            ses = part
    if sub is None:
        raise RuntimeError(f"Could not find sub-* in {path}")
    return sub, ses


def _pick_ses_from_path(p: Path) -> Optional[str]:
    """Return the first ``ses-*`` component found in *p* or ``None``."""
    return next((x for x in p.parts if _SES_RE.fullmatch(x)), None)


def _pick_date_from_path(p: Path) -> Optional[str]:
    """Return the first date-like component (``YYYY_MM_DD``) or ``None``."""
    return next((x for x in p.parts if _DATE_RE.search(x)), None)

# ─────────────────────────────────────────────────────────────────────────────
# Sequential-layout helpers
# ─────────────────────────────────────────────────────────────────────────────
def enumerate_series(series_dirs: List[Path]) -> Dict[Path, str]:
    """Return a 1-based, zero-padded index for each *series_dirs* element."""
    return {d: f"{i:04d}" for i, d in enumerate(sorted(series_dirs), 1)}


def series_out_dir(out_root: Path, sub: str, ses: Optional[str], idx: str) -> Path:
    """Build ``<out_root>/sub-XXX[/ses-YYY]/<idx>``."""
    parts: list[Path | str] = [out_root, sub]
    if ses:
        parts.append(ses)
    parts.append(idx)
    return Path(*parts)

# ─────────────────────────────────────────────────────────────────────────────
# Cheap DICOM sniffers
# ─────────────────────────────────────────────────────────────────────────────
_MIN_DCM_FILES = int(os.getenv("BIDSCOMATIC_MIN_SLICES", "10"))
"""
A directory must contain at least this many DICOM files to be treated as an
image series—unless the fallback single-file heuristic succeeds.

Override quickly from the shell, for example::

    export BIDSCOMATIC_MIN_SLICES=1
"""

def _looks_like_dicom(path: Path) -> bool:
    """Return ``True`` when *path* appears to be a valid DICOM file.

    The check is intentionally cheap: read minimal header and ensure
    ``PixelData`` exists.  Any exception results in ``False``.
    """
    try:
        hdr = pydicom.dcmread(path, stop_before_pixels=False, force=True)
        return hasattr(hdr, "PixelData")
    except Exception:
        return False


def is_image_series(sdir: Path) -> bool:
    """Heuristic to decide whether *sdir* is a DICOM image series.

    Acceptance criteria
    -------------------
    * Contains **≥** ``_MIN_DCM_FILES`` files with extension {.dcm, .ima}; or
    * Contains at least one such file that passes the lightweight header check
      (covers single-file Siemens mosaics, field-maps, scouts, etc.).

    Args:
        sdir: Candidate directory.

    Returns:
        ``True`` when *sdir* looks like an image series.
    """
    try:
        dcm_files = [
            f for f in sdir.iterdir()
            if f.is_file() and f.suffix.lower() in {".dcm", ".ima"}
        ]
        # Rule 1 – simple file-count threshold
        if len(dcm_files) >= _MIN_DCM_FILES:
            return True

        # Rule 2 – lightweight fallback for singleton folders
        if dcm_files and _looks_like_dicom(dcm_files[0]):
            return True
        return False
    except Exception:
        return False

# ─────────────────────────────────────────────────────────────────────────────
__all__ = [
    "guess_sub_ses",
    "_pick_ses_from_path",
    "_pick_date_from_path",
    "enumerate_series",
    "series_out_dir",
    "is_image_series",
]
