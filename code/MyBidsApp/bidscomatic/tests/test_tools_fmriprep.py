import pytest

from bidscomatic.tools.fmriprep import FmriprepConfig, FmriprepTool
from bidscomatic.engines.docker import DockerEngine


def test_fmriprep_tool_executes_per_subject(tmp_path, monkeypatch):
    """Verify fmriprep tool executes PER subject behavior."""
    data = tmp_path / "bids" / "sub-001"
    data.mkdir(parents=True)
    cfg = FmriprepConfig(
        project_dir=tmp_path,
        data_dir=tmp_path / "bids",
        out_dir=tmp_path / "out",
        work_dir=tmp_path / "work",
        tf_dir=tmp_path / "tf",
        fs_license=tmp_path / "license.txt",
    )
    cfg.fs_license.write_text("1234")
    subjects = ["001", "002"]
    engine = DockerEngine()
    calls = []

    def fake_run(image, args, *, volumes, env, entrypoint=None):
        calls.append({
            "image": image,
            "args": args,
            "volumes": volumes,
            "env": env,
            "entrypoint": entrypoint,
        })
        return 0

    monkeypatch.setattr(engine, "run", fake_run)
    FmriprepTool(cfg, subjects).execute(engine)
    assert len(calls) == 2
    assert "--participant-label" in calls[0]["args"]
    assert (tmp_path / "license.txt").exists()
    assert str(cfg.data_dir) in calls[0]["volumes"]


def test_fmriprep_tool_reset_bids_db(tmp_path):
    """Verify fmriprep tool reset BIDS DB behavior."""
    data = tmp_path / "bids" / "sub-001"
    data.mkdir(parents=True)
    cfg = FmriprepConfig(
        project_dir=tmp_path,
        data_dir=tmp_path / "bids",
        out_dir=tmp_path / "out",
        work_dir=tmp_path / "work",
        tf_dir=tmp_path / "tf",
        fs_license=tmp_path / "license.txt",
    )
    cfg.fs_license.write_text("1234")
    bids_db = cfg.work_dir / "bids_db"
    bids_db.mkdir(parents=True)
    marker = bids_db / "stale.db"
    marker.write_text("foo")

    class DummyEngine:
        def run(self, *a, **k):
            return 0

    FmriprepTool(cfg, ["001"]).execute(DummyEngine())
    assert marker.exists()

    cfg.reset_bids_db = True
    FmriprepTool(cfg, ["001"]).execute(DummyEngine())
    assert not marker.exists()


def test_fmriprep_tool_requires_license(tmp_path):
    """Verify fmriprep tool requires license behavior."""
    data = tmp_path / "bids" / "sub-001"
    data.mkdir(parents=True)
    cfg = FmriprepConfig(
        project_dir=tmp_path,
        data_dir=tmp_path / "bids",
        out_dir=tmp_path / "out",
        work_dir=tmp_path / "work",
        tf_dir=tmp_path / "tf",
        fs_license=tmp_path / "missing.txt",
    )

    class DummyEngine:
        def run(self, *a, **k):
            return 0

    tool = FmriprepTool(cfg, ["001"])
    with pytest.raises(FileNotFoundError):
        tool.execute(DummyEngine())


def test_fmriprep_tool_requires_readable_license(tmp_path):
    """Verify fmriprep tool requires readable license behavior."""
    data = tmp_path / "bids" / "sub-001"
    data.mkdir(parents=True)
    license_path = tmp_path / "license_dir"
    license_path.mkdir()
    cfg = FmriprepConfig(
        project_dir=tmp_path,
        data_dir=tmp_path / "bids",
        out_dir=tmp_path / "out",
        work_dir=tmp_path / "work",
        tf_dir=tmp_path / "tf",
        fs_license=license_path,
    )

    class DummyEngine:
        def run(self, *a, **k):
            return 0

    tool = FmriprepTool(cfg, ["001"])
    with pytest.raises(PermissionError):
        tool.execute(DummyEngine())
