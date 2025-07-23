from pathlib import Path
import json
import subprocess

CLI = ["python", "-m", "bidscomatic.cli", "dataset-description"]


def test_create_dataset_description(tmp_path: Path) -> None:
    ds = tmp_path / "study"
    ds.mkdir()

    subprocess.run(
        CLI + ["--create", "--name", "My Study"],
        cwd=ds,
        check=True,
    )

    dd = ds / "dataset_description.json"
    assert dd.exists()
    with dd.open() as fh:
        info = json.load(fh)
    assert info["Name"] == "My Study"


def test_create_with_extra_fields(tmp_path: Path) -> None:
    ds = tmp_path / "study2"
    ds.mkdir()

    subprocess.run(
        CLI
        + [
            "--create",
            "--name",
            "My Study",
            "--license",
            "CC0",
            "--funding",
            "Grant1",
            "--funding",
            "Grant2",
            "--dataset-doi",
            "10.1234/5678",
        ],
        cwd=ds,
        check=True,
    )

    with (ds / "dataset_description.json").open() as fh:
        info = json.load(fh)
    assert info["License"] == "CC0"
    assert info["Funding"] == ["Grant1", "Grant2"]
    assert info["DatasetDOI"] == "10.1234/5678"


def test_update_dataset_description(tmp_path: Path) -> None:
    ds = tmp_path / "study"
    ds.mkdir()
    (ds / "dataset_description.json").write_text("{}")

    subprocess.run(
        CLI + ["--update", "--name", "Updated"],
        cwd=ds,
        check=True,
    )

    with (ds / "dataset_description.json").open() as fh:
        info = json.load(fh)
    assert info["Name"] == "Updated"


def test_update_extra_fields(tmp_path: Path) -> None:
    ds = tmp_path / "study3"
    ds.mkdir()
    (ds / "dataset_description.json").write_text("{}")

    subprocess.run(
        CLI
        + [
            "--update",
            "--license",
            "MIT",
            "--funding",
            "GrantX",
        ],
        cwd=ds,
        check=True,
    )

    with (ds / "dataset_description.json").open() as fh:
        info = json.load(fh)
    assert info["License"] == "MIT"
    assert info["Funding"] == ["GrantX"]
