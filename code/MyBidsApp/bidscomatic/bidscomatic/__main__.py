"""
Module entry-point that makes the package runnable with

    python -m bidscomatic
    python -m bidscomatic.cli

Running the module instead of the console-script installed via
``[project.scripts] bidscomatic-cli = …`` is helpful when

* the wheel is executed inside a hermetic environment where console-scripts
  are not installed (e.g. zipapp, some test runners);
* the project is run from a source checkout without ``pip install -e .``; or
* explicit interpreter selection is required (``python3.12 -m bidscomatic``).

The behaviour is identical to the *bidscomatic-cli* console script because the
Click **group** object imported below performs all CLI dispatching.
No additional logic lives here by design.
"""

from bidscomatic.cli import main  # single public symbol needed

# --------------------------------------------------------------------------- #
# Guard block keeps the module import-safe.  When executed via ``-m`` the code
# path below runs; when merely imported (e.g. test discovery) it is skipped.
# ``pragma: no cover`` excludes it from coverage metrics because exercising
# the guard adds no functional value.
# --------------------------------------------------------------------------- #
if __name__ == "__main__":  # pragma: no cover
    main()
