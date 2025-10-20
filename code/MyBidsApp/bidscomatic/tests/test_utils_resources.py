from types import SimpleNamespace
import os
import sys

from bidscomatic.utils import resources


def test_tune_resources_auto(monkeypatch):
    """Verify tune resources auto behavior."""
    monkeypatch.setattr(resources, "_probe_cpus", lambda _platform: 16)
    monkeypatch.setattr(resources, "_probe_mem", lambda _platform: 64000)
    monkeypatch.setattr(resources, "_detect_rosetta", lambda _platform: "n/a")
    monkeypatch.setattr(resources, "platform_module", SimpleNamespace(machine=lambda: "x86_64"))
    spec = resources.tune_resources("img")
    assert spec.n_procs == 8
    assert spec.mem_mb == 55808
    assert spec.low_mem is False
    assert spec.omp_threads in {1, 2, 4}


def test_tune_resources_overrides():
    """Verify tune resources overrides behavior."""
    spec = resources.tune_resources(
        "img",
        auto=False,
        n_procs_default=2,
        mem_mb_default=16000,
        low_mem_default=True,
        n_procs_override=4,
        mem_mb_override=8000,
        low_mem_override=False,
        omp_threads_default=1,
        omp_threads_override=3,
    )
    assert spec.n_procs == 4
    assert spec.mem_mb == 8000
    assert spec.low_mem is False
    assert spec.omp_threads == 3


def test_tune_resources_logs_summary(monkeypatch):
    """Verify tune resources logs summary behavior."""
    calls = {}

    def fake_info(event, **kw):
        calls["event"] = event
        calls["kw"] = kw

    monkeypatch.setattr(resources, "log", SimpleNamespace(info=fake_info))
    monkeypatch.setattr(resources, "_probe_cpus", lambda _platform: 4)
    monkeypatch.setattr(resources, "_probe_mem", lambda _platform: 16000)
    monkeypatch.setattr(resources, "_detect_rosetta", lambda _platform: "n/a")
    monkeypatch.setattr(resources, "platform_module", SimpleNamespace(machine=lambda: "x86_64"))
    spec = resources.tune_resources("img")
    assert calls["event"] == "resources.tuned"
    assert calls["kw"]["n_procs"] == spec.n_procs
    assert calls["kw"]["mem_mb"] == spec.mem_mb


def test_format_resource_summary():
    """Verify format resource summary behavior."""
    spec = resources.ResourceSpec(
        platform="linux/amd64",
        n_procs=1,
        mem_mb=16000,
        low_mem=True,
        omp_threads=1,
        cpu_docker=14,
        mem_total_mb=22487,
        headroom_mb=6144,
        host_arch="arm64",
    )
    msg = resources.format_resource_summary(
        spec, subjects=["005"], image="img:tag"
    )
    banner = "Inside-VM: CPUs=14, MemTotal=22487MB"
    assert banner in msg
    assert msg.count(banner) == 1
    assert "Subjects: 005" in msg
    assert "Decision: low-mem ON" in msg


def test_format_resource_summary_native(monkeypatch):
    """Verify format resource summary native behavior."""
    monkeypatch.setitem(
        sys.modules, "nilearn", SimpleNamespace(__version__="0.10")
    )
    spec = resources.ResourceSpec(
        platform=None,
        n_procs=1,
        mem_mb=8000,
        low_mem=False,
        omp_threads=1,
        cpu_docker=8,
        mem_total_mb=32000,
        headroom_mb=4096,
        host_arch="arm64",
        mode="native",
    )
    msg = resources.format_resource_summary(spec, subjects=["001"], image="img")
    assert "Local: CPUs=8, MemTotal=32000MB" in msg
    assert "Backend: nilearn 0.10" in msg
    assert "Decision: native mode (Docker OFF)" in msg


def test_tune_resources_native(monkeypatch):
    """Verify tune resources native behavior."""
    def fail_probe(_):  # pragma: no cover - ensure not called
        raise AssertionError("docker probe should not run")

    monkeypatch.setattr(resources, "_probe_cpus", fail_probe)
    monkeypatch.setattr(resources, "_probe_mem", fail_probe)

    monkeypatch.setattr(os, "cpu_count", lambda: 8)

    def sysconf(key):
        if key == "SC_PAGE_SIZE":
            return 4096
        if key == "SC_PHYS_PAGES":
            return 8_388_608
        raise ValueError

    monkeypatch.setattr(os, "sysconf", sysconf)
    monkeypatch.setattr(
        resources, "platform_module", SimpleNamespace(machine=lambda: "arm64")
    )
    spec = resources.tune_resources("img", runner="native")
    assert spec.mode == "native"
    assert spec.cpu_docker == 8
    assert spec.mem_total_mb == 32768


def test_tune_resources_rosetta_soft_cap(monkeypatch):
    """Verify tune resources rosetta soft CAP behavior."""
    monkeypatch.setattr(resources, "_probe_cpus", lambda _platform: 14)
    monkeypatch.setattr(resources, "_probe_mem", lambda _platform: 22487)
    monkeypatch.setattr(resources, "_detect_rosetta", lambda _platform: "rosetta")
    monkeypatch.setattr(resources, "platform_module", SimpleNamespace(machine=lambda: "arm64"))
    monkeypatch.setattr(resources, "detect_platform", lambda _image: "linux/amd64")
    spec = resources.tune_resources("img")
    assert spec.n_procs == 2
    assert spec.mem_mb == 16343
    assert spec.low_mem is True
