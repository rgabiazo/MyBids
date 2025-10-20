# ---------------------------------------------------------------------------
# tests/test_anatomical.py                ★ UPDATED – writes real NIfTIs ★
# ---------------------------------------------------------------------------
from pathlib import Path
import subprocess
import nibabel as nib
import numpy as np


def _fake_3d(p: Path) -> None:
    """Write a minimal 3-D NIfTI and empty JSON sidecar.

    Args:
        p: Destination path for the synthetic image.
    """
    data = np.zeros((2, 2, 2), dtype=np.uint8)
    nib.save(nib.Nifti1Image(data, np.eye(4)), p)
    p.with_suffix("").with_suffix(".json").write_text("{}")


def test_bids_t1w(tmp_path: Path):
    """Verify BIDS T1W behavior."""
    ds = tmp_path / "ds"
    ds.mkdir()
    (ds / "dataset_description.json").write_text("{}")

    nii_root = ds / "sourcedata/nifti/sub-01/ses-01"
    nii_root.mkdir(parents=True)

    _fake_3d(nii_root / "T1w_mprage_800iso_vNav_1_i01234.nii.gz")
    _fake_3d(nii_root / "T1w_mprage_800iso_vNav_9_i05697.nii.gz")

    subprocess.run(
        [
            "python",
            "-m",
            "bidscomatic.cli",
            "bids",
            str(nii_root),
            "--anat",
            "t1w",
        ],
        check=True,
        cwd=ds,
    )

    assert (ds / "sub-01/ses-01/anat/sub-01_ses-01_T1w.nii.gz").exists()
