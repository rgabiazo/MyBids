from pathlib import Path
import json
import subprocess
import pandas as pd

CLI = ["python", "-m", "bidscomatic.cli", "events"]


def test_events_cli_onset_duration_only(tmp_path: Path) -> None:
    """Verify events CLI onset duration only behavior."""
    ds = tmp_path / "ds"
    ds.mkdir()
    (ds / "dataset_description.json").write_text("{}")

    behav = ds / "sourcedata" / "behavioural_task" / "sub-001"
    behav.mkdir(parents=True)
    sheet = behav / "task.csv"

    df = pd.DataFrame(
        {
            "onset_Run1": [0.0, 5.0, 9.5],
        }
    )
    df.to_csv(sheet, index=False)

    subprocess.run(
        CLI
        + [
            "sourcedata/behavioural_task",
            "--onset-cols",
            "onset_Run1 duration=3.5",
            "--task",
            "assocmemory",
        ],
        cwd=ds,
        check=True,
    )

    events_path = ds / "sub-001" / "func" / "sub-001_task-assocmemory_run-01_events.tsv"
    assert events_path.exists()

    out_df = pd.read_csv(events_path, sep="\t")
    assert list(out_df.columns) == ["onset", "duration"]
    assert out_df["duration"].unique().tolist() == [3.5]


def test_events_cli_stimuli(tmp_path: Path) -> None:
    """Verify events CLI stimuli behavior."""
    ds = tmp_path / "ds"
    ds.mkdir()
    (ds / "dataset_description.json").write_text("{}")

    behav = ds / "sourcedata" / "behavioural_task"
    behav.mkdir(parents=True)
    (behav / "sub-001").mkdir()
    (behav / "imgA.bmp").write_bytes(b"0")
    (behav / "imgB.bmp").write_bytes(b"0")

    sheet = behav / "sub-001" / "task.csv"
    df = pd.DataFrame(
        {
            "image_file": ["imgA.bmp", "imgB.bmp"],
            "is_correct": [1, 0],
            "onset_Run1": [0, 1],
            "rt_Run1": [0.2, 0.3],
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
            "is_correct",
            "--onset-cols",
            "onset_Run1",
            "--rt-cols",
            "rt_Run1",
            "--duration",
            "3",
            "--trialtype-patterns",
            "img=img",
            "--task",
            "demo",
            "--sub",
            "sub-001",
            "--create-stimuli-directory",
        ],
        cwd=ds,
        check=True,
    )

    assert (ds / "stimuli" / "imgA.bmp").exists()
    assert (ds / "stimuli" / "imgB.bmp").exists()


def test_events_cli_stim_root(tmp_path: Path) -> None:
    """Verify events CLI stim root behavior."""
    ds = tmp_path / "ds"
    ds.mkdir()
    (ds / "dataset_description.json").write_text("{}")

    behav = ds / "sourcedata" / "behavioural_task"
    (behav / "sub-001" / "ses-01").mkdir(parents=True)
    (behav / "imgA.bmp").write_bytes(b"0")

    sheet = behav / "sub-001" / "ses-01" / "task.csv"
    df = pd.DataFrame(
        {
            "image_file": ["imgA.bmp"],
            "is_correct": [1],
            "onset_Run1": [0],
            "rt_Run1": [0.2],
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
            "is_correct",
            "--onset-cols",
            "onset_Run1",
            "--rt-cols",
            "rt_Run1",
            "--duration",
            "3",
            "--trialtype-patterns",
            "img=img",
            "--task",
            "demo",
            "--sub",
            "sub-001",
            "--create-stimuli-directory",
            "--stim-root",
            "sourcedata/behavioural_task",
        ],
        cwd=ds,
        check=True,
    )

    assert (ds / "stimuli" / "imgA.bmp").exists()


