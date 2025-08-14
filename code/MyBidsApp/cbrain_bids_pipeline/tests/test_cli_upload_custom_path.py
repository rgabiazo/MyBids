import sys
import types


def _import_cli_with_stubs():
    stub = types.ModuleType("bids_cbrain_runner.api.client_openapi")
    stub.ApiException = Exception

    class CbrainClient: ...

    stub.CbrainClient = CbrainClient
    stub.CbrainTaskError = Exception
    sys.modules["bids_cbrain_runner.api.client_openapi"] = stub

    from bids_cbrain_runner import cli as cli_mod

    return cli_mod


def _common_patches(monkeypatch, cli_mod):
    monkeypatch.setattr(
        cli_mod, "get_sftp_provider_config", lambda provider_name=None: {}
    )
    monkeypatch.setattr(cli_mod, "load_cbrain_config", lambda: {})
    monkeypatch.setattr(cli_mod, "load_tools_config", lambda: {})
    monkeypatch.setattr(
        cli_mod,
        "ensure_token",
        lambda **kw: {"cbrain_api_token": "tok", "cbrain_base_url": "https://x"},
    )


def test_cli_upload_remote_root_and_map(monkeypatch):
    cli_mod = _import_cli_with_stubs()
    _common_patches(monkeypatch, cli_mod)

    kwargs_list = []

    def _fake_upload(cfg, base_url, token, steps, **kwargs):
        kwargs_list.append(kwargs)

    monkeypatch.setattr(cli_mod, "upload_bids_and_sftp_files", _fake_upload)

    argv = [
        "prog",
        "--upload-bids-and-sftp-files",
        "derivatives",
        "DeepPrep",
        "BOLD",
        "--upload-remote-root",
        "fmriprep/BOLD",
        "--upload-path-map",
        "anat=ses-01/anat",
    ]
    monkeypatch.setattr(sys, "argv", argv)
    cli_mod.main()

    assert kwargs_list
    assert kwargs_list[0]["remote_root"] == "fmriprep/BOLD"
    assert kwargs_list[0]["path_map"] == {"anat": "ses-01/anat"}

