from pathlib import Path
from click.testing import CliRunner
import json
from types import SimpleNamespace
from bidscomatic.cli import main as cli_main
from bidscomatic.tools.aroma import AromaConfig, AromaTool
from bidscomatic.engines.docker import DockerEngine
from bidscomatic.utils.resources import ResourceSpec


def test_aroma_tool_builds_and_executes(tmp_path, monkeypatch):
    """Verify aroma tool builds AND executes behavior."""
    cfg = AromaConfig(
        project_dir=tmp_path,
        prep_dir=tmp_path / "prep",
        out_dir=tmp_path / "out",
        work_dir=tmp_path / "work",
        tf_dir=tmp_path / "tf",
        clean_workdir=True,
        stop_on_first_crash=True,
    )
    subjects = ["001"]
    engine = DockerEngine()
    called = {}

    def fake_run(image, args, *, volumes, env, entrypoint=None):
        called["image"] = image
        called["args"] = args
        called["volumes"] = volumes
        called["env"] = env
        called["entrypoint"] = entrypoint
        return 0

    monkeypatch.setattr(engine, "run", fake_run)
    AromaTool(cfg, subjects).execute(engine)
    assert called["image"] == cfg.image
    assert "--participant-label" in called["args"]
    assert "--work-dir" in called["args"]
    assert "--use-plugin" in called["args"]
    assert "--omp-nthreads" in called["args"]
    assert "--clean-workdir" in called["args"]
    assert "--stop-on-first-crash" in called["args"]
    assert (cfg.work_dir / "nipype_linear.yml").exists()
    volumes = called["volumes"]
    assert volumes
    assert str(cfg.prep_dir) in volumes
    env = called["env"]
    assert env.get("KMP_BLOCKTIME") == "0"
    assert env.get("MALLOC_ARENA_MAX") == "1"


def test_cli_aroma_invokes_engine(tmp_path, monkeypatch):
    """Verify CLI aroma invokes engine behavior."""
    (tmp_path / "dataset_description.json").write_text("{}")
    bids_filter = tmp_path / "filters.json"
    bids_filter.write_text("{}")

    called = {}

    def fake_run(self, image, args, *, volumes, env, entrypoint=None):  # type: ignore[override]
        called["image"] = image
        called["args"] = args
        called["volumes"] = volumes
        called["env"] = env
        called["entrypoint"] = entrypoint
        return 0

    monkeypatch.setattr(DockerEngine, "run", fake_run)
    monkeypatch.setattr(
        "bidscomatic.cli.preprocess.tune_resources",
        lambda *a, **k: ResourceSpec(platform=None, n_procs=3, mem_mb=1234, low_mem=True, omp_threads=1),
    )

    runner = CliRunner()
    result = runner.invoke(
        cli_main,
        [
            "--bids-root",
            str(tmp_path),
            "preprocess",
            "aroma",
            "--subjects",
            "005",
            "--bids-filter-file",
            str(bids_filter),
            "--prep-dir",
            str(tmp_path / "override_prep"),
            "--clean-workdir",
            "--stop-on-first-crash",
        ],
    )
    assert result.exit_code == 0, result.output
    assert "--participant-label" in called["args"]
    assert "--work-dir" in called["args"]
    assert "--nprocs" in called["args"]
    assert "3" in called["args"]
    assert "--use-plugin" in called["args"]
    assert "--omp-nthreads" in called["args"]
    assert "--clean-workdir" in called["args"]
    assert "--stop-on-first-crash" in called["args"]
    assert str(tmp_path / "override_prep") in called["volumes"]
    assert called["env"].get("MALLOC_ARENA_MAX") == "1"


