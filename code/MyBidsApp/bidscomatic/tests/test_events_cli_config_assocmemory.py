from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pandas as pd
import yaml

CLI = ["python", "-m", "bidscomatic.cli", "events"]


def test_events_cli_config_assocmemory(tmp_path: Path) -> None:
    """Verify events CLI config assocmemory behavior."""
    ds = tmp_path / "ds"
    ds.mkdir()
    (ds / "dataset_description.json").write_text("{}")

    behav_root = ds / "sourcedata" / "behavioural_task"
    behav_root.mkdir(parents=True)
    behav = behav_root / "sub-001"
    behav.mkdir(parents=True)

    stim_map = {
        "Pair_Encoding": ["foo_OLD.bmp", "bar_OLD.bmp"],
        "Pair_Recog": ["foo_OLD.bmp", "bar_OLD.bmp", "baz_NEW.bmp"],
        "Face_Encoding": ["face1_OLD.bmp"],
        "Face_Recog": ["face1_OLD.bmp", "face2_NEW.bmp"],
    }
    for folder, names in stim_map.items():
        folder_path = behav_root / folder
        folder_path.mkdir(parents=True, exist_ok=True)
        for name in names:
            (folder_path / name).write_bytes(b"0")

    sheet = behav / "sub-001_AssocMemoryTask.csv"
    rows = [
        {
            "image_file": "Pair_Encoding/foo_OLD.bmp",
            "is_correct": "n/a",
            "encodeTrialRun1_Image.started": 5.0,
            "encodeTrialRun2_Image.started": pd.NA,
            "encodeTrialRun3_Image.started": pd.NA,
            "recogTrialRun1_Image.started": pd.NA,
            "recogTrialRun2_Image.started": pd.NA,
            "recogTrialRun3_Image.started": pd.NA,
            "encodeTrialTestKeyRespRun1.rt": 1.10,
            "encodeTrialTestKeyRespRun2.rt": pd.NA,
            "encodeTrialTestKeyRespRun3.rt": pd.NA,
            "recogTrialTestKeyRespRun1.rt": pd.NA,
            "recogTrialTestKeyRespRun2.rt": pd.NA,
            "recogTrialTestKeyRespRun3.rt": pd.NA,
        },
        {
            "image_file": "Pair_Encoding/bar_OLD.bmp",
            "is_correct": "n/a",
            "encodeTrialRun1_Image.started": 8.0,
            "encodeTrialRun2_Image.started": pd.NA,
            "encodeTrialRun3_Image.started": pd.NA,
            "recogTrialRun1_Image.started": pd.NA,
            "recogTrialRun2_Image.started": pd.NA,
            "recogTrialRun3_Image.started": pd.NA,
            "encodeTrialTestKeyRespRun1.rt": 1.05,
            "encodeTrialTestKeyRespRun2.rt": pd.NA,
            "encodeTrialTestKeyRespRun3.rt": pd.NA,
            "recogTrialTestKeyRespRun1.rt": pd.NA,
            "recogTrialTestKeyRespRun2.rt": pd.NA,
            "recogTrialTestKeyRespRun3.rt": pd.NA,
        },
        {
            "image_file": "Pair_Recog/foo_OLD.bmp",
            "is_correct": "hit",
            "encodeTrialRun1_Image.started": pd.NA,
            "encodeTrialRun2_Image.started": pd.NA,
            "encodeTrialRun3_Image.started": pd.NA,
            "recogTrialRun1_Image.started": 35.0,
            "recogTrialRun2_Image.started": pd.NA,
            "recogTrialRun3_Image.started": pd.NA,
            "encodeTrialTestKeyRespRun1.rt": pd.NA,
            "encodeTrialTestKeyRespRun2.rt": pd.NA,
            "encodeTrialTestKeyRespRun3.rt": pd.NA,
            "recogTrialTestKeyRespRun1.rt": 1.30,
            "recogTrialTestKeyRespRun2.rt": pd.NA,
            "recogTrialTestKeyRespRun3.rt": pd.NA,
        },
        {
            "image_file": "Pair_Recog/bar_OLD.bmp",
            "is_correct": "miss",
            "encodeTrialRun1_Image.started": pd.NA,
            "encodeTrialRun2_Image.started": pd.NA,
            "encodeTrialRun3_Image.started": pd.NA,
            "recogTrialRun1_Image.started": 42.0,
            "recogTrialRun2_Image.started": pd.NA,
            "recogTrialRun3_Image.started": pd.NA,
            "encodeTrialTestKeyRespRun1.rt": pd.NA,
            "encodeTrialTestKeyRespRun2.rt": pd.NA,
            "encodeTrialTestKeyRespRun3.rt": pd.NA,
            "recogTrialTestKeyRespRun1.rt": 1.45,
            "recogTrialTestKeyRespRun2.rt": pd.NA,
            "recogTrialTestKeyRespRun3.rt": pd.NA,
        },
        {
            "image_file": "Pair_Recog/baz_NEW.bmp",
            "is_correct": "CORRECT REJECTION",
            "encodeTrialRun1_Image.started": pd.NA,
            "encodeTrialRun2_Image.started": pd.NA,
            "encodeTrialRun3_Image.started": pd.NA,
            "recogTrialRun1_Image.started": 48.0,
            "recogTrialRun2_Image.started": pd.NA,
            "recogTrialRun3_Image.started": pd.NA,
            "encodeTrialTestKeyRespRun1.rt": pd.NA,
            "encodeTrialTestKeyRespRun2.rt": pd.NA,
            "encodeTrialTestKeyRespRun3.rt": pd.NA,
            "recogTrialTestKeyRespRun1.rt": 1.55,
            "recogTrialTestKeyRespRun2.rt": pd.NA,
            "recogTrialTestKeyRespRun3.rt": pd.NA,
        },
        {
            "image_file": "Face_Encoding/face1_OLD.bmp",
            "is_correct": "n/a",
            "encodeTrialRun1_Image.started": 12.0,
            "encodeTrialRun2_Image.started": pd.NA,
            "encodeTrialRun3_Image.started": pd.NA,
            "recogTrialRun1_Image.started": pd.NA,
            "recogTrialRun2_Image.started": pd.NA,
            "recogTrialRun3_Image.started": pd.NA,
            "encodeTrialTestKeyRespRun1.rt": 0.95,
            "encodeTrialTestKeyRespRun2.rt": pd.NA,
            "encodeTrialTestKeyRespRun3.rt": pd.NA,
            "recogTrialTestKeyRespRun1.rt": pd.NA,
            "recogTrialTestKeyRespRun2.rt": pd.NA,
            "recogTrialTestKeyRespRun3.rt": pd.NA,
        },
        {
            "image_file": "Face_Recog/face1_OLD.bmp",
            "is_correct": "miss",
            "encodeTrialRun1_Image.started": pd.NA,
            "encodeTrialRun2_Image.started": pd.NA,
            "encodeTrialRun3_Image.started": pd.NA,
            "recogTrialRun1_Image.started": 52.0,
            "recogTrialRun2_Image.started": pd.NA,
            "recogTrialRun3_Image.started": pd.NA,
            "encodeTrialTestKeyRespRun1.rt": pd.NA,
            "encodeTrialTestKeyRespRun2.rt": pd.NA,
            "encodeTrialTestKeyRespRun3.rt": pd.NA,
            "recogTrialTestKeyRespRun1.rt": 1.65,
            "recogTrialTestKeyRespRun2.rt": pd.NA,
            "recogTrialTestKeyRespRun3.rt": pd.NA,
        },
        {
            "image_file": "Face_Recog/face2_NEW.bmp",
            "is_correct": "FALSE ALARM",
            "encodeTrialRun1_Image.started": pd.NA,
            "encodeTrialRun2_Image.started": pd.NA,
            "encodeTrialRun3_Image.started": pd.NA,
            "recogTrialRun1_Image.started": 58.0,
            "recogTrialRun2_Image.started": pd.NA,
            "recogTrialRun3_Image.started": pd.NA,
            "encodeTrialTestKeyRespRun1.rt": pd.NA,
            "encodeTrialTestKeyRespRun2.rt": pd.NA,
            "encodeTrialTestKeyRespRun3.rt": pd.NA,
            "recogTrialTestKeyRespRun1.rt": 1.70,
            "recogTrialTestKeyRespRun2.rt": pd.NA,
            "recogTrialTestKeyRespRun3.rt": pd.NA,
        },
    ]
    pd.DataFrame(rows).to_csv(sheet, index=False)

    cfg = ds / "events.yaml"
    config = {
        "version": 1,
        "command": "events",
        "task": "assocmemory",
        "input": {
            "root": "sourcedata/behavioural_task",
            "pattern": "*AssocMemoryTask*.csv",
            "subjects": [],
            "sessions": [],
        },
        "ingest": {
            "img_col": "image_file",
            "accuracy_col": "is_correct",
            "durations": {"trial": 3.0},
            "onset_groups": [
                {
                    "onset_cols": [
                        "encodeTrialRun1_Image.started",
                        "recogTrialRun1_Image.started",
                        "encodeTrialRun2_Image.started",
                        "recogTrialRun2_Image.started",
                        "encodeTrialRun3_Image.started",
                        "recogTrialRun3_Image.started",
                    ],
                    "duration": 3.0,
                }
            ],
            "rt_cols": [
                "encodeTrialTestKeyRespRun1.rt",
                "recogTrialTestKeyRespRun1.rt",
                "encodeTrialTestKeyRespRun2.rt",
                "recogTrialTestKeyRespRun2.rt",
                "encodeTrialTestKeyRespRun3.rt",
                "recogTrialTestKeyRespRun3.rt",
            ],
            "trialtype_patterns": {
                "Pair_Encoding": "encoding_pair",
                "Face_Encoding": "encoding_face",
                "Place_Encoding": "encoding_place",
                "Pair_Recog": "recog_pair",
                "Face_Recog": "recog_face",
                "Place_Recog": "recog_place",
            },
        },
        "derive": {
            "regex_map": [
                {
                    "newcol": "phase",
                    "from": "trial_type",
                    "map": {
                        "encoding": "^(?:enc|encoding)_",
                        "recognition": "^(?:rec|ret|recogn)[a-z]*_",
                        "instruction": "^instruction",
                    },
                },
                {
                    "newcol": "acc_label",
                    "from": "response",
                    "map": {
                        "hit": r"(?i)^\s*hit\s*$",
                        "miss": r"(?i)^\s*miss\s*$",
                        "correct_rejection": r"(?i)^\s*correct\s*rej(ect(ion)?s?)?\.?\s*$",
                        "false_alarm": r"(?i)^\s*false\s*alarm\s*$",
                        "no_response": r"(?i)^\s*no\s*response\s*$",
                    },
                },
            ],
            "regex_extract": [
                {
                    "newcol": "condition",
                    "from": "trial_type",
                    "pattern": r"_(\w+)$",
                    "group": 0,
                    "apply_to": 'phase!="instruction"',
                }
            ],
            "id_from": [
                {"newcol": "stim_id", "from": "stim_file", "func": "basename"},
            ],
            "synth_rows": [
                {
                    "when": "block-start",
                    "groupby": ["phase", "condition"],
                    "onset": "first.onset-10",
                    "duration": 10.0,
                    "clamp_zero": True,
                    "set": {
                        "trial_type": 'fmt("instruction_{condition}_{phase}")',
                        "phase": "instruction",
                        "condition": "{condition}",
                        "is_instruction": "1",
                        "is_error": "0",
                        "acc_label": "",
                        "stim_id": "n/a",
                        "probe_type": "n/a",
                        "enc_is_tested": "0",
                        "enc_later_outcome": "n/a",
                    },
                }
            ],
            "map_values": [
                {
                    "newcol": "block_n",
                    "from": "phase",
                    "map": {
                        "encoding": "1",
                        "recognition": "2",
                        "instruction": "n/a",
                    },
                },
            ],
            "recode": [
                {
                    "newcol": "class_label",
                    "from": "probe_type",
                    "map": {"target": "old", "lure": "new"},
                }
            ],
            "joins": {
                "membership": {
                    "newcol": "probe_type",
                    "keys": ["condition", "stim_id"],
                    "exists_in": 'phase=="encoding"',
                    "apply_to": 'phase=="recognition"',
                    "true_value": "target",
                    "false_value": "lure",
                },
                "value": {
                    "newcol": "enc_later_outcome",
                    "value_from": "acc_label",
                    "keys": ["condition", "stim_id"],
                    "from_rows": 'phase=="recognition"',
                    "to_rows": 'phase=="encoding"',
                    "default": "not_tested",
                },
                "exists_to_flag": {
                    "newcol": "enc_is_tested",
                    "keys": ["condition", "stim_id"],
                    "from_rows": 'phase=="recognition"',
                    "to_rows": 'phase=="encoding"',
                    "true": 1,
                    "false": 0,
                },
            },
            "indices": [
                {
                    "newcol": "trial_n",
                    "groupby": ["phase", "condition"],
                    "orderby": "onset",
                    "start": 1,
                }
            ],
            "set_after_indices": [
                {
                    "when": 'acc_label==""',
                    "set": {"acc_label": "n/a"},
                },
                {
                    "when": 'phase=="instruction"',
                    "set": {"trial_n": "n/a"},
                },
            ],
            "flags": [
                {
                    "newcol": "is_error",
                    "expr": '((phase=="recognition") & ((acc_label=="miss") | (acc_label=="false_alarm") | (acc_label=="no_response"))) | ((phase=="encoding") & (enc_later_outcome=="miss"))',
                    "true": 1,
                    "false": 0,
                },
                {
                    "newcol": "analysis_include",
                    "expr": '(phase=="recognition") & ((acc_label=="hit") | (acc_label=="correct_rejection"))',
                    "true": 1,
                    "false": 0,
                },
            ],
            "optional": {
                "novelty": {
                    "enabled": True,
                    "regex_extract": {
                        "newcol": "novelty_type",
                        "from": "stim_id",
                        "pattern": r"_(old|new)(?=[.]|$)",
                        "group": 0,
                        "casefold": True,
                        "default": "",
                    },
                    "map_values": {
                        "newcol": "novelty_type",
                        "from": "novelty_type",
                        "map": {"old": "old", "new": "novel"},
                    },
                }
            },
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
                "class_label",
                "novelty_type",
                "analysis_include",
            ],
            "create_stimuli_directory": True,
            "create_events_json": True,
            "sidecar": {
                "field_descriptions": {
                    "onset": "Start time of the event measured from the beginning of the run.",
                    "duration": "Duration of the event.",
                    "trial_type": "Experimental condition label for each trial.",
                    "stim_file": "Relative path (from the dataset root) to the bitmap shown on that trial. Paths should begin with 'stimuli/'.",
                    "response_time": "Latency between stimulus onset and the participant’s button press.",
                    "response": "Behavioural accuracy category for the recognition trial.",
                    "phase": "Stage parsed from trial_type (encoding/recognition/instruction).",
                    "condition": "Condition parsed from trial_type (e.g., face/place/pair).",
                    "stim_id": "Basename of stim_file; used as join key across phases.",
                    "acc_label": "Normalized behavioural outcome (hit/miss/correct_rejection/false_alarm/no_response); blank on encoding.",
                    "probe_type": "For recognition, target if a matching encoding instance exists in the run; else lure.",
                    "enc_is_tested": "For encoding trials, whether a recognition probe occurred for this item in the run (0/1).",
                    "enc_later_outcome": "For encoding trials, the recognition outcome for the same item, or not_tested.",
                    "is_instruction": "Instruction row placed at each (phase,condition) block start (10 s before first trial).",
                    "is_error": "Incorrect/missed recognition or encoding item later missed (0/1).",
                    "block_n": "Within-run block index: encoding=1, recognition=2, instruction=n/a.",
                    "trial_n": "Within (phase,condition), 1-based trial index ordered by onset; blank on instruction.",
                    "class_label": "MVPA convenience label: old for target, new for lure.",
                    "novelty_type": "If inferable from filename, old vs novel probe.",
                    "analysis_include": "Mask flag for correct trials (hit/correct_rejection) (0/1).",
                },
                "field_units": {"response_time": "seconds"},
                "field_levels": {
                    "probe_type": {
                        "target": "Old (studied) item",
                        "lure": "New (unstudied) item",
                    },
                    "acc_label": {
                        "hit": "Correct old",
                        "miss": "Missed old",
                        "correct_rejection": "Correct new",
                        "false_alarm": "Incorrect old",
                        "no_response": "No keypress",
                    },
                },
            },
        },
    }
    cfg.write_text(yaml.safe_dump(config, sort_keys=False))

    subprocess.run(CLI + ["--config", "events.yaml"], cwd=ds, check=True)

    out_tsv = ds / "sub-001" / "func" / "sub-001_task-assocmemory_run-01_events.tsv"
    assert out_tsv.exists()

    df = pd.read_csv(out_tsv, sep="\t", keep_default_na=False)

    instr = df[df["phase"] == "instruction"]
    assert not instr.empty
    assert set(instr["is_instruction"]) == {"1"}
    assert set(instr["trial_n"]) == {"n/a"}

    encoding = df[df["phase"] == "encoding"].set_index("stim_id")
    assert str(encoding.loc["foo_OLD.bmp", "enc_is_tested"]) == "1"
    assert encoding.loc["foo_OLD.bmp", "enc_later_outcome"] == "hit"
    assert encoding.loc["foo_OLD.bmp", "acc_label"] == "n/a"
    assert encoding.loc["bar_OLD.bmp", "enc_later_outcome"] == "miss"
    assert str(encoding.loc["bar_OLD.bmp", "is_error"]) == "1"

    recognition = df[df["phase"] == "recognition"].set_index("stim_id")
    assert recognition.loc["foo_OLD.bmp", "probe_type"] == "target"
    assert recognition.loc["foo_OLD.bmp", "class_label"] == "old"
    assert str(recognition.loc["foo_OLD.bmp", "analysis_include"]) == "1"
    assert str(recognition.loc["bar_OLD.bmp", "is_error"]) == "1"
    assert recognition.loc["baz_NEW.bmp", "probe_type"] == "lure"
    assert recognition.loc["baz_NEW.bmp", "class_label"] == "new"
    assert str(recognition.loc["baz_NEW.bmp", "analysis_include"]) == "1"
    assert recognition.loc["baz_NEW.bmp", "novelty_type"] == "novel"
    assert str(recognition.loc["face2_NEW.bmp", "is_error"]) == "1"

    for stim in ["foo_OLD.bmp", "baz_NEW.bmp", "face2_NEW.bmp"]:
        assert (ds / "stimuli" / stim).exists()

    sidecar = json.loads(out_tsv.with_suffix(".json").read_text())
    assert sidecar["onset"]["Description"].startswith("Start time of the event")
    assert sidecar["response_time"]["Units"] == "seconds"
    assert sidecar["probe_type"]["Levels"]["lure"] == "New (unstudied) item"
