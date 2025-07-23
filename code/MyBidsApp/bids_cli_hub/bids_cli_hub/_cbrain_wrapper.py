"""Wrapper around ``bids_cbrain_runner.cli`` to allow invocation as
``bids cbrain …`` within the umbrella ``bids`` command.

The wrapper keeps full parity with the original *argparse* interface by
rebuilding ``sys.argv`` from the Click context and delegating execution to
:pyfunc:`bids_cbrain_runner.cli.main`.

Only comments and docstrings are added; behaviour is unchanged.
"""

from __future__ import annotations

import sys  # Standard library dependency for CLI argument manipulation.
import click  # Click supplies the umbrella command‑group infrastructure.
from bids_cbrain_runner.cli import (
    main as _cbrain_main,  # Original argparse‑based entry point.
)

# ---------------------------------------------------------------------------
# Click command definition
# ---------------------------------------------------------------------------

@click.command(
    context_settings={
        "ignore_unknown_options": True,  # Pass unrecognised flags downstream.
        "allow_extra_args": True,        # Forward positional arguments intact.
        "help_option_names": [],         # Let '--help' pass through untouched.
    }
)
@click.pass_context
def cbrain(ctx: click.Context) -> None:
    """CLI entry point for interacting with CBRAIN.

    Args:
        ctx: Click context that holds the arguments to be forwarded.

    Returns:
        None. The function hands control to
        :pyfunc:`bids_cbrain_runner.cli.main` after adjusting ``sys.argv``.

    Side Effects:
        Mutates :pydata:`sys.argv` so that the downstream *argparse* CLI
        perceives the correct command‑line layout.
    """
    # Re‑build ``sys.argv`` so the downstream CLI believes it was launched
    # directly as ``bids cbrain …``.  The first element is typically the
    # program name, so including it maintains argparse’s help output format.
    sys.argv = ["bids cbrain", *ctx.args]

    # Hand off execution to the original CBRAIN runner.  All exit codes and
    # console output originate from that function.
    _cbrain_main()
