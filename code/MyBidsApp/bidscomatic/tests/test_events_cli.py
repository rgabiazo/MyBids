from pathlib import Path
import json
import subprocess
import pandas as pd

CLI = ["python", "-m", "bidscomatic.cli", "events"]


def test_events_cli_stimuli(tmp_path: Path) -> None:
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


def test_events_cli_field_levels(tmp_path: Path) -> None:
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
