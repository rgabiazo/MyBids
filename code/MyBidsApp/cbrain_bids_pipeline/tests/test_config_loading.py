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
        "roots": {"derivatives_root": "derivatives"},
        "cbrain": {
            "hippunfold": {
                "hippunfold_output_dir": "derivatives/custom_hippunfold"
            },
            "fmriprep": {
                "fmriprep_output_dir": "derivatives/custom_fmriprep"
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
                },
                "fmriprep": {
                    "name": "Default fMRIPrep Name",
                    "bids_version": "1.10.0",
                    "dataset_type": "derivative",
                    "description": "Default description",
                    "generatedby": [
                        {
                            "name": "fMRIPrep",
                            "version": "23.0.2",
                            "codeURL": "https://github.com/nipreps/fmriprep",
                            "description": "Used for BIDS-compliant fMRI preprocessing."
                        },
                        {
                            "name": "CBRAIN",
                            "version": "6.3.0",
                            "codeURL": "https://github.com/aces/cbrain",
                            "description": "Used to execute fMRIPrep."
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
            },
            "fmriprep": {
                "fmriprep_output_dir": "derivatives/custom_fmriprep"
            }
        },
        "dataset_descriptions": {
            "cbrain": {
                "hippunfold": {
                    "name": "Overridden Hippunfold Name",
                    "description": "This came from the external override."
                },
                "fmriprep": {
                    "name": "Overridden fMRIPrep Name",
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

    # 1) Fake the “installed” package by copying in a minimal defaults.yaml
    pkg_root = tmp_path / "fake_install"
    write_minimal_defaults(str(pkg_root))

    # Monkey-patch PYTHONPATH so that imports find the fake install first
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

    assert cfg["derivatives_root"] == "derivatives"
    assert cfg.get("roots", {}).get("derivatives_root") == "derivatives"

    # Verify that the override was merged
    assert "cbrain" in cfg
    assert "hippunfold" in cfg["cbrain"]
    assert "fmriprep" in cfg["cbrain"]

    # 5) Now test resolve_output_dir + maybe_write_dataset_description for both tools
    outdir = resolve_output_dir(str(bids_test), "hippunfold", cfg)
    assert outdir.endswith("derivatives/custom_hippunfold")
    outdir_fmriprep = resolve_output_dir(str(bids_test), "fmriprep", cfg)
    assert outdir_fmriprep.endswith("derivatives/custom_fmriprep")

    # 6) Write dataset_description.json into the new output folder for both
    maybe_write_dataset_description(outdir, "hippunfold", cfg, dry_run=False)
    maybe_write_dataset_description(outdir_fmriprep, "fmriprep", cfg, dry_run=False)

    desc_file = os.path.join(outdir, "dataset_description.json")
    assert os.path.exists(desc_file)
    with open(desc_file, "r", encoding="utf-8") as f:
        dd = json.load(f)
    assert dd["Name"] == "Overridden Hippunfold Name"
    assert any(
        g.get("Name") == "cbrain_bids_pipeline" and g.get("Version") == __version__
        for g in dd.get("GeneratedBy", [])
    )
    desc_file2 = os.path.join(outdir_fmriprep, "dataset_description.json")
    assert os.path.exists(desc_file2)
    with open(desc_file2, "r", encoding="utf-8") as f:
        dd2 = json.load(f)
    assert dd2["Name"] == "Overridden fMRIPrep Name"
    assert any(
        g.get("Name") == "cbrain_bids_pipeline" and g.get("Version") == __version__
        for g in dd2.get("GeneratedBy", [])
    )


def test_maybe_write_dataset_description_deepprep(tmp_path, monkeypatch):
    """maybe_write_dataset_description handles deepprep metadata."""

    cfg = {
        "dataset_descriptions": {
            "cbrain": {
                "deepprep": {
                    "name": "DeepPrep (via CBRAIN)",
                    "bids_version": "1.10.0",
                    "dataset_type": "derivative",
                    "description": "DeepPrep pipeline output via CBRAIN",
                    "generatedby": [
                        {
                            "name": "DeepPrep",
                            "version": "24.1.2",
                            "codeURL": "",
                            "description": "Used for DeepPrep preprocessing.",
                        },
                        {
                            "name": "CBRAIN",
                            "version": "6.3.0",
                            "codeURL": "https://github.com/aces/cbrain",
                            "description": "Used to execute DeepPrep.",
                        },
                    ],
                }
            }
        }
    }

    outdir = tmp_path / "deepprep"
    outdir.mkdir()
    maybe_write_dataset_description(str(outdir), "deepprep", cfg, dry_run=False)

    assert (outdir / "dataset_description.json").exists()
