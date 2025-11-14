"""Streaming computation of basic fMRI QC metrics."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple

import math
import numpy as np
import pandas as pd
import nibabel as nib

import structlog

log = structlog.get_logger()

# ---------------------------------------------------------------------------
# Framewise displacement
# ---------------------------------------------------------------------------

def fd_power_from_par(par_path: str, head_radius_mm: float = 50.0) -> Optional[np.ndarray]:
    """Return Power FD series from FSL ``.par`` motion parameters."""
    try:
        mp = np.loadtxt(par_path)
    except Exception:
        log.warning("Could not read motion parameters", par=par_path)
        return None
    if mp.ndim == 1:
        mp = mp[None, :]
    rx, ry, rz, tx, ty, tz = mp.T
    drx = np.diff(rx, prepend=rx[0])
    dry = np.diff(ry, prepend=ry[0])
    drz = np.diff(rz, prepend=rz[0])
    dtx = np.diff(tx, prepend=tx[0])
    dty = np.diff(ty, prepend=ty[0])
    dtz = np.diff(tz, prepend=tz[0])
    fd = np.abs(dtx) + np.abs(dty) + np.abs(dtz)
    fd += head_radius_mm * (np.abs(drx) + np.abs(dry) + np.abs(drz))
    fd[0] = 0.0
    return fd.astype("float32")


def fd_from_confounds(conf_path: str) -> Optional[np.ndarray]:
    """Return FD series from a confounds TSV produced by fMRIPrep."""
    try:
        df = pd.read_csv(conf_path, sep="\t")
    except Exception:
        log.warning("Could not read confounds", path=conf_path)
        return None
    for col in ("framewise_displacement", "FramewiseDisplacement", "FD", "fd"):
        if col in df.columns:
            data = pd.to_numeric(df[col], errors="coerce").to_numpy(dtype="float32")
            if data.size and not np.isfinite(data[0]):
                data[0] = 0.0
            return data
    log.warning("No FD column found in confounds", path=conf_path)
    return None

# ---------------------------------------------------------------------------
# DVARS / tSNR
# ---------------------------------------------------------------------------

def stream_dvars(
    img_path: str, mask: np.ndarray, update_every: int = 50, desc: str | None = None
) -> np.ndarray:
    """Return DVARS series, streaming one volume at a time."""
    from .display import log_progress

    img = nib.load(img_path)
    data = img.dataobj
    T = img.shape[3]
    d = np.zeros(T, dtype="float32")
    prev = np.asarray(data[..., 0], dtype="float32")[mask]
    for t in range(1, T):
        cur = np.asarray(data[..., t], dtype="float32")[mask]
        diff = cur - prev
        d[t] = math.sqrt((diff * diff).mean())
        prev = cur
        if ((t + 1) % update_every == 0) or (t + 1 == T):
            log_progress(desc or "DVARS", t + 1, T)
    return d


def stream_tsnr(
    img_path: str, mask: np.ndarray, update_every: int = 50, desc: str | None = None
) -> Tuple[float, float, np.ndarray]:
    """Return mean, median and voxelwise tSNR."""
    from .display import log_progress

    img = nib.load(img_path)
    data = img.dataobj
    T = img.shape[3]
    nvox = int(mask.sum())
    mean = np.zeros(nvox, dtype="float64")
    M2 = np.zeros(nvox, dtype="float64")
    count = 0
    for t in range(T):
        x = np.asarray(data[..., t], dtype="float32")[mask].astype("float64", copy=False)
        count += 1
        delta = x - mean
        mean += delta / count
        delta2 = x - mean
        M2 += delta * delta2
        if ((t + 1) % update_every == 0) or (t + 1 == T):
            log_progress(desc or "tSNR", t + 1, T)
    std = np.sqrt(M2 / (count - 1)) if count >= 2 else np.full(nvox, np.nan)
    tsnr = mean / (std + 1e-8)
    return float(np.nanmean(tsnr)), float(np.nanmedian(tsnr)), tsnr.astype("float32")

# ---------------------------------------------------------------------------
# Mask handling
# ---------------------------------------------------------------------------

def load_mask(mask_path: Optional[str], bold_path: str) -> np.ndarray:
    """Load a mask and allow naive fallback when unavailable."""
    return load_mask_allow(mask_path, bold_path, allow_naive=True)


def load_mask_allow(mask_path: Optional[str], bold_path: str, allow_naive: bool) -> np.ndarray:
    """Load a mask or optionally construct a naive fallback.

    Args:
        mask_path: Candidate mask file. When ``None`` or unreadable and
            ``allow_naive`` is ``True``, a mask is derived from the mean signal.
        bold_path: Reference BOLD file used when constructing a naive mask.
        allow_naive: Whether a naive mask may be generated when missing.

    Returns:
        Boolean NumPy array representing the selected mask.

    Raises:
        FileNotFoundError: Raised when ``allow_naive`` is ``False`` and
            ``mask_path`` is absent or unreadable.
    """
    if mask_path:
        try:
            return nib.load(mask_path).get_fdata().astype(bool)
        except Exception:
            log.warning("Failed to load mask", mask=mask_path)
            if not allow_naive:
                raise
    if not allow_naive:
        raise FileNotFoundError(f"Mask not found for {bold_path}")
    img = nib.load(bold_path)
    data = img.get_fdata(dtype="float32")
    return (data.mean(axis=3) > 0)


@dataclass
class RunMetrics:
    """Container for per-run metrics."""

    label: str
    bold_path: str
    n_vols: int
    mean_dvars: Optional[float]
    fd_mean: Optional[float]
    fd_pct_over: Optional[float]
    tsnr_mean: Optional[float]
    tsnr_median: Optional[float]
