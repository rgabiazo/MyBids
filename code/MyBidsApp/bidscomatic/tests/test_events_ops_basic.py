from pathlib import Path
import subprocess
import pandas as pd

CLI = ["python", "-m", "bidscomatic.cli", "events"]


def test_events_ops_basic(tmp_path: Path) -> None:
    """Verify events OPS basic behavior."""
    ds = tmp_path / "ds"
    ds.mkdir()
    (ds / "dataset_description.json").write_text("{}")

    behav = ds / "sourcedata" / "behavioural_task"
    behav.mkdir(parents=True)
    (behav / "sub-001").mkdir()
    sheet = behav / "sub-001" / "task.csv"

    df = pd.DataFrame(
        {
            "image_file": [
                "Pair_Encoding_foo_OLD.bmp",
                "Pair_Encoding_bar_OLD.bmp",
                "Pair_Recog_foo_OLD.bmp",
                "Pair_Recog_baz_NEW.bmp",
            ],
            "is_correct": ["n/a", "n/a", "HIT", "FALSE_ALARM"],
            "encode_Run1": [10, 20, None, None],
            "recog_Run1": [None, None, 100, 110],
            "encode_rt_Run1": [1.0, 1.1, None, None],
            "recog_rt_Run1": [None, None, 2.0, 2.1],
        }
    )
    df.to_csv(sheet, index=False)

    cmd = CLI + [
        "sourcedata/behavioural_task",
        "--img-col",
        "image_file",
        "--accuracy-col",
        "is_correct",
        "--onset-cols",
        "encode_Run1,recog_Run1",
        "--rt-cols",
        "encode_rt_Run1,recog_rt_Run1",
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
        'newcol=phase from=trial_type map=encoding:^encoding_;recognition:^recog_',
        "--regex-extract",
        'newcol=condition from=trial_type pattern=_(?P<cond>[^_]+)$ group=cond',
        "--id-from",
        'newcol=stim_id from=stim_file func=basename',
        "--map-values",
        'newcol=acc_label from=response map=HIT=hit;FALSE_ALARM=false_alarm;n/a=',
        "--synth-rows",
        'when=block-start groupby=phase,condition onset=first.onset-10 duration=10 clamp-zero=true set=trial_type=fmt("instruction_{condition}_{phase}");phase=instruction;is_instruction=1',
        "--keep-cols-if-exist",
        'onset,duration,trial_type,stim_file,response_time,response,phase,condition,stim_id,acc_label,is_instruction',
    ]

    subprocess.run(cmd, cwd=ds, check=True)

    out = ds / "sub-001" / "func" / "sub-001_task-demo_run-01_events.tsv"
    assert out.exists()
    out_df = pd.read_csv(out, sep="\t")

    assert "phase" in out_df.columns
    assert out_df[out_df["phase"] == "instruction"].shape[0] == 2


def test_op_index_apply_to() -> None:
    """Verify OP index apply TO behavior."""
    import pandas as pd
    from bidscomatic.utils.ops import op_index

    df = pd.DataFrame({
        'phase': ['instruction', 'encoding', 'encoding'],
        'condition': ['pair', 'pair', 'pair'],
        'onset': [0, 1, 2],
    })
    res = op_index(df, newcol='trial_n', groupby=['phase', 'condition'], orderby='onset', start=1, apply_to='phase!="instruction"')
    assert res.loc[0, 'trial_n'] != res.loc[0, 'trial_n']  # NaN for instruction
    assert res[res['phase'] == 'encoding']['trial_n'].tolist() == [1, 2]


def test_op_index_apply_to_dotted_column() -> None:
    """Verify OP index apply TO dotted column behavior."""
    import pandas as pd
    from bidscomatic.utils.ops import op_index

    df = pd.DataFrame({
        'Instruction.started': [0.0, None, None],
        'phase': ['instruction', 'encoding', 'encoding'],
        'condition': ['pair', 'pair', 'pair'],
        'onset': [0, 1, 2],
    })
    res = op_index(
        df,
        newcol='trial_n',
        groupby=['phase', 'condition'],
        orderby='onset',
        start=1,
        apply_to='`Instruction.started`.isna()'
    )
    assert pd.isna(res.loc[0, 'trial_n'])
    assert res[res['phase'] == 'encoding']['trial_n'].tolist() == [1, 2]


