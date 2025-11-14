"""Test helpers for bidscomatic modules."""

from pathlib import Path

import numpy as np
import nibabel as nib
import subprocess


def make_dataset(
    tmp_path: Path,
    *,
    with_session: bool = True,
    run: str | None = None,
    direction: str | None = None,
    n_vols: int = 2,
    boldref: bool = False,
) -> Path:
    """Create a minimal BIDS-like dataset with a single BOLD run.

    Args:
        tmp_path: Root temporary path for the dataset.
        with_session: Whether to include a ``ses-01`` directory level.
        run: Optional run label (e.g., ``"01"``) for inclusion in the filename.
        direction: Optional phase-encoding direction tag (``dir-`` entity).
        n_vols: Number of time points in the generated BOLD file.
        boldref: When ``True``, create a corresponding ``*_boldref.nii.gz``.

    Returns:
        Path to the generated BOLD image.
    """
    (tmp_path / "dataset_description.json").write_text("{}")
    root = tmp_path / "sub-001"
    func = root / ("ses-01/func" if with_session else "func")
    func.mkdir(parents=True, exist_ok=True)

    tags = ["sub-001"]
    if with_session:
        tags.append("ses-01")
    tags.append("task-test")
    if run is not None:
        tags.append(f"run-{run}")
    if direction is not None:
        tags.append(f"dir-{direction}")

    shape = (2, 2, 2, n_vols)
    img = nib.Nifti1Image(np.zeros(shape, dtype="float32"), np.eye(4))
    bold_name = "_".join(tags) + "_bold.nii.gz"
    bold = func / bold_name
    img.to_filename(bold)

    if boldref:
        ref_name = bold_name.replace("_bold.nii.gz", "_boldref.nii.gz")
        ref_img = nib.Nifti1Image(np.zeros((2, 2, 2), dtype="float32"), np.eye(4))
        ref_img.to_filename(func / ref_name)

    return bold


def fake_run_factory(calls: list[list[str]]):
    """Create a fake FSL runner that records commands and writes expected outputs."""

    def _fake_run(
        cmd: list[str],
        *,
        capture: bool = False,
        on_stdout=None,
        suppress_final_result_from_live: bool = False,
    ):
        calls.append(cmd)
        cmd0 = cmd[0]
        if cmd0 == "fslmaths":
            if "-Tmean" in cmd:
                Path(cmd[-1] + ".nii.gz").touch()
            else:
                Path(cmd[2]).touch()
        elif cmd0 == "fslroi":
            Path(cmd[2] + ".nii.gz").touch()
        elif cmd0 == "mcflirt":
            out = Path(cmd[cmd.index("-out") + 1])
            out = out if out.suffix else out.with_suffix(".nii.gz")
            out.parent.mkdir(parents=True, exist_ok=True)
            out.touch()
            (out.parent / "prefiltered_func_data_mcf.par").write_text("0 0 0 0 0 0\n")
            (out.parent / "prefiltered_func_data_mcf_abs.rms").write_text("0\n")
            (out.parent / "prefiltered_func_data_mcf_rel.rms").write_text("0\n")
        elif cmd0 == "fsl_tsplot":
            Path(cmd[cmd.index("-o") + 1]).touch()
        stdout = "" if capture else None
        return subprocess.CompletedProcess(cmd, 0, stdout)

    return _fake_run