def test_aroma_tool_reset_bids_db(tmp_path):
    """Verify aroma tool reset BIDS DB behavior."""
    cfg = AromaConfig(
        project_dir=tmp_path,
        prep_dir=tmp_path / "prep",
        out_dir=tmp_path / "out",
        work_dir=tmp_path / "work",
        tf_dir=tmp_path / "tf",
    )
    for p in (cfg.prep_dir, cfg.out_dir, cfg.work_dir, cfg.tf_dir):
        p.mkdir(parents=True, exist_ok=True)
    bids_db = cfg.work_dir / "bids_db"
    bids_db.mkdir()
    marker = bids_db / "stale.db"
    marker.write_text("foo")

    AromaTool(cfg, ["001"]).build_spec()
    assert not marker.exists()

    # Re-create the marker and ensure explicit resets also clear it
    marker.write_text("foo")
    cfg.reset_bids_db = True
    AromaTool(cfg, ["001"]).build_spec()
    assert not marker.exists()


def test_cli_aroma_omp_override(tmp_path, monkeypatch):
    """Verify CLI aroma OMP override behavior."""
    (tmp_path / "dataset_description.json").write_text("{}")
    bids_filter = tmp_path / "filters.json"
    bids_filter.write_text("{}")
    prep = tmp_path / "prep"
    (prep / "sub-001").mkdir(parents=True)

    captured = {}

    def fake_run(self, image, args, *, volumes, env, entrypoint=None):  # type: ignore[override]
        captured["args"] = args
        return 0

    monkeypatch.setattr(DockerEngine, "run", fake_run)

    def fake_tune(*a, **k):
        captured["omp_override"] = k.get("omp_threads_override")
        return ResourceSpec(platform=None, n_procs=1, mem_mb=1000, low_mem=False, omp_threads=5)

    monkeypatch.setattr("bidscomatic.cli.preprocess.tune_resources", fake_tune)

    runner = CliRunner()
    result = runner.invoke(
        cli_main,
        [
            "--bids-root",
            str(tmp_path),
            "preprocess",
            "aroma",
            "--bids-filter-file",
            str(bids_filter),
            "--prep-dir",
            str(prep),
            "--omp-nthreads",
            "5",
        ],
    )
    assert result.exit_code == 0, result.output
    assert captured["omp_override"] == 5
    assert "--omp-nthreads" in captured["args"]
    assert "5" in captured["args"]


def test_cli_aroma_logs_resources(tmp_path, monkeypatch):
    """Verify CLI aroma logs resources behavior."""
    (tmp_path / "dataset_description.json").write_text("{}")
    bids_filter = tmp_path / "filters.json"
    bids_filter.write_text("{}")

    def fake_run(self, image, args, *, volumes, env, entrypoint=None):  # type: ignore[override]
        return 0

    monkeypatch.setattr(DockerEngine, "run", fake_run)

    def fake_tune(*a, **k):
        return ResourceSpec(
            platform="linux/amd64",
            n_procs=2,
            mem_mb=4000,
            low_mem=True,
            omp_threads=1,
            cpu_docker=8,
            mem_total_mb=8000,
            headroom_mb=1000,
            host_arch="x86_64",
        )

    monkeypatch.setattr(
        "bidscomatic.cli.preprocess.tune_resources", fake_tune
    )

    events = []

    def fake_info(event, **kw):
        events.append((event, kw))

    monkeypatch.setattr(
        "bidscomatic.cli.preprocess.log", SimpleNamespace(info=fake_info)
    )

    prep = tmp_path / "prep"
    (prep / "sub-001").mkdir(parents=True)

    runner = CliRunner()
    result = runner.invoke(
        cli_main,
        [
            "--bids-root",
            str(tmp_path),
            "preprocess",
            "aroma",
            "--subjects",
            "001",
            "--bids-filter-file",
            str(bids_filter),
            "--prep-dir",
            str(prep),
        ],
    )
    assert result.exit_code == 0, result.output
    assert any(e == "[aroma] resources.tuned" for e, _ in events)
    kw = [kw for e, kw in events if e == "[aroma] resources.tuned"][0]
    assert kw["n_procs"] == 2
    assert kw["mem_mb"] == 4000


