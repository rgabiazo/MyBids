import sys
import types
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

    from bids_cbrain_runner import cli as cli_mod
    return cli_mod


def _common_patches(monkeypatch, cli_mod):
    monkeypatch.setattr(cli_mod, "get_sftp_provider_config", lambda provider_name=None: {})
    monkeypatch.setattr(cli_mod, "load_cbrain_config", lambda: {})
    monkeypatch.setattr(cli_mod, "load_tools_config", lambda: {})
    monkeypatch.setattr(cli_mod, "ensure_token", lambda **kw: {"cbrain_api_token": "tok", "cbrain_base_url": "https://x"})


def test_delete_userfile_dry_run(monkeypatch):
    cli_mod = _import_cli_with_stubs()
    _common_patches(monkeypatch, cli_mod)

    called = {}
    monkeypatch.setattr(
        cli_mod,
        "delete_userfile",
        lambda client, ufid, *, dry_run=False, timeout=None: called.setdefault("args", (ufid, dry_run))
    )

    argv = ["prog", "--delete-userfile", "42", "--dry-delete"]
    monkeypatch.setattr(sys, "argv", argv)

    cli_mod.main()

    assert called.get("args") == (42, True)


def test_delete_group_filetype_resolves(monkeypatch):
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
        "delete_userfiles_by_group_and_type",
        lambda client, gid, ftypes, *, per_page=25, dry_run=False, timeout=None: calls.append((gid, ftypes, dry_run))
    )

    argv = ["prog", "--delete-group", "Trial", "--delete-filetype", "mnc", "txt"]
    monkeypatch.setattr(sys, "argv", argv)

    cli_mod.main()

    assert resolved.get("value") == "Trial"
    assert calls and calls[0][:2] == (7, ["mnc", "txt"])
