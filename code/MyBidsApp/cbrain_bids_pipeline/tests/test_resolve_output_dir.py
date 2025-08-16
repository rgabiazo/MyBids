from bids_cbrain_runner.utils.download_utils import resolve_output_dir


def test_resolve_output_dir_dry_run(tmp_path):
    bids_root = tmp_path / "dataset"
    bids_root.mkdir()
    out = resolve_output_dir(
        bids_root=str(bids_root),
        tool_name="hippunfold",
        config_dict=None,
        force=True,
        dry_run=True,
    )
    expected = bids_root / "derivatives" / "hippunfold"
    assert out == str(expected)
    assert not expected.exists()


def test_resolve_output_dir_override(tmp_path):
    bids_root = tmp_path / "dataset"
    bids_root.mkdir()
    out = resolve_output_dir(
        bids_root=str(bids_root),
        tool_name="hippunfold",
        config_dict=None,
        output_dir_name="DeepPrep",
        force=True,
        dry_run=True,
    )
    expected = bids_root / "derivatives" / "DeepPrep"
    assert out == str(expected)
    assert not expected.exists()


def test_resolve_output_dir_cli_precedence(tmp_path):
    bids_root = tmp_path / "dataset"
    bids_root.mkdir()
    cfg = {
        "cbrain": {"hippunfold": {"hippunfold_output_dir": "derivatives/config_path"}}
    }
    out = resolve_output_dir(
        bids_root=str(bids_root),
        tool_name="hippunfold",
        config_dict=cfg,
        output_dir_name="cli_path",
        force=True,
        dry_run=True,
    )
    expected = bids_root / "derivatives" / "cli_path"
    assert out == str(expected)
    assert not (bids_root / "derivatives" / "config_path").exists()
