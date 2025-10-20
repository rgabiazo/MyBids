"""Entry-point for ``bidscomatic-cli preprocess``.

This module exposes a Click *group* with sub-commands for various
preprocessing helpers.  Historically only pepolar fieldmap derivation was
available; the command now also provides a wrapper for fMRIPost-AROMA.
"""

from __future__ import annotations

from pathlib import Path
from typing import Tuple

import json
import click
import structlog

from bidscomatic.config.pepolar import PepolarConfig
from bidscomatic.pipelines.types import SubjectSession
from bidscomatic.pipelines.pepolar import derive_pepolar_fieldmaps
from bidscomatic.utils.filters import split_commas
from bidscomatic.config.tools import (
    load_aroma_config,
    load_fmriprep_config,
    load_epi_mask_config,
)
from bidscomatic.tools import (
    AromaTool,
    AromaConfig,
    FmriprepTool,
    FmriprepConfig,
    EpiMaskTool,
    EpiMaskConfig,
    run_epi_mask_native,
)
from bidscomatic.engines.docker import DockerEngine
from bidscomatic.utils.resources import tune_resources, format_resource_summary

log = structlog.get_logger()


@click.group(name="preprocess")
def preprocess_group() -> None:
    """Container-based preprocessing helpers."""


@preprocess_group.command("pepolar")
@click.option("--filter-sub", "filter_sub", multiple=True, callback=split_commas, metavar="<sub>")
@click.option("--filter-ses", "filter_ses", multiple=True, callback=split_commas, metavar="<ses>")
@click.option("--task", "tasks", multiple=True, callback=split_commas, metavar="<task>")
@click.option("--pepolar-split-rule", type=click.Choice(["mad", "iqr", "fixed"]), default="mad")
@click.option("--mad-k", type=float, default=3.0)
@click.option("--iqr-k", type=float, default=1.5)
@click.option("--nmad-bounds", type=click.Choice(["adaptive", "fixed", "none"]), default="adaptive")
@click.option("--nmad-bounds-k", type=float, default=1.5)
@click.option("--split-floor", type=float, default=0.06)
@click.option("--split-cap", type=float, default=0.20)
@click.option("--use-cc", type=int, default=1)
@click.option("--cc-rule", type=click.Choice(["fixed", "mad", "iqr", "off"]), default="fixed")
@click.option("--cc-min", type=float, default=0.97)
@click.option("--cc-bounds", type=click.Choice(["adaptive", "fixed", "none"]), default="adaptive")
@click.option("--cc-bounds-k", type=float, default=1.5)
@click.option("--split-logic", type=click.Choice(["OR", "AND"]), default="OR")
@click.option("--auto-split", type=int, default=1)
@click.option("--intensity-match", type=int, default=1)
@click.option("--use-brainmask", type=int, default=1)
@click.option("--bet-f", type=float, default=0.30)
@click.option("--geom-enforce", type=int, default=1)
@click.option("--use-bids-uri", type=int, default=0)
@click.option("--dry-run", is_flag=True, help="Perform a trial run without writing files.")
@click.pass_obj
def pepolar(
    ctx_obj,
    filter_sub: Tuple[str, ...],
    filter_ses: Tuple[str, ...],
    tasks: Tuple[str, ...],
    pepolar_split_rule: str,
    mad_k: float,
    iqr_k: float,
    nmad_bounds: str,
    nmad_bounds_k: float,
    split_floor: float,
    split_cap: float,
    use_cc: int,
    cc_rule: str,
    cc_min: float,
    cc_bounds: str,
    cc_bounds_k: float,
    split_logic: str,
    auto_split: int,
    intensity_match: int,
    use_brainmask: int,
    bet_f: float,
    geom_enforce: int,
    use_bids_uri: int,
    dry_run: bool,
) -> None:
    """Derive opposite phase-encoding fieldmaps (PEPOLAR)."""

    root: Path = ctx_obj["root"]
    subs = filter_sub or sorted(
        p.name.removeprefix("sub-") for p in root.glob("sub-*")
    )
    sess = filter_ses or [None]

    sessions = [
        SubjectSession(root=root, sub=f"sub-{s}", ses=(f"ses-{se}" if se else None))
        for s in subs
        for se in sess
    ]

    cfg = PepolarConfig(
        split_rule=pepolar_split_rule,
        mad_k=mad_k,
        iqr_k=iqr_k,
        nmad_bounds=nmad_bounds,
        nmad_bounds_k=nmad_bounds_k,
        split_floor=split_floor,
        split_cap=split_cap,
        use_cc=use_cc,
        cc_rule=cc_rule,
        cc_min=cc_min,
        cc_bounds=cc_bounds,
        cc_bounds_k=cc_bounds_k,
        split_logic=split_logic,
        auto_split=auto_split,
        intensity_match=intensity_match,
        use_brainmask=use_brainmask,
        bet_f=bet_f,
        geom_enforce=geom_enforce,
        use_bids_uri=use_bids_uri,
        dry_run=dry_run,
    )

    paths = derive_pepolar_fieldmaps(root, sessions, cfg, tasks=tasks)
    if not paths:
        click.echo("No opposite phase-encoding fieldmaps were derived.")
    else:
        intro = "Dry run: would write" if dry_run else "Wrote"
        click.echo(f"{intro} {len(paths)} fieldmap(s):")
        for p in paths:
            click.echo(f"  {p}")


