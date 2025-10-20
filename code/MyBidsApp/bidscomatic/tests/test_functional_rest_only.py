# ---------------------------------------------------------------------------
# tests/test_functional_rest_only.py      ★ UPDATED – no run-01, keep losers ★
# ---------------------------------------------------------------------------
"""
Regression-test for a **single** REST run.

* Exactly one REST NIfTI is created under sourcedata/nifti.
* `bidscomatic-cli bids … --func rest` is run.
* The file must be moved into `func/` **without** a `run-01` entity.
* The BIDS JSON side-car must contain `"TaskName": "rest"`.
"""

from pathlib import Path
import subprocess
import json
import nibabel as nib
import numpy as np


def _fake_4d(p: Path, vols: int) -> None:
    """Write a synthetic 4-D fMRI time series.

    Args:
        p: Destination path for the generated NIfTI file.
        vols: Number of volumes stored in the image.
    """
    data = np.zeros((2, 2, 2, vols), dtype=np.uint8)
    nib.save(nib.Nifti1Image(data, np.eye(4)), p)
    p.with_suffix("").with_suffix(".json").write_text("{}")


def test_rest_single_run_no_run_entity(tmp_path: Path) -> None:
    # 1 – minimal BIDS scaffold
    """Verify rest single RUN NO RUN entity behavior."""
    ds = tmp_path / "ds"
    ds.mkdir()
    (ds / "dataset_description.json").write_text("{}")

    # 2 – one REST candidate
    raw = ds / "sourcedata/nifti/sub-01/ses-01/rfmri_rest_ap"
    raw.mkdir(parents=True)
    _fake_4d(raw / "rfMRI_REST_AP_15_i0001.nii.gz", vols=150)

    # 3 – run CLI
    subprocess.run(
        [
            "python",
            "-m",
            "bidscomatic.cli",
            "bids",
            str(ds / "sourcedata/nifti"),
            "--func",
            "rest",
        ],
        check=True,
        cwd=ds,
    )

    # 4 – exactly one BOLD, **no run entity**
    func_dir = ds / "sub-01/ses-01/func"
    moved = list(func_dir.glob("*_bold.nii.gz"))
    assert moved, "No BOLD file produced"
    assert len(moved) == 1, f"Expected 1 BOLD file, found {len(moved)}"

    assert (
        moved[0].name == "sub-01_ses-01_task-rest_dir-AP_bold.nii.gz"
    ), f"Unexpected filename: {moved[0].name}"

    # 5 – TaskName present in side-car
    meta = json.loads(moved[0].with_suffix("").with_suffix(".json").read_text())
    assert meta.get("TaskName") == "rest", f"TaskName missing in {meta}"
