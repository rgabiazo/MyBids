from pathlib import Path
import json
import subprocess

CLI = ["python", "-m", "bidscomatic.cli", "phenotype-json"]


def _setup_dataset(tmp_path: Path) -> Path:
    """Create a minimal dataset with a single phenotype TSV.

    Args:
        tmp_path: Temporary directory provided by the pytest fixture.

    Returns:
        Path to the dataset root prepared for the test.
    """
    ds = tmp_path / "ds"
    ds.mkdir()
    (ds / "dataset_description.json").write_text("{}")
    pheno = ds / "phenotype"
    pheno.mkdir()
    tsv = pheno / "mmq_abl_ses-01.tsv"
    tsv.write_text("participant_id\tmmq_ability\nsub-001\t10\n")
    return ds


def _setup_runs_dataset(tmp_path: Path) -> Path:
    """Create a dataset containing per-run phenotype TSV files.

    Args:
        tmp_path: Temporary directory provided by the pytest fixture.

    Returns:
        Path to the dataset root prepared for the test.
    """
    ds = tmp_path / "ds"
    ds.mkdir()
    (ds / "dataset_description.json").write_text("{}")
    pheno = ds / "phenotype"
    pheno.mkdir()
    for run in (1, 2):
        tsv = pheno / f"mmq_abl_run-{run:02d}.tsv"
        tsv.write_text("participant_id\tmmq_ability\nsub-001\t10\n")
    return ds


def test_create_phenotype_json(tmp_path: Path) -> None:
    """Verify create phenotype JSON behavior."""
    ds = _setup_dataset(tmp_path)
    spec = ds / "spec.json"
    spec.write_text(
        json.dumps(
            {
                "MeasurementToolMetadata": {
                    "Description": "MMQ",
                    "TermURL": "https://example.com",
                },
                "mmq_ability": {"Description": "Ability", "Units": "score"},
            }
        )
    )
    subprocess.run(CLI + ["phenotype/mmq_abl_ses-01.tsv", "--json-spec", str(spec)], cwd=ds, check=True)
    meta = json.loads((ds / "phenotype/mmq_abl_ses-01.json").read_text())
    assert meta["mmq_ability"]["Description"] == "Ability"
    assert meta["MeasurementToolMetadata"]["Description"] == "MMQ"


def test_skip_without_overwrite(tmp_path: Path) -> None:
    """Verify skip without overwrite behavior."""
    ds = _setup_dataset(tmp_path)
    subprocess.run(CLI + ["phenotype/mmq_abl_ses-01.tsv"], cwd=ds, check=True)
    before = (ds / "phenotype/mmq_abl_ses-01.json").read_text()
    spec = ds / "extra.json"
    spec.write_text(json.dumps({"mmq_ability": {"Description": "New"}}))
    subprocess.run(CLI + ["phenotype/mmq_abl_ses-01.tsv", "--json-spec", str(spec)], cwd=ds, check=True)
    after = (ds / "phenotype/mmq_abl_ses-01.json").read_text()
    assert before == after


def test_flag_overrides(tmp_path: Path) -> None:
    """Verify flag overrides behavior."""
    ds = _setup_dataset(tmp_path)
    subprocess.run(
        CLI
        + [
            "phenotype/mmq_abl_ses-01.tsv",
            "--tool-description",
            "MMQ",
            "--tool-term-url",
            "https://example.com",
            "--field-description",
            "mmq_ability=Ability score",
            "--field-units",
            "mmq_ability=score",
        ],
        cwd=ds,
        check=True,
    )
    meta = json.loads((ds / "phenotype/mmq_abl_ses-01.json").read_text())
    assert meta["MeasurementToolMetadata"]["Description"] == "MMQ"
    assert meta["MeasurementToolMetadata"]["TermURL"] == "https://example.com"
    assert meta["mmq_ability"]["Description"] == "Ability score"
    assert meta["mmq_ability"]["Units"] == "score"


def test_overrides_beat_json_spec(tmp_path: Path) -> None:
    """Verify overrides beat JSON spec behavior."""
    ds = _setup_dataset(tmp_path)
    spec = ds / "spec.json"
    spec.write_text(
        json.dumps(
            {
                "MeasurementToolMetadata": {"Description": "OLD"},
                "mmq_ability": {"Description": "Old", "Units": "u"},
            }
        )
    )
    subprocess.run(
        CLI
        + [
            "phenotype/mmq_abl_ses-01.tsv",
            "--json-spec",
            str(spec),
            "--tool-description",
            "NEW",
            "--field-description",
            "mmq_ability=New",
        ],
        cwd=ds,
        check=True,
    )
    meta = json.loads((ds / "phenotype/mmq_abl_ses-01.json").read_text())
    assert meta["MeasurementToolMetadata"]["Description"] == "NEW"
    assert meta["mmq_ability"]["Description"] == "New"
    assert meta["mmq_ability"]["Units"] == "u"


def test_json_unicode_not_escaped(tmp_path: Path) -> None:
    """Verify JSON unicode NOT escaped behavior."""
    ds = _setup_dataset(tmp_path)
    subprocess.run(
        CLI
        + [
            "phenotype/mmq_abl_ses-01.tsv",
            "--field-description",
            "mmq_ability=Ability (0–80)",
        ],
        cwd=ds,
        check=True,
    )
    text = (ds / "phenotype/mmq_abl_ses-01.json").read_text()
    assert "(0–80)" in text
    assert "\\u2013" not in text


def test_create_json_multiple_runs(tmp_path: Path) -> None:
    """Verify create JSON multiple runs behavior."""
    ds = _setup_runs_dataset(tmp_path)
    subprocess.run(
        CLI
        + [
            "phenotype/mmq_abl_run-01.tsv",
            "phenotype/mmq_abl_run-02.tsv",
        ],
        cwd=ds,
        check=True,
    )
    assert (ds / "phenotype/mmq_abl_run-01.json").exists()
    assert (ds / "phenotype/mmq_abl_run-02.json").exists()


def test_overrides_apply_to_all_runs(tmp_path: Path) -> None:
    """Verify overrides apply TO ALL runs behavior."""
    ds = _setup_runs_dataset(tmp_path)
    subprocess.run(
        CLI
        + [
            "phenotype/mmq_abl_run-01.tsv",
            "phenotype/mmq_abl_run-02.tsv",
            "--field-description",
            "mmq_ability=Score",
        ],
        cwd=ds,
        check=True,
    )
    for run in ("01", "02"):
        meta = json.loads((ds / f"phenotype/mmq_abl_run-{run}.json").read_text())
        assert meta["mmq_ability"]["Description"] == "Score"

