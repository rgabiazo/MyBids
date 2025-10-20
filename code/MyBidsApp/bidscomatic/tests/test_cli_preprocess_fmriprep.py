from click.testing import CliRunner

from bidscomatic.cli import main as cli_main
from bidscomatic.engines.docker import DockerEngine
from bidscomatic.utils.resources import ResourceSpec


def test_cli_fmriprep_invokes_engine(tmp_path, monkeypatch):
    """Verify CLI fmriprep invokes engine behavior."""
    (tmp_path / "dataset_description.json").write_text("{}")
    bids = tmp_path / "bids"
    (bids / "sub-001").mkdir(parents=True)
    fs = tmp_path / "license.txt"
    fs.write_text("abc")

    called = []

    def fake_run(self, image, args, *, volumes, env, entrypoint=None):  # type: ignore[override]
        called.append({"args": args, "volumes": volumes, "env": env, "entrypoint": entrypoint})
        return 0

    monkeypatch.setattr(DockerEngine, "run", fake_run)
    monkeypatch.setattr(
        "bidscomatic.cli.preprocess.tune_resources",
        lambda *a, **k: ResourceSpec(platform=None, n_procs=1, mem_mb=1000, low_mem=False, omp_threads=1),
    )

    runner = CliRunner()
    result = runner.invoke(
        cli_main,
        [
            "--bids-root",
            str(tmp_path),
            "preprocess",
            "fmriprep",
            "--subjects",
            "001",
            "--data-dir",
            str(bids),
            "--fs-license",
            str(fs),
        ],
    )
    assert result.exit_code == 0, result.output
    assert called
    assert "--participant-label" in called[0]["args"]


def test_cli_fmriprep_autodiscovers_subjects(tmp_path, monkeypatch):
    """Verify CLI fmriprep autodiscovers subjects behavior."""
    (tmp_path / "dataset_description.json").write_text("{}")
    bids = tmp_path / "bids"
    (bids / "sub-001").mkdir(parents=True)
    fs = tmp_path / "license.txt"
    fs.write_text("abc")

    called = []

    def fake_run(self, image, args, *, volumes, env, entrypoint=None):  # type: ignore[override]
        called.append({"args": args, "volumes": volumes, "env": env, "entrypoint": entrypoint})
        return 0

    monkeypatch.setattr(DockerEngine, "run", fake_run)
    monkeypatch.setattr(
        "bidscomatic.cli.preprocess.tune_resources",
        lambda *a, **k: ResourceSpec(platform=None, n_procs=1, mem_mb=1000, low_mem=False, omp_threads=1),
    )

    runner = CliRunner()
    result = runner.invoke(
        cli_main,
        [
            "--bids-root",
            str(tmp_path),
            "preprocess",
            "fmriprep",
            "--data-dir",
            str(bids),
            "--fs-license",
            str(fs),
        ],
    )
    assert result.exit_code == 0, result.output
    assert called
    assert "001" in called[0]["args"]
