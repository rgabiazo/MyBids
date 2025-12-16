import sys
from pathlib import Path

import pytest

from bids_cbrain_runner import cli as cli_mod
from bids_cbrain_runner.commands.upload import _compute_normalization_root
from bids_cbrain_runner.utils.path_normalization import normalize_file_for_upload


# ---------------------------------------------------------------------------
# 1) CLI-level test: --upload-normalize-paths is propagated correctly
# ---------------------------------------------------------------------------


def test_cli_upload_sets_normalize_flag(monkeypatch):
    """
    Check that the CLI passes rewrite_absolute_paths=True to
    upload_bids_and_sftp_files when --upload-normalize-paths is given.
    """

    # ---- Stub out config / auth so CLI.main() doesn't touch real files or network ----

    def fake_get_sftp_provider_config(provider_name: str):
        # Minimal provider config; just enough for CLI logic.
        return {
            "cbrain_base_url": "https://dummy.example",
            "cbrain_id": 51,
        }

    def fake_get_sftp_provider_config_by_id(dp_id: int):
        # Not used in this test because cbrain_id already matches upload-dp-id,
        # but it remains for completeness.
        return {
            "cbrain_base_url": "https://dummy.example",
            "cbrain_id": dp_id,
        }

    def fake_load_cbrain_config():
        return {}

    def fake_load_tools_config():
        return {}

    def fake_ensure_token(base_url, cfg_path, cfg, force_refresh, timeout):
        # What CLI expects back from ensure_token.
        return {
            "cbrain_base_url": base_url,
            "cbrain_api_token": "FAKE_TOKEN",
        }

    def fake_resolve_group_id(base_url, token, ident, per_page, timeout):
        # Pretend the group always resolves successfully.
        return 42

    # Patch functions *on the CLI module*, because that's what main() uses.
    monkeypatch.setattr(cli_mod, "get_sftp_provider_config", fake_get_sftp_provider_config)
    monkeypatch.setattr(
        cli_mod, "get_sftp_provider_config_by_id", fake_get_sftp_provider_config_by_id
    )
    monkeypatch.setattr(cli_mod, "load_cbrain_config", fake_load_cbrain_config)
    monkeypatch.setattr(cli_mod, "load_tools_config", fake_load_tools_config)
    monkeypatch.setattr(cli_mod, "ensure_token", fake_ensure_token)
    monkeypatch.setattr(cli_mod, "resolve_group_id", fake_resolve_group_id)

    # ---- Capture how upload_bids_and_sftp_files is invoked ----
    captured: dict[str, object] = {}

    def fake_upload_bids_and_sftp_files(cfg, base_url, token, steps, **kwargs):
        captured["cfg"] = cfg
        captured["base_url"] = base_url
        captured["token"] = token
        captured["steps"] = steps
        captured["kwargs"] = kwargs

    # Crucial: patch the symbol that CLI.main() calls.
    monkeypatch.setattr(cli_mod, "upload_bids_and_sftp_files", fake_upload_bids_and_sftp_files)

    # ---- Simulate the CLI invocation ----
    argv = [
        "cbrain-cli",
        "--upload-bids-and-sftp-files",
        "derivatives",
        "fsl",
        "feat",
        "fsf",
        "*.fsf",
        "--upload-register",
        "--upload-dp-id",
        "51",
        "--upload-group-id",
        "FslTest",
        "--upload-normalize-paths",
        "--upload-dry-run",
    ]
    monkeypatch.setattr(sys, "argv", argv)

    # Run the CLI; should call fake_upload_bids_and_sftp_files exactly once.
    cli_mod.main()

    assert captured, "upload_bids_and_sftp_files was not called"

    # Steps should be passed through unchanged
    assert captured["steps"] == ["derivatives", "fsl", "feat", "fsf", "*.fsf"]

    kwargs = captured["kwargs"]
    # The important bit: CLI flag becomes rewrite_absolute_paths=True
    assert kwargs.get("rewrite_absolute_paths") is True
    # The CLI call also had --upload-dry-run
    assert kwargs.get("dry_run") is True


# ---------------------------------------------------------------------------
# 2) Normalisation behaviour for derivatives / dataset-root uploads
# ---------------------------------------------------------------------------


def test_normalize_paths_derivatives_dataset_root(tmp_path):
    """
    End‑to‑end-ish unit test for the normalization helpers:

    * Create a fake BIDS dataset under tmp_path.
    * A .fsf file in derivatives/fsl/feat/fsf contains an *absolute* path
      to a BOLD NIfTI file under the dataset root.
    * Call _compute_normalization_root() to determine how this subtree will
      be rooted on CBRAIN.
    * Run normalize_file_for_upload() with that root and check that the
      absolute path is rewritten to a dataset-root-relative path like:

          sub-002/ses-01/func/...
    """
    # Fake dataset layout
    ds_root = tmp_path / "bids_ds"
    func_dir = ds_root / "sub-002" / "ses-01" / "func"
    func_dir.mkdir(parents=True, exist_ok=True)

    bold_name = (
        "sub-002_ses-01_task-assocmemory_dir-AP_run-01_"
        "space-MNI152NLin6Asym_res-2_desc-preproc_bold.nii.gz"
    )
    bold_path = func_dir / bold_name
    bold_path.write_text("dummy nifti", encoding="utf-8")

    # Absolute path as it might appear inside a design.fsf
    abs_bold = str(bold_path.resolve())

    fsf_dir = ds_root / "derivatives" / "fsl" / "feat" / "fsf"
    fsf_dir.mkdir(parents=True, exist_ok=True)
    design_fsf = fsf_dir / "design.fsf"
    design_fsf.write_text(f'set feat_files(1) "{abs_bold}"\n', encoding="utf-8")

    # Upload context: this corresponds to:
    #   --upload-bids-and-sftp-files derivatives fsl feat fsf
    path_tuple = ("derivatives", "fsl", "feat", "fsf")
    deriv_parts = ("derivatives",)

    # Ask upload code what the logical root looks like on CBRAIN
    root_rel, flatten = _compute_normalization_root(
        path_tuple=path_tuple,
        is_direct_file=False,
        deriv_parts=deriv_parts,
    )

    # Expected for derivatives trees:
    #   root_rel == Path(".")  (dataset-root semantics)
    #   flatten == False       (keep hierarchy)
    assert flatten is False
    assert isinstance(root_rel, Path)
    assert str(root_rel) in (".", "")  # normalised dataset-root

    # Minimal config: treat .fsf as text for normalisation
    cfg = {
        "path_normalization": {
            "text_extensions": [".fsf"],
        }
    }

    temp_root = tmp_path / "normalized"
    temp_root.mkdir(parents=True, exist_ok=True)

    # Run the generic text normaliser
    out_path = normalize_file_for_upload(
        design_fsf,
        dataset_root=ds_root,
        temp_root=temp_root,
        cfg=cfg,
        dry_run=False,
        root_rel=root_rel,
        flatten=flatten,
    )

    # Should have written a new file (possibly in-place if temp_root not used)
    assert out_path.exists()
    text = out_path.read_text(encoding="utf-8")

    # The absolute path should now be dataset-root relative:
    #   sub-002/ses-01/func/<bold_name>
    expected_fragment = f"sub-002/ses-01/func/{bold_name}"
    assert expected_fragment in text, f"Expected '{expected_fragment}' in:\n{text}"
    # And the original absolute path should be gone.
    assert abs_bold not in text
