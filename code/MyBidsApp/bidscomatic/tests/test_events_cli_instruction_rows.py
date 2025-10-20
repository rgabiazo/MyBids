from pathlib import Path
import subprocess
import pandas as pd

CLI = ["python", "-m", "bidscomatic.cli", "events"]

def test_instruction_rows_are_synthesised_and_raw_removed(tmp_path: Path) -> None:
    """Verify instruction rows ARE synthesised AND RAW removed behavior."""
    ds = tmp_path / "ds"
    ds.mkdir()
    (ds / "dataset_description.json").write_text("{}")

    behav = ds / "sourcedata" / "behavioural_task" / "sub-001"
    behav.mkdir(parents=True)
    sheet = behav / "task.csv"

    df = pd.DataFrame(
        {
            "image_file": [
                "Pair_Encoding/foo.bmp",
                "Pair_Encoding/bar.bmp",
                "Pair_Recog/foo.bmp",
                "Pair_Recog/qux.bmp",
            ],
            "InstructionText.started": [62.895, None, 180.892, None],
            "encode_onset": [72.895, 81.984, None, None],
            "recog_onset": [None, None, 190.892, 199.59],
            "encode_rt": [1.776, 2.32, None, None],
            "recog_rt": [None, None, 2.349, 1.753],
            "trial_type": [
                "Pair_Encoding",
                "Pair_Encoding",
                "Pair_Recog",
                "Pair_Recog",
            ],
            "response": ["n/a", "n/a", "HIT", "MISS"],
        }
    )
    df.to_csv(sheet, index=False)

    cmd = CLI + [
        "sourcedata/behavioural_task",
        "--img-col", "image_file",
        "--accuracy-col", "response",
        "--onset-cols", "InstructionText.started duration=10",
        "--onset-cols", "encode_onset,recog_onset duration=3",
        "--rt-cols", "encode_rt,recog_rt",
        "--trialtype-patterns", "Pair_Encoding=encoding_pair;Pair_Recog=recog_pair",
        "--task", "demo",
        "--sub", "sub-001",
        "--keep-cols", "trial_type,stim_file,response_time,response,InstructionText.started",
        "--flag", "newcol=is_instruction_raw expr='`InstructionText.started`.notnull()' true=1 false=0",
        "--set", "when='is_instruction_raw==1' set='trial_type=instruction; phase=instruction; condition=n/a; response_time=n/a; response=n/a; stim_file='",
        "--regex-map", "newcol=phase from=trial_type map=encoding:^(enc|encoding)_;recognition:^(rec|ret|recogn)[a-z]*_;instruction:^instruction",
        "--regex-extract", "newcol=condition from=trial_type pattern='_(\\w+)$' group=0 apply-to='phase!=\"instruction\"'",
        "--synth-rows", "when='block-start' groupby='phase,condition' onset='first.onset-10' duration=10 clamp-zero=true set='trial_type=fmt(\"instruction_{condition}_{phase}\"); phase=instruction; condition={condition}; is_instruction=1'",
        "--drop", "when='is_instruction_raw==1'",
        "--keep-cols-if-exist", "onset,duration,trial_type,phase,condition,is_instruction",
    ]

    subprocess.run(cmd, cwd=ds, check=True)

    out_tsv = ds / "sub-001" / "func" / "sub-001_task-demo_run-01_events.tsv"
    df_out = pd.read_csv(out_tsv, sep="\t")

    instr = df_out[df_out["phase"] == "instruction"]
    assert set(instr["trial_type"]) == {"instruction_pair_encoding", "instruction_pair_recognition"}
    assert not (df_out["trial_type"] == "instruction").any()


def test_synth_rows_positive_offset(tmp_path: Path) -> None:
    """Verify synth rows positive offset behavior."""
    ds = tmp_path / "ds"
    ds.mkdir()
    (ds / "dataset_description.json").write_text("{}")

    behav = ds / "sourcedata" / "behavioural_task" / "sub-001"
    behav.mkdir(parents=True)
    sheet = behav / "task.csv"

    df = pd.DataFrame({
        "image_file": ["Pair_Encoding/foo.bmp", "Pair_Encoding/bar.bmp"],
        "encode_onset": [1.0, 2.0],
        "encode_rt": [0.5, 0.6],
        "trial_type": ["Pair_Encoding", "Pair_Encoding"],
        "response": ["n/a", "n/a"],
    })
    df.to_csv(sheet, index=False)

    cmd = CLI + [
        "sourcedata/behavioural_task",
        "--img-col", "image_file",
        "--accuracy-col", "response",
        "--onset-cols", "encode_onset duration=3",
        "--rt-cols", "encode_rt",
        "--trialtype-patterns", "Pair_Encoding=encoding_pair",
        "--task", "demo",
        "--sub", "sub-001",
        "--keep-cols", "trial_type,stim_file,response_time,response",
        "--regex-map", "newcol=phase from=trial_type map=encoding:^(enc|encoding)_",
        "--regex-extract", "newcol=condition from=trial_type pattern='_(\\w+)$' group=0",
        "--synth-rows", "when='block-start' groupby='phase,condition' onset='first.onset+5' duration=10 clamp-zero=true set='trial_type=fmt(\"instruction_{condition}_{phase}\");phase=instruction;is_instruction=1'",
        "--keep-cols-if-exist", "onset,duration,trial_type,phase,condition,is_instruction",
    ]

    subprocess.run(cmd, cwd=ds, check=True)

    out_tsv = ds / "sub-001" / "func" / "sub-001_task-demo_run-01_events.tsv"
    df_out = pd.read_csv(out_tsv, sep="\t")
    instr = df_out[df_out["phase"] == "instruction"].iloc[0]
    assert instr["onset"] == 6.0
    assert instr["trial_type"] == "instruction_pair_encoding"


def test_synth_rows_malformed_expression(caplog) -> None:
    """Verify synth rows malformed expression behavior."""
    import logging
    from bidscomatic.utils.ops import op_synth_rows

    df = pd.DataFrame({
        "phase": ["encoding"],
        "condition": ["pair"],
        "onset": [1.0],
    })
    caplog.set_level(logging.ERROR)
    res = op_synth_rows(
        df,
        when="block-start",
        groupby=["phase", "condition"],
        onset="badexpr",
        duration=10,
        clamp_zero=True,
        set_values={},
    )
    assert res.shape[0] == 1
    assert any("onset expression" in r.message for r in caplog.records)
