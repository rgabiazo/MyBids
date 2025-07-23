"""
Simple command‑line helpers used by *bids‑cbrain‑cli* and other entry points
in **bids_cbrain_runner**.

The public surface is intentionally minimal; at the moment there is only
:pyfunc:`parse_kv_pair`, but centralising the parser logic here keeps the main
CLI implementation concise and makes unit testing straightforward.

Rationale
~~~~~~~~~
Many CBRAIN tools expose a large number of optional parameters.  Allowing them
to be specified on the command line as ``--tool-param KEY=VALUE`` pairs gives
flexibility without inflating the CLI with dozens of bespoke flags.  Parsing
with :pymod:`ast` enables automatic interpretation of standard Python
literals—e.g. numbers, lists, dictionaries—so callers do not need to quote or
cast values manually.

Example
-------
>>> parse_kv_pair("iterations=5")
('iterations', 5)
>>> parse_kv_pair("thresholds=[0.1,0.2,0.3]")
('thresholds', [0.1, 0.2, 0.3])
>>> parse_kv_pair("name=hippunfold")  # falls back to raw string
('name', 'hippunfold')
"""

from __future__ import annotations

import ast
import argparse

# -----------------------------------------------------------------------------
# Public helpers
# -----------------------------------------------------------------------------

def parse_kv_pair(arg: str) -> tuple[str, any]:
    """Convert a ``KEY=VALUE`` string into a *(key, value)* tuple.

    Args:
        arg: Single argument supplied on the command line, formatted as
            ``KEY=VALUE``.  The key must not contain the ``=`` character.  The
            portion after the first ``=`` is treated as a Python literal.

    Returns:
        A 2‑tuple ``(key, value)`` where *key* is the left‑hand part of the
        input and *value* is the right‑hand part parsed via
        :pyfunc:`ast.literal_eval`.  When parsing fails the *value* is returned
        as the original string (un‑quoted).

    Raises:
        argparse.ArgumentTypeError: If *arg* does not contain the ``=``
            delimiter.
    """
    # Ensure the argument contains exactly one split point.  Using ``split``
    # with ``maxsplit=1`` keeps any ``=`` characters inside the value portion
    # intact (e.g. JSON‑like strings).
    if "=" not in arg:
        raise argparse.ArgumentTypeError(
            f"Invalid KEY=VALUE argument: {arg!r}")

    key, val = arg.split("=", 1)

    try:
        # Safely evaluate literals such as numbers, lists, dicts, booleans.  It
        # will never execute arbitrary code because *literal_eval* only
        # evaluates a subset of Python syntax corresponding to literals.
        parsed = ast.literal_eval(val)
    except (ValueError, SyntaxError):
        # If the value is *not* a valid literal, treat it as raw string so the
        # caller can still receive the information rather than failing fast.
        parsed = val

    return key, parsed
