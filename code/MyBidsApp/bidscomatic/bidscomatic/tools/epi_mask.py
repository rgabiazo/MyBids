from __future__ import annotations

"""Generate robust brain masks for BOLD series."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Sequence
import os
import structlog

from .base import Tool, ToolSpec

log = structlog.get_logger()

MASK_SCRIPT = """
import os, glob, logging, re
import nibabel as nb
from nilearn.masking import compute_epi_mask

logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(message)s')
log = logging.getLogger('epi-mask')
overwrite = os.environ.get('OVERWRITE') == '1'
PREP_ROOT = os.environ.get('PREP_DIR', '/prep')

def collect_subjects():
    subs = os.environ.get('SUBJECTS', '').split()
    if subs:
        return [s if s.startswith('sub-') else f'sub-{s}' for s in subs]
    if not os.path.isdir(PREP_ROOT):
        return []
    return sorted(
        d for d in os.listdir(PREP_ROOT)
        if d.startswith('sub-') and os.path.isdir(os.path.join(PREP_ROOT, d))
    )

def collect_func_dirs(sub):
    base = os.path.join(PREP_ROOT, sub)
    dirs = sorted(glob.glob(os.path.join(base, 'ses-*/func')))
    path = os.path.join(base, 'func')
    if os.path.isdir(path):
        dirs.append(path)
    return dirs

def collect_runs(sub, tasks):
    runs = []
    for func_dir in collect_func_dirs(sub):
        if tasks:
            for t in tasks:
                pattern = f"{func_dir}/*task-{t}*space-MNI152NLin6Asym_res-*2_desc-preproc_bold.nii.gz"
                candidates = glob.glob(pattern)
                runs.extend(sorted(f for f in candidates if re.search(r'_res-(?:0?2)_', f)))
        else:
            pattern = f"{func_dir}/*task-*space-MNI152NLin6Asym_res-*2_desc-preproc_bold.nii.gz"
            candidates = glob.glob(pattern)
            runs.extend(sorted(f for f in candidates if re.search(r'_res-(?:0?2)_', f)))
    return runs

def process_run(fname):
    out = fname.replace('_desc-preproc_bold', '_desc-brain_mask')
    if os.path.exists(out) and not overwrite:
        log.info('%s exists – skipped (use --overwrite)', os.path.basename(out))
        return True
    bold = nb.load(fname)
    mask = compute_epi_mask(bold)
    if (mask.get_fdata() > 0).sum() == 0:
        mask = compute_epi_mask(bold, lower_cutoff=0.1, opening=2)
    mask.to_filename(out)
    vox = int((mask.get_fdata() > 0).sum())
    print(os.path.basename(out), 'voxels:', vox)
    return vox > 0

tasks = [t for t in os.environ.get('TASKS', '').split() if t]
all_ok = True
count = 0
for sub in collect_subjects():
    runs = collect_runs(sub, tasks)
    print(f'=== EPI Masks | Subject: {sub} ===')
    print(f'Found {len(runs)} run(s)')
    print()
    for run in runs:
        log.info('Processing run: %s', os.path.basename(run))
        all_ok &= process_run(run)
        count += 1
    print()
