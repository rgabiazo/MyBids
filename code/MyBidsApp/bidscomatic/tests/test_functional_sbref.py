# ---------------------------------------------------------------------------
# tests/test_functional_sbref.py
# ---------------------------------------------------------------------------
"""
SBRef regression test.

Given:
* One task BOLD run (many vols)
* One SBRef run (1 vol) whose sidecar indicates "Single-band reference"

Expect:
* BOLD moved to func/ with ``_bold`` suffix
* SBRef moved alongside it with ``_sbref`` suffix
* Both JSON sidecars contain TaskName matching the CLI task argument
"""

from pathlib import Path
import subprocess
import json

import nibabel as nib
import numpy as np


def _fake_4d(p: Path, vols: int) -> None:
    data = np.zeros((2, 2, 2, vols), dtype=np.uint8)
    nib.save(nib.Nifti1Image(data, np.eye(4)), p)
    p.with_suffix("").with_suffix(".json").write_text("{}")


def _fake_sbref(p: Path) -> None:
    data = np.zeros((2, 2, 2, 1), dtype=np.uint8)
    nib.save(nib.Nifti1Image(data, np.eye(4)), p)
    meta = {
        "SeriesDescription": "rfMRI_TASK_AP_SBRef",
        "ImageComments": "Single-band reference",
        "SeriesNumber": 15,
    }
    p.with_suffix("").with_suffix(".json").write_text(json.dumps(meta))


def test_task_sbref_moved(tmp_path: Path) -> None:
    ds = tmp_path / "ds"
    ds.mkdir()
    (ds / "dataset_description.json").write_text("{}")

    raw = ds / "sourcedata/nifti/sub-01/ses-01/rfmri_task_ap"
    raw.mkdir(parents=True)

    _fake_4d(raw / "rfMRI_TASK_AP_16_i0001.nii.gz", vols=300)
    _fake_sbref(raw / "rfMRI_TASK_AP_15.nii.gz")

    subprocess.run(
        [
            "python",
            "-m",
            "bidscomatic.cli",
            "bids",
            str(ds / "sourcedata/nifti"),
            "--func",
            "task=assocmemory",
        ],
        check=True,
        cwd=ds,
    )

    func_dir = ds / "sub-01/ses-01/func"
    bold = func_dir / "sub-01_ses-01_task-assocmemory_dir-AP_bold.nii.gz"
    sbref = func_dir / "sub-01_ses-01_task-assocmemory_dir-AP_sbref.nii.gz"

    assert bold.exists(), "BOLD not moved into func/"
    assert sbref.exists(), "SBRef not moved into func/"

    bold_meta = json.loads(bold.with_suffix("").with_suffix(".json").read_text())
    sbref_meta = json.loads(sbref.with_suffix("").with_suffix(".json").read_text())
    assert bold_meta.get("TaskName") == "assocmemory"
    assert sbref_meta.get("TaskName") == "assocmemory"

    assert nib.load(bold).shape[-1] == 300
    assert nib.load(sbref).shape[-1] == 1
