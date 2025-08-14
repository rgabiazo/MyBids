import os
import json
from bids_cbrain_runner.commands.upload import ensure_remote_dir_structure
from bids_cbrain_runner.utils import paths as paths_mod

class DummySFTP:
    def __init__(self):
        self.existing = set(['/'])
        self.mkdir_calls = []
        self.cwd = '/'
    def chdir(self, path):
        self.cwd = path
    def getcwd(self):
        return self.cwd
    def stat(self, path):
        if path not in self.existing:
            raise FileNotFoundError()
    def mkdir(self, path):
        self.existing.add(path)
        self.mkdir_calls.append(path)

def test_no_derivatives_dir_for_single_file(monkeypatch, tmp_path):
    ds = tmp_path / "dataset"
    ds.mkdir()
    (ds / "dataset_description.json").write_text("{}")
    lic = ds / "derivatives" / "license.txt"
    lic.parent.mkdir()
    lic.write_text("MIT")

    monkeypatch.chdir(ds)
    monkeypatch.setattr(paths_mod, "load_pipeline_config", lambda: {"derivatives_root": "derivatives"})

    sftp = DummySFTP()
    created = ensure_remote_dir_structure(sftp, ("derivatives", "license.txt"))

    assert not created
    assert sftp.mkdir_calls == []

def test_nested_dirs_created(monkeypatch, tmp_path):
    ds = tmp_path / "dataset"
    ds.mkdir()
    (ds / "dataset_description.json").write_text("{}")
    subdir = ds / "sub-01" / "ses-01" / "anat"
    subdir.mkdir(parents=True)
    fpath = subdir / "file.nii.gz"
    fpath.write_text("dummy")

    monkeypatch.chdir(ds)
    monkeypatch.setattr(paths_mod, "load_pipeline_config", lambda: {"derivatives_root": "derivatives"})

    sftp = DummySFTP()
    created = ensure_remote_dir_structure(sftp, ("sub-01", "ses-01", "anat"))

    assert created
    assert sftp.mkdir_calls == ["/sub-01", "/sub-01/ses-01", "/sub-01/ses-01/anat"]

def test_custom_derivatives_root(monkeypatch, tmp_path):
    ds = tmp_path / "dataset"
    ds.mkdir()
    (ds / "dataset_description.json").write_text("{}")
    lic = ds / "derivatives" / "license.txt"
    lic.parent.mkdir()
    lic.write_text("MIT")

    monkeypatch.chdir(ds)
    monkeypatch.setattr(paths_mod, "load_pipeline_config", lambda: {"roots": {"derivatives_root": "outputs"}})

    sftp = DummySFTP()
    created = ensure_remote_dir_structure(sftp, ("derivatives", "license.txt"))

    assert created
    assert sftp.mkdir_calls == ["/derivatives"]


def test_derivatives_directory_structure(monkeypatch, tmp_path):
    ds = tmp_path / "dataset"
    ds.mkdir()
    (ds / "dataset_description.json").write_text("{}")
    ddir = ds / "derivatives" / "fsl" / "lvl1"
    ddir.mkdir(parents=True)

    monkeypatch.chdir(ds)
    monkeypatch.setattr(paths_mod, "load_pipeline_config", lambda: {"derivatives_root": "derivatives"})

    sftp = DummySFTP()
    created = ensure_remote_dir_structure(sftp, ("derivatives", "fsl", "lvl1"))

    assert created
    assert sftp.mkdir_calls == ["/fsl", "/fsl/lvl1"]


def test_nested_derivatives_root_file(monkeypatch, tmp_path):
    ds = tmp_path / "dataset"
    ds.mkdir()
    (ds / "dataset_description.json").write_text("{}")
    lic = (
        ds
        / "derivatives"
        / "fsl"
        / "level-1"
        / "preprocessing_preICA"
        / "license.txt"
    )
    lic.parent.mkdir(parents=True)
    lic.write_text("MIT")

    monkeypatch.chdir(ds)
    monkeypatch.setattr(
        paths_mod,
        "load_pipeline_config",
        lambda: {"derivatives_root": "derivatives/fsl/level-1/preprocessing_preICA"},
    )

    sftp = DummySFTP()
    created = ensure_remote_dir_structure(
        sftp,
        (
            "derivatives",
            "fsl",
            "level-1",
            "preprocessing_preICA",
            "license.txt",
        ),
    )

    assert not created
    assert sftp.mkdir_calls == []


def test_nested_derivatives_root_dir(monkeypatch, tmp_path):
    ds = tmp_path / "dataset"
    ds.mkdir()
    (ds / "dataset_description.json").write_text("{}")
    ddir = (
        ds
        / "derivatives"
        / "fsl"
        / "level-1"
        / "preprocessing_preICA"
        / "task"
    )
    ddir.mkdir(parents=True)

    monkeypatch.chdir(ds)
    monkeypatch.setattr(
        paths_mod,
        "load_pipeline_config",
        lambda: {"derivatives_root": "derivatives/fsl/level-1/preprocessing_preICA"},
    )

    sftp = DummySFTP()
    created = ensure_remote_dir_structure(
        sftp,
        (
            "derivatives",
            "fsl",
            "level-1",
            "preprocessing_preICA",
            "task",
        ),
    )

    assert created
    assert sftp.mkdir_calls == ["/task"]

