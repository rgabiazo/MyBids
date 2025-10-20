"""Simple CSV writers for QC metrics."""

from __future__ import annotations

from typing import List, Dict
import os

import pandas as pd
import structlog

log = structlog.get_logger()


def write_pairwise_csv(rows: List[Dict[str, object]], csv_path: str) -> None:
    """Write paired pre/post QC metrics to *csv_path*."""
    df = pd.DataFrame(rows, columns=[
        "id", "n_vols_pre", "n_vols_post",
        "mean_FD_mm", "%FD_gt_thresh",
        "mean_DVARS_pre", "mean_DVARS_post", "DVARS_change_%",
        "tSNR_mean_pre", "tSNR_mean_post", "tSNR_change_%",
    ])
    os.makedirs(os.path.dirname(csv_path), exist_ok=True)
    df.to_csv(csv_path, index=False)
    log.info("saved_pairwise_csv", path=csv_path)


def write_single_csv(rows: List[Dict[str, object]], csv_path: str) -> None:
    """Write single-run QC metrics to *csv_path*."""
    df = pd.DataFrame(rows, columns=[
        "id", "label", "n_vols",
        "mean_FD_mm", "%FD_gt_thresh",
        "mean_DVARS", "tSNR_mean", "tSNR_median",
        "bold_path",
    ])
    os.makedirs(os.path.dirname(csv_path), exist_ok=True)
    df.to_csv(csv_path, index=False)
    log.info("saved_single_csv", path=csv_path)
