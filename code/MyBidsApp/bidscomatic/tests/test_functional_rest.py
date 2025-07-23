# ---------------------------------------------------------------------------
# tests/test_functional_rest.py             ★ aligned with v3.11 behaviour ★
# ---------------------------------------------------------------------------
from pathlib import Path
import subprocess
import json
import nibabel as nib
import numpy as np

CLI = ["python", "-m", "bidscomatic.cli", "bids"]


def _fake_4d(p: Path, vols: int):
    data = np.zeros((2, 2, 2, vols), dtype=np.uint8)
    nib.save(nib.Nifti1Image(data, np.eye(4)), p)
    p.with_suffix("").with_suffix(".json").write_text("{}")


def test_rest_only_and_epi(tmp_path: Path):
    """
    Two REST candidates (100 & 150 vols) + one PA field-map.

    Expect exactly **one** AP BOLD (no run-entity) and the PA EPI in *fmap/*.
    """
    ds = tmp_path / "ds"
    ds.mkdir()
    (ds / "dataset_description.json").write_text("{}")

    raw = ds / "sourcedata/nifti/sub-01/ses-01/rfmri_rest_ap"
    raw.mkdir(parents=True)
    _fake_4d(raw / "rfMRI_REST_AP_10_i0001.nii.gz", 100)
    _fake_4d(raw / "rfMRI_REST_AP_15_i0002.nii.gz", 150)  # winner

    fmap_raw = ds / "sourcedata/nifti/sub-01/ses-01/rfmri_pa"
    fmap_raw.mkdir(parents=True)
    _fake_4d(fmap_raw / "rfMRI_PA_34.nii.gz", 3)

    subprocess.run(
        CLI + [str(ds / "sourcedata/nifti"), "--func", "rest", "--epi"],
        cwd=tmp_path,
        check=True,
    )

    func = list((ds / "sub-01/ses-01/func").glob("*_bold.nii.gz"))
    assert len(func) == 1
    assert func[0].name == "sub-01_ses-01_task-rest_dir-AP_bold.nii.gz"

    meta = json.loads(func[0].with_suffix("").with_suffix(".json").read_text())
    assert meta["TaskName"] == "rest"

    epi = ds / "sub-01/ses-01/fmap/sub-01_ses-01_dir-PA_epi.nii.gz"
    assert epi.exists()
