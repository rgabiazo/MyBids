"""Automatic resource tuning for containerised tools."""

from __future__ import annotations

from dataclasses import dataclass
import os
import platform
import subprocess
from typing import Iterable, Optional

import structlog

from .docker import detect_platform

log = structlog.get_logger()


@dataclass
class ResourceSpec:
    """Compute resources for running a tool."""

    platform: Optional[str]
    n_procs: int
    mem_mb: int
    low_mem: bool
    omp_threads: int
    cpu_docker: int | None = None
    mem_total_mb: int | None = None
    headroom_mb: int | None = None
    host_arch: str | None = None
    mode: str = "docker"


def _docker_cmd(platform: str | None, *inner: str) -> Optional[str]:
    """Run a tiny BusyBox command inside Docker and return stdout."""
    cmd = ["docker", "run", "--rm"]
    if platform:
        cmd += ["--platform", platform]
    cmd += ["busybox", *inner]
    try:  # pragma: no cover - best effort helper
        return subprocess.check_output(
            cmd, text=True, stderr=subprocess.DEVNULL
        ).strip()
    except Exception as exc:  # pragma: no cover
        log.info("resources.docker_cmd_failed", cmd=cmd, error=str(exc))
        return None


def _probe_cpus(platform: str | None) -> int:
    """Return the number of CPUs visible inside the container runtime."""
    out = _docker_cmd(
        platform,
        "sh",
        "-c",
        "getconf _NPROCESSORS_ONLN 2>/dev/null || nproc 2>/dev/null || grep -c ^processor /proc/cpuinfo",
    )
    try:
        return int(out) if out else 2
    except ValueError:
        return 2


def _probe_mem(platform: str | None) -> int:
    """Return the container memory limit in megabytes."""
    out = _docker_cmd(platform, "cat", "/proc/meminfo")
    if out:
        for line in out.splitlines():
            if line.startswith("MemTotal"):
                parts = line.split()
                try:
                    return int(int(parts[1]) / 1024)
                except Exception:  # pragma: no cover
                    break
    return 8192


def _detect_rosetta(platform: str | None) -> str:
    """Identify the binary translation layer used for x86 images on arm64."""
    host = platform_module.machine()
    if host != "arm64" or platform != "linux/amd64":
        return "n/a"
    cmd = [
        "docker",
        "run",
        "--rm",
        "--privileged",
        "--platform",
        "linux/arm64/v8",
        "busybox",
        "sh",
        "-c",
        (
            "mountpoint -q /proc/sys/fs/binfmt_misc || "
            "mount -t binfmt_misc binfmt_misc /proc/sys/fs/binfmt_misc 2>/dev/null || true; "
            "if [ -f /proc/sys/fs/binfmt_misc/rosetta ]; then echo rosetta; "
            "elif [ -f /proc/sys/fs/binfmt_misc/qemu-x86_64 ]; then echo qemu; "
            "elif [ -d /proc/sys/fs/binfmt_misc ]; then echo none; else echo none; fi"
        ),
    ]
    try:  # pragma: no cover - environment dependent
        return subprocess.check_output(
            cmd, text=True, stderr=subprocess.DEVNULL
        ).strip()
    except Exception as exc:  # pragma: no cover
        log.info("resources.rosetta_probe_failed", error=str(exc))
        return "error"


# "platform" is both variable name and module; rename module reference
platform_module = platform


