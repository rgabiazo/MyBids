"""Wrappers around selected FSL tools."""

from __future__ import annotations

from pathlib import Path
import click
import structlog

from bidscomatic.config.tools import load_mcflirt_config
from bidscomatic.pipelines import mcflirt as mcflirt_pipeline

log = structlog.get_logger()


@click.group(name="fsl")
def cli() -> None:
    """Containerised FSL helpers."""


@cli.command("mcflirt")
@click.argument("input_path", type=click.Path(path_type=Path), required=False)
@click.option("-i", "--input", "input_opt", type=click.Path(path_type=Path))
@click.option("--out", type=click.Path(path_type=Path))
@click.option("--ref")
@click.option("--size")
@click.option("--pattern")
@click.option("--only-plot", is_flag=True)
@click.option("--keep-nifti", is_flag=True)
@click.option("--force", is_flag=True, help="Overwrite existing outputs")
@click.pass_obj
def mcflirt_cmd(
    ctx_obj,
    input_path: Path | None,
    input_opt: Path | None,
    out: Path | None,
    ref: str | None,
    size: str | None,
    pattern: str | None,
    only_plot: bool,
    keep_nifti: bool,
    force: bool,
) -> None:
    """Run FSL MCFLIRT and generate FEAT-style plots."""

    def _parse_size(value: str) -> tuple[int, int]:
        """Convert ``WIDTHxHEIGHT`` into an integer tuple.

        Args:
            value: String supplied via ``--size``.

        Returns:
            Tuple containing width and height as integers.

        Raises:
            click.BadParameter: If *value* does not follow the expected format.
        """
        try:
            w_str, h_str = value.lower().split("x")
            return int(w_str), int(h_str)
        except Exception as exc:  # pragma: no cover - defensive
            raise click.BadParameter("SIZE must be WIDTHxHEIGHT") from exc

    path = input_opt or input_path
    if path is None:
        raise click.UsageError("Missing INPUT_PATH")

    cfg = load_mcflirt_config(ctx_obj["root"])
    pattern = pattern or cfg.pattern
    ref = ref or cfg.ref
    if size:
        w, h = _parse_size(size)
    else:
        w, h = cfg.width, cfg.height

    mcflirt_pipeline.run(
        path,
        out=out,
        ref=ref,
        size=(w, h),
        pattern=pattern,
        only_plot=only_plot,
        keep_nifti=keep_nifti,
        force=force,
    )


__all__ = ["cli"]
