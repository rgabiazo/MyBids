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
    monkeypatch.setattr(cli_mod, "resolve_group_id", lambda *a, **k: 1)
    return cli_mod


def test_download_spinner(monkeypatch):
    cli_mod = _setup_common(monkeypatch)

    calls = []
    monkeypatch.setattr(cli_mod, "download_tool_outputs", lambda **kw: calls.append(kw["show_spinner"]))

    argv = ["prog", "download", "--tool", "hippunfold", "--group", "1"]
    monkeypatch.setattr(sys, "argv", argv)

    with pytest.raises(SystemExit):
        cli_mod.main()

    assert calls == [True]


def test_download_spinner_debug(monkeypatch):
    cli_mod = _setup_common(monkeypatch)

    calls = []
    monkeypatch.setattr(cli_mod, "download_tool_outputs", lambda **kw: calls.append(kw["show_spinner"]))

    argv = ["prog", "--debug-logs", "download", "--tool", "hippunfold", "--group", "1"]
    monkeypatch.setattr(sys, "argv", argv)

    with pytest.raises(SystemExit):
        cli_mod.main()

    assert calls == [False]
