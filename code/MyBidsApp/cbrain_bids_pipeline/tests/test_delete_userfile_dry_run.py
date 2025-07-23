import logging

from bids_cbrain_runner.commands.userfiles import delete_userfile


class DummyClient:
    def __init__(self):
        self.deleted = False

    def get_userfile(self, userfile_id, timeout=None):
        return {"name": "demo"}

    def delete_userfiles(self, ids, timeout=None):
        self.deleted = True


def test_delete_userfile_dry_run_logs_once(caplog):
    client = DummyClient()
    caplog.set_level(logging.INFO)
    delete_userfile(client, 42, dry_run=True)
    assert not client.deleted
    assert caplog.text.count("[DRY] Would delete demo (ID=42)") == 1
