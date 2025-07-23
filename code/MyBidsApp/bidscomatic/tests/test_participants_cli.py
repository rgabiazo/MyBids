from pathlib import Path
import subprocess
import pandas as pd

CLI = ["python", "-m", "bidscomatic.cli", "participants"]

def test_participants_cli_basic(tmp_path: Path) -> None:
    ds = tmp_path / "ds"
    ds.mkdir()
    (ds / "dataset_description.json").write_text("{}")

    # Two subject folders
    (ds / "sub-001").mkdir()
    (ds / "sub-002").mkdir()

    # Metadata CSV with numeric IDs and coded values
    meta = ds / "participants_meta.csv"
    meta.write_text(
        "participant_id,Age,Sex,Group\n"
        "1,25,0,1\n"
        "2,35,1,0\n"
    )

    subprocess.run(
        CLI
        + [
            "--meta-file",
            str(meta),
            "--keep-cols",
            "Age,Sex,Group",
            "--rename-cols",
            "Age=age,Sex=sex,Group=group",
            "--map-values",
            "sex=0:M,1:F",
            "--map-values",
            "group=0:control,1:treatment",
        ],
        cwd=ds,
        check=True,
    )

    df = pd.read_csv(ds / "participants.tsv", sep="\t")
    assert list(df.columns) == ["participant_id", "age", "sex", "group"]
    assert df.loc[df["participant_id"] == "sub-001", "sex"].iloc[0] == "M"
    assert df.loc[df["participant_id"] == "sub-002", "sex"].iloc[0] == "F"
    assert df.loc[df["participant_id"] == "sub-001", "group"].iloc[0] == "treatment"
    assert df.loc[df["participant_id"] == "sub-002", "group"].iloc[0] == "control"
