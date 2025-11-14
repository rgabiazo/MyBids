"""Wrapper for the fMRIPost-AROMA container."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Sequence
import os
import shutil
import structlog

from .base import Tool, ToolSpec


log = structlog.get_logger()


@dataclass
class AromaConfig:
    """Configuration for running fMRIPost-AROMA."""

    project_dir: Path
    prep_dir: Path
    out_dir: Path
    work_dir: Path
    tf_dir: Path
    image: str = "nipreps/fmripost-aroma:0.0.12"
    task: str | None = None
    bids_filter: Path | None = None
    melodic_dim: str = "-200"
    denoising_method: str | None = "nonaggr"
    low_mem: bool = False
    n_procs: int = 1
    mem_mb: int = 16000
    omp_threads: int = 1
    clean_workdir: bool = False
    stop_on_first_crash: bool = False
    reset_bids_db: bool = False


class AromaTool(Tool):
    """Build a :class:`ToolSpec` for fMRIPost-AROMA."""

    def __init__(self, cfg: AromaConfig, subjects: Sequence[str]):
        """Store configuration and subject list."""
        self.cfg = cfg
        self.subjects = list(subjects)

    def _ensure_dirs(self) -> None:
        """Create output directories and reset the BIDS database if needed."""
        for p in (self.cfg.out_dir, self.cfg.work_dir, self.cfg.tf_dir):
            p.mkdir(parents=True, exist_ok=True)
        bids_db = self.cfg.work_dir / "bids_db"
        if bids_db.exists():
            if self.cfg.reset_bids_db:
                shutil.rmtree(bids_db)
                log.info("[aroma] reset_bids_db", path=str(bids_db))
            else:
                for child in bids_db.iterdir():
                    if child.is_dir():
                        shutil.rmtree(child)
                    else:
                        child.unlink()
        bids_db.mkdir(exist_ok=True)

    def build_spec(self) -> ToolSpec:
        """Return the container specification for fMRIPost-AROMA."""
        self._ensure_dirs()
        vols = {
            str(self.cfg.prep_dir): "/prep:ro",
            str(self.cfg.out_dir): "/out",
            str(self.cfg.work_dir): "/work",
            str(self.cfg.tf_dir): "/opt/templateflow",
        }
        plugin = self.cfg.work_dir / "nipype_linear.yml"
        plugin.write_text(
            "plugin: MultiProc\n"
            "plugin_args:\n"
            f"  n_procs: {self.cfg.n_procs}\n"
            f"  memory_gb: {self.cfg.mem_mb // 1024}\n"
            "  raise_insufficient: false\n"
        )

        env = {
            "TEMPLATEFLOW_HOME": os.environ.get("TEMPLATEFLOW_HOME", "/opt/templateflow"),
            "OMP_NUM_THREADS": str(self.cfg.omp_threads),
            "MKL_NUM_THREADS": str(self.cfg.omp_threads),
            "OPENBLAS_NUM_THREADS": str(self.cfg.omp_threads),
            "NUMEXPR_NUM_THREADS": str(self.cfg.omp_threads),
            "ITK_GLOBAL_DEFAULT_NUMBER_OF_THREADS": str(self.cfg.omp_threads),
            "KMP_AFFINITY": os.environ.get("KMP_AFFINITY", "disabled"),
            "KMP_BLOCKTIME": os.environ.get("KMP_BLOCKTIME", "0"),
            "OMP_DYNAMIC": os.environ.get("OMP_DYNAMIC", "FALSE"),
            "MKL_DYNAMIC": os.environ.get("MKL_DYNAMIC", "FALSE"),
            "MALLOC_ARENA_MAX": os.environ.get("MALLOC_ARENA_MAX", "1"),
        }
        args = [
            "/prep",
            "/out",
            "participant",
        ]
        if self.subjects:
            args += ["--participant-label", ",".join(self.subjects)]
        args += [
            "--work-dir",
            "/work",
            "--bids-database-dir",
            "/work/bids_db",
            "--skip_bids_validation",
            "--notrack",
            "--nprocs",
            str(self.cfg.n_procs),
            "--mem-mb",
            str(self.cfg.mem_mb),
            "--melodic-dimensionality",
            self.cfg.melodic_dim,
            "--omp-nthreads",
            str(self.cfg.omp_threads),
            "--use-plugin",
            "/work/nipype_linear.yml",
        ]
        if self.cfg.clean_workdir:
            args += ["--clean-workdir"]
        if self.cfg.stop_on_first_crash:
            args += ["--stop-on-first-crash"]
        if self.cfg.denoising_method:
            args += ["--denoising-method", self.cfg.denoising_method]
        if self.cfg.low_mem:
            args += ["--low-mem"]
        if self.cfg.bids_filter:
            dest = self.cfg.work_dir / self.cfg.bids_filter.name
            if self.cfg.bids_filter.resolve() != dest.resolve():
                shutil.copy(self.cfg.bids_filter, dest)
            args += ["--bids-filter-file", f"/work/{dest.name}"]
        if self.cfg.task and not self.cfg.bids_filter:
            # Write a tiny filter file when only --task was supplied
            dest = self.cfg.work_dir / f"bids_filters_{self.cfg.task}.json"
            dest.write_text(f"{{ \"task\": \"{self.cfg.task}\" }}\n")
            args += ["--bids-filter-file", f"/work/{dest.name}"]
        return ToolSpec(self.cfg.image, args, vols, env)
