"""\b
Command-line interface entry point for *dicomatic*.

The module configures global options, loads the YAML configuration, and
registers sub-commands that implement distinct workflows (query, bids
grouping, patient lookup, direct downloads, and metadata generation).
"""

from __future__ import annotations

import logging
import os
from types import SimpleNamespace

from dicomatic import __version__

import click

from dicomatic.commands.bids import bids as bids_cmd
from dicomatic.commands.download import download as download_cmd
from dicomatic.commands.metadata import metadata as metadata_cmd
from dicomatic.commands.patients import patients as patients_cmd
from dicomatic.commands.query import query as query_cmd
from dicomatic.config_loader import load_config
from dicomatic.utils.auth import ensure_authenticated
from dicomatic.utils.prompts import _interactive_menu


def _common_options(func):
    """Attach global CLI flags shared by every sub-command.

    Args:
        func: Click command function that receives the additional options.

    Returns:
        Callable: The original Click command wrapped with the shared options.
    """
    # Keep the order consistent with `help --all` output by adding
    # decorators in reverse.
    shared = [
        click.option(
            "-c",
            "--config",
            "config_path",
            type=click.Path(exists=True),
            help="Path to YAML configuration file.",
        ),
        click.option(
            "-u", "--username", help="DICOM username (overrides configuration or $DICOM_USERNAME)."
        ),
        click.option(
            "-p",
            "--password",
            hide_input=True,
            help="DICOM password (overrides configuration or $DICOM_PASSWORD).",
        ),
        click.option("--server", help="DICOM server AET@host (overrides configuration)."),
        click.option("--port", help="DICOM port (overrides configuration)."),
        click.option("--tls", help="DICOM TLS mode: aes | ssl | none (overrides configuration)."),
        click.option("--verbose", is_flag=True, help="Enable debug-level logging."),
        click.option(
            "--bids-root",
            "bids_root",
            type=click.Path(file_okay=False, exists=True),
            help="Explicit BIDS root (bypasses auto-discovery and YAML).",
        ),
    ]
    for opt in reversed(shared):
        func = opt(func)
    return func


@click.group(invoke_without_command=True)
@click.version_option(__version__)
@_common_options
@click.pass_context
def cli(  # noqa: D401 – imperative form is acceptable for CLI description
    ctx: click.Context,
    config_path: str | None,
    username: str | None,
    password: str | None,
    server: str | None,
    port: str | None,
    tls: str | None,
    verbose: bool,
    bids_root: str | None,
):
    """Entry point for the ``dicomatic`` command-line interface.

    Args:
        ctx: Click context object provided by ``@click.pass_context``.
        config_path: Optional path to the YAML configuration file.
        username: DICOM username overriding any configuration.
        password: DICOM password overriding any configuration.
        server: DICOM server address in ``AET@host`` form.
        port: DICOM server port number.
        tls: TLS mode to use for the DICOM connection.
        verbose: Enable debug-level logging when ``True``.
        bids_root: Optional explicit BIDS root path.
    """
    # ── 1. Configure logging ──────────────────────────────────────────
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s:%(name)s: %(message)s",
    )

    # ── 2. Load configuration and merge overrides ────────────────────
    cfg = load_config(config_path)
    cfg.verbose = verbose

    # Ensure optional namespaces exist to avoid attribute checks later
    if not getattr(cfg, "session_map", None):
        cfg.session_map = {}
    if not getattr(cfg, "bids", None):
        cfg.bids = SimpleNamespace(root="")

    if bids_root:
        cfg.bids.root = bids_root

    # Merge CLI flags (highest priority) into the DICOM namespace
    dic = cfg.dicom
    if server:
        dic.server = server
    if port:
        dic.port = port
    if tls:
        dic.tls = tls
    if username:
        dic.username = username
    if password:
        dic.password = password

    # Environment variables override YAML defaults if set
    dic.username = os.environ.get("DICOM_USERNAME", dic.username)
    dic.password = os.environ.get("DICOM_PASSWORD", dic.password)

    # Expose the final configuration to sub-commands
    ctx.obj = cfg

    # ── 3. Interactive menu vs direct sub-command ────────────────────
    if ctx.invoked_subcommand is None:
        # No explicit command → clear screen, authenticate, then launch TUI
        click.clear()
        click.echo("[==== DICOMATIC - DICOM Query & Download ====]\n")
        ensure_authenticated(cfg)
        _interactive_menu(ctx)
    else:
        # Command supplied → authenticate once, then continue
        ensure_authenticated(cfg)


# --------------------------------------------------------------------- #
# Sub-command registration.  Defining them here avoids circular imports #
# caused by Click’s lazy loading.                                       #
# --------------------------------------------------------------------- #
cli.add_command(query_cmd)
cli.add_command(patients_cmd)
cli.add_command(bids_cmd)
cli.add_command(download_cmd)
cli.add_command(metadata_cmd)  # metadata sub-command

if __name__ == "__main__":
    cli()