def tune_resources(
    image: str,
    *,
    runner: str = "docker",
    auto: bool = True,
    n_procs_default: int = 1,
    mem_mb_default: int = 16000,
    low_mem_default: bool = False,
    per_proc_mb: int | None = None,
    n_procs_override: int | None = None,
    mem_mb_override: int | None = None,
    low_mem_override: bool | None = None,
    omp_threads_default: int = 1,
    omp_threads_override: int | None = None,
) -> ResourceSpec:
    """Return resource recommendations for the given image.

    Args:
        image: Container image name passed to the tool launcher.
        runner: Execution backend (``"docker"`` or ``"native"``).
        auto: Whether host resources should be probed automatically.
        n_procs_default: Worker count used when auto tuning is disabled.
        mem_mb_default: Memory budget used when auto tuning is disabled.
        low_mem_default: Default low-memory flag when auto tuning is disabled.
        per_proc_mb: Desired memory per worker when set.
        n_procs_override: Explicit worker count, bypassing heuristics.
        mem_mb_override: Explicit memory allocation, bypassing heuristics.
        low_mem_override: Explicit low-memory flag, bypassing heuristics.
        omp_threads_default: Default OpenMP thread count.
        omp_threads_override: Explicit OpenMP thread count.

    Returns:
        ResourceSpec describing container CPU, memory, and OpenMP settings.
    """
    platform_str = detect_platform(image) if runner == "docker" else None

    if not auto:
        n_procs = n_procs_override or n_procs_default
        mem_mb = mem_mb_override or mem_mb_default
        low_mem = low_mem_override if low_mem_override is not None else low_mem_default
        omp = omp_threads_override or omp_threads_default
        log.info(
            "resources.tuned",
            platform=platform_str,
            n_procs=n_procs,
            mem_mb=mem_mb,
            low_mem=low_mem,
            omp_threads=omp,
            mode=runner,
        )
        return ResourceSpec(
            platform_str,
            n_procs,
            mem_mb,
            low_mem,
            omp,
            mode=runner,
        )

    if runner == "native":
        cpu_docker = os.cpu_count() or 1
        try:
            page = os.sysconf("SC_PAGE_SIZE")
            phys = os.sysconf("SC_PHYS_PAGES")
            mem_total_mb = (page * phys) // 1024 // 1024
        except Exception:
            mem_total_mb = 8192
    else:
        cpu_docker = _probe_cpus(platform_str)
        mem_total_mb = _probe_mem(platform_str)

    # Headroom heuristics
    if mem_total_mb <= 16384:
        headroom = 4096
    elif mem_total_mb <= 32768:
        headroom = 6144
    else:
        headroom = 8192
    mem_mb = mem_total_mb - headroom
    if mem_mb < 4096:
        mem_mb = mem_total_mb * 70 // 100

    if mem_mb_override is not None:
        mem_mb = mem_mb_override

    if low_mem_override is not None:
        low_mem = low_mem_override
    else:
        low_mem = mem_mb < 32000

    if per_proc_mb is None:
        per_proc_mb = 3500 if low_mem else 6500

    # Golden rule for selecting worker count
    cpu_cap = max(1, cpu_docker - 2)

    mem_safe_mb = mem_mb - 1024
    if mem_safe_mb < 1024:
        mem_safe_mb = mem_mb
    mem_cap = max(1, mem_safe_mb // per_proc_mb)

    host_arch = platform_module.machine()
    soft_cap = 8
    if runner == "docker" and host_arch == "arm64" and platform_str == "linux/amd64":
        # Running an x86 image on arm64 (e.g. under Rosetta/QEMU)
        _detect_rosetta(platform_str)
        soft_cap = 2

    n_procs = min(cpu_cap, mem_cap, soft_cap)

    if n_procs_override is not None:
        n_procs = n_procs_override

    if omp_threads_override is not None:
        omp = omp_threads_override
    else:
        omp = omp_threads_default
        if auto:
            if mem_mb >= 28000 and not low_mem:
                omp = max(omp, 4)
            elif mem_mb >= 12000 and not low_mem:
                omp = max(omp, 2)
            if low_mem and omp > 2:
                omp = 2

    log.info(
        "resources.tuned",
        platform=platform_str,
        host_arch=host_arch,
        cpu_docker=cpu_docker,
        mem_total_mb=mem_total_mb,
        headroom_mb=headroom,
        n_procs=n_procs,
        mem_mb=mem_mb,
        low_mem=low_mem,
        omp_threads=omp,
        mode=runner,
    )

    return ResourceSpec(
        platform_str,
        n_procs,
        mem_mb,
        low_mem,
        omp,
        cpu_docker,
        mem_total_mb,
        headroom,
        host_arch,
        runner,
    )


def format_resource_summary(
    spec: ResourceSpec,
    *,
    subjects: Iterable[str],
    image: str,
) -> str:
    """Return a human-readable summary of tuned resources.

    Args:
        spec: Resource specification returned by :func:`tune_resources`.
        subjects: Iterable of subject identifiers included in the run.
        image: Container image being executed.

    Returns:
        String summarising CPU, memory and mode decisions.
    """
    cpu_cap = (spec.cpu_docker - 2) if spec.cpu_docker and spec.cpu_docker > 2 else 1
    per_proc = 3500 if spec.low_mem else 6500
    mem_safe = spec.mem_mb - 1024 if spec.mem_mb > 1024 else spec.mem_mb
    n_procs_max = max(1, mem_safe // per_proc)

    lines: list[str] = []
    if spec.mode == "docker":
        if spec.cpu_docker is not None and spec.mem_total_mb is not None:
            lines.append(
                f"Inside-VM: CPUs={spec.cpu_docker}, MemTotal={spec.mem_total_mb}MB"
            )
        lines.append(
            "Using: n_procs={n} (CPU cap {cap}, max {mx}), mem={mem}MB (headroom {hd}MB)".format(
                n=spec.n_procs,
                cap=cpu_cap,
                mx=n_procs_max,
                mem=spec.mem_mb,
                hd=spec.headroom_mb or 0,
            )
        )
        lines.append(f"Subjects: {' '.join(subjects)}")
        lines.append(
            "Image: {img} | Platform: {plat} | Host arch: {arch}".format(
                img=image,
                plat=spec.platform or "n/a",
                arch=spec.host_arch or "n/a",
            )
        )
        decision = "low-mem ON" if spec.low_mem else "low-mem OFF"
        lines.append(f"Decision: {decision} (target ~{per_proc}MB/worker)")
    else:
        import sys
        import platform as plat
        import nilearn  # type: ignore

        if spec.cpu_docker is not None and spec.mem_total_mb is not None:
            lines.append(
                f"Local: CPUs={spec.cpu_docker}, MemTotal={spec.mem_total_mb}MB"
            )
        lines.append(f"Subjects: {' '.join(subjects)}")
        lines.append(
            "Backend: nilearn {nl} | Python {py} | OS: {os} | Arch: {arch} (native)".format(
                nl=nilearn.__version__,
                py=f"{sys.version_info.major}.{sys.version_info.minor}",
                os=plat.system(),
                arch=spec.host_arch or plat.machine(),
            )
        )
        lines.append("Decision: native mode (Docker OFF)")

    # Deduplicate any repeated lines to avoid double "Inside-VM" banners
    seen: set[str] = set()
    unique_lines: list[str] = []
    for line in lines:
        if line not in seen:
            unique_lines.append(line)
            seen.add(line)

    return "\n".join(unique_lines)


__all__ = ["ResourceSpec", "tune_resources", "format_resource_summary"]

