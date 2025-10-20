"""Expose the project-wide Click group for the ``bidscomatic-cli`` script.

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
side effect free and easy to test.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict

from bidscomatic import __version__

import click

from bidscomatic.config import load_config
from bidscomatic.utils.logging import setup_logging


class LazyGroup(click.Group):
    """Click group that imports sub-commands lazily."""

    def __init__(self, *args, **kwargs):
        """Initialise the base class and prepare the lazy registry."""
        self._lazy: dict[str, str] = {}
        super().__init__(*args, **kwargs)

    def set_lazy_command(self, name: str, target: str) -> None:
        """Register *name* to be imported from ``target`` on first use."""

        self._lazy[name] = target

    def get_command(self, ctx, cmd_name):  # noqa: D401 - Click signature
        """Resolve *cmd_name* from the eager map or import table."""
        cmd = super().get_command(ctx, cmd_name)
        if cmd is not None:
            return cmd
        target = self._lazy.get(cmd_name)
        if not target:
            return None
        module_name, attr = target.split(":", 1)
        import importlib

        module = importlib.import_module(module_name)
        cmd = getattr(module, attr)
        self.add_command(cmd, name=cmd_name)
        return cmd

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
    cls=LazyGroup,
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

main.set_lazy_command("unzip", "bidscomatic.cli.unzip:cli")
main.set_lazy_command("init", "bidscomatic.cli.init:cli")
main.set_lazy_command("convert", "bidscomatic.cli.convert:cli")
main.set_lazy_command("bids", "bidscomatic.cli.bids:cli")
main.set_lazy_command("participants", "bidscomatic.cli.participants:cli")
main.set_lazy_command("questionnaires", "bidscomatic.cli.questionnaires:cli")
main.set_lazy_command("phenotype-json", "bidscomatic.cli.phenotype_json:cli")
main.set_lazy_command("events", "bidscomatic.cli.events:cli")
main.set_lazy_command(
    "dataset-description", "bidscomatic.cli.dataset_description:cli"
)
main.set_lazy_command("validate", "bidscomatic.cli.validate:cli")
main.set_lazy_command("preprocess", "bidscomatic.cli.preprocess:cli")
main.set_lazy_command("qc", "bidscomatic.cli.qc:cli")
main.set_lazy_command("fsl", "bidscomatic.cli.fsl:cli")

# The public symbol exported by this module.  Required for ``python -m`` entry-points.
cli = main
__all__: list[str] = ["main"]
