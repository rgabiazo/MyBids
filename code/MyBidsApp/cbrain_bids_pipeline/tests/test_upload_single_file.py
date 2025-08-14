import os
import json
import yaml

import pytest

from bids_cbrain_runner.commands import upload as upload_mod
from bids_cbrain_runner.utils import paths as paths_mod


class DummySFTPClient:
    def __init__(self):
        self.cwd = "/"
        self.put_calls = []

    def getcwd(self):
        return self.cwd

    def chdir(self, path):
        self.cwd = path

    def stat(self, path):
        raise FileNotFoundError()

    def mkdir(self, path):
        pass

    def listdir(self, path):
        return []

    def put(self, lpath, rpath):
        self.put_calls.append((lpath, rpath))

    def close(self):
        pass


class DummySSHClient:
    def close(self):
        pass


def test_upload_single_file(monkeypatch, tmp_path):
    bids_root = tmp_path / "dataset"
    bids_root.mkdir()
    dd_path = bids_root / "dataset_description.json"
    dd_path.write_text(json.dumps({"Name": "Test"}))

    monkeypatch.chdir(bids_root)

    monkeypatch.setattr(upload_mod, "load_pipeline_config", lambda: {"derivatives_root": "derivatives"})
    monkeypatch.setattr(paths_mod, "load_pipeline_config", lambda: {"derivatives_root": "derivatives"})

    monkeypatch.setattr(upload_mod, "load_pipeline_config", lambda: {"derivatives_root": "derivatives"})
    monkeypatch.setattr(paths_mod, "load_pipeline_config", lambda: {"derivatives_root": "derivatives"})

    monkeypatch.setattr(upload_mod, "bids_validator_cli", lambda steps: True)

    dummy_sftp = DummySFTPClient()
    dummy_ssh = DummySSHClient()
    monkeypatch.setattr(upload_mod, "sftp_connect_from_config", lambda cfg: (dummy_ssh, dummy_sftp))

    upload_mod.upload_bids_and_sftp_files({}, "", "", ["dataset_description.json"])

    assert dummy_sftp.put_calls == [(str(dd_path), "/dataset_description.json")]


def test_ds_store_ignored(monkeypatch, tmp_path):
    """Finder metadata files should not be uploaded."""
    bids_root = tmp_path / "dataset"
    bids_root.mkdir()
    dd_path = bids_root / "dataset_description.json"
    dd_path.write_text("{}")
    # Create a macOS Finder file that must be ignored
    ds_store_path = bids_root / ".DS_Store"
    ds_store_path.write_text("junk")

    monkeypatch.chdir(bids_root)

    monkeypatch.setattr(upload_mod, "bids_validator_cli", lambda steps: True)

    dummy_sftp = DummySFTPClient()
    dummy_ssh = DummySSHClient()
    monkeypatch.setattr(upload_mod, "sftp_connect_from_config", lambda cfg: (dummy_ssh, dummy_sftp))

    # '*' would normally include .DS_Store but it should be filtered out
    upload_mod.upload_bids_and_sftp_files({}, "", "", ["*"])

    assert dummy_sftp.put_calls == [(str(dd_path), "/dataset_description.json")]


def test_upload_file_in_subdir(monkeypatch, tmp_path):
    bids_root = tmp_path / "dataset"
    bids_root.mkdir()
    (bids_root / "dataset_description.json").write_text("{}")
    lic_path = bids_root / "derivatives" / "license.txt"
    lic_path.parent.mkdir(parents=True)
    lic_path.write_text("MIT")

    monkeypatch.chdir(bids_root)
    monkeypatch.setattr(upload_mod, "load_pipeline_config", lambda: {"derivatives_root": "derivatives"})
    monkeypatch.setattr(paths_mod, "load_pipeline_config", lambda: {"derivatives_root": "derivatives"})
    monkeypatch.setattr(upload_mod, "bids_validator_cli", lambda steps: True)

    dummy_sftp = DummySFTPClient()
    dummy_ssh = DummySSHClient()
    monkeypatch.setattr(upload_mod, "sftp_connect_from_config", lambda cfg: (dummy_ssh, dummy_sftp))

    reg_calls = []
    monkeypatch.setattr(upload_mod, "register_files_on_provider", lambda **kw: reg_calls.append(kw))

    upload_mod.upload_bids_and_sftp_files(
        {},
        "https://x",
        "tok",
        ["derivatives", "license.txt"],
        do_register=True,
        dp_id=1,
    )

    assert dummy_sftp.put_calls == [(str(lic_path), "/license.txt")]
    assert reg_calls and reg_calls[0]["basenames"] == ["derivatives/license.txt"]


def test_upload_summary_file_in_subdir(monkeypatch, tmp_path):
    bids_root = tmp_path / "dataset"
    bids_root.mkdir()
    (bids_root / "dataset_description.json").write_text("{}")
    lic_path = bids_root / "derivatives" / "license.txt"
    lic_path.parent.mkdir(parents=True)
    lic_path.write_text("MIT")

    monkeypatch.chdir(bids_root)
    monkeypatch.setattr(upload_mod, "load_pipeline_config", lambda: {"derivatives_root": "derivatives"})
    monkeypatch.setattr(paths_mod, "load_pipeline_config", lambda: {"derivatives_root": "derivatives"})
    monkeypatch.setattr(upload_mod, "bids_validator_cli", lambda steps: True)

    dummy_sftp = DummySFTPClient()
    dummy_ssh = DummySSHClient()
    monkeypatch.setattr(upload_mod, "sftp_connect_from_config", lambda cfg: (dummy_ssh, dummy_sftp))
    monkeypatch.setattr(upload_mod, "list_subdirs_and_files", lambda c, p: ([], []))
    monkeypatch.setattr(
        upload_mod,
        "ensure_remote_dir_structure",
        lambda c, p, cfg=None, base_dir=None: False,
    )

    captured = []
    monkeypatch.setattr(upload_mod, "print_jsonlike_dict", lambda d, title=None: captured.append(d))

    upload_mod.upload_bids_and_sftp_files({}, "https://x", "tok", ["derivatives", "license.txt"])

    assert captured and captured[0] == {"license.txt": ["derivatives/license.txt"]}


