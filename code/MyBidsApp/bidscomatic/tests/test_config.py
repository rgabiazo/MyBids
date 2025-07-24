# -----------------------------------------------------------------------------
# file: MyBidsApp/tests/test_config.py
# -----------------------------------------------------------------------------
"""Smoke tests for the config loader.

Run from the repository root with:
    pytest -c code/MyBidsApp/pytest.ini -q
"""
from pathlib import Path

from bidscomatic import load_config
from importlib.resources import files
import yaml


def test_default_yaml_loads():
    """Loading the built‑in default YAML should succeed."""
    # Dataset root = repo root (three levels up from this file)
    root = Path(__file__).resolve().parents[4]  # → BIDS-ProjectDev

    cfg = load_config(dataset_root=root)

    # Minimal sanity checks – if these fail the YAML/schema mismatch.
    with files("bidscomatic.resources").joinpath("default_series.yaml").open() as fh:
        expected_version = yaml.safe_load(fh)["version"]
    assert cfg.version == expected_version
    assert "anatomical" in cfg.modalities
    assert "functional" in cfg.modalities
