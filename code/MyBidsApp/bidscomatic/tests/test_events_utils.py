import pandas as pd
from pathlib import Path
from bidscomatic.utils.events import make_events_frames


def _write_sheet(path: Path) -> None:
    """Write a behavioural spreadsheet for events utility tests.

    Args:
        path: Output CSV path populated with synthetic records.
    """
    df = pd.DataFrame(
        {
            "image_file": ["block1/fileA.bmp", "fileB.bmp"],
            "is_correct": [1, 0],
            "onset_Run1": [0, 1],
            "rt_Run1": [0.2, 0.3],
        }
    )
    df.to_csv(path, index=False)


def test_make_events_frames_defaults(tmp_path: Path) -> None:
    """Verify make events frames defaults behavior."""
    sheet = tmp_path / "task.csv"
    _write_sheet(sheet)
    frames = make_events_frames(
        sheet=sheet,
        img_col="image_file",
        accuracy_col="is_correct",
        onset_cols=["onset_Run1"],
        rt_cols=["rt_Run1"],
        duration=3,
        trialtype_patterns="file=file",
        sub="sub-001",
        ses=None,
        task="demo",
    )
    df = frames["sub-001_task-demo_run-01_events.tsv"]
    assert list(df.columns) == ["onset", "duration"]


def test_make_events_frames_basename(tmp_path: Path) -> None:
    """Verify make events frames basename behavior."""
    sheet = tmp_path / "task.csv"
    _write_sheet(sheet)
    frames = make_events_frames(
        sheet=sheet,
        img_col="image_file",
        accuracy_col="is_correct",
        onset_cols=["onset_Run1"],
        rt_cols=["rt_Run1"],
        duration=3,
        trialtype_patterns="file=file",
        sub="sub-001",
        ses=None,
        task="demo",
        keep_cols=["stim_file"],
    )
    df = frames["sub-001_task-demo_run-01_events.tsv"]
    assert list(df["stim_file"]) == ["fileA.bmp", "fileB.bmp"]


def test_make_events_frames_keep_raw(tmp_path: Path) -> None:
    """Verify make events frames keep RAW behavior."""
    sheet = tmp_path / "task.csv"
    _write_sheet(sheet)
    frames = make_events_frames(
        sheet=sheet,
        img_col="image_file",
        accuracy_col="is_correct",
        onset_cols=["onset_Run1"],
        rt_cols=["rt_Run1"],
        duration=3,
        trialtype_patterns="file=file",
        sub="sub-001",
        ses=None,
        task="demo",
        keep_raw_stim=True,
        keep_cols=["stim_file"],
    )
    df = frames["sub-001_task-demo_run-01_events.tsv"]
    assert list(df["stim_file"]) == [
        "block1/fileA.bmp",
        "fileB.bmp",
    ]


def test_make_events_frames_keep_cols(tmp_path: Path) -> None:
    """Verify make events frames keep cols behavior."""
    sheet = tmp_path / "task.csv"
    _write_sheet(sheet)
    frames = make_events_frames(
        sheet=sheet,
        img_col="image_file",
        accuracy_col="is_correct",
        onset_cols=["onset_Run1"],
        rt_cols=["rt_Run1"],
        duration=3,
        trialtype_patterns="file=file",
        sub="sub-001",
        ses=None,
        task="demo",
        keep_cols=["stim_file"],
    )
    df = frames["sub-001_task-demo_run-01_events.tsv"]
    assert list(df.columns) == ["onset", "duration", "stim_file"]


def test_make_events_frames_duration_col(tmp_path: Path) -> None:
    """Verify make events frames duration COL behavior."""
    sheet = tmp_path / "task.csv"
    df = pd.DataFrame(
        {
            "image_file": ["block1/fileA.bmp", "fileB.bmp"],
            "is_correct": [1, 0],
            "onset_Run1": [0, 1],
            "rt_Run1": [0.2, 0.3],
            "dur_s": [2.5, None],
        }
    )
    df.to_csv(sheet, index=False)

    frames = make_events_frames(
        sheet=sheet,
        img_col="image_file",
        accuracy_col="is_correct",
        onset_cols=["onset_Run1"],
        rt_cols=["rt_Run1"],
        duration=3,
        duration_col="dur_s",
        trialtype_patterns="file=file",
        sub="sub-001",
        ses=None,
        task="demo",
    )

    df_out = frames["sub-001_task-demo_run-01_events.tsv"]
    assert list(df_out["duration"]) == [2.5, 3.0]


def test_make_events_frames_trialtype_column(tmp_path: Path) -> None:
    """Verify make events frames trialtype column behavior."""
    sheet = tmp_path / "task.csv"
    df = pd.DataFrame(
        {
            "image_file": ["ignoredA.bmp", "ignoredB.bmp"],
            "is_correct": [1, 0],
            "onset_Run1": [0, 1],
            "rt_Run1": [0.2, 0.3],
            "trial_label": ["instruction", "trial"],
        }
    )
    df.to_csv(sheet, index=False)

    frames = make_events_frames(
        sheet=sheet,
        img_col="image_file",
        accuracy_col="is_correct",
        onset_cols=["onset_Run1"],
        rt_cols=["rt_Run1"],
        duration=3,
        trialtype_patterns=None,
        trialtype_col="trial_label",
        sub="sub-001",
        ses=None,
        task="demo",
        keep_cols=["trial_type"],
    )

    df_out = frames["sub-001_task-demo_run-01_events.tsv"]
    assert list(df_out["trial_type"]) == ["instruction", "trial"]

    frames_mapped = make_events_frames(
        sheet=sheet,
        img_col="image_file",
        accuracy_col="is_correct",
        onset_cols=["onset_Run1"],
        rt_cols=["rt_Run1"],
        duration=3,
        trialtype_patterns="instr=instruction;trial=experiment",
        trialtype_col="trial_label",
        sub="sub-001",
        ses=None,
        task="demo",
        keep_cols=["trial_type"],
    )
    df_map = frames_mapped["sub-001_task-demo_run-01_events.tsv"]
    assert list(df_map["trial_type"]) == ["instruction", "experiment"]


def test_make_events_frames_rt_column_matching(tmp_path: Path) -> None:
    """Verify make events frames RT column matching behavior."""
    sheet = tmp_path / "task.csv"
    df = pd.DataFrame(
        {
            "image_file": ["enc_run1.bmp", "rec_run1.bmp"],
            "is_correct": [1, 1],
            "encodeRun1_onset": [0.0, None],
            "recogRun1_onset": [None, 10.0],
            "encodeRun1_rt": [1.23, None],
            "recogRun1_rt": [None, 2.34],
        }
    )
    df.to_csv(sheet, index=False)

    frames = make_events_frames(
        sheet=sheet,
        img_col="image_file",
        accuracy_col="is_correct",
        onset_cols=["encodeRun1_onset", "recogRun1_onset"],
        rt_cols=["encodeRun1_rt", "recogRun1_rt"],
        duration=3,
        trialtype_patterns="enc=encode;rec=recog",
        sub="sub-001",
        ses=None,
        task="demo",
        keep_cols=["stim_file", "response_time"],
    )

    df_run1 = frames["sub-001_task-demo_run-01_events.tsv"]
    enc_rt = df_run1.loc[df_run1["stim_file"] == "enc_run1.bmp", "response_time"].iloc[0]
    rec_rt = df_run1.loc[df_run1["stim_file"] == "rec_run1.bmp", "response_time"].iloc[0]
    assert enc_rt == 1.23
    assert rec_rt == 2.34
