# -----------------------------------------------------------------------------
# file: MyBidsApp/tests/test_loader_two_yaml.py
# -----------------------------------------------------------------------------
"""Sanity-check: series.yaml + files.yaml are merged correctly."""
from pathlib import Path
from bidscomatic.config.loader import load_config

def test_loader_merges_two_yaml(tmp_path: Path):
    # 1) Create minimal series.yaml (modalities intentionally empty)
    """Verify loader merges TWO yaml behavior."""
    series = tmp_path / "series.yaml"
    series.write_text("version: '1.0'\nmodalities: {}\n")

    # 2) Create files.yaml that adds one ignore pattern
    files = tmp_path / "files.yaml"
    files.write_text(
        "files:\n"
        "  ignore:\n"
        "    files: ['*.uid']\n"
    )

    cfg = load_config(series_path=series, files_path=files)
    assert "*.uid" in cfg.files.ignore.files
    # Modalities should still be the empty dict that was written
    assert cfg.modalities == {}