def test_custom_derivatives_root(monkeypatch, tmp_path):
    """Changing derivatives_root should alter upload destination."""
    bids_root = tmp_path / "dataset"
    bids_root.mkdir()
    (bids_root / "dataset_description.json").write_text("{}")
    lic_path = bids_root / "derivatives" / "license.txt"
    lic_path.parent.mkdir(parents=True)
    lic_path.write_text("MIT")

    pkg_root = tmp_path / "fakepkg"
    cfg_dir = pkg_root / "bids_cbrain_runner" / "api" / "config"
    cfg_dir.mkdir(parents=True)
    custom_yaml = cfg_dir / "defaults.yaml"
    with open(custom_yaml, "w", encoding="utf-8") as f:
        yaml.safe_dump({"derivatives_root": "outputs"}, f)

    def _load() -> dict:
        with open(custom_yaml, "r", encoding="utf-8") as fh:
            return yaml.safe_load(fh) or {}

    monkeypatch.chdir(bids_root)
    monkeypatch.setattr(upload_mod, "load_pipeline_config", _load)
    monkeypatch.setattr(paths_mod, "load_pipeline_config", _load)
    monkeypatch.setattr(upload_mod, "bids_validator_cli", lambda steps: True)

    dummy_sftp = DummySFTPClient()
    dummy_ssh = DummySSHClient()
    monkeypatch.setattr(upload_mod, "sftp_connect_from_config", lambda cfg: (dummy_ssh, dummy_sftp))

    upload_mod.upload_bids_and_sftp_files({}, "", "", ["derivatives", "license.txt"])

    assert dummy_sftp.put_calls == [(str(lic_path), "/derivatives/license.txt")]


def test_dry_run_skips_transfer(monkeypatch, tmp_path):
    bids_root = tmp_path / "dataset"
    bids_root.mkdir()
    (bids_root / "dataset_description.json").write_text("{}")
    lic_path = bids_root / "derivatives" / "license.txt"
    lic_path.parent.mkdir(parents=True)
    lic_path.write_text("MIT")

    monkeypatch.chdir(bids_root)
    monkeypatch.setattr(upload_mod, "bids_validator_cli", lambda steps: True)

    dummy_sftp = DummySFTPClient()
    dummy_ssh = DummySSHClient()
    monkeypatch.setattr(upload_mod, "sftp_connect_from_config", lambda cfg: (dummy_ssh, dummy_sftp))

    upload_mod.upload_bids_and_sftp_files({}, "", "", ["derivatives", "license.txt"], dry_run=True)

    assert dummy_sftp.put_calls == []


def test_recursive_fallback(monkeypatch, tmp_path):
    """Upload should recurse when final directory has subfolders."""
    bids_root = tmp_path / "dataset"
    bids_root.mkdir()
    (bids_root / "dataset_description.json").write_text("{}")
    feat_dir = bids_root / "sub-01" / "ses-01" / "func" / "task.feat"
    feat_dir.mkdir(parents=True)
    fpath = feat_dir / "file.txt"
    fpath.write_text("dummy")

    monkeypatch.chdir(bids_root)
    monkeypatch.setattr(upload_mod, "bids_validator_cli", lambda steps: True)

    dummy_sftp = DummySFTPClient()
    dummy_ssh = DummySSHClient()
    monkeypatch.setattr(upload_mod, "sftp_connect_from_config", lambda cfg: (dummy_ssh, dummy_sftp))
    monkeypatch.setattr(upload_mod, "list_subdirs_and_files", lambda c, p: ([], []))
    monkeypatch.setattr(
        upload_mod,
        "ensure_remote_dir_structure",
        lambda c, p, cfg=None, base_dir=None: False,
    )

    upload_mod.upload_bids_and_sftp_files({}, "", "", ["sub-*", "ses-*", "func"])

    assert dummy_sftp.put_calls == [(str(fpath), "/sub-01/ses-01/func/task.feat/file.txt")]


def test_missing_pattern_skips_connection(monkeypatch, tmp_path):
    """No SFTP connection should be made when nothing matches."""
    bids_root = tmp_path / "dataset"
    bids_root.mkdir()
    (bids_root / "dataset_description.json").write_text("{}")

    monkeypatch.chdir(bids_root)
    monkeypatch.setattr(upload_mod, "bids_validator_cli", lambda steps: True)

    conn_called = False

    def fake_connect(cfg):
        nonlocal conn_called
        conn_called = True
        return DummySSHClient(), DummySFTPClient()

    monkeypatch.setattr(upload_mod, "sftp_connect_from_config", fake_connect)

    upload_mod.upload_bids_and_sftp_files({}, "", "", ["nope.txt"])

    assert not conn_called

