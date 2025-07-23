import os
import json

import pytest

from bids_cbrain_runner.commands import upload as upload_mod


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

