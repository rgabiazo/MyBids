from pathlib import Path
import subprocess
import pandas as pd

CLI = ["python", "-m", "bidscomatic.cli", "events"]

def test_events_cli_with_config(tmp_path: Path) -> None:
    """Verify events CLI with config behavior."""
    ds = tmp_path / "ds"
    ds.mkdir()
    (ds / "dataset_description.json").write_text("{}")

    behav = ds / "sourcedata" / "behavioural_task"
    (behav / "sub-001").mkdir(parents=True)
    sheet = behav / "sub-001" / "task.csv"
    df = pd.DataFrame(
        {
            "image_file": ["Pair_Encoding/stim1.bmp", "Pair_Recog/stim2.bmp"],
            "onset_Run1": [1.0, 5.0],
            "rt_Run1": [0.5, 0.7],
            "trial_type": ["Pair_Encoding", "Pair_Recog"],
            "response": ["n/a", "HIT"],
        }
    )
    df.to_csv(sheet, index=False)

    cfg = ds / "events.yaml"
    cfg.write_text(
        """
version: 1
command: events
task: demo
input:
  root: sourcedata/behavioural_task
  pattern: "*.csv"
ingest:
  img_col: image_file
  accuracy_col: response
  trialtype_col: trial_type
  onset_groups:
    - onset_cols: [onset_Run1]
      duration: 3
  rt_cols: [rt_Run1]
  trialtype_patterns:
    Pair_Encoding: encoding_pair
    Pair_Recog: recog_pair
derive:
  regex_map:
    - newcol: phase
      from: trial_type
      map:
        encoding: '^(enc|encoding)_'
        recognition: '^(rec|ret|recogn)[a-z]*_'
  regex_extract:
    - newcol: condition
      from: trial_type
      pattern: '_(?P<cond>[^_]+)$'
      group: cond
  id_from:
    - newcol: stim_id
      from: stim_file
      func: basename
  map_values:
    - newcol: acc_label
      from: response
      casefold: true
      map:
        hit: hit
        miss: miss
        n/a: ''
output:
  keep_cols:
    - trial_type
    - stim_file
    - response_time
    - response
  keep_cols_if_exist:
    - onset
    - duration
    - trial_type
    - stim_file
    - response_time
    - response
    - phase
    - condition
    - stim_id
    - acc_label
  create_events_json: true
"""
    )

    subprocess.run(CLI + ["--config", "events.yaml"], cwd=ds, check=True)

    out_tsv = ds / "sub-001" / "func" / "sub-001_task-demo_run-01_events.tsv"
    df_out = pd.read_csv(out_tsv, sep="\t")
    assert list(df_out["trial_type"]) == ["encoding_pair", "recog_pair"]
    assert df_out.loc[1, "acc_label"] == "hit"