def test_cli_aroma_prints_summary(tmp_path, monkeypatch):
    """Verify CLI aroma prints summary behavior."""
    (tmp_path / "dataset_description.json").write_text("{}")
    bids_filter = tmp_path / "filters.json"
    bids_filter.write_text("{}")
    prep = tmp_path / "prep"
    (prep / "sub-001").mkdir(parents=True)

    def fake_run(self, image, args, *, volumes, env, entrypoint=None):  # type: ignore[override]
        return 0

    monkeypatch.setattr(DockerEngine, "run", fake_run)
    monkeypatch.setattr(
        "bidscomatic.cli.preprocess.tune_resources",
        lambda *a, **k: ResourceSpec(
            platform="linux/amd64",
            n_procs=1,
            mem_mb=4096,
            low_mem=True,
            omp_threads=1,
            cpu_docker=2,
            mem_total_mb=8192,
            headroom_mb=4096,
            host_arch="arm64",
            mode="docker",
        ),
    )

    runner = CliRunner()
    result = runner.invoke(
        cli_main,
        [
            "--bids-root",
            str(tmp_path),
            "preprocess",
            "aroma",
            "--subjects",
            "001",
            "--bids-filter-file",
            str(bids_filter),
            "--prep-dir",
            str(prep),
        ],
    )
    assert result.exit_code == 0, result.output
    assert "Inside-VM: CPUs=2, MemTotal=8192MB" in result.output


def test_cli_aroma_defaults_to_docker(tmp_path, monkeypatch):
    """Verify CLI aroma defaults TO docker behavior."""
    (tmp_path / "dataset_description.json").write_text("{}")
    bids_filter = tmp_path / "filters.json"
    bids_filter.write_text("{}")
    prep = tmp_path / "prep"
    (prep / "sub-001").mkdir(parents=True)

    def fake_run(self, image, args, *, volumes, env, entrypoint=None):  # type: ignore[override]
        return 0

    monkeypatch.setattr(DockerEngine, "run", fake_run)

    called: dict[str, str | None] = {}

    def fake_tune(*a, **k):
        called["runner"] = k.get("runner")
        return ResourceSpec(
            platform="linux/amd64",
            n_procs=1,
            mem_mb=4096,
            low_mem=False,
            omp_threads=1,
            cpu_docker=2,
            mem_total_mb=8192,
            headroom_mb=4096,
            host_arch="arm64",
            mode="docker",
        )

    monkeypatch.setattr(
        "bidscomatic.cli.preprocess.tune_resources", fake_tune
    )

    runner = CliRunner()
    result = runner.invoke(
        cli_main,
        [
            "--bids-root",
            str(tmp_path),
            "preprocess",
            "aroma",
            "--subjects",
            "001",
            "--bids-filter-file",
            str(bids_filter),
            "--prep-dir",
            str(prep),
        ],
    )
    assert result.exit_code == 0, result.output
    assert called.get("runner") == "docker"


def test_cli_aroma_autodetect_subjects(tmp_path, monkeypatch):
    """Verify CLI aroma autodetect subjects behavior."""
    (tmp_path / "dataset_description.json").write_text("{}")
    prep = tmp_path / "prep"
    (prep / "sub-001").mkdir(parents=True)
    (prep / "sub-002").mkdir()
    bids_filter = tmp_path / "filters.json"
    bids_filter.write_text("{}")

    called = {}

    def fake_run(self, image, args, *, volumes, env, entrypoint=None):  # type: ignore[override]
        called["args"] = args
        called["entrypoint"] = entrypoint
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
            "aroma",
            "--bids-filter-file",
            str(bids_filter),
            "--prep-dir",
            str(prep),
        ],
    )
    assert result.exit_code == 0, result.output
    assert "--participant-label" not in called["args"]


