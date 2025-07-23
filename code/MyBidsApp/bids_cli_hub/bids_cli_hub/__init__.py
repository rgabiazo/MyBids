
"""Top-level initialisation for :mod:`bids_cli_hub`."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__: str = version("bids_cli_hub")
except PackageNotFoundError:
    __version__ = "0.0.0"

__all__ = ["__version__"]
