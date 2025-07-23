import types

from bids_cbrain_runner.commands import groups as groups_mod


class DummyClient:
    def __init__(self):
        self.created = None
        self.page_calls = []
        self.list_impl = lambda *, page=1, per_page=25, timeout=None: []

    def list_groups(self, *, page=1, per_page=25, timeout=None):
        self.page_calls.append(page)
        return self.list_impl(page=page, per_page=per_page, timeout=timeout)

    def create_group(self, name, description=None, *, timeout=None):
        self.created = {"name": name, "description": description, "timeout": timeout}
        return types.SimpleNamespace(id=42, name=name, description=description)

def test_create_group_success(monkeypatch):
    client = DummyClient()
    monkeypatch.setattr(groups_mod, "CbrainClient", lambda *a, **k: client)

    res = groups_mod.create_group("https://x", "tok", "Proj-1", "desc")
    assert res["id"] == 42
    assert client.created["name"] == "Proj-1"
    assert client.created["description"] == "desc"

def test_create_group_existing(monkeypatch):
    client = DummyClient()
    client.list_impl = lambda *, page=1, per_page=25, timeout=None: [
        types.SimpleNamespace(id=1, name="Proj-1")
    ]
    monkeypatch.setattr(groups_mod, "CbrainClient", lambda *a, **k: client)

    res = groups_mod.create_group("https://x", "tok", "Proj-1")
    assert res is None
    assert client.created is None


def test_create_group_paginated_existing(monkeypatch):
    """Existing project detected on a later page."""

    client = DummyClient()

    def list_impl(*, page=1, per_page=25, timeout=None):
        if page == 1:
            return [
                types.SimpleNamespace(id=1, name="A"),
                types.SimpleNamespace(id=2, name="B"),
            ][:per_page]
        if page == 2:
            return [types.SimpleNamespace(id=3, name="Proj-1")]
        return []

    client.list_impl = list_impl
    monkeypatch.setattr(groups_mod, "CbrainClient", lambda *a, **k: client)

    res = groups_mod.create_group("https://x", "tok", "Proj-1", per_page=2)
    assert res is None
    assert client.created is None


def test_resolve_group_id_by_name(monkeypatch):
    monkeypatch.setattr(
        groups_mod,
        "list_groups",
        lambda *a, **k: [{"id": 99, "name": "Trial"}],
    )

    gid = groups_mod.resolve_group_id("https://x", "tok", "Trial")
    assert gid == 99


def test_resolve_group_id_missing(monkeypatch):
    monkeypatch.setattr(groups_mod, "list_groups", lambda *a, **k: [])

    gid = groups_mod.resolve_group_id("https://x", "tok", "Foo")
    assert gid is None


class DummyApi:
    def __init__(self, status=200):
        self.status = status

    def groups_id_get(self, gid, _request_timeout=None):
        if self.status != 200:
            raise groups_mod.ApiException("not found")
        return types.SimpleNamespace(id=gid)


def test_resolve_group_id_numeric(monkeypatch):
    client = types.SimpleNamespace(groups_api=DummyApi())
    monkeypatch.setattr(groups_mod, "CbrainClient", lambda *a, **k: client)
    monkeypatch.setattr(groups_mod, "ApiException", Exception)

    gid = groups_mod.resolve_group_id("https://x", "tok", "77")
    assert gid == 77


def test_resolve_group_id_numeric_missing(monkeypatch):
    client = types.SimpleNamespace(groups_api=DummyApi(status=404))
    monkeypatch.setattr(groups_mod, "CbrainClient", lambda *a, **k: client)
    monkeypatch.setattr(groups_mod, "ApiException", Exception)

    gid = groups_mod.resolve_group_id("https://x", "tok", "77")
    assert gid is None

