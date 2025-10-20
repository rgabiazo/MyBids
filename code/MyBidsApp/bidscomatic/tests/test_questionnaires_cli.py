import pandas as pd
import subprocess
from pathlib import Path

CLI = ["python", "-m", "bidscomatic.cli", "questionnaires"]


def _make_dataset(tmp_path: Path) -> Path:
    """Create a minimal dataset for questionnaire CLI tests.

    Args:
        tmp_path: Temporary directory provided by the pytest fixture.

    Returns:
        Path to the dataset root prepared for the test.
    """
    ds = tmp_path / "ds"
    ds.mkdir()
    (ds / "dataset_description.json").write_text("{}")
    (ds / "sub-001").mkdir()
    (ds / "sub-006").mkdir()
    return ds


def _write_csv(path: Path) -> None:
    """Write a CSV sheet containing mock questionnaire data.

    Args:
        path: Destination path for the generated CSV file.
    """
    path.write_text(
        "participant_id,MMQ_base,MMQ_follow\n"
        "sub-001,1,10\n"
        "sub-002,2,20\n"
        "sub-006,3,30\n"
        "sub-007,4,40\n"
    )


def test_questionnaires_uses_bids_subjects(tmp_path: Path) -> None:
    """Verify questionnaires uses BIDS subjects behavior."""
    ds = _make_dataset(tmp_path)
    sheet = ds / "sheet.csv"
    _write_csv(sheet)
    subprocess.run(CLI + [str(sheet), "--session-mode", "multi"], cwd=ds, check=True)

    df = pd.read_csv(ds / "phenotype/mmq_ses-01.tsv", sep="\t")
    assert list(df["participant_id"]) == ["sub-001", "sub-006"]


def test_questionnaires_updates_with_new_subject(tmp_path: Path) -> None:
    """Verify questionnaires updates with NEW subject behavior."""
    ds = _make_dataset(tmp_path)
    sheet = ds / "sheet.csv"
    _write_csv(sheet)
    subprocess.run(CLI + [str(sheet), "--session-mode", "multi"], cwd=ds, check=True)

    (ds / "sub-002").mkdir()
    subprocess.run(CLI + [str(sheet), "--session-mode", "multi"], cwd=ds, check=True)

    df = pd.read_csv(ds / "phenotype/mmq_ses-01.tsv", sep="\t")
    assert list(df["participant_id"]) == ["sub-001", "sub-002", "sub-006"]


def test_questionnaires_all_subjects_flag(tmp_path: Path) -> None:
    """Verify questionnaires ALL subjects flag behavior."""
    ds = _make_dataset(tmp_path)
    sheet = ds / "sheet.csv"
    _write_csv(sheet)
    subprocess.run(
        CLI + [str(sheet), "--session-mode", "multi", "--all-subjects"],
        cwd=ds,
        check=True,
    )

    df = pd.read_csv(ds / "phenotype/mmq_ses-01.tsv", sep="\t")
    assert set(df["participant_id"]) == {"sub-001", "sub-002", "sub-006", "sub-007"}
