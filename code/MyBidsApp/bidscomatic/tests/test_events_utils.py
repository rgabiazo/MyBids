import pandas as pd
from pathlib import Path
from bidscomatic.utils.events import make_events_frames


def _write_sheet(path: Path) -> None:
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
