from pathlib import Path
import os
import os
import subprocess
import pandas as pd


CLI = ["python", "-m", "bidscomatic.cli", "events"]


def _make_sheet(path: Path) -> None:
    """Create a minimal behavioural spreadsheet for CLI tests.

    Args:
        path: Destination CSV file written for the test scenario.
    """
    df = pd.DataFrame(
        {
            "image_file": ["foo.bmp"],
            "onset_Run1": [1.0],
            "rt_Run1": [0.5],
            "trial_type": ["Pair_Encoding"],
            "response": ["n/a"],
        }
    )
    df.to_csv(path, index=False)


def test_dir_inferred_from_json(tmp_path: Path) -> None:
    """Verify DIR inferred from JSON behavior."""
    ds = tmp_path / "ds"
    ds.mkdir()
    (ds / "dataset_description.json").write_text("{}")

    # Behavioural sheet
    behav = ds / "sourcedata" / "behavioural_task" / "sub-001"
    behav.mkdir(parents=True)
    _make_sheet(behav / "task.csv")

    # Existing BOLD run with PhaseEncodingDirection
    func = ds / "sub-001" / "func"
    func.mkdir(parents=True)
    (func / "sub-001_task-demo_run-01_bold.nii.gz").write_bytes(b"0")
    (func / "sub-001_task-demo_run-01_bold.json").write_text(
        '{"PhaseEncodingDirection": "j-"}'
    )

    env = os.environ | {"PYTHONPATH": str(Path(__file__).resolve().parents[1])}
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
            "Pair_Encoding=encoding_pair",
            "--task",
            "demo",
            "--sub",
            "sub-001",
        ],
        cwd=ds,
        check=True,
        env=env,
    )

    out = ds / "sub-001" / "func" / "sub-001_task-demo_dir-PA_run-01_events.tsv"
    assert out.exists()


def test_dir_from_filename_fallback(tmp_path: Path) -> None:
    """Verify DIR from filename fallback behavior."""
    ds = tmp_path / "ds"
    ds.mkdir()
    (ds / "dataset_description.json").write_text("{}")

    behav = ds / "sourcedata" / "behavioural_task" / "sub-002"
    behav.mkdir(parents=True)
    _make_sheet(behav / "task.csv")

    func = ds / "sub-002" / "func"
    func.mkdir(parents=True)
    # BOLD file encodes dir in filename but lacks JSON
    (func / "sub-002_task-demo_dir-AP_run-01_bold.nii.gz").write_bytes(b"0")

    env = os.environ | {"PYTHONPATH": str(Path(__file__).resolve().parents[1])}
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
            "Pair_Encoding=encoding_pair",
            "--task",
            "demo",
            "--sub",
            "sub-002",
        ],
        cwd=ds,
        check=True,
        env=env,
    )

    out = ds / "sub-002" / "func" / "sub-002_task-demo_dir-AP_run-01_events.tsv"
    assert out.exists()

