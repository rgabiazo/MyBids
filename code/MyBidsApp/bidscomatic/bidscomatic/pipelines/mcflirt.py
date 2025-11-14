"""High level pipeline to wrap FSL MCFLIRT into a BIDS derivative dataset.

The original implementation produced quality control outputs under a generic
``qc`` directory.  The refactored version writes a self‑contained derivatives
dataset named ``MCFLIRT`` with a layout matching the specification outlined in
the project documentation.  The structure is roughly::

    <bids_root>/MCFLIRT/
        dataset_description.json
        figures/<sub-id>/<basename>_desc-*_timeseries.png
        logs/<sub-id>/[<ses-id>]/<basename>_desc-mcflirt[...]
        <sub-id>/[<ses-id>]/func/<basename>_desc-mcflirt_motion.tsv

The module exposes :func:`run` which behaves similarly to the previous version
while returning the paths to the generated ``*_motion.tsv`` files.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import json
import logging
import re
import shutil
from statistics import mean
from typing import List, Tuple

import nibabel as nib
import click

from bidscomatic import __version__
from bidscomatic.utils import fsl
from bidscomatic.utils.paths import dataset_root_or_raise

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helper data structure describing all relevant output paths for a single run
# ---------------------------------------------------------------------------
@dataclass
class _Paths:
    """Collection of derivative paths produced by a single MCFLIRT run."""

    deriv_root: Path
    logs_dir: Path
    figures_dir: Path
    func_dir: Path
    base: str
    par: Path
    abs_rms: Path
    rel_rms: Path
    motion_tsv: Path
    motion_json: Path
    rot_png: Path
    trans_png: Path
    disp_png: Path


def _basename(in_file: Path) -> str:
    """Return the BIDS entity base name for *in_file* without suffix/desc.

    Args:
        in_file: Path to the BOLD file processed by MCFLIRT.

    Returns:
        Concatenated BIDS entities (sub, ses, task, etc.) without extensions.
    """
    tags = re.findall(
        r"(sub-[^_]+|ses-[^_]+|task-[^_]+|acq-[^_]+|dir-[^_]+|run-[^_]+|space-[^_]+|res-[^_]+)",
        in_file.name,
    )
    return "_".join(tags) if tags else in_file.stem


def _build_paths(in_file: Path, base_override: Path | None = None) -> _Paths:
    """Compute derivative paths for *in_file* inside the MCFLIRT dataset.

    Args:
        in_file: BOLD image processed by MCFLIRT.
        base_override: Optional dataset root overriding the file's dataset root.

    Returns:
        _Paths dataclass describing derivative directories and filenames.
    """
    ds_root = dataset_root_or_raise(in_file)
    deriv_root = (base_override or ds_root) / "MCFLIRT"

    base = _basename(in_file)
    sub = re.search(r"sub-[^_]+", base).group(0)
    ses_match = re.search(r"ses-[^_]+", base)
    ses = ses_match.group(0) if ses_match else None

    func_dir = deriv_root / sub
    logs_dir = deriv_root / "logs" / sub
    if ses:
        func_dir /= ses
        logs_dir /= ses
    func_dir /= "func"

    figures_dir = deriv_root / "figures" / sub

    motion_tsv = func_dir / f"{base}_desc-mcflirt_motion.tsv"
    motion_json = func_dir / f"{base}_desc-mcflirt_motion.json"
    par = logs_dir / f"{base}_desc-mcflirt.par"
    abs_rms = logs_dir / f"{base}_desc-mcflirt_abs.rms"
    rel_rms = logs_dir / f"{base}_desc-mcflirt_rel.rms"
    rot_png = figures_dir / f"{base}_desc-rot_timeseries.png"
    trans_png = figures_dir / f"{base}_desc-trans_timeseries.png"
    disp_png = figures_dir / f"{base}_desc-displacement_timeseries.png"

    return _Paths(
        deriv_root=deriv_root,
        logs_dir=logs_dir,
        figures_dir=figures_dir,
        func_dir=func_dir,
        base=base,
        par=par,
        abs_rms=abs_rms,
        rel_rms=rel_rms,
        motion_tsv=motion_tsv,
        motion_json=motion_json,
        rot_png=rot_png,
        trans_png=trans_png,
        disp_png=disp_png,
    )


def _ensure_dataset_description(root: Path) -> None:
    """Create ``dataset_description.json`` in *root* if missing.

    Args:
        root: Derivatives directory that should contain the metadata file.
    """
    dd = root / "dataset_description.json"
    if dd.exists():
        return
    root.mkdir(parents=True, exist_ok=True)
    meta = {
        "Name": "MCFLIRT",
        "BIDSVersion": "1.10.0",
        "GeneratedBy": [
            {"Name": "MCFLIRT"},
            {
                "Name": "bidscomatic",
                "Version": __version__,
                "CodeURL": "https://github.com/rgabiazo/MyBids/tree/main/code/MyBidsApp/bidscomatic",
            },
        ],
    }
    dd.write_text(json.dumps(meta, indent=2))


def _par_to_tsv(par: Path, tsv: Path, js: Path) -> None:
    """Convert an FSL ``.par`` file to TSV and JSON sidecar.

    Args:
        par: Path to the FSL ``.par`` motion parameter file.
        tsv: Destination TSV file storing rotation and translation series.
        js: Destination JSON file describing column metadata.
    """
    cols = ["rot_x", "rot_y", "rot_z", "trans_x", "trans_y", "trans_z"]
    rows = [line.strip().split() for line in par.read_text().splitlines() if line.strip()]

    tsv.parent.mkdir(parents=True, exist_ok=True)
    with tsv.open("w") as f:
        f.write("\t".join(cols) + "\n")
        for row in rows:
            f.write("\t".join(row) + "\n")

    meta = {
        "Columns": cols,
        "Units": {
            "rot_x": "radians",
            "rot_y": "radians",
            "rot_z": "radians",
            "trans_x": "mm",
            "trans_y": "mm",
            "trans_z": "mm",
        },
    }
    js.write_text(json.dumps(meta, indent=2))


def _has_outputs(paths: _Paths) -> bool:
    """Return ``True`` when all expected derivative files exist."""
    required = [paths.motion_tsv, paths.motion_json, paths.rot_png, paths.trans_png, paths.disp_png]
    return all(p.exists() for p in required)


def _context_strings(in_file: Path) -> tuple[str, str, str, str, str]:
    """Return BIDS entity strings for pretty console output."""

    def _tag(pattern: str) -> str | None:
        """Return the first regex match or ``None``."""
        m = re.search(pattern, in_file.name)
        return m.group(0) if m else None

    return (
        _tag(r"sub-[^_]+") or "n/a",
        _tag(r"ses-[^_]+") or "n/a",
        _tag(r"task-[^_]+") or "n/a",
        _tag(r"run-[^_]+") or "n/a",
        _tag(r"dir-[^_]+") or "n/a",
    )


def mcflirt_one(
    in_file: Path,
    paths: _Paths,
    *,
    ref: str = "middle",
    size: Tuple[int, int] = (747, 167),
    only_plot: bool = False,
    keep_nifti: bool = False,
) -> Path:
    """Run MCFLIRT on a single BOLD file and create plots.

    Args:
        in_file: Input BOLD image.
        paths: Pre-computed derivative paths for this run.
        ref: MCFLIRT reference volume (``"first"``, ``"middle"``, or ``"last"``).
        size: Figure size passed to plotting routines.
        only_plot: When ``True``, assume motion correction already exists and only plot.
        keep_nifti: When ``True``, retain intermediate NIfTI products.

    Returns:
        Path to the generated motion TSV file.
    """
    paths.logs_dir.mkdir(parents=True, exist_ok=True)
    paths.figures_dir.mkdir(parents=True, exist_ok=True)

    sub, ses, task, run, direction = _context_strings(in_file)

    img = nib.load(str(in_file))
    if img.ndim != 4 or img.shape[3] < 2:
        log.error("mcflirt input not 4D: %s", in_file)
        raise click.ClickException("Input image must be 4D with more than one volume")
    T = img.shape[3]
    zooms = img.header.get_zooms()
    tr = float(zooms[3]) if len(zooms) > 3 else 0.0

    click.secho("MCFLIRT & Plots", fg="cyan")
    click.echo("──────────────────────────────────────────────────────────────────────")
    click.echo(f" Subject:            {sub}")
    click.echo(f" Session:            {ses}")
    click.echo(f" Task:               {task}")
    click.echo(f" Run:                {run}")
    click.echo(f" Dir/Phase:          {direction}")
    click.echo(f" Volumes (T):        {T}")
    click.echo(f" TR (s):             {tr:.6f}")
    click.echo(f" Input BOLD:         {in_file}")
    click.echo(f" Logs dir:           {paths.logs_dir}")
    click.echo(f" Figures dir:        {paths.figures_dir}")
    click.echo()

    prefiltered = paths.logs_dir / "prefiltered_func_data.nii.gz"
    example = paths.logs_dir / "example_func"
    out_base = paths.logs_dir / "prefiltered_func_data_mcf"
    par_tmp = paths.logs_dir / "prefiltered_func_data_mcf.par"
    abs_rms_tmp = paths.logs_dir / "prefiltered_func_data_mcf_abs.rms"
    rel_rms_tmp = paths.logs_dir / "prefiltered_func_data_mcf_rel.rms"

    if only_plot:
        missing = [p for p in (paths.par, paths.abs_rms, paths.rel_rms) if not p.exists()]
        if missing:
            names = ", ".join(m.name for m in missing)
            log.error("mcflirt missing motion files: %s", names)
            raise click.ClickException(f"Missing motion files: {names}")
    else:
        fsl.run_cmd(["fslmaths", str(in_file), str(prefiltered), "-odt", "float"])
        if ref == "middle":
            idx = T // 2
            fsl.run_cmd(["fslroi", str(prefiltered), str(example), str(idx), "1"])
        elif ref == "first":
            fsl.run_cmd(["fslroi", str(prefiltered), str(example), "0", "1"])
        elif ref == "mean":
            fsl.run_cmd(["fslmaths", str(prefiltered), "-Tmean", str(example)])
        elif ref.startswith("vol="):
            idx = ref.split("=", 1)[1]
            fsl.run_cmd(["fslroi", str(prefiltered), str(example), idx, "1"])
        else:
            shutil.copy(ref, str(example) + ".nii.gz")

        fsl.run_cmd(
            [
                "mcflirt",
                "-in",
                str(prefiltered),
                "-out",
                str(out_base),
                "-reffile",
                str(example),
                "-mats",
                "-plots",
                "-rmsrel",
                "-rmsabs",
                "-spline_final",
                "-report",
            ]
        )

        par_tmp.rename(paths.par)
        abs_rms_tmp.rename(paths.abs_rms)
        rel_rms_tmp.rename(paths.rel_rms)

    # Create plots -----------------------------------------------------------
    fsl.run_cmd(
        [
            "fsl_tsplot",
            "-i",
            str(paths.par),
            "-u",
            "1",
            "--start=1",
            "--finish=3",
            "-a",
            "x,y,z",
            "-t",
            "MCFLIRT estimated rotations (radians)",
            "-w",
            str(size[0]),
            "-h",
            str(size[1]),
            "-o",
            str(paths.rot_png),
        ]
    )

    fsl.run_cmd(
        [
            "fsl_tsplot",
            "-i",
            str(paths.par),
            "-u",
            "1",
            "--start=4",
            "--finish=6",
            "-a",
            "x,y,z",
            "-t",
            "MCFLIRT estimated translations (mm)",
            "-w",
            str(size[0]),
            "-h",
            str(size[1]),
            "-o",
            str(paths.trans_png),
        ]
    )

    fsl.run_cmd(
        [
            "fsl_tsplot",
            "-i",
            f"{paths.abs_rms},{paths.rel_rms}",
            "-a",
            "absolute,relative",
            "-t",
            "MCFLIRT estimated mean displacement (mm)",
            "-w",
            str(size[0]),
            "-h",
            str(size[1]),
            "-o",
            str(paths.disp_png),
        ]
    )

    # Summary table ---------------------------------------------------------
    try:
        abs_vals = [float(v) for v in paths.abs_rms.read_text().split()]
        rel_vals = [float(v) for v in paths.rel_rms.read_text().split()]
        abs_mean = mean(abs_vals) if abs_vals else 0.0
        rel_mean = mean(rel_vals) if rel_vals else 0.0
        N = len(abs_vals)
    except Exception:
        abs_mean = rel_mean = 0.0
        N = 0

    click.echo()
    click.echo(" Volumes:            %s" % N)
    click.echo(" Mean ABS (mm):      %.3f" % abs_mean)
    click.echo(" Mean REL (mm):      %.3f" % rel_mean)
    click.echo(f" Plots dir:          {paths.figures_dir}")
    click.echo(
        " Plots:              "
        f"{paths.rot_png.name} | {paths.trans_png.name} | {paths.disp_png.name}"
    )

    if not keep_nifti:
        for f in [prefiltered, out_base.with_suffix(".nii.gz"), Path(str(example) + ".nii.gz")]:
            if f.exists():
                f.unlink()

    _par_to_tsv(paths.par, paths.motion_tsv, paths.motion_json)

    click.secho("\n✓ Done.", fg="green")
    return paths.motion_tsv


def run(
    in_path: Path,
    *,
    out: Path | None = None,
    ref: str = "middle",
    size: Tuple[int, int] = (747, 167),
    pattern: str = "*_desc-nonaggrDenoised_bold.nii.gz",
    only_plot: bool = False,
    keep_nifti: bool = False,
    force: bool = False,
) -> List[Path]:
    """Entry point handling both single files and directories.

    Args:
        in_path: Path to a BOLD file or directory of files.
        out: Optional derivative root overriding the dataset root.
        ref: MCFLIRT reference volume selection.
        size: Plot size passed to :func:`mcflirt_one`.
        pattern: Glob pattern used when scanning directories.
        only_plot: When ``True``, only render plots for existing results.
        keep_nifti: When ``True``, keep intermediate NIfTI outputs.
        force: When ``True``, rerun even if derivatives exist.

    Returns:
        List of motion TSV paths generated for each processed file.
    """
    processed: List[Path] = []

    def _process_file(f: Path) -> None:
        """Process a single input file and collect the resulting TSV path."""
        paths = _build_paths(f, out)
        _ensure_dataset_description(paths.deriv_root)
        if _has_outputs(paths) and not force:
            click.echo(f"[mcflirt] skip existing {paths.motion_tsv}")
            log.info("mcflirt.skip", path=str(paths.motion_tsv))
            return
        if force:
            for p in [
                paths.par,
                paths.abs_rms,
                paths.rel_rms,
                paths.motion_tsv,
                paths.motion_json,
                paths.rot_png,
                paths.trans_png,
                paths.disp_png,
            ]:
                if p.exists():
                    p.unlink()
        processed.append(
            mcflirt_one(
                f,
                paths,
                ref=ref,
                size=size,
                only_plot=only_plot,
                keep_nifti=keep_nifti,
            )
        )

    if in_path.is_dir():
        files = sorted(in_path.glob(pattern))
        if not files:
            files = sorted(
                p for p in in_path.glob("*_bold.nii.gz") if "boldref" not in p.name
            )
        if not files:
            raise FileNotFoundError(f"No matching files in {in_path}")
        for f in files:
            _process_file(f)
    else:
        _process_file(in_path)

    return processed


__all__ = ["run", "mcflirt_one"]

