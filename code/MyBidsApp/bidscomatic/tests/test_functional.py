# ---------------------------------------------------------------------------
# tests/test_functional.py                  ★ aligned with v3.11 behaviour ★
# ---------------------------------------------------------------------------
from pathlib import Path
import subprocess
import nibabel as nib
import numpy as np


def _fake_4d(p: Path, vols: int) -> None:
    data = np.zeros((2, 2, 2, vols), dtype=np.uint8)
    nib.save(nib.Nifti1Image(data, np.eye(4)), p)
    p.with_suffix("").with_suffix(".json").write_text("{}")


def test_bold_runs(tmp_path: Path) -> None:
    """
    Three AP runs → only the highest-volume file is kept **without** run-entity.
    """
    ds = tmp_path / "ds"
    ds.mkdir()
    (ds / "dataset_description.json").write_text("{}")

    raw = ds / "sourcedata/nifti/sub-01/ses-01/rfmri_task_ap"
    raw.mkdir(parents=True)
    _fake_4d(raw / "rfMRI_TASK_AP_22_i01234.nii.gz", 300)
    _fake_4d(raw / "rfMRI_TASK_AP_25_i01235.nii.gz", 290)
    _fake_4d(raw / "rfMRI_TASK_AP_28_i01236.nii.gz", 310)  # winner

    subprocess.run(
        [
            "python",
            "-m",
            "bidscomatic.cli",
            "bids",
            str(ds / "sourcedata/nifti"),
            "--func",
            "task",
        ],
        check=True,
        cwd=tmp_path,
    )

    moved = list((ds / "sub-01/ses-01/func").glob("*_bold.nii.gz"))
    assert len(moved) == 1
    assert moved[0].name == "sub-01_ses-01_task-task_dir-AP_bold.nii.gz"
