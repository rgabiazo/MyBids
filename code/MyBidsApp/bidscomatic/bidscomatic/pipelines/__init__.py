"""
Public façade for the *pipelines* sub-package.

This module exposes the high-level helpers used by the CLI and by other
internal components:

* **Archive handling**
    * :func:`unzip_archives`
    * :class:`UnzipResult`

* **DICOM → NIfTI conversion**
    * :func:`convert_dicom_tree`
    * :class:`Dcm2NiixResult`

* **BIDS-ification helpers**
    * :func:`bidsify_anatomical`
    * :func:`bidsify_functional`

* **Shared value object**
    * :class:`SubjectSession`

Importing from ``bidscomatic.pipelines`` rather than individual modules keeps
call-sites stable even when underlying filenames change.
"""

from __future__ import annotations

# ────────────────────────────────────────────────────────────────────────────
# Public helpers – ordered roughly chronologically for a typical workflow.
# (1)  Unpack → (2)  Convert → (3)  BIDS-ify.
# ────────────────────────────────────────────────────────────────────────────
from .types import SubjectSession, Dcm2NiixResult, UnzipResult
from .unzip import unzip_archives
from .convert import convert_dicom_tree
from .anatomical import bidsify_anatomical
from .functional import bidsify_functional
from .discovery import is_image_series  # predicate reused elsewhere

__all__: list[str] = [
    # Unzip helpers
    "unzip_archives",
    "UnzipResult",
    # Conversion helpers
    "convert_dicom_tree",
    "Dcm2NiixResult",
    # BIDS-ification helpers
    "bidsify_anatomical",
    "bidsify_functional",
    # Shared value object
    "SubjectSession",
    # Convenience predicate
    "is_image_series",
]

# ---------------------------------------------------------------------------
# Compatibility shim
# ---------------------------------------------------------------------------
# Older external code may still import `bidscomatic.pipelines.bidsify`.
# Provide a lightweight alias so that legacy imports do not break while
# emitting a deprecation warning.
import sys as _sys
import warnings as _warnings

_sys.modules["bidscomatic.pipelines.bidsify"] = _sys.modules[__name__]
_warnings.warn(
    "'bidscomatic.pipelines.bidsify' is deprecated; import from "
    "'bidscomatic.pipelines.anatomical' instead.",
    DeprecationWarning,
    stacklevel=2,
)
