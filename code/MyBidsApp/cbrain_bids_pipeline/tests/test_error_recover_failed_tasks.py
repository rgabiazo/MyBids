from bids_cbrain_runner.commands import tools as tools_mod


def test_error_recover_failed_tasks_filters(monkeypatch):
    monkeypatch.setattr(tools_mod, 'CbrainClient', lambda base_url, token: object())
    monkeypatch.setattr(
        tools_mod,
        'list_tasks_by_group',
        lambda *a, **k: [
            {'id': 1, 'status': 'Completed'},
            {'id': 2, 'status': 'Error Recoverable'},
            {'id': 3, 'status': 'Failed On Cluster'},
        ],
    )

    calls = []
    monkeypatch.setattr(
        tools_mod,
        'error_recover_task',
        lambda base_url, token, tid, *, timeout=None, current_status=None: calls.append((tid, current_status)),
    )

    tools_mod.error_recover_failed_tasks('https://x', 'tok', 7)

    assert calls == [(2, 'Error Recoverable'), (3, 'Failed On Cluster')]
