"""
Quick sanity-check for the `bidscomatic-cli init` helper.
"""
from pathlib import Path
import json
import subprocess
import sys

# Path to the CLI entry-point inside the editable venv
CLI = ["python", "-m", "bidscomatic.cli", "init"]

def test_init_writes_dataset_description(tmp_path: Path):
    out_dir = tmp_path / "MyStudy"
    # 1) run the CLI in a subprocess to exercise the real entry-point
    result = subprocess.run(
        CLI + [str(out_dir), "--name", "My Study"],
        capture_output=True,
        text=True,
        check=True,
    )
    assert "dataset_description.json" in result.stdout

    # 2) verify the file exists and contains the provided name
    dd_file = out_dir / "dataset_description.json"
    assert dd_file.exists()
    with dd_file.open() as fh:
        data = json.load(fh)
    assert data["Name"] == "My Study"


def test_no_rename_on_existing_dir(tmp_path: Path) -> None:
    ds = tmp_path / "My_Existing"
    ds.mkdir()
    # Write a placeholder dataset_description.json
    (ds / "dataset_description.json").write_text("{}")

    subprocess.run(
        CLI
        + [
            str(ds),
            "--name",
            "New Name",
            "--force",
            "--no-rename-root",
        ],
        check=True,
        cwd=tmp_path,
    )

    # Folder should be unchanged
    assert ds.exists()
    assert (tmp_path / "New-Name").exists() is False

    with (ds / "dataset_description.json").open() as fh:
        info = json.load(fh)
    assert info["Name"] == "New Name"
