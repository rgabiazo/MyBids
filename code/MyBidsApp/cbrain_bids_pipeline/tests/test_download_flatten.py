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


def test_flattened_download(monkeypatch, tmp_path):
    # Remote tree for one HippUnfold userfile
    tree = {
        "/uf/sub-001_ses-01_hippunfold": (["hippunfold", "logs", "work"], []),
        "/uf/sub-001_ses-01_hippunfold/hippunfold": (["anat"], []),
        "/uf/sub-001_ses-01_hippunfold/hippunfold/anat": ([], ["file.nii.gz"]),
        "/uf/sub-001_ses-01_hippunfold/logs": ([], ["run.log"]),
        "/uf/sub-001_ses-01_hippunfold/work": ([], ["work.txt"]),
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
        keep_dirs=["logs", "work"],
        wrapper="hippunfold",
    )

    assert (tmp_path / "sub-001" / "ses-01" / "anat" / "file.nii.gz").exists()
    assert (tmp_path / "logs" / "sub-001" / "ses-01" / "run.log").exists()
    assert (tmp_path / "work" / "sub-001" / "ses-01" / "work.txt").exists()
    assert not (tmp_path / "hippunfold").exists()


def test_flattened_download_keepdir_files(monkeypatch, tmp_path):
    """Files at the root of a keep-dir are copied even when subfolders exist."""

    tree = {
        "/uf/sub-001_ses-01_hippunfold": (["hippunfold", "work"], []),
        "/uf/sub-001_ses-01_hippunfold/hippunfold": (["anat"], []),
        "/uf/sub-001_ses-01_hippunfold/hippunfold/anat": ([], ["file.nii.gz"]),
        "/uf/sub-001_ses-01_hippunfold/work": (["sub-001"], ["root.txt"]),
        "/uf/sub-001_ses-01_hippunfold/work/sub-001": (["ses-01"], []),
        "/uf/sub-001_ses-01_hippunfold/work/sub-001/ses-01": ([], ["work.txt"]),
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
        keep_dirs=["work"],
        wrapper="hippunfold",
    )

    assert (tmp_path / "work" / "sub-001" / "ses-01" / "work.txt").exists()
    assert (tmp_path / "work" / "sub-001" / "ses-01" / "root.txt").exists()


def test_flattened_download_skip_overlaps(monkeypatch, tmp_path):
    """Keep-dirs also listed in skip-dirs should be ignored."""

    tree = {
        "/uf/sub-001_ses-01_hippunfold": (["hippunfold", "config", "logs"], []),
        "/uf/sub-001_ses-01_hippunfold/hippunfold": (["anat"], []),
        "/uf/sub-001_ses-01_hippunfold/hippunfold/anat": ([], ["file.nii.gz"]),
        "/uf/sub-001_ses-01_hippunfold/config": ([], ["settings.yml"]),
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
        skip_dirs=["config"],
        keep_dirs=["config", "logs"],
        wrapper="hippunfold",
    )

    assert (tmp_path / "logs" / "sub-001" / "ses-01" / "run.log").exists()
    assert not (tmp_path / "config").exists()
