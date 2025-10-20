from pathlib import Path
import subprocess
import pandas as pd

CLI = ["python", "-m", "bidscomatic.cli", "events"]

def test_events_cli_full_pipeline(tmp_path: Path) -> None:
    """Verify events CLI full pipeline behavior."""
    ds = tmp_path / "ds"
    ds.mkdir()
    (ds / "dataset_description.json").write_text("{}")

    behav = ds / "sourcedata" / "behavioural_task"
    (behav / "sub-001").mkdir(parents=True)
    # create dummy stimulus files
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

    subprocess.run(
        CLI
        + [
            "sourcedata/behavioural_task",
            "--img-col",
            "image_file",
            "--accuracy-col",
            "response",
            "--onset-cols",
            "onset_Run1",
            "--rt-cols",
            "rt_Run1",
            "--duration",
            "3",
            "--trialtype-patterns",
            "Pair_Encoding=encoding_pair;Pair_Recog=recog_pair",
            "--task",
            "demo",
            "--sub",
            "sub-001",
            "--keep-cols",
            "trial_type,stim_file,response_time,response",
            "--regex-map",
            "newcol=phase from=trial_type map=encoding:^(enc|encoding)_;recognition:^(rec|ret|recogn)[a-z]*_;instruction:^instruction_",
            "--regex-extract",
            "newcol=condition from=trial_type pattern=_(?P<cond>[^_]+)$ group=cond apply-to='phase!=\"instruction\"'",
            "--id-from",
            "newcol=stim_id from=stim_file func=basename",
            "--map-values",
            "newcol=acc_label from=response casefold=true map='hit=hit;miss=miss;correct rejection=correct_rejection;false alarm=false_alarm;no response=no_response;n/a='",
            "--join-membership",
            "newcol=probe_type keys=condition,stim_id exists-in='phase==\"encoding\"' apply-to='phase==\"recognition\"' true-value=target false-value=lure",
            "--join-value",
            "newcol=enc_later_outcome value-from=acc_label keys=condition,stim_id from-rows='phase==\"recognition\"' to-rows='phase==\"encoding\"' default=not_tested",
            "--exists-to-flag",
            "newcol=enc_is_tested keys=condition,stim_id from-rows='phase==\"recognition\"' to-rows='phase==\"encoding\"' true=1 false=0",
            "--synth-rows",
            "when=block-start groupby=phase,condition onset=first.onset-10 duration=10 clamp-zero=true set=trial_type=fmt(\"instruction_{condition}_{phase}\");phase=instruction;is_instruction=1;is_error=0;acc_label=;stim_id=n/a;probe_type=n/a;enc_is_tested=0;enc_later_outcome=n/a",
            "--flag",
            "newcol=is_error expr='(phase==\"recognition\" & acc_label in [\"miss\",\"false_alarm\",\"no_response\"]) | (phase==\"encoding\" & enc_later_outcome==\"miss\")' true=1 false=0",
            "--index",
            "newcol=trial_n groupby=phase,condition orderby=onset start=1",
            "--map-values",
            "newcol=block_n from=phase map=encoding=1;recognition=2;instruction=n/a",
            "--flag",
            "newcol=analysis_include expr='acc_label in [\"hit\",\"correct_rejection\"]' true=1 false=0",
            "--regex-extract",
            "newcol=novelty_type from=stim_file pattern=_(?P<nov>(old|new))(?=\\.|$) group=nov casefold=true default=",
            "--map-values",
            "newcol=novelty_type from=novelty_type map=old=old;new=novel",
            "--keep-cols-if-exist",
            "onset,duration,trial_type,stim_file,response_time,response,phase,condition,stim_id,acc_label,probe_type,enc_is_tested,enc_later_outcome,is_instruction,is_error,block_n,trial_n,novelty_type,analysis_include",
            "--create-events-json",
            "--create-stimuli-directory",
        ],
        cwd=ds,
        check=True,
    )

    out_tsv = ds / "sub-001" / "func" / "sub-001_task-demo_run-01_events.tsv"
    df_out = pd.read_csv(out_tsv, sep="\t")

    # instruction row clamped to zero onset
    assert df_out.loc[0, "trial_type"].startswith("instruction_")
    assert df_out.loc[0, "onset"] == 0.0

    # verify response mapping coverage
    assert {"hit", "miss", "correct_rejection", "no_response"} <= set(df_out["acc_label"])

    # join results: probe_type and encoding back-propagation
    recog = df_out[df_out["phase"] == "recognition"].set_index("stim_id")
    assert recog.loc["foo_old.bmp", "probe_type"] == "target"
    assert recog.loc["bar_old.bmp", "probe_type"] == "target"
    assert recog.loc["baz_new.bmp", "probe_type"] == "lure"
    assert recog.loc["qux_new.bmp", "probe_type"] == "lure"

    enc = df_out[df_out["phase"] == "encoding"].set_index("stim_id")
    assert enc.loc["foo_old.bmp", "enc_is_tested"] == 1
    assert enc.loc["foo_old.bmp", "enc_later_outcome"] == "hit"
    assert enc.loc["bar_old.bmp", "enc_is_tested"] == 1
    assert enc.loc["bar_old.bmp", "enc_later_outcome"] == "miss"

    # is_error flag
    assert df_out[df_out["acc_label"] == "false_alarm"].empty  # no false_alarm in dataset
    assert df_out[df_out["acc_label"] == "miss"]["is_error"].iloc[0] == 1
    assert df_out[df_out["acc_label"] == "no_response"]["is_error"].iloc[0] == 1
    enc_miss = df_out[(df_out["phase"] == "encoding") & (df_out["stim_id"] == "bar_old.bmp")]
    assert enc_miss["is_error"].iloc[0] == 1

    # analysis_include flag
    assert df_out[df_out["acc_label"] == "hit"]["analysis_include"].iloc[0] == 1
    assert df_out[df_out["acc_label"] == "correct_rejection"]["analysis_include"].iloc[0] == 1
    assert df_out[df_out["acc_label"] == "miss"]["analysis_include"].iloc[0] == 0
    assert df_out[df_out["acc_label"] == "no_response"]["analysis_include"].iloc[0] == 0

    # novelty mapping
    assert {"old", "novel"} <= set(df_out["novelty_type"])
