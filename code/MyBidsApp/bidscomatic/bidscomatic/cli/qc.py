"""Quality-control metrics for BOLD runs."""

from __future__ import annotations

from pathlib import Path
from typing import List, Dict, Tuple, Optional

import os

import click
import numpy as np
import structlog

from bidscomatic.qc.metrics import (
    fd_from_confounds,
    fd_power_from_par,
    stream_dvars,
    stream_tsnr,
    load_mask_allow,
    RunMetrics,
)
from bidscomatic.qc.discover import (
    find_bold_files,
    discover_runs,
    find_mask_for_bold,
    find_confounds_for_bold,
    find_par_for_bold,
)
from bidscomatic.qc.report import write_pairwise_csv, write_single_csv
from bidscomatic.qc.display import log_header, log_inputs, log_metric_start
from bidscomatic.utils.paths import qc_run_dir

log = structlog.get_logger()


def _compute_metrics(
    bold,
    fd_from: str,
    fd_power_radius: float,
    calc_dvars: bool,
    calc_tsnr: bool,
    fd_thresh: float,
    save_series: bool,
    write_tsnr_nifti: bool,
    allow_naive_mask: bool,
    update_every: int,
    overwrite: bool,
    mask_fallback: Optional[np.ndarray] = None,
) -> Tuple[Optional[RunMetrics], Optional[np.ndarray]]:
    """Compute metrics for a single run.

    Returns a tuple ``(metrics, mask_used)``. When ``overwrite`` is ``False``
    and the QC output directory already exists under the dataset-level ``qc``
    folder, ``(None, None)`` is returned to indicate the run was skipped.
    """

    run_stem = Path(bold.path).name.replace(".nii.gz", "")
    qc_dir = qc_run_dir(Path(bold.path), stem=run_stem)
    if qc_dir.exists() and not overwrite:
        log.info("skip_existing", bold=bold.path, qc_dir=str(qc_dir))
        return None, None
    qc_dir.mkdir(parents=True, exist_ok=True)

    mask_path = find_mask_for_bold(bold.path)
    if mask_path:
        mask = load_mask_allow(mask_path, bold.path, allow_naive_mask)
    elif mask_fallback is not None:
        mask = mask_fallback
    else:
        mask = load_mask_allow(None, bold.path, allow_naive_mask)
    mask_name = (
        mask_path
        if mask_path
        else "<fallback>" if mask_fallback is not None else "<naive>"
    )

    import nibabel as nib

    img = nib.load(bold.path)
    if mask.shape != img.shape[:3]:
        raise click.ClickException(
            f"Mask shape {mask.shape} does not match BOLD {img.shape[:3]}"
        )
    n_vols = img.shape[3]

    fd_series = None
    fd_src = None
    conf = None
    if fd_from in ("auto", "confounds"):
        conf = find_confounds_for_bold(bold.path)
        if conf:
            fd_series = fd_from_confounds(conf)
            if fd_series is not None:
                fd_src = "confounds"
    if fd_series is None and fd_from in ("auto", "par"):
        par = find_par_for_bold(bold.path)
        if par:
            fd_series = fd_power_from_par(par, head_radius_mm=fd_power_radius)
            if fd_series is not None:
                fd_src = "par"
    if fd_series is None:
        log.warning("fd_missing", bold=bold.path)
    elif len(fd_series) != n_vols:
        raise click.ClickException(
            f"FD series length {len(fd_series)} does not match BOLD {n_vols} volumes"
        )
    else:
        log.info("fd_source", source=fd_src, bold=bold.path)

    mean_dvars = None
    if calc_dvars:
        log_metric_start(bold.label, "DVARS", bold.path, mask_name, conf)
        dvars = stream_dvars(bold.path, mask, update_every, desc=f"{bold.label} DVARS")
        mean_dvars = float(np.nanmean(dvars))
        if save_series:
            out = qc_dir / f"{run_stem}_dvars.tsv"
            np.savetxt(out, dvars, fmt="%.6f")
            log.info("saved_dvars", path=str(out))

    tsnr_mean = tsnr_median = None
    if calc_tsnr:
        log_metric_start(bold.label, "tSNR", bold.path, mask_name, conf)
        tsnr_mean, tsnr_median, tsnr_map = stream_tsnr(
            bold.path, mask, update_every, desc=f"{bold.label} tSNR"
        )
        if save_series:
            out = qc_dir / f"{run_stem}_tsnr.tsv"
            np.savetxt(out, tsnr_map, fmt="%.6f")
            log.info("saved_tsnr", path=str(out))
        if write_tsnr_nifti:
            vol = np.zeros(img.shape[:3], dtype="float32")
            vol[mask] = tsnr_map
            tsnr_img = nib.Nifti1Image(vol, img.affine, img.header)
            out_img = qc_dir / f"{run_stem}_desc-tsnr.nii.gz"
            nib.save(tsnr_img, out_img)
            log.info("saved_tsnr_nifti", path=str(out_img))

    fd_mean = fd_pct = None
    if fd_series is not None:
        fd_mean = float(np.nanmean(fd_series))
        valid = np.isfinite(fd_series)
        fd_pct = (
            float(100.0 * np.mean(fd_series[valid] > fd_thresh)) if valid.any() else np.nan
        )
        if save_series:
            out = qc_dir / f"{run_stem}_fd.tsv"
            np.savetxt(out, fd_series, fmt="%.6f")
            log.info("saved_fd", path=str(out))

    metrics = RunMetrics(
        label=bold.label,
        bold_path=bold.path,
        n_vols=n_vols,
        mean_dvars=mean_dvars,
        fd_mean=fd_mean,
        fd_pct_over=fd_pct,
        tsnr_mean=tsnr_mean,
        tsnr_median=tsnr_median,
    )
    return metrics, mask


