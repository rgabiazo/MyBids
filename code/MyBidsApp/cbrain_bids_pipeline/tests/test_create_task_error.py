import json
import types

import pytest

import bids_cbrain_runner.api.client_openapi as client_mod
from bids_cbrain_runner.api.client_openapi import CbrainClient, CbrainTaskError


def test_create_task_offline_server_error(monkeypatch):
    """Formatting of API errors should be human-readable."""

    monkeypatch.setattr(
        client_mod, "get_api_client", lambda base_url, token: types.SimpleNamespace()
    )
    monkeypatch.setattr(client_mod, "ToolsApi", lambda api_client: None)
    monkeypatch.setattr(client_mod, "ToolConfigsApi", lambda api_client: None)
    monkeypatch.setattr(client_mod, "BourreauxApi", lambda api_client: None)
    monkeypatch.setattr(client_mod, "TasksApi", lambda api_client: None)
    monkeypatch.setattr(client_mod, "UserfilesApi", lambda api_client: None)
    monkeypatch.setattr(client_mod, "GroupsApi", lambda api_client: None)
    client = CbrainClient("https://x", "tok")

    class DummyTasksApi:
        def tasks_post_without_preload_content(self, cbrain_task):
            payload = {"tool_config_id": ["is on an Execution Server that is currently offline"]}
            return types.SimpleNamespace(data=json.dumps(payload).encode(), status=422)

    client.tasks_api = DummyTasksApi()

    with pytest.raises(CbrainTaskError) as exc:
        client.create_task({})

    msg = str(exc.value)
    assert "HTTP 422" in msg
    assert "tool_config_id is on an Execution Server" in msg
