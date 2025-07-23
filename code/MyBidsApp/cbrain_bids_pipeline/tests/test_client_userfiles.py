import sys
import types

# Minimal stubs so that CbrainClient imports successfully
models_mod = types.ModuleType("openapi_client.models")

class Dummy:
    def __init__(self, *a, **k):
        pass

class MultiUserfilesModReq:
    def __init__(self, file_ids=None):
        self.file_ids = file_ids

    def to_dict(self):
        return {"file_ids": self.file_ids}

models_mod.Bourreau = Dummy
models_mod.CbrainTask = Dummy
models_mod.CbrainTaskModReq = Dummy
models_mod.DataProvider = Dummy
models_mod.FileInfo = Dummy
models_mod.Group = Dummy
models_mod.GroupModReq = Dummy
models_mod.MultiRegistrationModReq = Dummy
models_mod.MultiUserfilesModReq = MultiUserfilesModReq
models_mod.RegistrationInfo = Dummy
models_mod.SessionInfo = Dummy
models_mod.Tag = Dummy
models_mod.TagModReq = Dummy
models_mod.Tool = Dummy
models_mod.ToolConfig = Dummy
models_mod.User = Dummy
models_mod.UserModReq = Dummy
models_mod.Userfile = Dummy
models_mod.UserfileModReq = Dummy
sys.modules.setdefault("openapi_client.models", models_mod)
sys.modules.setdefault("openapi_client.models.group", models_mod)
sys.modules.setdefault("openapi_client.models.group_mod_req", models_mod)
sys.modules.setdefault("openapi_client.models.multi_userfiles_mod_req", models_mod)
for name in [
    "bourreau",
    "cbrain_task",
    "cbrain_task_mod_req",
    "data_provider",
    "file_info",
    "multi_registration_mod_req",
    "registration_info",
    "session_info",
    "tag",
    "tag_mod_req",
    "tool",
    "tool_config",
    "user",
    "user_mod_req",
    "userfile",
    "userfile_mod_req",
]:
    sys.modules.setdefault(f"openapi_client.models.{name}", models_mod)

from bids_cbrain_runner.api.client_openapi import (
    CbrainClient,
    MultiUserfilesModReq,
)


class DummyResp:
    def __init__(self, status=200):
        self.status_code = status

    def raise_for_status(self):
        raise AssertionError("raise_for_status called")


def test_delete_userfiles_builds_request(monkeypatch):
    captured = {}

    def fake_delete(base_url, endpoint, token, *, json=None, timeout=None, allow_redirects=True, **_):
        captured["args"] = (base_url, endpoint, token)
        captured["json"] = json
        captured["timeout"] = timeout
        captured["allow_redirects"] = allow_redirects
        return DummyResp()

    monkeypatch.setattr(
        "bids_cbrain_runner.api.client_openapi.cbrain_delete",
        fake_delete,
    )

    client = object.__new__(CbrainClient)
    client.base_url = "https://x"
    client.token = "tok"

    client.delete_userfiles([1, 2, 3], timeout=5)

    assert captured["args"] == ("https://x", "userfiles/delete_files", "tok")
    assert captured["json"] == {"file_ids": ["1", "2", "3"]}
    assert captured["timeout"] == 5
    assert captured["allow_redirects"] is False


def test_delete_userfiles_accepts_302(monkeypatch):
    def fake_delete(*a, **k):
        return DummyResp(status=302)

    monkeypatch.setattr(
        "bids_cbrain_runner.api.client_openapi.cbrain_delete",
        fake_delete,
    )

    client = object.__new__(CbrainClient)
    client.base_url = "https://x"
    client.token = "tok"

    # Should not raise for 302 responses
    client.delete_userfiles([99])

