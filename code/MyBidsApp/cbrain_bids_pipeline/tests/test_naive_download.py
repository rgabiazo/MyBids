from pathlib import Path

from bids_cbrain_runner.utils import download_utils


class DummySFTP:
    """Minimal stub mimicking Paramiko's SFTPClient."""

    def __init__(self):
        self.get_calls = []

    def get(self, src, dst):
        self.get_calls.append((src, dst))
        Path(dst).parent.mkdir(parents=True, exist_ok=True)
        Path(dst).write_text("placeholder")


def test_naive_download(monkeypatch, tmp_path):
    tree = {
        "/remote/data": (["keep", "skip_me"], ["root.txt"]),
        "/remote/data/keep": ([], ["keep1.txt"]),
        "/remote/data/skip_me": ([], ["ignored.txt"]),
    }

    def fake_listdirs(_, path):
        return tree.get(path, ([], []))

    monkeypatch.setattr(download_utils, "list_subdirs_and_files", fake_listdirs)

    sftp = DummySFTP()
    download_utils.naive_download(
        sftp=sftp,
        remote_dir="/remote/data",
        local_root=str(tmp_path),
        skip_dirs=["skip_me"],
    )

    assert (tmp_path / "data" / "root.txt").exists()
    assert (tmp_path / "data" / "keep" / "keep1.txt").exists()
    assert not (tmp_path / "data" / "skip_me").exists()

    expected = [
        ("/remote/data/root.txt", str(tmp_path / "data" / "root.txt")),
        (
            "/remote/data/keep/keep1.txt",
            str(tmp_path / "data" / "keep" / "keep1.txt"),
        ),
    ]
    assert sftp.get_calls == expected


def test_naive_download_skip_files(monkeypatch, tmp_path):
    tree = {
        "/remote/data": ([], ["keep.txt", "ignore.txt"]),
    }

    def fake_listdirs(_, path):
        return tree.get(path, ([], []))

    monkeypatch.setattr(download_utils, "list_subdirs_and_files", fake_listdirs)

    sftp = DummySFTP()
    download_utils.naive_download(
        sftp=sftp,
        remote_dir="/remote/data",
        local_root=str(tmp_path),
        skip_files=["ignore.txt"],
    )

    assert (tmp_path / "data" / "keep.txt").exists()
    assert not (tmp_path / "data" / "ignore.txt").exists()
    assert sftp.get_calls == [
        ("/remote/data/keep.txt", str(tmp_path / "data" / "keep.txt"))
    ]
