import logging
import sys
import types

import pytest


def _import_cli_with_stubs():
    stub = types.ModuleType('bids_cbrain_runner.api.client_openapi')
    stub.ApiException = Exception

    class CbrainTaskError(Exception):
        pass

    class CbrainClient:
        pass

    stub.CbrainTaskError = CbrainTaskError
    stub.CbrainClient = CbrainClient
    sys.modules['bids_cbrain_runner.api.client_openapi'] = stub

    from bids_cbrain_runner import cli as cli_mod
    return cli_mod


def test_cli_handles_launch_tool_error(monkeypatch, tmp_path, caplog):
    cli_mod = _import_cli_with_stubs()

    monkeypatch.setattr(
        cli_mod, "get_sftp_provider_config", lambda provider_name=None: {}
    )
    monkeypatch.setattr(cli_mod, "load_cbrain_config", lambda: {})
    monkeypatch.setattr(cli_mod, "load_tools_config", lambda: {})
    monkeypatch.setattr(cli_mod, "ensure_token", lambda **_: {"cbrain_api_token": "tok", "cbrain_base_url": "https://x"})
    monkeypatch.setattr(cli_mod, "resolve_group_id", lambda *a, **k: 1)

    def raise_error(*a, **k):
        raise cli_mod.CbrainTaskError("Execution server offline")

    monkeypatch.setattr(cli_mod, "launch_tool", raise_error)

    argv = [
        "prog",
        "--launch-tool",
        "dummy",
        "--launch-tool-group-id",
        "1",
    ]
    monkeypatch.setattr(sys, "argv", argv)
    monkeypatch.chdir(str(tmp_path))

    caplog.set_level(logging.ERROR)
    with pytest.raises(SystemExit) as exc:
        cli_mod.main()
    assert exc.value.code == 1
    assert "Execution server offline" in caplog.text
