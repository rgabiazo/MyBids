import json
import sys
import types

from bids_cbrain_runner.commands.alias import AliasSpec, make_task_aliases


def test_make_task_aliases(tmp_path, monkeypatch):
    func = tmp_path / "sub-001" / "ses-01" / "func"
    anat = tmp_path / "sub-001" / "ses-01" / "anat"
    func.mkdir(parents=True)
    anat.mkdir(parents=True)
    (func / "sub-001_ses-01_task-foo_run-01_bold.nii.gz").write_text("data")
    (func / "sub-001_ses-01_task-foo_run-01_bold.json").write_text(
        json.dumps({"TaskName": "foo"})
    )
    (anat / "sub-001_ses-01_task-foo_run-01_T1w.nii.gz").write_text("data")

    spec = AliasSpec([], "foo", "bar", sub="001", ses="01")
    monkeypatch.chdir(tmp_path)
    make_task_aliases(spec)

    assert (func / "sub-001_ses-01_task-bar_run-01_bold.nii.gz").is_symlink()
    assert (anat / "sub-001_ses-01_task-bar_run-01_T1w.nii.gz").is_symlink()
    with open(func / "sub-001_ses-01_task-bar_run-01_bold.json") as fh:
        data = json.load(fh)
    assert data["TaskName"] == "bar"


def test_make_task_aliases_restricted_dir(tmp_path, monkeypatch):
    func = tmp_path / "sub-001" / "ses-01" / "func"
    anat = tmp_path / "sub-001" / "ses-01" / "anat"
    func.mkdir(parents=True)
    anat.mkdir(parents=True)
    (func / "sub-001_ses-01_task-foo_run-01_bold.nii.gz").write_text("data")
    (anat / "sub-001_ses-01_task-foo_run-01_T1w.nii.gz").write_text("data")

    spec = AliasSpec([], "foo", "bar", sub="001", ses="01", inner=["anat"])
    monkeypatch.chdir(tmp_path)
    make_task_aliases(spec)

    assert (anat / "sub-001_ses-01_task-bar_run-01_T1w.nii.gz").is_symlink()
    assert not (func / "sub-001_ses-01_task-bar_run-01_bold.nii.gz").exists()


def test_make_task_aliases_no_session(tmp_path, monkeypatch):
    func = tmp_path / "sub-001" / "func"
    func.mkdir(parents=True)
    (func / "sub-001_task-foo_run-01_bold.nii.gz").write_text("data")

    spec = AliasSpec([], "foo", "bar", sub="001", inner=["func"])
    monkeypatch.chdir(tmp_path)
    make_task_aliases(spec)

    assert (func / "sub-001_task-bar_run-01_bold.nii.gz").is_symlink()


def test_make_task_aliases_dry_run(tmp_path, monkeypatch, caplog):
    func = tmp_path / "sub-001" / "ses-01" / "func"
    func.mkdir(parents=True)
    src = func / "sub-001_ses-01_task-foo_run-01_bold.nii.gz"
    src.write_text("data")

    spec = AliasSpec([], "foo", "bar", sub="001", ses="01")
    monkeypatch.chdir(tmp_path)
    with caplog.at_level("INFO"):
        make_task_aliases(spec, dry_run=True)

    assert not (func / "sub-001_ses-01_task-bar_run-01_bold.nii.gz").exists()
    assert any("Would symlink" in msg for msg in caplog.text.splitlines())


def _import_cli_with_stubs():
    stub = types.ModuleType("bids_cbrain_runner.api.client_openapi")
    stub.ApiException = Exception

    class CbrainClient:
        def __init__(self, *a, **k):
            pass

    stub.CbrainClient = CbrainClient
    stub.CbrainTaskError = Exception
    sys.modules["bids_cbrain_runner.api.client_openapi"] = stub
    from bids_cbrain_runner import cli as cli_mod
    return cli_mod


def _common_patches(monkeypatch, cli_mod):
    monkeypatch.setattr(cli_mod, "get_sftp_provider_config", lambda provider_name=None: {})
    monkeypatch.setattr(cli_mod, "load_cbrain_config", lambda: {})
    monkeypatch.setattr(cli_mod, "load_tools_config", lambda: {})
    monkeypatch.setattr(
        cli_mod,
        "ensure_token",
        lambda **kw: {"cbrain_api_token": "tok", "cbrain_base_url": "https://x"},
    )


def test_cli_alias(monkeypatch, tmp_path):
    cli_mod = _import_cli_with_stubs()
    _common_patches(monkeypatch, cli_mod)

    func = tmp_path / "sub-001" / "ses-01" / "func"
    func.mkdir(parents=True)
    (func / "sub-001_ses-01_task-foo_run-01_bold.nii.gz").write_text("data")
    (func / "sub-001_ses-01_task-foo_run-01_bold.json").write_text(
        json.dumps({"TaskName": "foo"})
    )
    monkeypatch.chdir(tmp_path)
    argv = ["prog", "--alias", "foo=bar,sub=001,ses=01"]
    monkeypatch.setattr(sys, "argv", argv)

    cli_mod.main()

    assert (func / "sub-001_ses-01_task-bar_run-01_bold.nii.gz").is_symlink()
    with open(func / "sub-001_ses-01_task-bar_run-01_bold.json") as fh:
        data = json.load(fh)
    assert data["TaskName"] == "bar"