@click.command(name="qc", context_settings=dict(help_option_names=["-h", "--help"], show_default=True))
@click.option("-i", "--inputs", multiple=True, type=click.Path(path_type=Path), required=True)
@click.option("--recursive", is_flag=True, help="Recurse into directories.")
@click.option("--bold-glob", multiple=True, help="Glob(s) relative to inputs.")
@click.option("--task", multiple=True, help="Task name(s) filter.")
@click.option("--space", default=None, help="Space filter like MNI...")
@click.option("--pre-tag", default="desc-preproc_bold")
@click.option("--post-tag", default="desc-nonaggrDenoised_bold")
@click.option("--calc-dvars", is_flag=True)
@click.option("--calc-tsnr", is_flag=True)
@click.option("--fd-from", type=click.Choice(["auto", "confounds", "par"]), default="auto")
@click.option("--fd-power-radius", default=50.0, type=float)
@click.option("--fd-thresh", default=0.5, type=float)
@click.option("--pairs-only", is_flag=True, help="Only output pairs when both PRE and POST exist.")
@click.option("--save-series", is_flag=True, help="Write metric series inside qc/ directories.")
@click.option("--allow-naive-mask", is_flag=True, help="Use mean image > 0 if mask missing.")
@click.option("--write-tsnr-nifti", is_flag=True, help="Write voxelwise tSNR maps as NIfTI.")
@click.option("--update-every", default=50, type=int)
@click.option("--overwrite", is_flag=True, help="Recompute even if qc/ directory exists")
def cli(
    inputs: List[Path],
    recursive: bool,
    bold_glob: Tuple[str, ...],
    task: Tuple[str, ...],
    space: str | None,
    pre_tag: str,
    post_tag: str,
    calc_dvars: bool,
    calc_tsnr: bool,
    fd_from: str,
    fd_power_radius: float,
    fd_thresh: float,
    pairs_only: bool,
    save_series: bool,
    allow_naive_mask: bool,
    write_tsnr_nifti: bool,
    update_every: int,
    overwrite: bool,
) -> None:
    """Compute QC metrics for one or more BOLD runs.

    Args:
        inputs: Files or directories used to locate BOLD runs.
        recursive: When ``True`` recurse into sub-directories.
        bold_glob: Optional glob patterns relative to *inputs*.
        task: Task filters applied to discovered runs.
        space: Spatial filter string such as ``MNI152NLin6Asym``.
        pre_tag: Filename tag that marks pre-processed runs.
        post_tag: Filename tag that marks post-processed runs.
        calc_dvars: Whether to compute DVARS metrics.
        calc_tsnr: Whether to compute tSNR metrics.
        fd_from: Source used to derive framewise displacement values.
        fd_power_radius: Head radius used for FD derived from motion parameters.
        fd_thresh: Threshold for reporting FD percentages.
        pairs_only: Skip runs without pre/post pairs when ``True``.
        save_series: Persist per-volume metric series to disk.
        allow_naive_mask: Fall back to simple masks when anatomical masks fail.
        write_tsnr_nifti: Emit voxelwise tSNR maps as NIfTI images.
        update_every: Number of volumes processed between progress updates.
        overwrite: Recalculate metrics even if outputs exist.
    """
    if write_tsnr_nifti and not calc_tsnr:
        raise click.BadOptionUsage("--write-tsnr-nifti", "requires --calc-tsnr")
    paths = [str(p) for p in inputs]
    bolds = find_bold_files(paths, recursive, list(bold_glob) or None)
    if not bolds:
        raise click.ClickException("No BOLD files found")
    runs = discover_runs(bolds, pre_tag, post_tag, space, list(task) or None)
    grouped: Dict[Tuple, Dict[str, List]] = {}
    for r in runs:
        grouped.setdefault(r.id_key, {"PRE": [], "POST": [], "SINGLE": []})
        grouped[r.id_key][r.label].append(r)

    metrics_list = []
    if calc_dvars:
        metrics_list.append("DVARS")
    metrics_list.append("FD")
    if calc_tsnr:
        metrics_list.append("tSNR")
    log_header(metrics_list, len(bolds), len(grouped))

    rows_pair: List[Dict[str, object]] = []
    rows_single: List[Dict[str, object]] = []

    for bucket in grouped.values():
        pres = bucket["PRE"]
        posts = bucket["POST"]
        singles = bucket["SINGLE"]
        if pres and posts:
            log_inputs(pres[0].path, posts[0].path)
            pre_res = _compute_metrics(
                pres[0],
                fd_from,
                fd_power_radius,
                calc_dvars,
                calc_tsnr,
                fd_thresh,
                save_series,
                write_tsnr_nifti,
                allow_naive_mask,
                update_every,
                overwrite,
            )
            if pre_res[0] is None:
                continue
            pre_m, pre_mask = pre_res
            post_res = _compute_metrics(
                posts[0],
                fd_from,
                fd_power_radius,
                calc_dvars,
                calc_tsnr,
                fd_thresh,
                save_series,
                write_tsnr_nifti,
                allow_naive_mask,
                update_every,
                overwrite,
                mask_fallback=pre_mask,
            )
            if post_res[0] is None:
                continue
            post_m, _ = post_res
            rows_pair.append(
                {
                    "id": "_".join(
                        filter(None, [pres[0].tokens.get(k) for k in ("sub", "ses", "task", "dir", "run")])
                    ),
                    "n_vols_pre": pre_m.n_vols,
                    "n_vols_post": post_m.n_vols,
                    "mean_FD_mm": pre_m.fd_mean,
                    "%FD_gt_thresh": pre_m.fd_pct_over,
                    "mean_DVARS_pre": pre_m.mean_dvars,
                    "mean_DVARS_post": post_m.mean_dvars,
                    "DVARS_change_%": (
                        100.0 * (post_m.mean_dvars - pre_m.mean_dvars) / pre_m.mean_dvars
                        if (pre_m.mean_dvars and post_m.mean_dvars)
                        else None
                    ),
                    "tSNR_mean_pre": pre_m.tsnr_mean,
                    "tSNR_mean_post": post_m.tsnr_mean,
                    "tSNR_change_%": (
                        100.0 * (post_m.tsnr_mean - pre_m.tsnr_mean) / pre_m.tsnr_mean
                        if (pre_m.tsnr_mean and post_m.tsnr_mean)
                        else None
                    ),
                }
            )
        elif not pairs_only:
            for r in pres + posts + singles:
                log_inputs(r.path, None)
                res = _compute_metrics(
                    r,
                    fd_from,
                    fd_power_radius,
                    calc_dvars,
                    calc_tsnr,
                    fd_thresh,
                    save_series,
                    write_tsnr_nifti,
                    allow_naive_mask,
                    update_every,
                    overwrite,
                )
                if res[0] is None:
                    continue
                m, _ = res
                rows_single.append(
                    {
                        "id": "_".join(
                            filter(None, [r.tokens.get(k) for k in ("sub", "ses", "task", "dir", "run")])
                        ),
                        "label": r.label,
                        "n_vols": m.n_vols,
                        "mean_FD_mm": m.fd_mean,
                        "%FD_gt_thresh": m.fd_pct_over,
                        "mean_DVARS": m.mean_dvars,
                        "tSNR_mean": m.tsnr_mean,
                        "tSNR_median": m.tsnr_median,
                        "bold_path": r.path,
                    }
                )

    if rows_pair:
        write_pairwise_csv(rows_pair, os.path.join(os.getcwd(), "qc_pairs.csv"))
    if rows_single:
        write_single_csv(rows_single, os.path.join(os.getcwd(), "qc_single.csv"))
