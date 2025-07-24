import sys
import pytest

from bids_cbrain_runner.commands import upload as upload_mod
from bids_cbrain_runner.commands import sftp as sftp_mod
from bids_cbrain_runner.utils import filetypes as filetypes_mod


class DummySSH:
    def close(self):
        pass


class DummySFTP:
    def __init__(self):
        self.uploaded = []

    def getcwd(self):
        return "/"

    def chdir(self, path):
        pass

    def put(self, local, remote):
        self.uploaded.append((local, remote))

    def close(self):
        pass


def _fake_listdir_factory(map_dict):
    def _fake_listdirs(_, directory):
        return map_dict.get(directory, ([], []))

    return _fake_listdirs


def test_upload_bids_and_sftp_files(monkeypatch, tmp_path):
    ds = tmp_path / "bids"
    ds.mkdir()
    (ds / "dataset_description.json").write_text("{}")
    local_sub = ds / "sub-01" / "ses-01" / "anat"
    local_sub.mkdir(parents=True)
    fpath = local_sub / "file.nii.gz"
    fpath.write_text("dummy")

    monkeypatch.setattr(upload_mod, "bids_validator_cli", lambda steps: True)

    dummy = DummySFTP()
    monkeypatch.setattr(upload_mod, "sftp_connect_from_config", lambda cfg: (DummySSH(), dummy))
    monkeypatch.setattr(upload_mod, "list_subdirs_and_files", lambda c, p: ([], []))
    monkeypatch.setattr(upload_mod, "ensure_remote_dir_structure", lambda c, p: False)

    reg_calls = []
    monkeypatch.setattr(upload_mod, "register_files_on_provider", lambda **kw: reg_calls.append(kw))
    monkeypatch.setattr(upload_mod, "find_userfile_id_by_name_and_provider", lambda *a, **k: 42)
    move_calls = []
    monkeypatch.setattr(upload_mod, "update_userfile_group_and_move", lambda **kw: move_calls.append(kw))

    monkeypatch.chdir(str(ds))
    upload_mod.upload_bids_and_sftp_files(
        cfg={},
        base_url="https://x",
        token="tok",
        steps=["sub-*", "ses-*", "anat"],
        do_register=True,
        dp_id=1,
        filetypes=["BidsSubject"],
        group_id=2,
        move_provider=3,
    )

    assert dummy.uploaded == [(str(fpath), "/sub-01/ses-01/anat/file.nii.gz")]
    assert reg_calls and reg_calls[0]["provider_id"] == 1
    assert move_calls and move_calls[0]["userfile_id"] == 42


def test_auto_filetype_dataset_description(monkeypatch, tmp_path):
    ds = tmp_path / "bids"
    ds.mkdir()
    (ds / "dataset_description.json").write_text("{}")

    monkeypatch.setattr(upload_mod, "bids_validator_cli", lambda steps: True)
    monkeypatch.setattr(
        filetypes_mod,
        "load_pipeline_config",
        lambda: {
            "filetype_inference": {
                "fallback": "BidsSubject",
                "patterns": {
                    "dataset_description.json": "JsonFile",
                    "sub-*": "BidsSubject",
                },
            }
        },
    )

    dummy = DummySFTP()
    monkeypatch.setattr(upload_mod, "sftp_connect_from_config", lambda cfg: (DummySSH(), dummy))
    monkeypatch.setattr(upload_mod, "list_subdirs_and_files", lambda c, p: ([], []))
    monkeypatch.setattr(upload_mod, "ensure_remote_dir_structure", lambda c, p: False)

    reg_calls = []
    monkeypatch.setattr(upload_mod, "register_files_on_provider", lambda **kw: reg_calls.append(kw))

    monkeypatch.chdir(str(ds))
    upload_mod.upload_bids_and_sftp_files(
        cfg={},
        base_url="https://x",
        token="tok",
        steps=["dataset_description.json"],
        do_register=True,
        dp_id=1,
        filetypes=None,
    )

    assert reg_calls and reg_calls[0]["types"] == ["JsonFile"]


