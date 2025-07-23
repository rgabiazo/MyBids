"""Public façade for the ``io`` sub-package.

This package exposes wrappers around external command-line utilities and
helpers that modify the filesystem. Only helpers intended for external
consumption are re-exported; private helpers stay internal to avoid accidental
API exposure.

Attributes:
    run_dcm2niix (Callable[[Path, Path], List[Path]]): Wrapper around the
        ``dcm2niix`` binary. Converts a single DICOM series directory into one
        or more NIfTI/JSON files and returns the list of newly created files.
        See :pymod:`bidscomatic.io.dcm2niix` for details.
"""

from .dcm2niix import run_dcm2niix  # re-export the canonical helper

__all__ = ["run_dcm2niix"]
