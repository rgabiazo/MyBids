import pytest

from bids_cbrain_runner.commands import tool_launcher as tl_mod


def test_launch_tool_separates_non_boutiques_params(monkeypatch):
    """Parameters unknown to the Boutiques descriptor should live outside
    the ``invoke`` block."""

    descriptor = {
        "inputs": [
            {"id": "bids_dir", "type": "File", "optional": False},
            {"id": "output_dir_name", "type": "String", "optional": False},
        ]
    }

    class DummyClient:
        def __init__(self, base_url, token):
            self.payload = None

        def fetch_boutiques_descriptor(self, _):
            return descriptor

        def create_task(self, payload):
            self.payload = payload
            # Simulate API response including a description field
            return {**payload, "description": "ok\ncreated"}

    dummy_client = DummyClient("https://x", "tok")
    monkeypatch.setattr(tl_mod, "CbrainClient", lambda base_url, token: dummy_client)
    monkeypatch.setattr(tl_mod, "run_with_spinner", lambda func, msg, show=True: func())

    tools_cfg = {
        "deepprep": {
            "default_cluster": "cluster",
            "clusters": {"cluster": {"tool_config_id": 1, "bourreau_id": 2}},
        }
    }

    extra = {
        "bids_dir": 1,
        "output_dir_name": "out",
        "cbrain_enable_output_cache_cleaner": True,
    }

    tl_mod.launch_tool(
        base_url="https://x",
        token="tok",
        tools_cfg=tools_cfg,
        tool_name="deepprep",
        extra_params=extra,
        group_id=3,
        dry_run=False,
        show_spinner=False,
    )

    payload = dummy_client.payload
    assert payload["params"]["invoke"] == {"bids_dir": 1, "output_dir_name": "out"}
    assert payload["params"]["cbrain_enable_output_cache_cleaner"] is True
