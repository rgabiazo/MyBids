# ---------------------------------------------------------------------------
# tests/test_functional_sbref_multi_run.py
# ---------------------------------------------------------------------------
"""
Regression: multiple BOLD runs + multiple SBRefs must pair 1:1 without reusing
(or crashing due to stale SBRef paths).
"""

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


def test_multi_run_sbref_pairs_unique(tmp_path: Path) -> None:
    ds = tmp_path / "ds"
    ds.mkdir()
    (ds / "dataset_description.json").write_text("{}")

    trt = 0.0244851

    # Mimic a "sequential" / nested conversion layout like:
    # sub-*/ses-*/<date>_<sub>_baseline/<series>/<files>
    base = ds / "sourcedata/nifti/sub-01/ses-01/2024_01_11_001_baseline"
    (base / "0012").mkdir(parents=True)
    (base / "0013").mkdir(parents=True)
    (base / "0015").mkdir(parents=True)
    (base / "0016").mkdir(parents=True)
    (base / "0018").mkdir(parents=True)
    (base / "0019").mkdir(parents=True)

    # BOLD runs (same vols so we keep all and add run-01..03)
    _fake_epi(
        base / "0013/rfMRI_TASK_AP_13.nii.gz",
        vols=200,
        meta={"PhaseEncodingDirection": "j-", "TotalReadoutTime": trt},
    )
    _fake_epi(
        base / "0016/rfMRI_TASK_AP_16.nii.gz",
        vols=200,
        meta={"PhaseEncodingDirection": "j-", "TotalReadoutTime": trt},
    )
    _fake_epi(
        base / "0019/rfMRI_TASK_AP_19.nii.gz",
        vols=200,
        meta={"PhaseEncodingDirection": "j-", "TotalReadoutTime": trt},
    )

    # SBRefs
    sbref_meta = {
        "SeriesDescription": "rfMRI_TASK_AP_SBRef",
        "ImageComments": "Single-band reference",
        "PhaseEncodingDirection": "j-",
        "TotalReadoutTime": trt,
    }
    _fake_epi(base / "0012/rfMRI_TASK_AP_12.nii.gz", vols=1, meta=sbref_meta)
    _fake_epi(base / "0015/rfMRI_TASK_AP_15.nii.gz", vols=1, meta=sbref_meta)
    _fake_epi(base / "0018/rfMRI_TASK_AP_18.nii.gz", vols=1, meta=sbref_meta)

    subprocess.run(
        CLI + [str(ds / "sourcedata/nifti"), "--func", "task=assocmemory"],
        cwd=ds,
        check=True,
    )

    func_dir = ds / "sub-01/ses-01/func"

    # Expected: 3 BOLD + 3 SBRef, paired uniquely
    for run in ("01", "02", "03"):
        bold = func_dir / f"sub-01_ses-01_task-assocmemory_dir-AP_run-{run}_bold.nii.gz"
        sbref = func_dir / f"sub-01_ses-01_task-assocmemory_dir-AP_run-{run}_sbref.nii.gz"
        assert bold.exists()
        assert sbref.exists()
        assert nib.load(bold).shape[-1] == 200
        assert nib.load(sbref).shape[-1] == 1
