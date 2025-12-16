from pathlib import Path
import subprocess
import json

import nibabel as nib
import numpy as np

CLI = ["python", "-m", "bidscomatic.cli", "bids"]


def _fake_epi(dst: Path, vols: int, meta: dict) -> None:
    data = np.zeros((2, 2, 2, vols), dtype=np.uint8)
    nib.save(nib.Nifti1Image(data, np.eye(4)), dst)
    dst.with_suffix("").with_suffix(".json").write_text(json.dumps(meta))


def test_rest_dir_inferred_from_phase_encoding_direction(tmp_path: Path) -> None:
    ds = tmp_path / "ds"
    ds.mkdir()
    (ds / "dataset_description.json").write_text("{}")

    # Note: filenames do NOT contain _AP_/_PA_ tokens.
    raw_rest = ds / "sourcedata/nifti/sub-01/ses-01/rfmri_rest_misc"
    raw_rest.mkdir(parents=True)

    trt = 0.0244851
    meta = {"PhaseEncodingDirection": "j-", "TotalReadoutTime": trt}

    _fake_epi(raw_rest / "rfMRI_REST_10_i0001.nii.gz", vols=100, meta=meta)
    _fake_epi(raw_rest / "rfMRI_REST_15_i0002.nii.gz", vols=150, meta=meta)

    subprocess.run(
        CLI + [str(ds / "sourcedata/nifti"), "--func", "rest"],
        cwd=ds,
        check=True,
    )

    out = ds / "sub-01/ses-01/func/sub-01_ses-01_task-rest_dir-AP_bold.nii.gz"
    assert out.exists(), "REST BOLD should be moved and dir inferred as AP from JSON PED"
    assert nib.load(out).shape[-1] == 150, "Should select the 150-vol run as the winner"
