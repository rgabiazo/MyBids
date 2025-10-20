from pathlib import Path
import os
import subprocess
from zipfile import ZipFile

CLI = ["python", "-m", "bidscomatic.cli", "unzip"]


def test_unzip_plain_text_output(tmp_path: Path) -> None:
    """Verify unzip plain text output behavior."""
    archive = tmp_path / "example.zip"
    with ZipFile(archive, "w") as zf:
        zf.writestr("dummy.dcm", b"0")

    result = subprocess.run(
        CLI + [str(archive)],
        capture_output=True,
        text=True,
        check=True,
        cwd=tmp_path,
    )

    assert '{"event":' not in result.stdout
    assert "Z [info" not in result.stdout


def test_default_json_log_location(tmp_path: Path) -> None:
    """Verify default JSON LOG location behavior."""
    archive = tmp_path / "example.zip"
    with ZipFile(archive, "w") as zf:
        zf.writestr("dummy.dcm", b"0")

    from bidscomatic.utils import logging as log_utils

    pkg_logs = Path(log_utils.__file__).resolve().parents[1] / "logs"
    log_file = pkg_logs / "bidscomatic.log"
    if log_file.exists():
        log_file.unlink()

    env = os.environ.copy()
    env["BIDS_ROOT"] = str(tmp_path / "missing")

    subprocess.run(
        CLI + [str(archive)],
        capture_output=True,
        text=True,
        check=True,
        cwd=tmp_path,
        env=env,
    )

    assert log_file.exists()


def test_dataset_root_log_location(tmp_path: Path) -> None:
    """Verify dataset root LOG location behavior."""
    archive = tmp_path / "example.zip"
    with ZipFile(archive, "w") as zf:
        zf.writestr("dummy.dcm", b"0")

    from bidscomatic.utils import logging as log_utils

    repo_root = Path(log_utils.__file__).resolve().parents[5]
    pkg_logs = Path(log_utils.__file__).resolve().parents[1] / "logs"
    log_file = pkg_logs / "bidscomatic.log"
    if log_file.exists():
        log_file.unlink()

    env = os.environ.copy()
    env["BIDS_ROOT"] = str(repo_root)

    subprocess.run(
        CLI + [str(archive)],
        capture_output=True,
        text=True,
        check=True,
        cwd=repo_root,
        env=env,
    )

    assert log_file.exists()
    log_file.unlink()
