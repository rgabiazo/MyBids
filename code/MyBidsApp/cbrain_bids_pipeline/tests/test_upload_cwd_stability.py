"""Regression tests for upload path computations.

The SFTP helper :func:`ensure_remote_dir_structure` changes the remote
working directory as a side effect.  Historically, subsequent calls to
``build_remote_path`` relied on :meth:`SFTPClient.getcwd`, which produced
incorrect nested paths after the first iteration.  This module verifies
that ``upload_bids_and_sftp_files`` now preserves the initial remote root
for all uploads.
"""

from __future__ import annotations

import json

from bids_cbrain_runner.commands import upload as upload_mod
from bids_cbrain_runner.utils import paths as paths_mod


class DummySFTPClient:
    """Minimal stand-in for :class:`paramiko.SFTPClient`.

    The client tracks its current working directory but does not touch any
    real network resources.  ``chdir`` simply updates ``cwd``.
    """

    def __init__(self) -> None:  # pragma: no cover - trivial
        self.cwd = "/"
        self.put_calls: list[tuple[str, str]] = []

    def getcwd(self) -> str:  # pragma: no cover - trivial
        return self.cwd

    def chdir(self, path: str) -> None:  # pragma: no cover - trivial
        self.cwd = path

    def stat(self, path: str):  # pragma: no cover - always missing
        raise FileNotFoundError()

    def mkdir(self, path: str) -> None:  # pragma: no cover - no-op
        pass

    def listdir(self, path: str) -> list[str]:  # pragma: no cover - no files
        return []

    def put(self, lpath: str, rpath: str) -> None:  # pragma: no cover - record
        self.put_calls.append((lpath, rpath))

    def close(self) -> None:  # pragma: no cover - no-op
        pass


class DummySSHClient:
    def close(self) -> None:  # pragma: no cover - no-op
        pass


def test_remote_root_unchanged_by_cwd(monkeypatch, tmp_path):
    """Uploading multiple sub-directories should not nest remote paths."""

    bids_root = tmp_path / "ds"
    bids_root.mkdir()
    (bids_root / "dataset_description.json").write_text(json.dumps({"Name": "X"}))

    anat_file = bids_root / "sub-01" / "ses-01" / "anat" / "sub-01_ses-01_T1w.nii.gz"
    fmap_file = bids_root / "sub-01" / "ses-01" / "fmap" / "sub-01_ses-01_epi.nii.gz"
    fmap_file.parent.mkdir(parents=True)
    anat_file.parent.mkdir(parents=True)
    anat_file.write_text("anat")
    fmap_file.write_text("fmap")

    monkeypatch.chdir(bids_root)

    dummy_sftp = DummySFTPClient()
    dummy_ssh = DummySSHClient()

    # Patch configuration and network helpers.
    monkeypatch.setattr(paths_mod, "load_pipeline_config", lambda: {"derivatives_root": "derivatives"})
    monkeypatch.setattr(upload_mod, "load_pipeline_config", lambda: {"derivatives_root": "derivatives"})
    monkeypatch.setattr(upload_mod, "bids_validator_cli", lambda steps: True)
    monkeypatch.setattr(upload_mod, "sftp_connect_from_config", lambda cfg: (dummy_ssh, dummy_sftp))

    # Simulate directory creation changing the SFTP CWD.
    def fake_ensure(sftp_client, path_tuple, cfg=None, base_dir=None):
        remote_dir = upload_mod.build_remote_path(path_tuple, False, base_dir or "/", cfg=cfg)
        sftp_client.chdir(remote_dir)
        return True

    monkeypatch.setattr(upload_mod, "ensure_remote_dir_structure", fake_ensure)
    monkeypatch.setattr(upload_mod, "list_subdirs_and_files", lambda c, p: ([], []))

    upload_mod.upload_bids_and_sftp_files({}, "", "", ["sub-01"])

    assert dummy_sftp.put_calls == [
        (str(anat_file), "/sub-01/ses-01/anat/sub-01_ses-01_T1w.nii.gz"),
        (str(fmap_file), "/sub-01/ses-01/fmap/sub-01_ses-01_epi.nii.gz"),
    ]

