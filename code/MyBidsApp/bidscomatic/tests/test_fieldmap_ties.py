# ---------------------------------------------------------------------------
# tests/test_fieldmap_ties.py          2025-06-02  • stable version
# ---------------------------------------------------------------------------
"""
Tie-break regression test: when two PA field-map candidates have the same
volume-count, bidsify_fieldmaps() must select the one with the **higher
SeriesNumber** (…_36 > …_34) and move it into fmap/.
"""

from pathlib import Path
import subprocess
import nibabel as nib
import numpy as np

CLI = ["python", "-m", "bidscomatic.cli", "bids"]


def _fake_epi(dst: Path, series_idx: int) -> None:
    """Write a tiny NIfTI (1 or 2 vols) + empty JSON side-car."""
    vols = 1 + (series_idx % 2)  # odd → 2 vols, even → 1 vol
    img = nib.Nifti1Image(np.zeros((2, 2, 2, vols), dtype=np.uint8), np.eye(4))
    nib.save(img, dst)
    dst.with_suffix("").with_suffix(".json").write_text("{}")


def test_series_index_tiebreak(tmp_path: Path):
    ds = tmp_path / "ds"; ds.mkdir()
    (ds / "dataset_description.json").write_text("{}")

    # AP bold already in BIDS so --epi triggers lookup
    func_dir = ds / "sub-01" / "func"; func_dir.mkdir(parents=True)
    _fake_epi(func_dir / "sub-01_task-rest_dir-AP_bold.nii.gz", 0)

    # two PA candidates
    raw = ds / "sourcedata/nifti/sub-01/rfmri_pa"; raw.mkdir(parents=True)
    lo = raw / "rfMRI_PA_34.nii.gz"   # lower Series#
    hi = raw / "rfMRI_PA_36.nii.gz"   # higher Series#
    _fake_epi(lo, 34)
    _fake_epi(hi, 36)

    subprocess.run(
        CLI + [str(ds / "sourcedata/nifti"), "--epi"],
        cwd=ds,
        check=True,
    )

    epi_out = ds / "sub-01/fmap/sub-01_dir-PA_epi.nii.gz"
    assert epi_out.exists(), "EPI field-map missing"

    # --- tie-break verification ---
    assert not hi.exists(), "rfMRI_PA_36 should have been moved"
    assert     lo.exists(), "rfMRI_PA_34 should remain in sourcedata"
