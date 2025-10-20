from pathlib import Path
import subprocess
import pandas as pd
import yaml

CLI = ["python", "-m", "bidscomatic.cli", "events"]

def test_events_cli_config_full(tmp_path: Path) -> None:
    """Verify events CLI config full behavior."""
    ds = tmp_path / "ds"
    ds.mkdir()
    (ds / "dataset_description.json").write_text("{}")

    behav = ds / "sourcedata" / "behavioural_task"
    (behav / "sub-001").mkdir(parents=True)
    (behav / "Pair_Encoding").mkdir()
    (behav / "Pair_Recog").mkdir()
    for stim in ["foo_old.bmp", "bar_old.bmp"]:
        (behav / "Pair_Encoding" / stim).write_bytes(b"0")
    for stim in ["foo_old.bmp", "bar_old.bmp", "baz_new.bmp", "qux_new.bmp"]:
        (behav / "Pair_Recog" / stim).write_bytes(b"0")

    sheet = behav / "sub-001" / "task.csv"
    df = pd.DataFrame(
        {
            "image_file": [
                "Pair_Encoding/foo_old.bmp",
                "Pair_Encoding/bar_old.bmp",
                "Pair_Recog/foo_old.bmp",
                "Pair_Recog/bar_old.bmp",
                "Pair_Recog/baz_new.bmp",
                "Pair_Recog/qux_new.bmp",
            ],
            "onset_Run1": [5, 8, 15, 20, 25, 30],
            "rt_Run1": [1.1, 1.2, 2.1, 1.5, 2.2, 0.0],
            "trial_type": [
                "Pair_Encoding",
                "Pair_Encoding",
                "Pair_Recog",
                "Pair_Recog",
                "Pair_Recog",
                "Pair_Recog",
            ],
            "response": [
                "n/a",
                "n/a",
                "HIT",
                "MISS",
                "CORRECT REJECTION",
                "NO RESPONSE",
            ],
        }
    )
    df.to_csv(sheet, index=False)

    cfg = ds / "events.yaml"
    config = {
        "version": 1,
        "command": "events",
        "task": "demo",
        "input": {"root": "sourcedata/behavioural_task", "pattern": "*.csv"},
        "ingest": {
            "img_col": "image_file",
            "accuracy_col": "response",
            "onset_groups": [{"onset_cols": ["onset_Run1"], "duration": 3}],
            "rt_cols": ["rt_Run1"],
            "trialtype_patterns": {
                "Pair_Encoding": "encoding_pair",
                "Pair_Recog": "recog_pair",
            },
        },
        "derive": {
            "regex_map": [
                {
                    "newcol": "phase",
                    "from": "trial_type",
                    "map": {
                        "encoding": "^(enc|encoding)_",
                        "recognition": "^(rec|ret|recogn)[a-z]*_",
                    },
                }
            ],
            "regex_extract": [
                {
                    "newcol": "condition",
                    "from": "trial_type",
                    "pattern": "_(?P<cond>[^_]+)$",
                    "group": "cond",
                }
            ],
            "id_from": [{"newcol": "stim_id", "from": "stim_file", "func": "basename"}],
            "map_values": [
                {
                    "newcol": "acc_label",
                    "from": "response",
                    "casefold": True,
                    "map": {
                        "hit": "hit",
                        "miss": "miss",
                        "correct rejection": "correct_rejection",
                        "false alarm": "false_alarm",
                        "no response": "no_response",
                        "n/a": "",
                    },
                }
            ],
            "joins": {
                "membership": {
                    "newcol": "probe_type",
                    "keys": ["condition", "stim_id"],
                    "exists_in": "phase==\"encoding\"",
                    "apply_to": "phase==\"recognition\"",
                    "true_value": "target",
                    "false_value": "lure",
                },
                "value": {
                    "newcol": "enc_later_outcome",
                    "value_from": "acc_label",
                    "keys": ["condition", "stim_id"],
                    "from_rows": "phase==\"recognition\"",
                    "to_rows": "phase==\"encoding\"",
                    "default": "not_tested",
                },
                "exists_to_flag": {
                    "newcol": "enc_is_tested",
                    "keys": ["condition", "stim_id"],
                    "from_rows": "phase==\"recognition\"",
                    "to_rows": "phase==\"encoding\"",
                    "true": 1,
                    "false": 0,
                },
            },
            "synth_rows": [
                {
                    "when": "block-start",
                    "groupby": ["phase", "condition"],
                    "onset": "first.onset-10",
                    "duration": 10,
                    "clamp_zero": True,
                    "set": {
                        "trial_type": 'fmt("instruction_{condition}_{phase}")',
                        "phase": "instruction",
                        "is_instruction": 1,
                        "is_error": 0,
                        "acc_label": "",
                        "stim_id": "n/a",
                        "probe_type": "n/a",
                        "enc_is_tested": 0,
                        "enc_later_outcome": "n/a",
                    },
                }
            ],
            "flags": [
                {
                    "newcol": "is_error",
                    "expr": "(phase=='recognition' & acc_label in ['miss','false_alarm','no_response']) | (phase=='encoding' & enc_later_outcome=='miss')",
                    "true": 1,
                    "false": 0,
                },
                {
                    "newcol": "analysis_include",
                    "expr": "acc_label in ['hit','correct_rejection']",
                    "true": 1,
                    "false": 0,
                },
            ],
            "indices": [
                {
                    "newcol": "trial_n",
                    "groupby": ["phase", "condition"],
                    "orderby": "onset",
                    "start": 1,
                }
            ],
            "recode": [
                {
                    "newcol": "block_n",
                    "from": "phase",
                    "map": {"encoding": 1, "recognition": 2, "instruction": "n/a"},
                }
            ],
        },
        "output": {
            "keep_cols": ["trial_type", "stim_file", "response_time", "response"],
            "keep_cols_if_exist": [
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
                "probe_type",
                "enc_is_tested",
                "enc_later_outcome",
                "is_instruction",
                "is_error",
                "block_n",
                "trial_n",
                "analysis_include",
            ],
            "create_events_json": True,
        },
    }
    cfg.write_text(yaml.safe_dump(config))

    subprocess.run(CLI + ["--config", "events.yaml"], cwd=ds, check=True)

    out_tsv = ds / "sub-001" / "func" / "sub-001_task-demo_run-01_events.tsv"
    df_out = pd.read_csv(out_tsv, sep="\t")

    assert df_out.loc[0, "onset"] == 0.0
    recog = df_out[df_out["phase"] == "recognition"].set_index("stim_id")
    assert recog.loc["foo_old.bmp", "probe_type"] == "target"
    assert recog.loc["baz_new.bmp", "probe_type"] == "lure"
    enc = df_out[df_out["phase"] == "encoding"].set_index("stim_id")
    assert enc.loc["foo_old.bmp", "enc_is_tested"] == 1
    assert enc.loc["bar_old.bmp", "enc_later_outcome"] == "miss"
    assert df_out[df_out["acc_label"] == "miss"]["is_error"].iloc[0] == 1
    assert df_out[df_out["acc_label"] == "hit"]["analysis_include"].iloc[0] == 1
