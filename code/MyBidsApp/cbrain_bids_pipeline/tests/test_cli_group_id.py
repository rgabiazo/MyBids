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
    monkeypatch.setattr(cli_mod, "ensure_token", lambda **kw: {"cbrain_api_token": "tok", "cbrain_base_url": "https://x"})
    return cli_mod


def test_cli_launch_tool_group_name(monkeypatch):
    cli_mod = _setup_common(monkeypatch)

    monkeypatch.setattr(
        cli_mod,
        "resolve_group_id",
        lambda base_url, token, ident, per_page=100, timeout=None: 42,
    )

    launch_calls = []
    monkeypatch.setattr(cli_mod, "launch_tool", lambda **kw: launch_calls.append(kw))

    argv = [
        "prog",
        "--launch-tool",
        "hippunfold",
        "--group-id",
        "MyProj",
    ]
    monkeypatch.setattr(sys, "argv", argv)
    with pytest.raises(SystemExit):
        cli_mod.main()

    assert launch_calls and launch_calls[0]["group_id"] == 42


def test_cli_download_group_name(monkeypatch, tmp_path):
    cli_mod = _setup_common(monkeypatch)

    monkeypatch.setattr(
        cli_mod,
        "resolve_group_id",
        lambda base_url, token, ident, per_page=100, timeout=None: 13,
    )

    dl_calls = []
    monkeypatch.setattr(cli_mod, "download_tool_outputs", lambda **kw: dl_calls.append(kw))

    argv = [
        "prog",
        "download",
        "--tool",
        "hippunfold",
        "--group",
        "MyProj",
        "--config",
        str(tmp_path / "cfg.yaml"),
    ]
    monkeypatch.setattr(sys, "argv", argv)
    with pytest.raises(SystemExit):
        cli_mod.main()

    assert dl_calls and dl_calls[0]["group_id"] == 13


def test_launch_tool_spinner(monkeypatch):
    cli_mod = _setup_common(monkeypatch)

    monkeypatch.setattr(cli_mod, "resolve_group_id", lambda *a, **k: 11)

    spinner = []
    monkeypatch.setattr(
        cli_mod,
        "run_with_spinner",
        lambda func, msg, show=True: spinner.append(show) or func(),
    )

    monkeypatch.setattr(cli_mod, "launch_tool", lambda **kw: None)

    argv = ["prog", "--launch-tool", "hippunfold", "--group-id", "Proj"]
    monkeypatch.setattr(sys, "argv", argv)

    with pytest.raises(SystemExit):
        cli_mod.main()

    # The CLI no longer wraps ``launch_tool`` with ``run_with_spinner`` to
    # avoid console artefacts.  Ensure the helper was not invoked.
    assert spinner == []


def test_launch_tool_spinner_debug(monkeypatch):
    cli_mod = _setup_common(monkeypatch)

    monkeypatch.setattr(cli_mod, "resolve_group_id", lambda *a, **k: 11)

    spinner = []
    monkeypatch.setattr(
        cli_mod,
        "run_with_spinner",
        lambda func, msg, show=True: spinner.append(show) or func(),
    )

    monkeypatch.setattr(cli_mod, "launch_tool", lambda **kw: None)

    argv = [
        "prog",
        "--launch-tool",
        "hippunfold",
        "--group-id",
        "Proj",
        "--debug-logs",
    ]
    monkeypatch.setattr(sys, "argv", argv)

    with pytest.raises(SystemExit):
        cli_mod.main()

    # Debug mode suppresses the spinner for other commands, but ``launch_tool``
    # is now executed directly without the helper.
    assert spinner == []
