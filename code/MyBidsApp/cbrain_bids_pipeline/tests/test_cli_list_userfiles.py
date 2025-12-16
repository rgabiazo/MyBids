import sys
import types

import sys
import types
import importlib
import pytest


def _import_cli_with_stubs():
    stub = types.ModuleType('bids_cbrain_runner.api.client_openapi')
    stub.ApiException = Exception
    class CbrainClient:
        def __init__(self, *a, **k):
            pass
    stub.CbrainClient = CbrainClient
    stub.CbrainTaskError = Exception
    sys.modules['bids_cbrain_runner.api.client_openapi'] = stub

    # Force a fresh import so the stubbed module is used even if the CLI was
    # previously imported by another test.
    sys.modules.pop('bids_cbrain_runner.cli', None)
    cli_mod = importlib.import_module('bids_cbrain_runner.cli')
    return cli_mod


def _common_patches(monkeypatch, cli_mod):
    monkeypatch.setattr(cli_mod, "get_sftp_provider_config", lambda provider_name=None: {})
    monkeypatch.setattr(cli_mod, "load_cbrain_config", lambda: {})
    monkeypatch.setattr(cli_mod, "load_tools_config", lambda: {})
    monkeypatch.setattr(cli_mod, "ensure_token", lambda **kw: {"cbrain_api_token": "tok", "cbrain_base_url": "https://x"})


def test_list_userfiles_group_name(monkeypatch):
    cli_mod = _import_cli_with_stubs()
    _common_patches(monkeypatch, cli_mod)

    resolved = {}
    monkeypatch.setattr(
        cli_mod,
        "resolve_group_id",
        lambda base_url, token, ident, per_page=100, timeout=None: (
            resolved.setdefault("value", ident),
            7,
        )[1],
    )

    calls = []
    monkeypatch.setattr(
        cli_mod,
        "list_userfiles_by_group",
        lambda client, gid, per_page=25, timeout=None: calls.append(gid) or [],
    )

    spinner_calls = []
    monkeypatch.setattr(
        cli_mod,
        "run_with_spinner",
        lambda func, msg, show=True: spinner_calls.append(show) or func(),
    )

    argv = ["prog", "--list-userfiles-group", "Trial"]
    monkeypatch.setattr(sys, "argv", argv)

    cli_mod.main()

    assert resolved["value"] == "Trial"
    assert calls and calls[0] == 7
    assert spinner_calls == [True]


def test_group_and_provider_name(monkeypatch):
    cli_mod = _import_cli_with_stubs()
    _common_patches(monkeypatch, cli_mod)

    monkeypatch.setattr(cli_mod, "resolve_group_id", lambda *a, **k: 7)

    calls = []
    monkeypatch.setattr(
        cli_mod,
        "list_userfiles_by_group_and_provider",
        lambda client, gid, pid, per_page=25, timeout=None: calls.append((gid, pid)) or [],
    )

    spinner_calls = []
    monkeypatch.setattr(
        cli_mod,
        "run_with_spinner",
        lambda func, msg, show=True: spinner_calls.append(show) or func(),
    )

    argv = ["prog", "--group-and-provider", "Trial", "4", "--debug-logs"]
    monkeypatch.setattr(sys, "argv", argv)

    cli_mod.main()

    assert calls and calls[0] == (7, 4)
    assert spinner_calls == [False]

