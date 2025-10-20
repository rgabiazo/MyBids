"""User-facing console helpers for QC metrics."""
from __future__ import annotations

import os
import structlog

log = structlog.get_logger()


def log_header(metrics: list[str], n_bolds: int, n_groups: int) -> None:
    """Display a top summary banner for the run."""
    title = " | ".join(metrics)
    line = "\u2500" * max(40, len(title))  # unicode box drawing '─'
    log.info(title)
    log.info(line)
    plural_g = "s" if n_groups != 1 else ""
    log.info(f"Found {n_bolds} BOLD file(s) in {n_groups} group{plural_g}")


def log_inputs(pre: str | None, post: str | None) -> None:
    """List input files, handling pairs or single runs."""
    log.info("Inputs:")
    if pre and post:
        log.info(f"  pre : {os.path.basename(pre)}")
        log.info(f"  post: {os.path.basename(post)}")
    elif pre:
        log.info(f"  file: {os.path.basename(pre)}")
    elif post:
        log.info(f"  file: {os.path.basename(post)}")


def log_metric_start(label: str, metric: str, bold: str, mask: str, confounds: str | None = None) -> None:
    """Announce the start of a metric computation for a run."""
    log.info(f"\u25B6 {label} {metric}")  # ▶ arrow
    if confounds:
        log.info(f"  Confounds: {os.path.basename(confounds)}")
    log.info(f"  BOLD     : {os.path.basename(bold)}")
    log.info(f"  Mask     : {os.path.basename(mask)}")


def log_progress(desc: str, vol: int, total: int) -> None:
    """Log a progress update for streaming metrics."""
    pct = vol / total * 100.0
    log.info(f"  Progress : {vol}/{total} ({pct:.1f}%)", metric=desc)
