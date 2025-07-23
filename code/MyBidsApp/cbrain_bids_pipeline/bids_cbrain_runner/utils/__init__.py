"""Convenience exports for the :mod:`bids_cbrain_runner.utils` package."""

# Reuse the package version information from the parent package
from .. import __version__

from .filetypes import guess_filetype
from .progress import Spinner, run_with_spinner

__all__ = ["guess_filetype", "Spinner", "run_with_spinner"]


