import sys
import types
import pytest


def _import_cli_with_stubs():
    stub = types.ModuleType("bids_cbrain_runner.api.client_openapi")
    stub.ApiException = Exception

    class CbrainClient: ...

    stub.CbrainClient = CbrainClient
    stub.CbrainTaskError = Exception
    sys.modules["bids_cbrain_runner.api.client_openapi"] = stub

    from bids_cbrain_runner import cli as cli_mod

    return cli_mod


def _common_patches(monkeypatch, cli_mod):
    monkeypatch.setattr(
        cli_mod, "get_sftp_provider_config", lambda provider_name=None: {}
    )
    monkeypatch.setattr(cli_mod, "load_cbrain_config", lambda: {})
    monkeypatch.setattr(cli_mod, "load_tools_config", lambda: {})
    monkeypatch.setattr(
        cli_mod,
        "ensure_token",
        lambda **kw: {"cbrain_api_token": "tok", "cbrain_base_url": "https://x"},
    )
    monkeypatch.setattr(cli_mod, "resolve_group_id", lambda *a, **k: 1)


def test_alias_after_download_subcommand(monkeypatch):
    cli_mod = _import_cli_with_stubs()
    _common_patches(monkeypatch, cli_mod)

    alias_specs = []
    monkeypatch.setattr(
        cli_mod,
        "run_aliases",
        lambda specs, dry_run=False: alias_specs.append(specs),
    )
    monkeypatch.setattr(cli_mod, "download_tool_outputs", lambda **kw: None)

    argv = [
        "prog",
        "download",
        "--tool",
        "deepprep",
        "--group",
        "grp",
        "--alias",
        "derivatives",
        "DeepPrep",
        "BOLD",
        "sub-*",
        "ses-*",
        "func",
        "6cat=assocmemory",
    ]
    monkeypatch.setattr(sys, "argv", argv)
    with pytest.raises(SystemExit):
        cli_mod.main()

    assert alias_specs
    spec = alias_specs[0][0]
    # Wildcard components like 'sub-*', 'ses-*' and 'func' are ignored when
    # determining the base directory for aliasing.
    assert spec.steps == ["derivatives", "DeepPrep", "BOLD"]
    assert spec.old == "6cat"
    assert spec.new == "assocmemory"


def test_alias_after_download_dry_run(monkeypatch):
    cli_mod = _import_cli_with_stubs()
    _common_patches(monkeypatch, cli_mod)

    called = {}

    def fake_run_aliases(specs, dry_run=False):
        called["dry_run"] = dry_run

    monkeypatch.setattr(cli_mod, "run_aliases", fake_run_aliases)
    monkeypatch.setattr(cli_mod, "download_tool_outputs", lambda **kw: None)

    argv = [
        "prog",
        "download",
        "--tool",
        "deepprep",
        "--group",
        "grp",
        "--alias",
        "derivatives",
        "DeepPrep",
        "BOLD",
        "sub-*",
        "ses-*",
        "func",
        "6cat=assocmemory",
        "--dry-run",
    ]
    monkeypatch.setattr(sys, "argv", argv)
    with pytest.raises(SystemExit):
        cli_mod.main()

    assert called.get("dry_run") is True

