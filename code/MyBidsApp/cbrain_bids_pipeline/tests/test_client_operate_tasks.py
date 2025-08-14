from bids_cbrain_runner.api.client_openapi import CbrainClient


class DummyTasksApi:
    def __init__(self, recorder):
        self._recorder = recorder

    def tasks_operation_post(self, operation=None, tasklist=None, _request_timeout=None):
        self._recorder["operation"] = operation
        self._recorder["tasklist"] = tasklist
        self._recorder["timeout"] = _request_timeout
        return object()


def test_operate_tasks_builds_request():
    captured: dict = {}
    client = object.__new__(CbrainClient)
    client.tasks_api = DummyTasksApi(captured)
    client.base_url = "https://x"
    client.token = "tok"

    client.operate_tasks("delete", [1, 2], timeout=7)

    assert captured["operation"] == "delete"
    assert captured["tasklist"].tasklist == [1, 2]
    assert captured["timeout"] == 7
