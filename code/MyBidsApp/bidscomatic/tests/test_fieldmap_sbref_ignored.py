# ---------------------------------------------------------------------------
# tests/test_fieldmap_sbref_ignored.py
# ---------------------------------------------------------------------------
"""
Fieldmap safety regression: SBRef-looking EPI files must NOT be treated as
field-maps.
"""

from pathlib import Path
import subprocess
import json

import nibabel as nib
import numpy as np

CLI = ["python", "-m", "bidscomatic.cli", "bids"]


def _fake_bold(dst: Path, vols: int = 10) -> None:
    data = np.zeros((2, 2, 2, vols), dtype=np.uint8)
    nib.save(nib.Nifti1Image(data, np.eye(4)), dst)
    dst.with_suffix("").with_suffix(".json").write_text("{}")


def _fake_sbref_epi(dst: Path) -> None:
    data = np.zeros((2, 2, 2, 1), dtype=np.uint8)
    nib.save(nib.Nifti1Image(data, np.eye(4)), dst)
    meta = {
        "SeriesDescription": "rfMRI_PA_SBRef",
        "ImageComments": "Single-band reference",
        "SeriesNumber": 25,
    }
    dst.with_suffix("").with_suffix(".json").write_text(json.dumps(meta))


def test_sbref_candidate_not_used_as_fieldmap(tmp_path: Path) -> None:
    ds = tmp_path / "ds"
    ds.mkdir()
    (ds / "dataset_description.json").write_text("{}")

    func_dir = ds / "sub-01/ses-01/func"
    func_dir.mkdir(parents=True)
    _fake_bold(func_dir / "sub-01_ses-01_task-rest_dir-AP_bold.nii.gz", vols=10)

    raw = ds / "sourcedata/nifti/sub-01/ses-01/rfmri_pa"
    raw.mkdir(parents=True)
    cand = raw / "rfMRI_PA_25.nii.gz"
    _fake_sbref_epi(cand)

    subprocess.run(
        CLI + [str(ds / "sourcedata/nifti"), "--epi"],
        cwd=ds,
        check=True,
    )

    epi_out = ds / "sub-01/ses-01/fmap/sub-01_ses-01_dir-PA_epi.nii.gz"
    assert not epi_out.exists(), "SBRef candidate was incorrectly moved as a fieldmap"
    assert cand.exists(), "SBRef candidate should remain in sourcedata when ignored"
