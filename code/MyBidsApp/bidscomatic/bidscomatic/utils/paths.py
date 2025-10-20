"""Helpers for working with dataset-relative paths.

These utilities centralise logic for locating the BIDS dataset root and
constructing quality-control output directories.  Keeping this logic in one
place helps maintain consistency across modules.
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

import structlog

from .validator import find_bids_root_upwards

log = structlog.get_logger()


def dataset_root_or_raise(start: Path) -> Path:
    """Return the dataset root containing ``dataset_description.json``.

    Args:
        start: Path somewhere inside the dataset.

    Returns:
        Path to the dataset root.

    Raises:
        FileNotFoundError: If no root is found.
    """
    resolved = start.resolve()
    root = find_bids_root_upwards(resolved)
    if root is None:
        log.error("dataset_root_missing", start=str(start))
        raise FileNotFoundError(f"No dataset_description.json found for {start}")
    log.debug("dataset_root", start=str(resolved), root=str(root))
    return root


def qc_root_for_file(path: Path, *, base: Path | None = None) -> Path:
    """Return the QC root directory for *path*.

    The QC directory mirrors the input's location relative to the dataset root:
    ``<root>/qc/<relative>``.

    Args:
        path: BOLD file or directory inside the dataset.
        base: Optional base directory to override the computed QC root. When
            provided, the relative path under the dataset root is appended to
            *base*.

    Returns:
        Path to the QC root corresponding to *path*.
    """
    resolved = path.resolve()
    ds_root = dataset_root_or_raise(resolved)
    try:
        rel = resolved.parent.relative_to(ds_root)
    except ValueError as err:
        log.error("path_outside_dataset", path=str(path), root=str(ds_root))
        raise ValueError(f"{path} is not inside dataset root {ds_root}") from err
    root = base / rel if base else ds_root / "qc" / rel
    log.debug("qc_root", path=str(path), qc=str(root))
    return root


def qc_run_dir(bold_path: Path, *, base: Path | None = None, stem: Optional[str] = None) -> Path:
    """Return QC output directory for a specific BOLD run.

    Args:
        bold_path: Path to the BOLD image.
        base: Optional base directory for QC outputs. When omitted the directory
            is placed under ``<dataset>/qc`` mirroring the input structure.
        stem: Optional filename stem for the run directory. Defaults to the BOLD
            filename without ``.nii.gz``.

    Returns:
        Path to the directory where QC outputs for the run should be written.
    """
    run_stem = stem or bold_path.name.replace(".nii.gz", "")
    root = qc_root_for_file(bold_path, base=base)
    out_dir = root / run_stem
    log.info("qc_run_dir", bold=str(bold_path), dir=str(out_dir))
    return out_dir


__all__ = ["dataset_root_or_raise", "qc_root_for_file", "qc_run_dir"]
