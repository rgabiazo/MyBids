import os

import pytest

from bids_cbrain_runner.commands import download as download_mod


def test_download_tool_outputs_wrapper(tmp_path, monkeypatch):
    (tmp_path / "dataset_description.json").write_text("{}")
    monkeypatch.chdir(tmp_path)

    monkeypatch.setattr(download_mod, "load_pipeline_config", lambda: {})
    monkeypatch.setattr(download_mod, "load_tools_config", lambda: {"deepprep": {}})

    class Dummy:
        def close(self):
            pass

    monkeypatch.setattr(download_mod, "sftp_connect_from_config", lambda cfg: (Dummy(), Dummy()))
    monkeypatch.setattr(download_mod, "CbrainClient", lambda base_url, token: object())
    monkeypatch.setattr(
        download_mod,
        "list_userfiles_by_group",
        lambda client, group_id, per_page=500, timeout=None: [{"id": 1, "name": "sub-001", "type": "FileCollection"}],
    )
    monkeypatch.setattr(download_mod, "run_with_spinner", lambda func, msg, show=True: func())
    monkeypatch.setattr(download_mod, "maybe_write_dataset_description", lambda **kw: None)

    calls = {}

    def fake_flattened_download(**kw):
        calls.update(kw)

    monkeypatch.setattr(download_mod, "flattened_download", fake_flattened_download)

    download_mod.download_tool_outputs(
        base_url="x",
        token="t",
        cfg={},
        tool_name="deepprep",
        output_type="FileCollection",
        group_id=1,
    )

    assert calls["wrapper"] == "FileCollection"
    assert calls["local_root"].endswith(os.path.join("derivatives", "FileCollection"))
