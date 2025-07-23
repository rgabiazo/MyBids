"""
Entry-point module that exposes the project-wide Click *group* ``main`` under
the console script **bidscomatic-cli**.

The module:

* declares a single Click *group* called :pyfunc:`main`;
* wires common global flags (dataset root, YAML overrides, verbosity, etc.);
* sets up logging via :pyfunc:`bidscomatic.utils.logging.setup_logging`;
* validates that the working directory is a BIDS dataset for commands that
  require one;
* loads the merged *series.yaml / files.yaml* configuration unless the invoked
  sub-command is *init*;
* registers every sub-command located in sibling modules.

No state is mutated outside the Click context, which keeps the CLI layer
side-effect-free and easy to test.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict

from bidscomatic import __version__

import click

from bidscomatic.config import load_config
from bidscomatic.utils.logging import setup_logging

# ─────────────────────────────────────────────────────────────────────────────
# Context settings shared by the entire Click hierarchy
# Show “-h/--help” and provide default values in the automatic help text.
# ─────────────────────────────────────────────────────────────────────────────
_CTX: Dict[str, Any] = dict(
    help_option_names=["-h", "--help"],
    show_default=True,
    max_content_width=120,
)

# ─────────────────────────────────────────────────────────────────────────────
# Top-level Click *group*
# All sub-commands are attached via :pyfunc:`add_command` below.
# ─────────────────────────────────────────────────────────────────────────────
@click.group(
    context_settings=_CTX,
    help="""\b
bidscomatic-cli – BIDS toolkit.

"""
)
@click.version_option(__version__)
@click.option(
    "-r",
    "--bids-root",
    type=click.Path(file_okay=False, path_type=Path),
    help="Path to the BIDS dataset root (folder with dataset_description.json).",
)
@click.option("-s", "--series-yaml", type=click.Path(dir_okay=False, path_type=Path))
@click.option("-f", "--files-yaml",  type=click.Path(dir_okay=False, path_type=Path))
@click.option("-v", "--verbose",     is_flag=True, help="INFO-level console output.")
@click.option("--debug",            is_flag=True, help="DEBUG console + JSON logfile.")
@click.option(
    "--save-logfile",
    type=click.Path(dir_okay=False, writable=True, path_type=Path),
    help="Mirror console output into this plain-text file.",
)
@click.pass_context
def main(  # noqa: D401 – Click requires the callback to be named “main”.
    ctx: click.Context,
    bids_root:  Path | None,
    series_yaml: Path | None,
    files_yaml:  Path | None,
    verbose: bool,
    debug:   bool,
    save_logfile: Path | None,
) -> None:
    """Root command executed by *bidscomatic-cli*.

    Args:
        ctx: Click runtime context that carries objects across sub-commands.
        bids_root: Optional dataset root supplied via ``--bids-root``.  Falls
            back to ``$BIDS_ROOT`` or the current directory.
        series_yaml: Explicit path to a *series.yaml* override.
        files_yaml: Explicit path to a *files.yaml* override.
        verbose: Emit INFO-level messages on stdout.
        debug: Emit DEBUG-level messages and enable JSON file logging.
        save_logfile: Optional path for a plain-text log that mirrors console
            output.

    Raises:
        click.ClickException: When the invoked sub-command expects a BIDS
            dataset but ``dataset_description.json`` is missing.
    """
    root = bids_root or Path(os.environ.get("BIDS_ROOT", ".")).resolve()
    subcmd = ctx.invoked_subcommand or ""

    # Guard against accidental execution outside a dataset --------------------
    if subcmd not in {"init", "unzip", "convert", "dataset-description"} and not (
        root / "dataset_description.json"
    ).exists():
        raise click.ClickException(
            f"{root} is not a BIDS dataset – create one first:\n\n"
            f"  bidscomatic-cli init {root} --name \"MyStudy\"\n"
        )

    # Logging must be configured before any output is produced ----------------
    force_info = (
        subcmd
        in {
            "unzip",
            "convert",
            "bids",
            "events",
            "participants",
            "questionnaires",
            "validate",
        }
    ) and not (verbose or debug)
    setup_logging(
        dataset_root=root if root.exists() else None,
        verbose=verbose,
        debug=debug,
        force_info=force_info,
        extra_text_log=save_logfile,
    )

    # Load YAML configuration unless the command explicitly works without it --
    cfg = None if subcmd == "init" else load_config(
        series_path=series_yaml,
        files_path=files_yaml,
        dataset_root=root if root.exists() else None,
    )

    # Stash frequently-needed objects in the Click context --------------------
    ctx.obj = {
        "root": root,
        "cfg":  cfg,
        "verbose": verbose,
        "debug":   debug,
    }

# ─────────────────────────────────────────────────────────────────────────────
# Sub-command registrations
# Imports are placed *after* the Click group definition to avoid circular
# dependencies during module import.
# ─────────────────────────────────────────────────────────────────────────────
from .unzip          import cli as unzip_cmd          # noqa: E402
from .init           import cli as init_cmd           # noqa: E402
from .convert        import cli as convert_cmd        # noqa: E402
from .bids           import cli as bids_cmd           # noqa: E402
from .participants   import cli as participants_cmd   # noqa: E402
from .questionnaires import cli as questionnaires_cmd # noqa: E402
from .phenotype_json import cli as phenotype_json_cmd # noqa: E402
from .events         import cli as events_cmd         # noqa: E402
from .dataset_description import cli as dataset_description_cmd  # noqa: E402
from .validate       import cli as validate_cmd       # noqa: E402

main.add_command(unzip_cmd)
main.add_command(init_cmd)
main.add_command(convert_cmd)
main.add_command(bids_cmd)
main.add_command(participants_cmd)
main.add_command(questionnaires_cmd)
main.add_command(phenotype_json_cmd)
main.add_command(events_cmd)
main.add_command(dataset_description_cmd)
main.add_command(validate_cmd)

# The public symbol exported by this module.  Required for ``python -m`` entry-points.
cli = main
__all__: list[str] = ["main"]
