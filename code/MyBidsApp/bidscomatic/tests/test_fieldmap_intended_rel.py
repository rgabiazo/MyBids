# ---------------------------------------------------------------------------
# tests/test_fieldmap_intended_rel.py
# ---------------------------------------------------------------------------
"""
Regression: --intended-rel updates fmap IntendedFor using subject-relative paths
(e.g. 'ses-01/func/...') and harmonizes TotalReadoutTime when consistent.
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


def test_intended_rel_updates_fmap_json(tmp_path: Path) -> None:
    ds = tmp_path / "ds"
    ds.mkdir()
    (ds / "dataset_description.json").write_text("{}")

    trt = 0.0244851

    # ── Task (assocmemory): 3 BOLD + 3 SBRef in sourcedata
    raw_task = ds / "sourcedata/nifti/sub-01/ses-01/rfmri_task_ap"
    raw_task.mkdir(parents=True)

    # BOLD (multi-volume)
    _fake_epi(
        raw_task / "rfMRI_TASK_AP_13.nii.gz",
        vols=200,
        meta={"PhaseEncodingDirection": "j-", "TotalReadoutTime": trt},
    )
    _fake_epi(
        raw_task / "rfMRI_TASK_AP_16.nii.gz",
        vols=200,
        meta={"PhaseEncodingDirection": "j-", "TotalReadoutTime": trt},
    )
    _fake_epi(
        raw_task / "rfMRI_TASK_AP_19.nii.gz",
        vols=200,
        meta={"PhaseEncodingDirection": "j-", "TotalReadoutTime": trt},
    )

    # SBRef (single-volume + marker)
    sbref_meta = {
        "SeriesDescription": "rfMRI_TASK_AP_SBRef",
        "ImageComments": "Single-band reference",
        "PhaseEncodingDirection": "j-",
        "TotalReadoutTime": trt,
    }
    _fake_epi(raw_task / "rfMRI_TASK_AP_12.nii.gz", vols=1, meta=sbref_meta)
    _fake_epi(raw_task / "rfMRI_TASK_AP_15.nii.gz", vols=1, meta=sbref_meta)
    _fake_epi(raw_task / "rfMRI_TASK_AP_18.nii.gz", vols=1, meta=sbref_meta)

    # ── Rest: 1 BOLD + 1 SBRef in sourcedata
    raw_rest = ds / "sourcedata/nifti/sub-01/ses-01/rfmri_rest_ap"
    raw_rest.mkdir(parents=True)

    _fake_epi(
        raw_rest / "rfMRI_REST_AP_22.nii.gz",
        vols=150,
        meta={"PhaseEncodingDirection": "j-", "TotalReadoutTime": trt},
    )
    _fake_epi(
        raw_rest / "rfMRI_REST_AP_21.nii.gz",
        vols=1,
        meta={
            "SeriesDescription": "rfMRI_REST_AP_SBRef",
            "ImageComments": "Single-band reference",
            "PhaseEncodingDirection": "j-",
            "TotalReadoutTime": trt,
        },
    )

    # ── Opposite-phase fieldmap candidate (PA) with "wrong" TRT initially
    raw_fmap = ds / "sourcedata/nifti/sub-01/ses-01/rfmri_pa"
    raw_fmap.mkdir(parents=True)
    _fake_epi(
        raw_fmap / "rfMRI_PA_25.nii.gz",
        vols=3,
        meta={
            "PhaseEncodingDirection": "j",
            "TotalReadoutTime": 0.1111111,  # should get harmonized to `trt`
        },
    )

    # Run bids with epi + intended-rel
    subprocess.run(
        CLI
        + [
            str(ds / "sourcedata/nifti"),
            "--func",
            "task=assocmemory,rest",
            "--epi",
            "--intended-rel",
        ],
        cwd=ds,
        check=True,
    )

    fmap_nii = ds / "sub-01/ses-01/fmap/sub-01_ses-01_dir-PA_epi.nii.gz"
    fmap_json = fmap_nii.with_suffix("").with_suffix(".json")
    assert fmap_nii.exists(), "EPI fieldmap was not moved into fmap/"
    assert fmap_json.exists(), "EPI fieldmap JSON sidecar missing"

    meta = json.loads(fmap_json.read_text())

    # TRT harmonized
    assert abs(float(meta.get("TotalReadoutTime")) - trt) < 1e-9

    # IntendedFor uses subject-relative paths and includes BOLD + SBRef
    expected = sorted(
        [
            # assocmemory BOLD
            "ses-01/func/sub-01_ses-01_task-assocmemory_dir-AP_run-01_bold.nii.gz",
            "ses-01/func/sub-01_ses-01_task-assocmemory_dir-AP_run-02_bold.nii.gz",
            "ses-01/func/sub-01_ses-01_task-assocmemory_dir-AP_run-03_bold.nii.gz",
            # assocmemory SBRef
            "ses-01/func/sub-01_ses-01_task-assocmemory_dir-AP_run-01_sbref.nii.gz",
            "ses-01/func/sub-01_ses-01_task-assocmemory_dir-AP_run-02_sbref.nii.gz",
            "ses-01/func/sub-01_ses-01_task-assocmemory_dir-AP_run-03_sbref.nii.gz",
            # rest BOLD + SBRef (no run entity)
            "ses-01/func/sub-01_ses-01_task-rest_dir-AP_bold.nii.gz",
            "ses-01/func/sub-01_ses-01_task-rest_dir-AP_sbref.nii.gz",
        ]
    )
    got = sorted(meta.get("IntendedFor", []))
    assert got == expected, f"IntendedFor mismatch:\nExpected:\n{expected}\nGot:\n{got}"
