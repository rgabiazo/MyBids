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
    monkeypatch.setattr(cli_mod, "get_sftp_provider_config", lambda provider_name=None: {})
    monkeypatch.setattr(cli_mod, "load_cbrain_config", lambda: {})
    monkeypatch.setattr(cli_mod, "load_tools_config", lambda: {})
    monkeypatch.setattr(
        cli_mod,
        "ensure_token",
        lambda **kw: {"cbrain_api_token": "tok", "cbrain_base_url": "https://x"},
    )


def test_cli_upload_steps_stripped(monkeypatch):
    cli_mod = _import_cli_with_stubs()
    _common_patches(monkeypatch, cli_mod)

    up_steps = []
    monkeypatch.setattr(
        cli_mod,
        "upload_bids_and_sftp_files",
        lambda cfg, base_url, token, steps, **kw: up_steps.append(steps),
    )

    argv = [
        "prog",
        "--upload-bids-and-sftp-files",
        "derivatives",
        "  license.txt",
    ]
    monkeypatch.setattr(sys, "argv", argv)
    cli_mod.main()

    assert up_steps and up_steps[0] == ["derivatives", "license.txt"]
