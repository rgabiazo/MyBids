import pandas as pd
from bidscomatic.utils.ops import apply_ops


def test_events_ops_full_pipeline() -> None:
    """Verify events OPS full pipeline behavior."""
    df = pd.DataFrame(
        {
            "onset": [0, 10, 100, 110, 200, 300],
            "duration": [3, 3, 3, 3, 3, 3],
            "trial_type": [
                "encoding_pair",
                "encoding_pair",
                "recog_pair",
                "recog_pair",
                "encoding_place",
                "recog_place",
            ],
            "stim_file": [
                "foo_OLD.bmp",
                "bar_OLD.bmp",
                "foo_OLD.bmp",
                "baz_NEW.bmp",
                "spam_OLD.bmp",
                "spam_OLD.bmp",
            ],
            "response_time": [1.0, 1.1, 2.0, 2.1, 1.5, 2.5],
            "response": ["n/a", "n/a", "HIT", "FALSE ALARM", "n/a", "MISS"],
            "run": [1, 1, 1, 1, 1, 1],
        }
    )

    ops = [
        (
            "regex_map",
            {
                "newcol": "phase",
                "from_col": "trial_type",
                "mapping": {
                    "encoding": "^encoding",
                    "recognition": "^recog",
                },
            },
        ),
        (
            "regex_extract",
            {
                "newcol": "condition",
                "from_col": "trial_type",
                "pattern": "_(?P<cond>[^_]+)$",
                "group": "cond",
                "apply_to": 'phase!="instruction"',
            },
        ),
        ("id_from", {"newcol": "stim_id", "from_col": "stim_file", "func": "basename"}),
        (
            "map_values",
            {
                "newcol": "acc_label",
                "from_col": "response",
                "mapping": {
                    "HIT": "hit",
                    "MISS": "miss",
                    "FALSE ALARM": "false_alarm",
                    "n/a": "",
                },
                "casefold": False,
            },
        ),
        (
            "join_membership",
            {
                "newcol": "probe_type",
                "keys": ["condition", "stim_id"],
                "exists_in": 'phase=="encoding"',
                "apply_to": 'phase=="recognition"',
                "true_value": "target",
                "false_value": "lure",
                "scope": "run",
            },
        ),
        (
            "join_value",
            {
                "newcol": "enc_later_outcome",
                "value_from": "acc_label",
                "keys": ["condition", "stim_id"],
                "from_rows": 'phase=="recognition"',
                "to_rows": 'phase=="encoding"',
                "default": "not_tested",
                "scope": "run",
            },
        ),
        (
            "exists_to_flag",
            {
                "newcol": "enc_is_tested",
                "keys": ["condition", "stim_id"],
                "from_rows": 'phase=="recognition"',
                "to_rows": 'phase=="encoding"',
                "true_val": 1,
                "false_val": 0,
                "scope": "run",
            },
        ),
        (
            "synth_rows",
            {
                "when": "block-start",
                "groupby": ["phase", "condition"],
                "onset": "first.onset-10",
                "duration": 10,
                "clamp_zero": True,
                "set_values": {
                    "trial_type": 'fmt("instruction_{condition}_{phase}")',
                    "phase": "instruction",
                    "is_instruction": "1",
                    "is_error": "0",
                    "acc_label": "",
                    "stim_id": "n/a",
                    "probe_type": "n/a",
                    "enc_is_tested": "0",
                    "enc_later_outcome": "n/a",
                },
            },
        ),
        (
            "flag",
            {
                "newcol": "is_error",
                "expr": ' (phase=="recognition" & acc_label in ["miss","false_alarm","no_response"]) | (phase=="encoding" & enc_later_outcome=="miss")',
                "true": 1,
                "false": 0,
            },
        ),
        (
            "index",
            {
                "newcol": "trial_n",
                "groupby": ["phase", "condition"],
                "orderby": "onset",
                "start": 1,
                "apply_to": 'phase!="instruction"',
            },
        ),
        (
            "map_values",
            {"newcol": "block_n", "from_col": "phase", "mapping": {"encoding": 1, "recognition": 2, "instruction": "n/a"}},
        ),
        (
            "map_values",
            {"newcol": "class_label", "from_col": "probe_type", "mapping": {"target": "old", "lure": "new"}},
        ),
        (
            "flag",
            {
                "newcol": "analysis_include",
                "expr": 'acc_label in ["hit","correct_rejection"]',
                "true": 1,
                "false": 0,
            },
        ),
        (
            "regex_extract",
            {
                "newcol": "novelty_type",
                "from_col": "stim_id",
                "pattern": "_(old|new)(?=\\.|$)",
                "group": 0,
                "casefold": True,
                "default": "",
            },
        ),
        (
            "map_values",
            {"newcol": "novelty_type", "from_col": "novelty_type", "mapping": {"old": "old", "new": "novel"}},
        ),
        (
            "keep_cols_if_exist",
            {
                "cols": [
                    "onset",
                    "duration",
                    "trial_type",
                    "phase",
                    "condition",
                    "stim_file",
                    "stim_id",
                    "response_time",
                    "response",
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
                ]
            },
        ),
    ]

    out = apply_ops(df, ops)

    assert out[out["phase"] == "instruction"].shape[0] == 4
    rec = out[out["phase"] == "recognition"].reset_index(drop=True)
    enc = out[out["phase"] == "encoding"].reset_index(drop=True)
    assert rec.loc[rec["stim_id"] == "foo_OLD.bmp", "probe_type"].iloc[0] == "target"
    assert rec.loc[rec["stim_id"] == "baz_NEW.bmp", "probe_type"].iloc[0] == "lure"
    assert enc.loc[enc["stim_id"] == "foo_OLD.bmp", "enc_later_outcome"].iloc[0] == "hit"
    assert enc.loc[enc["stim_id"] == "bar_OLD.bmp", "enc_later_outcome"].iloc[0] == "not_tested"
    assert enc.loc[enc["stim_id"] == "spam_OLD.bmp", "enc_later_outcome"].iloc[0] == "miss"
    assert enc.loc[enc["stim_id"] == "foo_OLD.bmp", "enc_is_tested"].iloc[0] == 1
    assert enc.loc[enc["stim_id"] == "bar_OLD.bmp", "enc_is_tested"].iloc[0] == 0
    assert rec.loc[rec["stim_id"] == "baz_NEW.bmp", "novelty_type"].iloc[0] == "novel"
    assert rec.loc[rec["stim_id"] == "foo_OLD.bmp", "novelty_type"].iloc[0] == "old"
    assert rec.loc[rec["stim_id"] == "foo_OLD.bmp", "trial_n"].iloc[0] == 1
    assert rec.loc[rec["stim_id"] == "baz_NEW.bmp", "trial_n"].iloc[0] == 2
    assert out[out["phase"] == "instruction"]["trial_n"].isna().all()
