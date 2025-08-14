"""
Lightweight helpers for human‑readable console output.

This module intentionally keeps formatting concerns (pretty‑printing) separate
from computational logic.  The sole public helper,
:pyfunc:`print_jsonlike_dict`, takes an already structured *Python* object –
typically produced by the directory‑tree walkers – and logs it as an indented
JSON block for visual inspection of nested structures without embedding BIDS
knowledge in the logger itself.

Why use ``logger.info`` instead of ``print``?
-------------------------------------------
Integrating with the stdlib :pymod:`logging` framework allows caller code to
control verbosity globally (e.g. ``--debug-logs`` flag) and to redirect output
as needed when running inside notebooks or CI pipelines.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Mapping

logger = logging.getLogger(__name__)

__all__ = ["print_jsonlike_dict"]

# -----------------------------------------------------------------------------
# Public helper
# -----------------------------------------------------------------------------

def print_jsonlike_dict(data: Mapping[str, Any] | Any, message: str = "Found matching directory structure") -> None:
    """Log *data* as an indented JSON string preceded by *message*.

    Args:
        data: Any JSON‑serialisable Python object (commonly a dict).  The
            function does *not* attempt to coerce non‑serialisable objects –
            callers must provide a clean structure.
        message: Descriptive header inserted *before* the rendered JSON to give
            readers context.  Defaults to a generic description used throughout
            the CLI.

    Returns:
        ``None`` – side‑effect only via ``logger.info``.
    """
    # ``json.dumps`` with an indent ensures consistent multi‑line formatting
    # regardless of the original object order.
    formatted = json.dumps(data, indent=4)

    # A leading newline separates the block from previous log lines, improving
    # readability in dense console output.
    logger.info("\n%s\n%s\n", message, formatted)