def test_auto_filetype_subject(monkeypatch, tmp_path):
    ds = tmp_path / "bids"
    ds.mkdir()
    (ds / "dataset_description.json").write_text("{}")
    (ds / "sub-01" / "ses-01" / "anat").mkdir(parents=True)
    (ds / "sub-01" / "ses-01" / "anat" / "a.nii.gz").write_text("dummy")

    monkeypatch.setattr(upload_mod, "bids_validator_cli", lambda steps: True)
    monkeypatch.setattr(
        filetypes_mod,
        "load_pipeline_config",
        lambda: {
            "filetype_inference": {
                "fallback": "BidsSubject",
                "patterns": {"sub-*": "BidsSubject"},
            }
        },
    )

    dummy = DummySFTP()
    monkeypatch.setattr(upload_mod, "sftp_connect_from_config", lambda cfg: (DummySSH(), dummy))
    monkeypatch.setattr(upload_mod, "list_subdirs_and_files", lambda c, p: ([], []))
    monkeypatch.setattr(upload_mod, "ensure_remote_dir_structure", lambda c, p: False)

    reg_calls = []
    monkeypatch.setattr(upload_mod, "register_files_on_provider", lambda **kw: reg_calls.append(kw))

    monkeypatch.chdir(str(ds))
    upload_mod.upload_bids_and_sftp_files(
        cfg={},
        base_url="https://x",
        token="tok",
        steps=["sub-*"],
        do_register=True,
        dp_id=1,
        filetypes=None,
    )

    assert reg_calls and reg_calls[0]["types"] == ["BidsSubject"]


def test_register_existing_files(monkeypatch, tmp_path):
    """Existing remote files should still be registered to a new group."""

    ds = tmp_path / "bids"
    ds.mkdir()
    (ds / "dataset_description.json").write_text("{}")

    monkeypatch.setattr(upload_mod, "bids_validator_cli", lambda steps: True)

    dummy = DummySFTP()
    # Pretend the remote already contains the JSON file
    monkeypatch.setattr(upload_mod, "sftp_connect_from_config", lambda cfg: (DummySSH(), dummy))
    monkeypatch.setattr(upload_mod, "list_subdirs_and_files", lambda c, p: ([], ["dataset_description.json"]))
    monkeypatch.setattr(upload_mod, "ensure_remote_dir_structure", lambda c, p: False)

    reg_calls = []
    monkeypatch.setattr(upload_mod, "register_files_on_provider", lambda **kw: reg_calls.append(kw))

    monkeypatch.chdir(str(ds))
    upload_mod.upload_bids_and_sftp_files(
        cfg={},
        base_url="https://x",
        token="tok",
        steps=["dataset_description.json"],
        do_register=True,
        dp_id=1,
        filetypes=None,
        group_id=2,
    )

    assert reg_calls and reg_calls[0]["basenames"] == ["dataset_description.json"]


def test_sftp_cd_steps_and_tree(monkeypatch):
    tree_map = {
        "/": (["sub-01"], []),
        "/sub-01": (["ses-01"], []),
        "/sub-01/ses-01": (["anat"], []),
        "/sub-01/ses-01/anat": ([], ["file.nii.gz"]),
    }
    monkeypatch.setattr(sftp_mod, "sftp_connect_from_config", lambda cfg: (DummySSH(), DummySFTP()))
    monkeypatch.setattr(sftp_mod, "list_subdirs_and_files", _fake_listdir_factory(tree_map))

    captured = []
    monkeypatch.setattr(sftp_mod, "print_jsonlike_dict", lambda d, title=None: captured.append(d))

    sftp_mod.sftp_cd_steps({}, ["sub-*", "ses-*"])

    assert captured[0] == {"sub-01": {"ses-01": {"anat": ["file.nii.gz"]}}}

    dummy = DummySFTP()
    tree = sftp_mod.build_sftp_path_tree(dummy, "/", ["sub-*", "ses-*"])
    assert tree["sub-01"]["ses-01"]["anat"]["_files"] == ["file.nii.gz"]


