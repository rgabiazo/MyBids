from bids_cbrain_runner.commands.tools import list_tasks_by_group


def test_list_tasks_prefix_and_id(monkeypatch):
    tasks = [
        {"id": 1, "group_id": 77, "type": "BoutiquesTask::Hippunfold", "tool_config_id": 505},
        {"id": 2, "group_id": 77, "type": "hippunfold-v2", "tool_config_id": 606},
        {"id": 3, "group_id": 77, "type": "OtherTool", "tool_config_id": 707},
        {"id": 4, "group_id": 12, "type": "Hippunfold", "tool_config_id": 505},
    ]

    monkeypatch.setattr(
        "bids_cbrain_runner.commands.tools.fetch_all_tasks",
        lambda client, per_page=100, timeout=None: tasks,
    )

    dummy_client = object()

    res = list_tasks_by_group(dummy_client, 77, task_type="hIPp")
    assert [t["id"] for t in res] == [1, 2]

    res_id = list_tasks_by_group(dummy_client, 77, task_type="606")
    assert [t["id"] for t in res_id] == [2]
