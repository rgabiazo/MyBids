# code/cbrain_bids_pipeline/tests/test_config_loading.py

import json
import logging
import os

import yaml

from bids_cbrain_runner import __version__
from bids_cbrain_runner.api.config_loaders import load_pipeline_config
from bids_cbrain_runner.utils.download_utils import (
    maybe_write_dataset_description,
    resolve_output_dir,
)

LOG = logging.getLogger(__name__)


def write_minimal_defaults(tmpdir):
    """Create a minimal defaults.yaml inside a fake package install."""
    cfg = {
        "cbrain": {
            "hippunfold": {
                "hippunfold_output_dir": "derivatives/custom_hippunfold"
            }
        },
        "dataset_descriptions": {
            "cbrain": {
                "hippunfold": {
                    "name": "Default Hippunfold Name",
                    "bids_version": "1.10.0",
                    "dataset_type": "derivative",
                    "description": "Default description",
                    "generatedby": [
                        {
                            "name": "Hippunfold",
                            "version": "1.5.2",
                            "codeURL": "https://github.com/khanlab/hippunfold",
                            "description": "Used for hippocampal segmentations."
                        },
                        {
                            "name": "CBRAIN",
                            "version": "6.3.0",
                            "codeURL": "https://github.com/aces/cbrain",
                            "description": "Used to execute hippunfold."
                        }
                    ]
                }
            }
        }
    }
    pkg_cfg_dir = os.path.join(tmpdir, "bids_cbrain_runner", "api", "config")
    os.makedirs(pkg_cfg_dir, exist_ok=True)
    with open(os.path.join(pkg_cfg_dir, "defaults.yaml"), "w", encoding="utf-8") as f:
        yaml.safe_dump(cfg, f)


def write_external_override(tmproot):
    """Under <BIDS_ROOT>/code/config, write a config.yaml that overrides defaults."""
    override = {
        "cbrain": {
            "hippunfold": {
                "hippunfold_output_dir": "derivatives/custom_hippunfold"
            }
        },
        "dataset_descriptions": {
            "cbrain": {
                "hippunfold": {
                    "name": "Overridden Hippunfold Name",
                    "description": "This came from the external override."
                }
            }
        }
    }

    config_dir = os.path.join(tmproot, "code", "config")
    os.makedirs(config_dir, exist_ok=True)
    with open(os.path.join(config_dir, "config.yaml"), "w", encoding="utf-8") as f:
        yaml.safe_dump(override, f)
    return os.path.join(config_dir, "config.yaml")


def test_pipeline_config_and_description(tmp_path, monkeypatch, caplog):
    """
    1) Create a fake install-layout under tmp_path:
       - <tmp_path>/bids_cbrain_runner/api/config/defaults.yaml
    2) Create a fake BIDS root with dataset_description.json in a temp folder.
    3) Put an override at <BIDS_ROOT>/code/config/config.yaml
    4) cd into BIDS_ROOT, call load_pipeline_config(), then verify
       resolve_output_dir() and maybe_write_dataset_description().
    """

    # Capture INFO-level logs
    caplog.set_level(logging.INFO)

    # 1) Fake the “installed” package by copying in our own minimal defaults.yaml
    pkg_root = tmp_path / "fake_install"
    write_minimal_defaults(str(pkg_root))

    # Monkey-patch PYTHONPATH so that imports find our fake install first
    monkeypatch.setenv("PYTHONPATH", str(pkg_root) + os.pathsep + os.environ.get("PYTHONPATH", ""))
    monkeypatch.chdir(str(pkg_root))

    # 2) Create a fake BIDS root under tmp_path/BIDS_test
    bids_test = tmp_path / "BIDS_test"
    bids_test.mkdir()
    ds_desc = {"Name": "MyFakeBIDS", "BIDSVersion": "1.6.0"}
    with open(str(bids_test / "dataset_description.json"), "w", encoding="utf-8") as f:
        json.dump(ds_desc, f)

    # 3) Write the override config under <BIDS_ROOT>/code/config/config.yaml
    write_external_override(str(bids_test))

    # 4) cd into BIDS_ROOT and call load_pipeline_config()
    monkeypatch.chdir(str(bids_test))
    cfg = load_pipeline_config()

    # Verify that our override was merged
    assert "cbrain" in cfg
    assert "hippunfold" in cfg["cbrain"]

    # 5) Now test resolve_output_dir + maybe_write_dataset_description
    outdir = resolve_output_dir(str(bids_test), "hippunfold", cfg)
    assert outdir.endswith("derivatives/custom_hippunfold")

    # 6) Write dataset_description.json into the new output folder:
    maybe_write_dataset_description(outdir, "hippunfold", cfg, dry_run=False)

    desc_file = os.path.join(outdir, "dataset_description.json")
    assert os.path.exists(desc_file), "dataset_description.json should have been created"
    with open(desc_file, "r", encoding="utf-8") as f:
        dd = json.load(f)
    assert dd["Name"] == "Overridden Hippunfold Name"
    assert any(
        g.get("Name") == "cbrain_bids_pipeline" and g.get("Version") == __version__
        for g in dd.get("GeneratedBy", [])
    )
