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


def test_error_recover_task_single(monkeypatch):
    cli_mod = _import_cli_with_stubs()
    _common(monkeypatch, cli_mod)

    calls = []
    monkeypatch.setattr(
        cli_mod,
        'error_recover_task',
        lambda base_url, token, tid, *, timeout=None: calls.append(tid),
    )

    argv = ['prog', '--error-recover', '42']
    monkeypatch.setattr(sys, 'argv', argv)

    cli_mod.main()

    assert calls == [42]


def test_error_recover_failed_group(monkeypatch):
    cli_mod = _import_cli_with_stubs()
    _common(monkeypatch, cli_mod)

    monkeypatch.setattr(cli_mod, 'resolve_group_id', lambda *a, **k: 99)

    calls = []
    monkeypatch.setattr(
        cli_mod,
        'error_recover_failed_tasks',
        lambda base_url, token, gid, *, task_type=None, per_page=100, timeout=None: calls.append((gid, task_type)),
    )

    argv = ['prog', '--error-recover-failed', 'MyProj', '--task-type', 'DeepPrep']
    monkeypatch.setattr(sys, 'argv', argv)

    cli_mod.main()

    assert calls == [(99, 'DeepPrep')]
