"""
Configuration package façade.

Exports the small, stable surface that external callers rely on:

* :func:`load_config` – Parse, merge, and validate *series.yaml* and
  *files.yaml* into a single :class:`ConfigSchema` instance.
* :class:`ConfigSchema` – Pydantic model representing the fully-validated
  configuration.

Anything not imported here is considered private implementation detail and may
change without prior notice.
"""

# Re-export the single public loader helper.
from .loader import load_config  # noqa: F401  (import re-exposed on purpose)

# Re-export the root Pydantic schema so callers can check/inspect types.
from .schema import ConfigSchema  # noqa: F401

# Public symbols visible to ``from bidscomatic.config import *``.
__all__: list[str] = ["load_config", "ConfigSchema"]
