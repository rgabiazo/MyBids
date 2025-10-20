from __future__ import annotations

from pathlib import Path
import subprocess
import pandas as pd
import yaml
from importlib import resources

CLI = ["python", "-m", "bidscomatic.cli", "events"]

def test_events_config_template_roundtrip(tmp_path: Path) -> None:
    """Verify events config template roundtrip behavior."""
    ds = tmp_path / "ds"
    ds.mkdir()
    (ds / "dataset_description.json").write_text("{}")

    behav = ds / "sourcedata" / "behavioural_task" / "sub-001"
    behav.mkdir(parents=True)
    sheet = behav / "task.csv"
    df = pd.DataFrame(
        {
            "image_file": ["Pair_Encoding/stim1.bmp", "Pair_Recog/stim2.bmp"],
            "onset": [1.0, 5.0],
            "rt": [0.5, 0.7],
            "trial_type": ["Pair_Encoding", "Pair_Recog"],
            "response": ["n/a", "HIT"],
        }
    )
    df.to_csv(sheet, index=False)

    tpl_path = resources.files("bidscomatic.resources") / "events_template.yaml"
    cfg = yaml.safe_load(tpl_path.read_text())

    cfg["task"] = "demo"
    cfg["input"]["root"] = "sourcedata/behavioural_task"
    cfg["input"]["pattern"] = "*.csv"
    cfg["input"]["subjects"] = []
    cfg["input"]["sessions"] = []

    ingest = cfg["ingest"]
    ingest["img_col"] = "image_file"
    ingest["accuracy_col"] = "response"
    ingest["trialtype_col"] = "trial_type"
    ingest["durations"] = {"instruction": 10, "trial": 3}
    ingest["onset_groups"] = [{"onset_cols": ["onset"], "duration": 3}]
    ingest["rt_cols"] = ["rt"]
    ingest["trialtype_patterns"] = {"Pair_Encoding": "encoding_pair", "Pair_Recog": "recog_pair"}

    derive = cfg["derive"]
    derive["regex_map"] = [
        {
            "newcol": "phase",
            "from": "trial_type",
            "map": {
                "encoding": "^(enc|encoding)_",
                "recognition": "^(rec|ret|recogn)[a-z]*_",
            },
        }
    ]
    derive["regex_extract"] = [
        {
            "newcol": "condition",
            "from": "trial_type",
            "pattern": "_(\\w+)$",
            "group": 1,
        }
    ]
    derive["id_from"] = [{"newcol": "stim_id", "from": "stim_file", "func": "basename"}]
    derive["map_values"] = [
        {
            "newcol": "acc_label",
            "from": "response",
            "casefold": True,
            "map": {"hit": "hit", "miss": "miss", "n/a": ""},
        }
    ]

    output = cfg["output"]
    output["keep_cols"] = ["trial_type", "stim_file", "response_time", "response"]
    output["keep_cols_if_exist"] = [
        "onset",
        "duration",
        "trial_type",
        "stim_file",
        "response_time",
        "response",
        "phase",
        "condition",
        "stim_id",
        "acc_label",
    ]
    output["create_events_json"] = True

    cfg_path = ds / "events.yaml"
    cfg_path.write_text(yaml.safe_dump(cfg))

    subprocess.run(CLI + ["--config", str(cfg_path.name)], cwd=ds, check=True)

    out_tsv = ds / "sub-001" / "func" / "sub-001_task-demo_run-01_events.tsv"
    df_out = pd.read_csv(out_tsv, sep="\t")
    assert list(df_out["trial_type"]) == ["encoding_pair", "recog_pair"]
    assert df_out.loc[1, "acc_label"] == "hit"
