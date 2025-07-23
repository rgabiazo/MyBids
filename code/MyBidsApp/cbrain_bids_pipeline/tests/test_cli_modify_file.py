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


def _setup_common(monkeypatch):
    cli_mod = _import_cli_with_stubs()
    monkeypatch.setattr(cli_mod, 'get_sftp_provider_config', lambda provider_name=None: {})
    monkeypatch.setattr(cli_mod, 'load_cbrain_config', lambda: {})
    monkeypatch.setattr(cli_mod, 'load_tools_config', lambda: {})
    monkeypatch.setattr(cli_mod, 'ensure_token', lambda **kw: {'cbrain_api_token': 'tok', 'cbrain_base_url': 'https://x'})
    return cli_mod


def test_modify_file_group_name(monkeypatch):
    cli_mod = _setup_common(monkeypatch)

    monkeypatch.setattr(cli_mod, 'resolve_group_id', lambda *a, **k: 7)

    called = {}
    monkeypatch.setattr(
        cli_mod,
        'update_userfile_group_and_move',
        lambda base_url, token, userfile_id, *, new_group_id=None, new_provider_id=None, timeout=None: called.setdefault('args', (userfile_id, new_group_id))
    )

    argv = ['prog', '--modify-file', '--userfile-id', '42', '--new-group-id', 'Trial']
    monkeypatch.setattr(sys, 'argv', argv)

    cli_mod.main()

    assert called.get('args') == (42, 7)