def test_cli_upload_and_download(monkeypatch, tmp_path):
    import types
    stub = types.ModuleType('bids_cbrain_runner.api.client_openapi')
    stub.ApiException = Exception
    class DummyClient: ...
    class CbrainClient: ...
    stub.CbrainClient = CbrainClient
    stub.CbrainTaskError = Exception
    sys.modules['bids_cbrain_runner.api.client_openapi'] = stub

    from bids_cbrain_runner import cli as cli_mod

    monkeypatch.setattr(cli_mod, "get_sftp_provider_config", lambda provider_name=None: {})
    monkeypatch.setattr(cli_mod, "get_sftp_provider_config_by_id", lambda pid: {})
    monkeypatch.setattr(cli_mod, "load_cbrain_config", lambda: {})
    monkeypatch.setattr(cli_mod, "load_tools_config", lambda: {})
    monkeypatch.setattr(cli_mod, "ensure_token", lambda **kw: {"cbrain_api_token": "tok", "cbrain_base_url": "https://x"})
    monkeypatch.setattr(cli_mod, "resolve_group_id", lambda *a, **k: 7)

    up_calls = []
    monkeypatch.setattr(cli_mod, "upload_bids_and_sftp_files", lambda *a, **kw: up_calls.append((a, kw)))
    dl_calls = []
    monkeypatch.setattr(cli_mod, "download_tool_outputs", lambda **kw: dl_calls.append(kw))

    argv = [
        "prog",
        "--sftp-provider",
        "p1",
        "--upload-bids-and-sftp-files",
        "sub-*",
        "ses-*",
        "anat",
        "--upload-register",
        "--upload-dp-id",
        "5",
    ]
    monkeypatch.setattr(sys, "argv", argv)
    cli_mod.main()
    assert up_calls
    assert up_calls[0][0][3] == ["sub-*", "ses-*", "anat"]

    argv = [
        "prog",
        "download",
        "--tool",
        "hippunfold",
        "--group",
        "7",
        "--config",
        str(tmp_path / "cfg.yaml"),
        "--force",
    ]
    monkeypatch.setattr(sys, "argv", argv)
    with pytest.raises(SystemExit):
        cli_mod.main()
    assert dl_calls
    assert dl_calls[0]["group_id"] == 7
    assert dl_calls[0]["cfg"]["local_config_path"] == str(tmp_path / "cfg.yaml")


def test_cli_group_name(monkeypatch, tmp_path):
    import types
    stub = types.ModuleType('bids_cbrain_runner.api.client_openapi')
    stub.ApiException = Exception
    class DummyClient: ...
    class CbrainClient: ...
    stub.CbrainClient = CbrainClient
    stub.CbrainTaskError = Exception
    sys.modules['bids_cbrain_runner.api.client_openapi'] = stub

    from bids_cbrain_runner import cli as cli_mod

    monkeypatch.setattr(cli_mod, "get_sftp_provider_config", lambda provider_name=None: {})
    monkeypatch.setattr(cli_mod, "load_cbrain_config", lambda: {})
    monkeypatch.setattr(cli_mod, "load_tools_config", lambda: {})
    monkeypatch.setattr(cli_mod, "ensure_token", lambda **kw: {"cbrain_api_token": "tok", "cbrain_base_url": "https://x"})

    monkeypatch.setattr(
        cli_mod,
        "resolve_group_id",
        lambda base_url, token, ident, per_page=100, timeout=None: 7,
    )

    up_calls = []
    monkeypatch.setattr(cli_mod, "upload_bids_and_sftp_files", lambda *a, **kw: up_calls.append(kw))

    argv = [
        "prog",
        "--upload-bids-and-sftp-files",
        "sub-*",
        "--upload-group-id",
        "MyTrial",
    ]
    monkeypatch.setattr(sys, "argv", argv)
    cli_mod.main()
    assert up_calls and up_calls[0]["group_id"] == 7


def test_cli_upload_dp_id_switch(monkeypatch):
    import types
    stub = types.ModuleType('bids_cbrain_runner.api.client_openapi')
    stub.ApiException = Exception
    class DummyClient: ...
    class CbrainClient: ...
    stub.CbrainClient = CbrainClient
    stub.CbrainTaskError = Exception
    sys.modules['bids_cbrain_runner.api.client_openapi'] = stub

    from bids_cbrain_runner import cli as cli_mod

    monkeypatch.setattr(cli_mod, "get_sftp_provider_config", lambda provider_name=None: {"cbrain_id": 51})
    monkeypatch.setattr(cli_mod, "get_sftp_provider_config_by_id", lambda pid: {"cbrain_id": pid})
    monkeypatch.setattr(cli_mod, "load_cbrain_config", lambda: {})
    monkeypatch.setattr(cli_mod, "load_tools_config", lambda: {})
    monkeypatch.setattr(cli_mod, "ensure_token", lambda **kw: {"cbrain_api_token": "tok", "cbrain_base_url": "https://x"})

    up_calls = []
    monkeypatch.setattr(cli_mod, "upload_bids_and_sftp_files", lambda cfg, *a, **kw: up_calls.append(cfg))

    argv = ["prog", "--upload-bids-and-sftp-files", "sub-*", "--upload-dp-id", "32"]
    monkeypatch.setattr(sys, "argv", argv)

    cli_mod.main()

    assert up_calls and up_calls[0].get("cbrain_id") == 32