def test_op_index_then_set_na() -> None:
    """Verify OP index then SET NA behavior."""
    import pandas as pd
    from bidscomatic.utils.ops import op_index, op_set

    df = pd.DataFrame({
        'phase': ['instruction', 'encoding', 'encoding'],
        'condition': ['pair', 'pair', 'pair'],
        'onset': [0, 1, 2],
    })
    res = op_index(df, newcol='trial_n', groupby=['phase', 'condition'], orderby='onset', start=1)
    assert res.loc[0, 'trial_n'] == 1
    res = op_set(res, when='phase=="instruction"', set_values={'trial_n': float('nan')})
    assert res.loc[0, 'trial_n'] != res.loc[0, 'trial_n']  # NaN after set


def test_regex_extract_apply_to_numeric_group() -> None:
    """Verify regex extract apply TO numeric group behavior."""
    import pandas as pd
    from bidscomatic.utils.ops import op_regex_extract

    df = pd.DataFrame({
        'trial_type': ['instruction', 'encoding'],
        'info': ['foo', 'foo_BAR'],
    })
    res = op_regex_extract(
        df,
        newcol='cond',
        from_col='info',
        pattern='(foo)_([A-Z]+)$',
        group=1,
        apply_to='trial_type!="instruction"',
        default='',
    )
    assert pd.isna(res.loc[0, 'cond'])
    assert res.loc[1, 'cond'] == 'BAR'


def test_cli_regex_extract_numeric_group(tmp_path: Path) -> None:
    """Verify CLI regex extract numeric group behavior."""
    ds = tmp_path / "ds"
    ds.mkdir()
    (ds / "dataset_description.json").write_text("{}")

    behav = ds / "sourcedata" / "behavioural_task"
    behav.mkdir(parents=True)
    (behav / "sub-001").mkdir()
    sheet = behav / "sub-001" / "task.csv"

    df = pd.DataFrame(
        {
            "image_file": ["Pair_Encoding/foo_OLD.bmp"],
            "is_correct": ["n/a"],
            "encode_Run1": [10],
            "encode_rt_Run1": [1.0],
        }
    )
    df.to_csv(sheet, index=False)

    cmd = CLI + [
        "sourcedata/behavioural_task",
        "--img-col", "image_file",
        "--accuracy-col", "is_correct",
        "--onset-cols", "encode_Run1",
        "--rt-cols", "encode_rt_Run1",
        "--duration", "3",
        "--trialtype-patterns", "Pair_Encoding=encoding_pair",
        "--task", "demo",
        "--sub", "sub-001",
        "--keep-cols", "trial_type,stim_file",
        "--regex-extract", 'newcol=nov from=stim_file pattern=_(OLD|NEW) group=0',
        "--keep-cols-if-exist", 'trial_type,stim_file,nov',
    ]

    subprocess.run(cmd, cwd=ds, check=True)

    out = ds / "sub-001" / "func" / "sub-001_task-demo_run-01_events.tsv"
    df_out = pd.read_csv(out, sep="\t")
    assert df_out.loc[0, "nov"] == "OLD"


def test_op_set_and_drop() -> None:
    """Verify OP SET AND drop behavior."""
    import pandas as pd
    from bidscomatic.utils.ops import op_set, op_drop

    df = pd.DataFrame({"a": [1, 2], "b": [10, 20]})
    res = op_set(df, when="a==1", set_values={"b": 99, "c": "foo"})
    assert res.loc[0, "b"] == 99
    assert res.loc[0, "c"] == "foo"
    res = op_drop(res, when="a==2")
    assert res.shape[0] == 1
    assert res.iloc[0]["a"] == 1


def test_flag_set_with_dotted_column() -> None:
    """Verify flag SET with dotted column behavior."""
    import pandas as pd
    from bidscomatic.utils.ops import op_flag, op_set

    df = pd.DataFrame({"Instruction.started": [0.0, None], "b": [1, 2]})
    res = op_flag(
        df,
        newcol="is_inst",
        expr="`Instruction.started`.notna()",
        true=1,
        false=0,
    )
    assert res["is_inst"].tolist() == [1, 0]
    res = op_set(res, when="`Instruction.started`==0", set_values={"b": 99})
    assert res.loc[0, "b"] == 99