@preprocess_group.command("aroma")
@click.option(
    "--subjects",
    multiple=True,
    callback=split_commas,
    help="Comma-separated or repeatable subject IDs",
)
@click.option("--task")
@click.option("--bids-filter-file", type=click.Path(path_type=Path))
@click.option(
    "--create-filter",
    type=str,
    help="Create a simple filter file (e.g. 'task=memory') inside the work directory",
)
@click.option("--prep-dir", type=click.Path(path_type=Path))
@click.option("--out-dir", type=click.Path(path_type=Path))
@click.option("--work-dir", type=click.Path(path_type=Path))
@click.option("--tf-dir", type=click.Path(path_type=Path))
@click.option("--image")
@click.option("--melodic-dim")
@click.option(
    "--denoising-method",
    type=click.Choice(["nonaggr", "aggr", "both"]),
    default=None,
    help="Select ICA-AROMA denoising strategy (default: nonaggr)",
)
@click.option(
    "--denoising-off",
    is_flag=True,
    help="Disable ICA-AROMA denoising",
)
@click.option("--nprocs", type=int)
@click.option("--mem-mb", type=int)
@click.option("--omp-nthreads", type=int)
@click.option("--clean-workdir/--no-clean-workdir", default=None)
@click.option("--stop-on-first-crash/--no-stop-on-first-crash", default=None)
@click.option("--low-mem/--no-low-mem", default=None)
@click.option(
    "--no-auto-resources", is_flag=True, help="Use static resources from configuration"
)
@click.option("--reset-bids-db/--no-reset-bids-db", default=None)
@click.option("--runner", type=click.Choice(["native", "docker"]), default="docker")
@click.pass_obj
def aroma_cmd(
    ctx_obj,
    subjects,
    task,
    bids_filter_file,
    create_filter,
    prep_dir,
    out_dir,
    work_dir,
    tf_dir,
    image,
    melodic_dim,
    denoising_method,
    denoising_off,
    nprocs,
    mem_mb,
    omp_nthreads,
    clean_workdir,
    stop_on_first_crash,
    low_mem,
    no_auto_resources,
    reset_bids_db,
    runner,
):
    """Run fMRIPost-AROMA on preprocessed BOLD files."""

    root: Path = ctx_obj["root"]

    if create_filter and bids_filter_file:
        raise click.ClickException(
            "--create-filter cannot be used with --bids-filter-file"
        )

    overrides = {
        "prep_dir": prep_dir,
        "out_dir": out_dir,
        "work_dir": work_dir,
        "tf_dir": tf_dir,
        "image": image,
        "melodic_dim": melodic_dim,
        "clean_workdir": clean_workdir,
        "stop_on_first_crash": stop_on_first_crash,
        "reset_bids_db": reset_bids_db,
    }
    cfg_model = load_aroma_config(root, overrides=overrides)
    if denoising_off:
        cfg_model.denoising_method = None
    elif denoising_method:
        cfg_model.denoising_method = denoising_method

    if bids_filter_file and not bids_filter_file.is_absolute():
        bids_filter_file = root / bids_filter_file

    if create_filter:
        try:
            key, value = create_filter.split("=", 1)
        except ValueError as exc:  # pragma: no cover - defensive
            raise click.ClickException(
                "--create-filter requires KEY=VALUE syntax"
            ) from exc
        cfg_model.work_dir.mkdir(parents=True, exist_ok=True)
        filter_path = cfg_model.work_dir / f"bids_filters_{value}.json"
        filter_path.write_text(json.dumps({key: value}) + "\n")
        bids_filter_file = filter_path
        log.info("[aroma] created_filter_file", path=str(filter_path))

    if task and bids_filter_file and not create_filter:
        log.info(
            "[aroma] --bids-filter-file overrides --task",
            bids_filter=str(bids_filter_file),
            task=task,
        )

    subs = list(subjects)
    subs_for_tool = subs
    if not subs:
        subs = sorted(
            p.name.removeprefix("sub-")
            for p in cfg_model.prep_dir.glob("sub-*")
            if p.is_dir()
        )
        if not subs:
            raise click.ClickException(
                f"No subjects found under {cfg_model.prep_dir}"
            )
        subs_for_tool = []
        log.info("[aroma] auto_discovered_subjects", subjects=subs)
    else:
        log.info("[aroma] subjects_provided", subjects=subs)

    res = tune_resources(
        cfg_model.image,
        runner=runner,
        auto=not no_auto_resources,
        n_procs_default=cfg_model.n_procs,
        mem_mb_default=cfg_model.mem_mb,
        low_mem_default=cfg_model.low_mem,
        n_procs_override=nprocs,
        mem_mb_override=mem_mb,
        low_mem_override=low_mem,
        omp_threads_default=cfg_model.omp_threads,
        omp_threads_override=omp_nthreads,
    )
    log.info(
        "[aroma] resources.tuned",
        platform=res.platform,
        host_arch=res.host_arch,
        cpu_docker=res.cpu_docker,
        mem_total_mb=res.mem_total_mb,
        headroom_mb=res.headroom_mb,
        n_procs=res.n_procs,
        mem_mb=res.mem_mb,
        low_mem=res.low_mem,
        omp_threads=res.omp_threads,
    )
    summary = format_resource_summary(
        res, subjects=subs, image=cfg_model.image
    )
    click.echo(summary + "\n")
    cfg = AromaConfig(
        project_dir=root,
        prep_dir=cfg_model.prep_dir,
        out_dir=cfg_model.out_dir,
        work_dir=cfg_model.work_dir,
        tf_dir=cfg_model.tf_dir,
        image=cfg_model.image,
        task=task,
        bids_filter=bids_filter_file,
        melodic_dim=str(cfg_model.melodic_dim),
        denoising_method=cfg_model.denoising_method,
        low_mem=res.low_mem,
        n_procs=res.n_procs,
        mem_mb=res.mem_mb,
        omp_threads=res.omp_threads,
        clean_workdir=cfg_model.clean_workdir,
        stop_on_first_crash=cfg_model.stop_on_first_crash,
        reset_bids_db=cfg_model.reset_bids_db,
    )
    engine = DockerEngine(platform=res.platform)
    AromaTool(cfg, subs_for_tool).execute(engine)