def test_cli_aroma_task_ignored_with_filter(tmp_path, monkeypatch):
    """Verify CLI aroma task ignored with filter behavior."""
    (tmp_path / "dataset_description.json").write_text("{}")
    prep = tmp_path / "prep"
    (prep / "sub-001").mkdir(parents=True)
    bids_filter = tmp_path / "filters.json"
    bids_filter.write_text("{}")

    called = {}

    def fake_run(self, image, args, *, volumes, env, entrypoint=None):  # type: ignore[override]
        called["args"] = args
        called["entrypoint"] = entrypoint
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
            "aroma",
            "--bids-filter-file",
            str(bids_filter),
            "--task",
            "assocmemory",
            "--prep-dir",
            str(prep),
        ],
    )
    assert result.exit_code == 0, result.output
    args = called["args"]
    assert args.count("--bids-filter-file") == 1
    assert any("filters.json" in a for a in args)
    assert all("bids_filters_assocmemory" not in a for a in args)


def test_aroma_tool_resets_bids_db(tmp_path):
    """Verify aroma tool resets BIDS DB behavior."""
    cfg = AromaConfig(
        project_dir=tmp_path,
        prep_dir=tmp_path / "prep",
        out_dir=tmp_path / "out",
        work_dir=tmp_path / "work",
        tf_dir=tmp_path / "tf",
    )
    bids_db = cfg.work_dir / "bids_db"
    bids_db.mkdir(parents=True)
    stale = bids_db / "stale.db"
    stale.write_text("foo")
    AromaTool(cfg, ["001"]).build_spec()
    assert bids_db.exists()
    assert not stale.exists()


def test_cli_aroma_create_filter(tmp_path, monkeypatch):
    """Verify CLI aroma create filter behavior."""
    (tmp_path / "dataset_description.json").write_text("{}")
    prep = tmp_path / "prep"
    (prep / "sub-005").mkdir(parents=True)

    called = {}

    def fake_run(self, image, args, *, volumes, env, entrypoint=None):  # type: ignore[override]
        called["args"] = args
        called["entrypoint"] = entrypoint
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
            "aroma",
            "--subjects",
            "005",
            "--create-filter",
            "task=memory",
            "--task",
            "memory",
            "--prep-dir",
            str(prep),
            "--work-dir",
            str(tmp_path / "work"),
        ],
    )
    assert result.exit_code == 0, result.output
    filter_path = tmp_path / "work" / "bids_filters_memory.json"
    assert filter_path.exists()
    data = json.loads(filter_path.read_text())
    assert data == {"task": "memory"}
    args = called["args"]
    idx = args.index("--bids-filter-file")
    assert args[idx + 1] == "/work/bids_filters_memory.json"


def test_cli_aroma_full_invocation(tmp_path, monkeypatch):
    """Run preprocess aroma with explicit directories and filter file."""
    (tmp_path / "dataset_description.json").write_text("{}")
    prep = tmp_path / "derivatives" / "DeepPrep" / "BOLD"
    out_dir = tmp_path / "derivatives" / "fmripost_aroma"
    work_dir = tmp_path / "derivatives" / "work" / "fmripost_aroma"
    tf_dir = tmp_path / "derivatives" / "templateflow"
    (prep / "sub-005").mkdir(parents=True)
    work_dir.mkdir(parents=True)
    bids_filter = work_dir / "bids_filters_assocmemory.json"
    bids_filter.write_text(json.dumps({"task": "assocmemory"}))

    called = {}

    def fake_run(self, image, args, *, volumes, env, entrypoint=None):  # type: ignore[override]
        called["volumes"] = volumes
        called["args"] = args
        called["entrypoint"] = entrypoint
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
            "aroma",
            "--subjects",
            "005",
            "--bids-filter-file",
            str(bids_filter.relative_to(tmp_path)),
            "--task",
            "assocmemory",
            "--prep-dir",
            str(prep.relative_to(tmp_path)),
            "--out-dir",
            str(out_dir.relative_to(tmp_path)),
            "--work-dir",
            str(work_dir.relative_to(tmp_path)),
            "--tf-dir",
            str(tf_dir.relative_to(tmp_path)),
        ],
    )
    assert result.exit_code == 0, result.output
    volumes = called["volumes"]
    assert str(prep) in volumes
    assert str(out_dir) in volumes
    assert str(work_dir) in volumes
    assert str(tf_dir) in volumes
