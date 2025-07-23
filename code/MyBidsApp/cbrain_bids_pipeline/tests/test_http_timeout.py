import sys
import types

from bids_cbrain_runner.api import client as client_mod
from bids_cbrain_runner.commands import groups as groups_mod


class DummyResp:
    def __init__(self):
        self.status_code = 200
        self._json = {}
    def json(self):
        return self._json


def test_cbrain_get_env_timeout(monkeypatch):
    called = {}
    def fake_get(url, headers=None, params=None, timeout=None):
        called['timeout'] = timeout
        return DummyResp()
    monkeypatch.setattr(client_mod.requests, 'get', fake_get)
    monkeypatch.setenv('CBRAIN_TIMEOUT', '7')
    client_mod.cbrain_get('https://x', 'groups', 'tok')
    assert called['timeout'] == 7.0


def test_default_timeout(monkeypatch):
    called = {}
    def fake_get(url, headers=None, params=None, timeout=None):
        called['timeout'] = timeout
        return DummyResp()
    monkeypatch.setattr(client_mod.requests, 'get', fake_get)
    monkeypatch.delenv('CBRAIN_TIMEOUT', raising=False)
    client_mod.cbrain_get('https://x', 'groups', 'tok')
    assert called['timeout'] == client_mod.DEFAULT_TIMEOUT


def test_list_groups_forwards_timeout(monkeypatch):
    captured = {}

    class DummyClient:
        def __init__(self, *a, **k):
            pass

        def list_groups(self, *, page=1, per_page=25, timeout=None):
            captured['timeout'] = timeout
            return []

    monkeypatch.setattr(groups_mod, 'CbrainClient', DummyClient)
    groups_mod.list_groups('https://x', 'tok', timeout=5)
    assert captured['timeout'] == 5


def test_cli_timeout_option(monkeypatch):
    stub = types.ModuleType('bids_cbrain_runner.api.client_openapi')
    stub.ApiException = Exception
    class CbrainClient: ...
    stub.CbrainClient = CbrainClient
    stub.CbrainTaskError = Exception
    monkeypatch.setitem(sys.modules, 'bids_cbrain_runner.api.client_openapi', stub)

    from bids_cbrain_runner import cli as cli_mod
    monkeypatch.setattr(cli_mod, 'get_sftp_provider_config', lambda provider_name=None: {})
    monkeypatch.setattr(cli_mod, 'load_cbrain_config', lambda: {})
    monkeypatch.setattr(cli_mod, 'load_tools_config', lambda: {})
    monkeypatch.setattr(
        cli_mod,
        'ensure_token',
        lambda **kw: {
            'cbrain_api_token': 'tok',
            'cbrain_base_url': 'https://x',
        },
    )

    called = {}
    monkeypatch.setattr(
        cli_mod,
        'list_groups',
        lambda *a, **kw: called.setdefault('timeout', kw.get('timeout')) or [],
    )

    monkeypatch.setattr(sys, 'argv', ['prog', '--list-groups', '--timeout', '3'])
    cli_mod.main()
    assert called['timeout'] == 3.0
