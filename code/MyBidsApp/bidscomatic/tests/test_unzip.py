# ---------------------------------------------------------------------------
# code/MyBidsApp/tests/test_unzip.py        ← assertion updated
# ---------------------------------------------------------------------------
from pathlib import Path
from zipfile import ZipFile

from bidscomatic.pipelines.unzip import unzip_archives


def test_unzip_single_zip(tmp_path: Path):
    # 1) create a throw-away zip with one fake DICOM
    archive = tmp_path / "sub-001.zip"
    dcm_name = "IMAGE0001.dcm"
    with ZipFile(archive, "w") as zf:
        zf.writestr(dcm_name, b"dummy")

    # 2) run the extractor
    res = unzip_archives(archive)

    # at least one directory was reported
    assert res.archive_dirs
    # and the expected file now exists
    dcm_file = res.archive_dirs[0] / dcm_name
    assert dcm_file.exists() and dcm_file.read_bytes() == b"dummy"