def test_events_cli_events_json(tmp_path: Path) -> None:
    """Verify events CLI events JSON behavior."""
    ds = tmp_path / "ds"
    ds.mkdir()
    (ds / "dataset_description.json").write_text("{}")

    behav = ds / "sourcedata" / "behavioural_task"
    behav.mkdir(parents=True)
    (behav / "sub-001").mkdir()
    sheet = behav / "sub-001" / "task.csv"
    df = pd.DataFrame(
        {
            "image_file": ["imgA.bmp"],
            "is_correct": [1],
            "onset_Run1": [0],
            "rt_Run1": [0.2],
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
            "is_correct",
            "--onset-cols",
            "onset_Run1",
            "--rt-cols",
            "rt_Run1",
            "--duration",
            "3",
            "--trialtype-patterns",
            "img=img",
            "--task",
            "demo",
            "--sub",
            "sub-001",
            "--keep-cols",
            "trial_type",
            "--create-events-json",
        ],
        cwd=ds,
        check=True,
    )

    json_file = ds / "sub-001" / "func" / "sub-001_task-demo_run-01_events.json"
    assert json_file.exists()

    meta = json.loads(json_file.read_text())
    assert {
        "onset",
        "duration",
        "trial_type",
        "GeneratedBy",
    } <= set(meta)
    assert meta["onset"]["Description"] == "Event onset relative to run start"
    assert meta["onset"]["Units"] == "seconds"
    assert meta["duration"]["Description"] == "Event duration"
    assert meta["duration"]["Units"] == "seconds"
    assert meta["trial_type"]["Levels"] == {"img": ""}
    assert meta["GeneratedBy"]["Name"] == "bidscomatic"
    assert "Version" in meta["GeneratedBy"]
    assert meta["GeneratedBy"]["CodeURL"].startswith("https://github.com/")


