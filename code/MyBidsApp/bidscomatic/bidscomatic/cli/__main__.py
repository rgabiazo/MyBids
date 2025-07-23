"""
Module-level wrapper so that executing

    python -m bidscomatic.cli …

behaves identically to invoking the console script **bidscomatic-cli** that is
declared in *pyproject.toml*.

The file contains no additional logic beyond importing the Click *group* and
calling it when executed as a script.
"""

from bidscomatic.cli import main  # Re-exported Click command-group


if __name__ == "__main__":  # pragma: no cover
    # Delegate control to Click’s command-group so all options and sub-commands
    # are available when the module is run with ``python -m``.
    main()
