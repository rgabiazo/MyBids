import sys
import types


def _import_cli_with_stubs():
    stub = types.ModuleType('bids_cbrain_runner.api.client_openapi')
    stub.ApiException = Exception
    class CbrainClient:
        pass
    stub.CbrainClient = CbrainClient
    stub.CbrainTaskError = Exception
    sys.modules['bids_cbrain_runner.api.client_openapi'] = stub

    from bids_cbrain_runner import cli as cli_mod
    return cli_mod


def _common(monkeypatch, cli_mod):
    monkeypatch.setattr(cli_mod, 'get_sftp_provider_config', lambda provider_name=None: {})
    monkeypatch.setattr(cli_mod, 'load_cbrain_config', lambda: {})
    monkeypatch.setattr(cli_mod, 'load_tools_config', lambda: {})
    monkeypatch.setattr(cli_mod, 'ensure_token', lambda **kw: {'cbrain_api_token': 'tok', 'cbrain_base_url': 'https://x'})


def test_task_status_group(monkeypatch):
    cli_mod = _import_cli_with_stubs()
    _common(monkeypatch, cli_mod)

    monkeypatch.setattr(cli_mod, 'resolve_group_id', lambda *a, **k: 99)

    calls = []
    monkeypatch.setattr(
        cli_mod,
        'show_group_tasks_status',
        lambda base_url, token, gid, *, task_type=None, per_page=100, timeout=None: calls.append((gid, task_type)),
    )

    argv = ['prog', '--task-status', 'MyProj', '--task-type', 'hippunfold']
    monkeypatch.setattr(sys, 'argv', argv)

    cli_mod.main()

    assert calls == [(99, 'hippunfold')]


def test_task_status_single(monkeypatch):
    cli_mod = _import_cli_with_stubs()
    _common(monkeypatch, cli_mod)

    monkeypatch.setattr(cli_mod, 'resolve_group_id', lambda *a, **k: None)

    calls = []
    monkeypatch.setattr(
        cli_mod,
        'show_task_status',
        lambda base_url, token, tid: calls.append(tid),
    )

    argv = ['prog', '--task-status', '123']
    monkeypatch.setattr(sys, 'argv', argv)

    cli_mod.main()

    assert calls == [123]


def test_task_status_group_numeric_missing(monkeypatch):
    cli_mod = _import_cli_with_stubs()
    _common(monkeypatch, cli_mod)

    monkeypatch.setattr(cli_mod, 'resolve_group_id', lambda *a, **k: None)

    calls = []
    monkeypatch.setattr(
        cli_mod,
        'show_task_status',
        lambda base_url, token, tid: calls.append(tid),
    )

    argv = ['prog', '--task-status', '77']
    monkeypatch.setattr(sys, 'argv', argv)

    cli_mod.main()

    assert calls == [77]


def test_task_status_group_numeric(monkeypatch):
    cli_mod = _import_cli_with_stubs()
    _common(monkeypatch, cli_mod)

    monkeypatch.setattr(cli_mod, 'resolve_group_id', lambda *a, **k: 77)

    calls = []
    monkeypatch.setattr(
        cli_mod,
        'show_group_tasks_status',
        lambda base_url, token, gid, *, task_type=None, per_page=100, timeout=None: calls.append(gid),
    )

    argv = ['prog', '--task-status', '77']
    monkeypatch.setattr(sys, 'argv', argv)

    cli_mod.main()

    assert calls == [77]
