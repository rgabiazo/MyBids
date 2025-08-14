"""CLI wrapper for running the BIDS validator."""

from __future__ import annotations

from pathlib import Path

import click
import structlog

from ..utils.display import echo_banner, echo_success
from ..utils.validator import find_bids_root_upwards, run_bids_validator

log = structlog.get_logger()


@click.command(
    name="validate",
    context_settings=dict(help_option_names=["-h", "--help"], max_content_width=120),
    help="Run the Node bids-validator on the dataset or a sub-tree.",
)
@click.argument("steps", nargs=-1)
@click.pass_obj
def cli(ctx_obj, steps: tuple[str, ...]) -> None:
    """Run the Node bids-validator on the dataset.

    Args:
        ctx_obj: Click context populated in ``bidscomatic.cli.main``.
        steps: Optional relative path components under the dataset root.

    Raises:
        click.ClickException: When the dataset cannot be located or when
            validation fails.
    """
    root: Path = ctx_obj["root"]
    target = root.joinpath(*steps) if steps else root
    ds_root = find_bids_root_upwards(target)
    if ds_root is None:
        raise click.ClickException("Could not locate dataset_description.json.")

    echo_banner("Validate dataset")
    log.info("Running bids-validator on: %s", ds_root)
    success = run_bids_validator(ds_root)
    if not success:
        raise click.ClickException("BIDS validation failed.")
    echo_success("BIDS validation passed.")


__all__ = ["cli"]