print(f'Processed {count} run(s). {"All masks are non-zero." if all_ok else "Found zero mask(s)."}')
"""


@dataclass
class EpiMaskConfig:
    """Configuration for generating EPI masks."""

    prep_dir: Path
    image: str = "nipreps/fmriprep:25.1.4"
    n_procs: int = 1
    mem_mb: int = 4000
    low_mem: bool = False
    omp_threads: int = 1
    overwrite: bool = False
    extra_args: list[str] = field(default_factory=list)


class EpiMaskTool(Tool):
    """Build a :class:`ToolSpec` for generating BOLD masks."""

    def __init__(self, cfg: EpiMaskConfig, subjects: Sequence[str], tasks: Sequence[str] | None = None):
        """Persist configuration and selection filters."""
        self.cfg = cfg
        self.subjects = list(subjects)
        self.tasks = list(tasks) if tasks else []

    def build_spec(self) -> ToolSpec:  # type: ignore[override]
        """Return the container spec for mask generation."""
        vols = {str(self.cfg.prep_dir): "/prep"}
        env = {
            "SUBJECTS": " ".join(self.subjects),
            "TASKS": " ".join(self.tasks),
            "OMP_NUM_THREADS": str(self.cfg.omp_threads),
            "ITK_GLOBAL_DEFAULT_NUMBER_OF_THREADS": str(self.cfg.omp_threads),
            "OPENBLAS_NUM_THREADS": "1",
            "MKL_NUM_THREADS": "1",
            "NUMEXPR_NUM_THREADS": "1",
            "OVERWRITE": "1" if self.cfg.overwrite else "0",
            "PREP_DIR": "/prep",
        }
        args = ["-c", MASK_SCRIPT]
        args.extend(self.cfg.extra_args)
        return ToolSpec(
            self.cfg.image,
            args,
            vols,
            env,
            entrypoint="python",
        )


def run_native(cfg: EpiMaskConfig, subjects: Sequence[str], tasks: Sequence[str] | None = None) -> None:
    """Generate EPI masks without requiring Docker.

    Parameters
    ----------
    cfg
        Configuration object describing the preprocessed derivatives
        directory and thread settings.
    subjects
        Iterable of subject identifiers (with or without ``sub-`` prefix).
    tasks
        Optional list of task labels to restrict the runs that are processed.
    """

    import glob
    import logging
    import re

    import nibabel as nb  # type: ignore
    from nilearn.masking import compute_epi_mask  # type: ignore

    logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(message)s')
    slog = logging.getLogger('epi-mask')

    subs = [s if str(s).startswith('sub-') else f'sub-{s}' for s in subjects]

    def collect_func_dirs(sub: str) -> list[Path]:
        """Return functional derivative directories for *sub*."""
        dirs = sorted(cfg.prep_dir.glob(f"{sub}/ses-*/func"))
        p = cfg.prep_dir / sub / "func"
        if p.is_dir():
            dirs.append(p)
        return dirs

    def collect_runs(sub: str) -> list[Path]:
        """Return matching runs for *sub* filtered by ``tasks`` if provided."""
        runs: list[Path] = []
        for func_dir in collect_func_dirs(sub):
            if tasks:
                patterns = [
                    f"*task-{t}*space-MNI152NLin6Asym_res-*2_desc-preproc_bold.nii.gz"
                    for t in tasks
                ]
            else:
                patterns = [
                    "*task-*space-MNI152NLin6Asym_res-*2_desc-preproc_bold.nii.gz"
                ]
            for pattern in patterns:
                candidates = func_dir.glob(pattern)
                runs.extend(
                    sorted(
                        f for f in candidates if re.search(r"_res-(?:0?2)_", f.name)
                    )
                )
        return runs

    env = {
        "OMP_NUM_THREADS": str(cfg.omp_threads),
        "ITK_GLOBAL_DEFAULT_NUMBER_OF_THREADS": str(cfg.omp_threads),
        "OPENBLAS_NUM_THREADS": "1",
        "MKL_NUM_THREADS": "1",
        "NUMEXPR_NUM_THREADS": "1",
    }
    old_env = os.environ.copy()
    os.environ.update(env)
    try:
        all_ok = True
        count = 0
        for sub in subs:
            runs = collect_runs(sub)
            print(f"=== EPI Masks | Subject: {sub} ===")
            print(f"Found {len(runs)} run(s)")
            print()
            for run in runs:
                slog.info("Processing run: %s", run.name)
                out = run.with_name(run.name.replace("_desc-preproc_bold", "_desc-brain_mask"))
                if out.exists() and not cfg.overwrite:
                    slog.info("%s exists – skipped (use --overwrite)", out.name)
                    all_ok &= True
                else:
                    bold = nb.load(str(run))
                    mask = compute_epi_mask(bold)
                    if (mask.get_fdata() > 0).sum() == 0:
                        mask = compute_epi_mask(bold, lower_cutoff=0.1, opening=2)
                    mask.to_filename(str(out))
                    vox = int((mask.get_fdata() > 0).sum())
                    print(out.name, "voxels:", vox)
                    all_ok &= vox > 0
                count += 1
            print()
        print(
            f"Processed {count} run(s). {'All masks are non-zero.' if all_ok else 'Found zero mask(s).'}"
        )
    finally:
        os.environ.clear()
        os.environ.update(old_env)

