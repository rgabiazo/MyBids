from pathlib import Path
import subprocess
import pandas as pd

CLI = ["python", "-m", "bidscomatic.cli", "events"]

def test_events_cli_config_filters(tmp_path: Path) -> None:
    """Verify events CLI config filters behavior."""
    ds = tmp_path / "ds"
    ds.mkdir()
    (ds / "dataset_description.json").write_text("{}")

    behav = ds / "sourcedata" / "behavioural_task"
    # Subject with session
    (behav / "sub-001" / "ses-01").mkdir(parents=True)
    sheet1 = behav / "sub-001" / "ses-01" / "task.csv"
    df = pd.DataFrame(
        {
            "image_file": ["stim1.bmp"],
            "onset_Run1": [1.0],
            "rt_Run1": [0.5],
            "trial_type": ["Pair_Encoding"],
            "response": ["n/a"],
        }
    )
    df.to_csv(sheet1, index=False)

    # Subject without session
    (behav / "sub-002").mkdir(parents=True)
    sheet2 = behav / "sub-002" / "task.csv"
    df.to_csv(sheet2, index=False)

    cfg = ds / "events.yaml"
    cfg.write_text(
        """
version: 1
command: events
task: events
input:
  root: sourcedata/behavioural_task
  pattern: "*.csv"
  subjects: ["001", "002"]
  sessions: ["01"]
ingest:
  img_col: image_file
  accuracy_col: response
  onset_groups:
    - onset_cols: [onset_Run1]
      duration: 3
  rt_cols: [rt_Run1]
  trialtype_patterns:
    stim: stim
derive: {}
output:
  keep_cols: [trial_type, stim_file, response_time, response]
  keep_cols_if_exist: [onset, duration, trial_type, stim_file, response_time, response]
"""
    )

    subprocess.run(CLI + ["--config", "events.yaml"], cwd=ds, check=True)

    out1 = ds / "sub-001" / "ses-01" / "func" / "sub-001_ses-01_task-events_run-01_events.tsv"
    out1_alt = ds / "sub-001" / "func" / "sub-001_task-events_run-01_events.tsv"
    assert out1.exists() or out1_alt.exists()
    assert not list((ds / "sub-002").glob("**/*events.tsv"))
