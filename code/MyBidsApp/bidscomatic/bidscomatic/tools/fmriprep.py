from __future__ import annotations

"""Wrapper for the fMRIPrep container."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Sequence
import shutil
import os
import structlog

from .base import Tool, ToolSpec
from bidscomatic.engines import ExecutionEngine

log = structlog.get_logger()


@dataclass
class FmriprepConfig:
    """Configuration values required to run fMRIPrep."""

    project_dir: Path
    data_dir: Path
    out_dir: Path
    work_dir: Path
    tf_dir: Path
    fs_license: Path
    image: str = "nipreps/fmriprep:25.1.4"
    anat_only: bool = False
    reconall: bool = False
    low_mem: bool = False
    n_procs: int = 1
    mem_mb: int = 16000
    omp_threads: int = 1
    extra_args: list[str] = field(default_factory=list)
    reset_bids_db: bool = False


class FmriprepTool(Tool):
    """Build and run fMRIPrep for one or more subjects."""

    def __init__(self, cfg: FmriprepConfig, subjects: Sequence[str]):
        """Store configuration and subject list."""
        self.cfg = cfg
        self.subjects = list(subjects)
        self._fs_license_dest = self.cfg.project_dir / "license.txt"

    # ------------------------------------------------------------------
    def _prepare(self) -> None:
        """Create working directories and stage the FreeSurfer license."""
        for p in (self.cfg.out_dir, self.cfg.work_dir, self.cfg.tf_dir):
            p.mkdir(parents=True, exist_ok=True)
        bids_db = self.cfg.work_dir / "bids_db"
        if self.cfg.reset_bids_db and bids_db.exists():
            shutil.rmtree(bids_db)
            log.info("[fmriprep] reset_bids_db", path=str(bids_db))
        bids_db.mkdir(exist_ok=True)

        if self.cfg.fs_license:
            if not self.cfg.fs_license.exists():
                raise FileNotFoundError(
                    f"FreeSurfer license not found: {self.cfg.fs_license}"
                )
            try:
                self.cfg.fs_license.read_text()
            except OSError as exc:  # pragma: no cover - rare
                raise PermissionError(
                    f"FreeSurfer license not readable: {self.cfg.fs_license}"
                ) from exc
            if self.cfg.fs_license.resolve() != self._fs_license_dest.resolve():
                shutil.copy(self.cfg.fs_license, self._fs_license_dest)
                log.info("[fmriprep] staged_fs_license", path=str(self._fs_license_dest))
        elif not self._fs_license_dest.exists():
            raise FileNotFoundError(
                f"FreeSurfer license not found: {self._fs_license_dest}"
            )
        else:
            try:
                self._fs_license_dest.read_text()
            except OSError as exc:  # pragma: no cover - rare
                raise PermissionError(
                    f"FreeSurfer license not readable: {self._fs_license_dest}"
                ) from exc

        plugin = self.cfg.work_dir / "nipype_multiproc.yml"
        plugin.write_text(
            "\n".join(
                [
                    "plugin: MultiProc",
                    "plugin_args:",
                    f"  n_procs: {self.cfg.n_procs}",
                    f"  memory_gb: {self.cfg.mem_mb // 1024}",
                    "  raise_insufficient: false",
                ]
            )
        )

    # ------------------------------------------------------------------
    def _build_spec_for_subject(self, sub: str) -> ToolSpec:
        """Assemble the container spec for a single subject."""
        vols = {
            str(self.cfg.data_dir): "/data:ro",
            str(self.cfg.out_dir): "/out",
            str(self.cfg.work_dir): "/work",
            str(self.cfg.tf_dir): "/opt/templateflow",
            str(self._fs_license_dest): "/license.txt:ro",
        }
        env = {
            "FS_LICENSE": "/license.txt",
            "TEMPLATEFLOW_HOME": os.environ.get("TEMPLATEFLOW_HOME", "/opt/templateflow"),
            "OMP_NUM_THREADS": str(self.cfg.omp_threads),
            "ITK_GLOBAL_DEFAULT_NUMBER_OF_THREADS": str(self.cfg.omp_threads),
            "OPENBLAS_NUM_THREADS": "1",
            "MKL_NUM_THREADS": "1",
            "NUMEXPR_NUM_THREADS": "1",
            "KMP_AFFINITY": "disabled",
            "KMP_INIT_AT_FORK": "FALSE",
        }
        args = [
            "/data",
            "/out",
            "participant",
            "--participant-label",
            sub,
            "--bids-database-dir",
            "/work/bids_db",
            "--use-plugin",
            "/work/nipype_multiproc.yml",
            "--nprocs",
            str(self.cfg.n_procs),
            "--omp-nthreads",
            str(self.cfg.omp_threads),
            "--mem-mb",
            str(self.cfg.mem_mb),
            "-w",
            "/work",
            "--clean-workdir",
            "--resource-monitor",
            "--output-spaces",
            "MNI152NLin6Asym:res-02",
        ]
        if self.cfg.anat_only:
            args += ["--anat-only"]
        if not self.cfg.reconall:
            args += ["--fs-no-reconall"]
        if self.cfg.low_mem:
            args += ["--low-mem"]
        args.extend(self.cfg.extra_args)
        return ToolSpec(self.cfg.image, args, vols, env)

    # ------------------------------------------------------------------
    def execute(self, engine: ExecutionEngine) -> int:  # type: ignore[override]
        """Run fMRIPrep via *engine* for each configured subject."""
        self._prepare()
        rc = 0
        for sub in self.subjects:
            spec = self._build_spec_for_subject(sub)
            rc = engine.run(
                spec.image,
                spec.args,
                volumes=spec.volumes,
                env=spec.env,
                entrypoint=spec.entrypoint,
            )
            if rc != 0:
                break
        return rc
