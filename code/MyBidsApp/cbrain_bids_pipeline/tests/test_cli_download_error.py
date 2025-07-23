import logging
import sys
import types

import pytest


def ensure_token_stub(**_):
    return {"cbrain_api_token": "tok", "cbrain_base_url": "https://x"}


def _import_cli_with_stubs():
    stub = types.ModuleType('bids_cbrain_runner.api.client_openapi')
    stub.ApiException = Exception
    class CbrainClient: ...
    stub.CbrainClient = CbrainClient
    stub.CbrainTaskError = Exception
    sys.modules['bids_cbrain_runner.api.client_openapi'] = stub

    from bids_cbrain_runner import cli as cli_mod
    return cli_mod


def test_download_missing_dataset(monkeypatch, tmp_path, caplog):
    cli_mod = _import_cli_with_stubs()

    monkeypatch.setattr(
        cli_mod,
        "get_sftp_provider_config",
        lambda provider_name=None: {},
    )
    monkeypatch.setattr(cli_mod, "load_cbrain_config", lambda: {})
    monkeypatch.setattr(cli_mod, "load_tools_config", lambda: {})

    monkeypatch.setattr(cli_mod, "ensure_token", ensure_token_stub)

    def raise_fnf(**_):
        raise FileNotFoundError("dataset missing")

    monkeypatch.setattr(cli_mod, "download_tool_outputs", raise_fnf)

    monkeypatch.setattr(cli_mod, "resolve_group_id", lambda *a, **k: 1)

    argv = [
        "prog",
        "download",
        "--tool",
        "hippunfold",
        "--group",
        "1",
    ]
    monkeypatch.setattr(sys, "argv", argv)
    monkeypatch.chdir(str(tmp_path))

    caplog.set_level(logging.ERROR)
    with pytest.raises(SystemExit) as exc:
        cli_mod.main()
    assert exc.value.code == 1

    assert "dataset missing" in caplog.text


def test_download_http_error(monkeypatch, tmp_path, caplog):
    cli_mod = _import_cli_with_stubs()

    monkeypatch.setattr(
        cli_mod,
        "get_sftp_provider_config",
        lambda provider_name=None: {},
    )
    monkeypatch.setattr(cli_mod, "load_cbrain_config", lambda: {})
    monkeypatch.setattr(cli_mod, "load_tools_config", lambda: {})
    monkeypatch.setattr(cli_mod, "ensure_token", ensure_token_stub)

    def raise_rt(**_):
        raise RuntimeError("HTTP 404")

    monkeypatch.setattr(cli_mod, "download_tool_outputs", raise_rt)
    monkeypatch.setattr(cli_mod, "resolve_group_id", lambda *a, **k: 1)

    argv = [
        "prog",
        "download",
        "--tool",
        "hippunfold",
        "--group",
        "1",
    ]
    monkeypatch.setattr(sys, "argv", argv)
    monkeypatch.chdir(str(tmp_path))

    caplog.set_level(logging.ERROR)
    with pytest.raises(SystemExit) as exc:
        cli_mod.main()
    assert exc.value.code == 1
    assert "HTTP 404" in caplog.text


def test_download_request_exception(monkeypatch, tmp_path, caplog):
    cli_mod = _import_cli_with_stubs()

    monkeypatch.setattr(
        cli_mod,
        "get_sftp_provider_config",
        lambda provider_name=None: {},
    )
    monkeypatch.setattr(cli_mod, "load_cbrain_config", lambda: {})
    monkeypatch.setattr(cli_mod, "load_tools_config", lambda: {})
    monkeypatch.setattr(cli_mod, "ensure_token", ensure_token_stub)

    import bids_cbrain_runner.commands.download as download_mod

    class DummyExc(Exception):
        pass

    dummy_requests = types.SimpleNamespace(
        exceptions=types.SimpleNamespace(RequestException=DummyExc)
    )

    def raise_exc(*_a, **_kw):
        raise DummyExc("timeout")

    monkeypatch.setattr(download_mod, "requests", dummy_requests)
    monkeypatch.setattr(download_mod, "cbrain_get", raise_exc)

    argv = [
        "prog",
        "download",
        "--tool",
        "hippunfold",
        "--id",
        "1",
    ]
    monkeypatch.setattr(sys, "argv", argv)
    monkeypatch.chdir(str(tmp_path))

    caplog.set_level(logging.ERROR)
    with pytest.raises(SystemExit) as exc:
        cli_mod.main()
    assert exc.value.code == 1
    assert "timeout" in caplog.text
