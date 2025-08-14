from bids_cbrain_runner.commands import tools as tools_mod


def test_retry_failed_tasks_filters(monkeypatch):
    monkeypatch.setattr(tools_mod, 'CbrainClient', lambda base_url, token: object())
    monkeypatch.setattr(
        tools_mod,
        'list_tasks_by_group',
        lambda *a, **k: [
            {'id': 1, 'status': 'Completed'},
            {'id': 2, 'status': 'Failed On Cluster'},
        ],
    )

    calls = []
    monkeypatch.setattr(
        tools_mod,
        'retry_task',
        lambda base_url, token, tid, *, timeout=None, current_status=None: calls.append((tid, current_status)),
    )

    tools_mod.retry_failed_tasks('https://x', 'tok', 7)

    assert calls == [(2, 'Failed On Cluster')]
