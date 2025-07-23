"""
Lazy import wrapper for the *dicomatic.bids* sub-package.

The public API intentionally exposes only one helper:

* :func:`dicomatic.bids.download_bids`

The function lives in *dicomatic.bids.planner* but is imported on first
access to avoid a circular-dependency chain with
``dicomatic.utils.bids_helpers`` during interpreter start-up.
"""

from importlib import import_module
from types import ModuleType
from typing import Any

__all__: list[str] = ["download_bids"]


def __getattr__(name: str) -> Any:  # PEP 562 dynamic attribute access
    """Resolve the *download_bids* symbol on first request.

    Parameters
    ----------
    name:
        Attribute requested by client code.

    Returns
    -------
    Any
        The underlying object from :pymod:`dicomatic.bids.planner`.

    Raises
    ------
    AttributeError
        If *name* does not match ``download_bids``.
    """
    if name == "download_bids":
        mod: ModuleType = import_module("dicomatic.bids.planner")
        return getattr(mod, "download_bids")
    raise AttributeError(f"module {__name__!r} has no attribute {name}")