@preprocess_group.command("fmriprep")
@click.option("--subjects", multiple=True, callback=split_commas)
@click.option("--data-dir", type=click.Path(path_type=Path))
@click.option("--out-dir", type=click.Path(path_type=Path))
@click.option("--work-dir", type=click.Path(path_type=Path))
@click.option("--tf-dir", type=click.Path(path_type=Path))
@click.option("--fs-license", type=click.Path(path_type=Path))
@click.option("--image")
@click.option("--anat-only/--no-anat-only", default=None)
@click.option("--reconall/--no-reconall", default=None)
@click.option("--nprocs", type=int)
@click.option("--mem-mb", type=int)
@click.option("--omp-nthreads", type=int)
@click.option("--low-mem/--no-low-mem", default=None)
@click.option("--no-auto-resources", is_flag=True, help="Use static resources from configuration")
@click.option("--reset-bids-db/--no-reset-bids-db", default=None)
@click.option("--runner", type=click.Choice(["native", "docker"]), default="native")
@click.pass_obj
def fmriprep_cmd(
    ctx_obj,
    subjects,
    data_dir,
    out_dir,
    work_dir,
    tf_dir,
    fs_license,
    image,
    anat_only,
    reconall,
    nprocs,
    mem_mb,
    omp_nthreads,
    low_mem,
    no_auto_resources,
    reset_bids_db,
    runner,
):
    """Run fMRIPrep on raw BIDS data."""

    root: Path = ctx_obj["root"]
    overrides = {
        "data_dir": data_dir,
        "out_dir": out_dir,
        "work_dir": work_dir,
        "tf_dir": tf_dir,
        "fs_license": fs_license,
        "image": image,
        "anat_only": anat_only,
        "reconall": reconall,
        "reset_bids_db": reset_bids_db,
    }
    cfg_model = load_fmriprep_config(root, overrides=overrides)

    subs = list(subjects)
    if not subs:
        subs = sorted(
            p.name.removeprefix("sub-")
            for p in cfg_model.data_dir.glob("sub-*")
            if p.is_dir()
        )
        if not subs:
            raise click.ClickException(f"No subjects found under {cfg_model.data_dir}")
        log.info("[fmriprep] auto_discovered_subjects", subjects=subs)
    else:
        log.info("[fmriprep] subjects_provided", subjects=subs)

    per_proc = 6000 if cfg_model.anat_only else 9000
    res = tune_resources(
        cfg_model.image,
        auto=not no_auto_resources,
        n_procs_default=cfg_model.n_procs,
        mem_mb_default=cfg_model.mem_mb,
        low_mem_default=cfg_model.low_mem,
        per_proc_mb=per_proc,
        n_procs_override=nprocs,
        mem_mb_override=mem_mb,
        low_mem_override=low_mem,
        omp_threads_default=cfg_model.omp_threads,
        omp_threads_override=omp_nthreads,
    )
    log.info(
        "[fmriprep] resources.tuned",
        platform=res.platform,
        host_arch=res.host_arch,
        cpu_docker=res.cpu_docker,
        mem_total_mb=res.mem_total_mb,
        headroom_mb=res.headroom_mb,
        n_procs=res.n_procs,
        mem_mb=res.mem_mb,
        low_mem=res.low_mem,
        omp_threads=res.omp_threads,
    )
    click.echo(
        format_resource_summary(
            res, subjects=subs, image=cfg_model.image
        )
    )

    cfg = FmriprepConfig(
        project_dir=root,
        data_dir=cfg_model.data_dir,
        out_dir=cfg_model.out_dir,
        work_dir=cfg_model.work_dir,
        tf_dir=cfg_model.tf_dir,
        fs_license=cfg_model.fs_license,
        image=cfg_model.image,
        anat_only=cfg_model.anat_only if anat_only is None else anat_only,
        reconall=cfg_model.reconall if reconall is None else reconall,
        low_mem=res.low_mem,
        n_procs=res.n_procs,
        mem_mb=res.mem_mb,
        omp_threads=res.omp_threads,
        reset_bids_db=cfg_model.reset_bids_db,
    )
    engine = DockerEngine(platform=res.platform)
    FmriprepTool(cfg, subs).execute(engine)