def test_events_cli_onset_group_duration(tmp_path: Path) -> None:
    """Verify events CLI onset group duration behavior."""
    ds = tmp_path / "ds"
    ds.mkdir()
    (ds / "dataset_description.json").write_text("{}")

    behav = ds / "sourcedata" / "behavioural_task"
    behav.mkdir(parents=True)
    (behav / "sub-001").mkdir()
    sheet = behav / "sub-001" / "task.csv"

    df = pd.DataFrame(
        {
            "image_file": ["imgA.bmp", "imgB.bmp"],
            "is_correct": [1, 1],
            "inst_started": [0, None],
            "onset_Run1": [None, 5],
            "rt_Run1": [None, 0.5],
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
        "inst_started duration=10",
        "--onset-cols",
        "onset_Run1 duration=3",
        "--rt-cols",
        "rt_Run1",
        "--trialtype-patterns",
        "img=img",
        "--task",
        "demo",
        "--sub",
        "sub-001",
        "--keep-cols",
        "trial_type,stim_file,response_time,response,inst_started",
    ]

    subprocess.run(cmd, cwd=ds, check=True)

    out = ds / "sub-001" / "func" / "sub-001_task-demo_run-01_events.tsv"
    df_out = pd.read_csv(out, sep="\t")
    assert df_out.shape[0] == 2
    assert df_out.loc[df_out["inst_started"].notna(), "duration"].iloc[0] == 10
    assert df_out.loc[df_out["inst_started"].isna(), "duration"].iloc[0] == 3


def test_events_cli_duration_column(tmp_path: Path) -> None:
    """Verify events CLI duration column behavior."""
    ds = tmp_path / "ds"
    ds.mkdir()
    (ds / "dataset_description.json").write_text("{}")

    behav = ds / "sourcedata" / "behavioural_task"
    behav.mkdir(parents=True)
    (behav / "sub-001").mkdir()
    sheet = behav / "sub-001" / "task.csv"

    df = pd.DataFrame(
        {
            "image_file": ["imgA.bmp", "imgB.bmp"],
            "is_correct": [1, 1],
            "onset_Run1": [0, 5],
            "rt_Run1": [0.2, 0.5],
            "duration_s": [2.5, 4.0],
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
        "onset_Run1",
        "--rt-cols",
        "rt_Run1",
        "--duration-col",
        "duration_s",
        "--trialtype-patterns",
        "img=img",
        "--task",
        "demo",
        "--sub",
        "sub-001",
    ]

    subprocess.run(cmd, cwd=ds, check=True)

    out = ds / "sub-001" / "func" / "sub-001_task-demo_run-01_events.tsv"
    df_out = pd.read_csv(out, sep="\t")
    assert list(df_out["duration"]) == [2.5, 4.0]


def test_events_cli_field_levels(tmp_path: Path) -> None:
    """Verify events CLI field levels behavior."""
    ds = tmp_path / "ds"
    ds.mkdir()
    (ds / "dataset_description.json").write_text("{}")

    behav = ds / "sourcedata" / "behavioural_task"
    behav.mkdir(parents=True)
    (behav / "sub-001").mkdir()
    sheet = behav / "sub-001" / "task.csv"
    df = pd.DataFrame(
        {
            "image_file": ["imgA.bmp"],
            "is_correct": [1],
            "onset_Run1": [0],
            "rt_Run1": [0.2],
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
            "is_correct",
            "--onset-cols",
            "onset_Run1",
            "--rt-cols",
            "rt_Run1",
            "--duration",
            "3",
            "--trialtype-patterns",
            "img=img",
            "--task",
            "demo",
            "--sub",
            "sub-001",
            "--keep-cols",
            "trial_type",
            "--create-events-json",
            "--field-levels",
            "trial_type=img:face",
        ],
        cwd=ds,
        check=True,
    )

    meta = json.loads(
        (ds / "sub-001" / "func" / "sub-001_task-demo_run-01_events.json").read_text()
    )
    assert meta["trial_type"]["Levels"] == {"img": "face"}


def test_events_cli_field_levels_warn(tmp_path: Path) -> None:
    """Verify events CLI field levels warn behavior."""
    ds = tmp_path / "ds"
    ds.mkdir()
    (ds / "dataset_description.json").write_text("{}")

    behav = ds / "sourcedata" / "behavioural_task"
    behav.mkdir(parents=True)
    (behav / "sub-001").mkdir()
    sheet = behav / "sub-001" / "task.csv"
    df = pd.DataFrame(
        {
            "image_file": ["imgA.bmp"],
            "is_correct": [1],
            "onset_Run1": [0],
            "rt_Run1": [0.2],
        }
    )
    df.to_csv(sheet, index=False)

    result = subprocess.run(
        CLI
        + [
            "sourcedata/behavioural_task",
            "--img-col",
            "image_file",
            "--accuracy-col",
            "is_correct",
            "--onset-cols",
            "onset_Run1",
            "--rt-cols",
            "rt_Run1",
            "--duration",
            "3",
            "--trialtype-patterns",
            "img=img",
            "--task",
            "demo",
            "--sub",
            "sub-001",
            "--keep-cols",
            "trial_type",
            "--create-events-json",
            "--field-levels",
            "unknown=foo:bar",
        ],
        cwd=ds,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "--field-levels ignored unknown column 'unknown'" in result.stdout


def test_events_cli_set_and_drop(tmp_path: Path) -> None:
    """Verify events CLI SET AND drop behavior."""
    ds = tmp_path / "ds"
    ds.mkdir()
    (ds / "dataset_description.json").write_text("{}")

    behav = ds / "sourcedata" / "behavioural_task"
    behav.mkdir(parents=True)
    (behav / "sub-001").mkdir()
    sheet = behav / "sub-001" / "task.csv"

    df = pd.DataFrame(
        {
            "image_file": ["imgA.bmp", "imgB.bmp"],
            "is_correct": [1, 1],
            "inst_started": [0, None],
            "onset_Run1": [None, 5],
            "rt_Run1": [None, 0.5],
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
        "inst_started duration=10",
        "--onset-cols",
        "onset_Run1 duration=3",
        "--rt-cols",
        "rt_Run1",
        "--trialtype-patterns",
        "img=img",
        "--task",
        "demo",
        "--sub",
        "sub-001",
        "--set",
        "set=keep=1",
        "--drop",
        "when=inst_started.notna()",
        "--keep-cols",
        "trial_type,inst_started",
        "--keep-cols-if-exist",
        "trial_type,keep",
    ]

    subprocess.run(cmd, cwd=ds, check=True)

    out = ds / "sub-001" / "func" / "sub-001_task-demo_run-01_events.tsv"
    df_out = pd.read_csv(out, sep="\t")
    assert df_out.shape[0] == 1
    assert df_out.loc[0, "trial_type"] == "img"
    assert df_out.loc[0, "keep"] == 1


def test_events_cli_trialtype_col(tmp_path: Path) -> None:
    """Verify events CLI trialtype COL behavior."""
    ds = tmp_path / "ds"
    ds.mkdir()
    (ds / "dataset_description.json").write_text("{}")

    behav = ds / "sourcedata" / "behavioural_task"
    behav.mkdir(parents=True)
    (behav / "sub-001").mkdir()

    sheet = behav / "sub-001" / "task.csv"
    df = pd.DataFrame(
        {
            "image_file": ["anyA.bmp", "anyB.bmp"],
            "is_correct": [1, 0],
            "onset_Run1": [0, 1],
            "rt_Run1": [0.2, 0.3],
            "trial_label": ["instruction", "trial"],
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
            "is_correct",
            "--onset-cols",
            "onset_Run1",
            "--rt-cols",
            "rt_Run1",
            "--duration",
            "3",
            "--trialtype-col",
            "trial_label",
            "--task",
            "demo",
            "--sub",
            "sub-001",
            "--keep-cols",
            "trial_type",
        ],
        cwd=ds,
        check=True,
    )

    out_tsv = ds / "sub-001" / "func" / "sub-001_task-demo_run-01_events.tsv"
    df_out = pd.read_csv(out_tsv, sep="\t")
    assert list(df_out["trial_type"]) == ["instruction", "trial"]
