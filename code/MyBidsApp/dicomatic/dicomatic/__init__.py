"""
Public interface for *dicomatic*.

The package currently exposes a single convenience re-export:

* :class:`dicomatic.models.DownloadPlan` – planning record consumed by
  download helpers and metadata writers.

Additional high-level objects should be re-exported here to provide a
stable import path for external code, e.g. ::

    from dicomatic import DownloadPlan
"""

from importlib.metadata import PackageNotFoundError, version
from .models import DownloadPlan  # Re-export for external consumers

try:
    __version__: str = version("dicomatic")
except PackageNotFoundError:
    __version__ = "0.0.0"

__all__: list[str] = ["DownloadPlan", "__version__"]
