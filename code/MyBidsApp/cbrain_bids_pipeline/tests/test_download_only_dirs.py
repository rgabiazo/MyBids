import sys
import types
from pathlib import Path

import pytest

from bids_cbrain_runner.utils import download_utils


class DummySFTP:
    """Minimal stub mimicking Paramiko's SFTPClient."""

    def __init__(self):
        self.get_calls = []

    def get(self, src, dst):
        self.get_calls.append((src, dst))
        Path(dst).parent.mkdir(parents=True, exist_ok=True)
        Path(dst).write_text("placeholder")


def test_naive_download_include_dirs(monkeypatch, tmp_path):
    tree = {
        "/remote/data": (["keep", "skip"], ["root.txt"]),
        "/remote/data/keep": ([], ["keep1.txt"]),
        "/remote/data/skip": ([], ["skip1.txt"]),
    }

    def fake_listdirs(_, path):
        return tree.get(path, ([], []))

    monkeypatch.setattr(download_utils, "list_subdirs_and_files", fake_listdirs)

    sftp = DummySFTP()
    download_utils.naive_download(
        sftp=sftp,
        remote_dir="/remote/data",
        local_root=str(tmp_path),
        include_dirs=["keep"],
    )

    assert (tmp_path / "data" / "keep" / "keep1.txt").exists()
    assert not (tmp_path / "data" / "skip").exists()
    assert not (tmp_path / "data" / "root.txt").exists()


def test_flattened_download_include_dirs(monkeypatch, tmp_path):
    tree = {
        "/uf/sub-001_ses-01_hippunfold": (["hippunfold", "logs"], []),
        "/uf/sub-001_ses-01_hippunfold/hippunfold": (["anat"], []),
        "/uf/sub-001_ses-01_hippunfold/hippunfold/anat": ([], ["file.nii.gz"]),
        "/uf/sub-001_ses-01_hippunfold/logs": ([], ["run.log"]),
    }

    def fake_listdirs(_, path):
        return tree.get(path, ([], []))

    monkeypatch.setattr(download_utils, "list_subdirs_and_files", fake_listdirs)

    sftp = DummySFTP()
    download_utils.flattened_download(
        sftp=sftp,
        remote_dir="/uf/sub-001_ses-01_hippunfold",
        local_root=str(tmp_path),
        tool_name="hippunfold",
        keep_dirs=["logs"],
        wrapper="hippunfold",
        include_dirs=["hippunfold/anat"],
    )

    assert (tmp_path / "sub-001" / "ses-01" / "anat" / "file.nii.gz").exists()
    assert not (tmp_path / "logs").exists()
