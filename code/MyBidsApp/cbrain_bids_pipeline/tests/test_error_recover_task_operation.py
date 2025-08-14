import pytest
from bids_cbrain_runner.commands import tools as tools_mod


class DummyClient:
    def __init__(self, calls):
        self._calls = calls

    def operate_tasks(self, operation, task_ids, *, timeout=None):
        self._calls.append((operation, task_ids, timeout))


@pytest.mark.parametrize("status", ["Error Recoverable", "Failed On Cluster"])
def test_error_recover_task(monkeypatch, status):
    calls: list[tuple[str, list[int], None]] = []
    monkeypatch.setattr(
        tools_mod,
        "CbrainClient",
        lambda base_url, token: DummyClient(calls),
    )
    tools_mod.error_recover_task("https://x", "tok", 5, current_status=status)
    assert calls == [("recover", [5], None)]
