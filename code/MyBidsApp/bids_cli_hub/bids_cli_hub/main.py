"""
Umbrella command-line interface for the *BIDS helper* toolbox.

This module exposes a single Click *group* named :pyfunc:`cli` that re-exports
three independent command-line applications under one top-level command
(``bids``).  The helper keeps each sub-tool intact; it merely provides a shared
entry point so that related utilities are discoverable via a common prefix.

Sub-commands
------------
``bids`` delegates to three existing Click applications—nothing is wrapped or
modified beyond registration:

* ``bids bidscomatic`` → :pyfunc:`bidscomatic.cli.main`
* ``bids dicomatic``   → :pyfunc:`dicomatic.cli.cli`
* ``bids cbrain``      → :pyfunc:`bids_cli_hub._cbrain_wrapper.cbrain`

Running the module directly (``python -m bids_cli_hub.main``) starts the same
Click parser that the installed ``bids`` executable would invoke.
"""

from __future__ import annotations

import click

# ---------------------------------------------------------------------------
# Import the Click commands exported by each individual package.  Import paths
# point to the canonical public entry points so that versioned behaviour is
# preserved even when the underlying packages evolve.
# ---------------------------------------------------------------------------
from bidscomatic.cli import main as bidscomatic_cli  # noqa: E402 – intentional order
from dicomatic.cli import cli as dicomatic_cli  # noqa: E402
from ._cbrain_wrapper import cbrain as cbrain_cli  # noqa: E402
from . import __version__


@click.group(
    context_settings={"help_option_names": ["-h", "--help"], "max_content_width": 120}
)
@click.version_option(__version__)
def cli() -> None:
    """bids – umbrella command that exposes the helper tools.

    This group defines no options of its own; it merely registers the
    ``bidscomatic``, ``dicomatic`` and ``cbrain`` commands so that running
    ``bids --help`` lists them in one place.

    Returns:
        None. The function registers sub-commands and exits.
    """
    # Group body intentionally empty – sub-commands are attached below.
    pass  # noqa: D401 – required by Click but contains no logic.


# ---------------------------------------------------------------------------
# Sub-command registration.  The *name* parameter ensures predictable CLI
# spelling regardless of the original function names.
# ---------------------------------------------------------------------------
cli.add_command(bidscomatic_cli, name="bidscomatic")
cli.add_command(dicomatic_cli, name="dicomatic")
cli.add_command(cbrain_cli, name="cbrain")


if __name__ == "__main__":
    # Enable ``python path/to/main.py`` for local development and debugging.
    cli()