@preprocess_group.command("epi-mask")
@click.option("--subjects", multiple=True, callback=split_commas)
@click.option("--task", "tasks", multiple=True, callback=split_commas, metavar="<task>")
@click.option("--prep-dir", type=click.Path(path_type=Path))
@click.option("--image")
@click.option("--nprocs", type=int)
@click.option("--mem-mb", type=int)
@click.option("--omp-nthreads", type=int)
@click.option("--low-mem/--no-low-mem", default=None)
@click.option("--no-auto-resources", is_flag=True, help="Use static resources from configuration")
@click.option("--overwrite", is_flag=True, help="Overwrite existing masks.")
@click.option("--runner", type=click.Choice(["native", "docker"]), default="native")
@click.pass_obj
def epi_mask_cmd(
    ctx_obj,
    subjects,
    tasks,
    prep_dir,
    image,
    nprocs,
    mem_mb,
    omp_nthreads,
    low_mem,
    no_auto_resources,
    overwrite,
    runner,
):
    """Create brain masks from preprocessed BOLD runs."""

    root: Path = ctx_obj["root"]
    overrides = {"prep_dir": prep_dir, "image": image}
    cfg_model = load_epi_mask_config(root, overrides=overrides)

    subs = list(subjects)
    if not subs:
        subs = sorted(
            p.name.removeprefix("sub-")
            for p in cfg_model.prep_dir.glob("sub-*")
            if p.is_dir()
        )
        if not subs:
            raise click.ClickException(f"No subjects found under {cfg_model.prep_dir}")
        log.info("[epi_mask] auto_discovered_subjects", subjects=subs)
    else:
        log.info("[epi_mask] subjects_provided", subjects=subs)

    res = tune_resources(
        cfg_model.image,
        runner=runner,
        auto=not no_auto_resources,
        n_procs_default=cfg_model.n_procs,
        mem_mb_default=cfg_model.mem_mb,
        low_mem_default=cfg_model.low_mem,
        n_procs_override=nprocs,
        mem_mb_override=mem_mb,
        low_mem_override=low_mem,
        omp_threads_default=cfg_model.omp_threads,
        omp_threads_override=omp_nthreads,
    )
    log.info(
        "[epi_mask] resources.tuned",
        platform=res.platform,
        host_arch=res.host_arch,
        cpu_docker=res.cpu_docker,
        mem_total_mb=res.mem_total_mb,
        headroom_mb=res.headroom_mb,
        n_procs=res.n_procs,
        mem_mb=res.mem_mb,
        low_mem=res.low_mem,
        omp_threads=res.omp_threads,
    )
    summary = format_resource_summary(
        res, subjects=subs, image=cfg_model.image
    )
    click.echo(summary + "\n")

    cfg = EpiMaskConfig(
        prep_dir=cfg_model.prep_dir,
        image=cfg_model.image,
        n_procs=res.n_procs,
        mem_mb=res.mem_mb,
        low_mem=res.low_mem,
        omp_threads=res.omp_threads,
        overwrite=overwrite or cfg_model.overwrite,
    )
    if runner == "docker":
        engine = DockerEngine(platform=res.platform)
        EpiMaskTool(cfg, subs, tasks).execute(engine)
    else:
        run_epi_mask_native(cfg, subs, tasks)


cli = preprocess_group
