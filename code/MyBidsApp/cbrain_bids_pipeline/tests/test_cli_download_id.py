import sys
import types

import pytest


def _import_cli_with_stubs():
    stub = types.ModuleType('bids_cbrain_runner.api.client_openapi')
    stub.ApiException = Exception
    class CbrainClient: ...
    stub.CbrainClient = CbrainClient
    stub.CbrainTaskError = Exception
    sys.modules['bids_cbrain_runner.api.client_openapi'] = stub

    from bids_cbrain_runner import cli as cli_mod
    return cli_mod


def _setup_common(monkeypatch):
    cli_mod = _import_cli_with_stubs()
    monkeypatch.setattr(cli_mod, "get_sftp_provider_config", lambda provider_name=None: {})
    monkeypatch.setattr(cli_mod, "load_cbrain_config", lambda: {})
    monkeypatch.setattr(cli_mod, "load_tools_config", lambda: {})
    monkeypatch.setattr(
        cli_mod,
        "ensure_token",
        lambda **kw: {"cbrain_api_token": "tok", "cbrain_base_url": "https://x"},
    )
    return cli_mod


def test_download_single_id(monkeypatch):
    cli_mod = _setup_common(monkeypatch)

    dl_calls = []
    monkeypatch.setattr(cli_mod, "download_tool_outputs", lambda **kw: dl_calls.append(kw))

    argv = ["prog", "download", "--tool", "hippunfold", "--id", "42"]
    monkeypatch.setattr(sys, "argv", argv)

    with pytest.raises(SystemExit):
        cli_mod.main()

    assert dl_calls
    assert dl_calls[0]["userfile_id"] == 42
    assert dl_calls[0]["group_id"] is None

