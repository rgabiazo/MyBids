"""Robust statistics helpers used by the pepolar pipeline."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence
import statistics


@dataclass(slots=True)
class Bounds:
    """Closed interval used for numeric clipping operations."""

    floor: float
    cap: float


def mad(xs: Sequence[float]) -> float:
    """Median absolute deviation."""
    med = statistics.median(xs)
    return statistics.median(abs(x - med) for x in xs)


def tukey_bounds(xs: Sequence[float], k: float) -> Bounds:
    """Return Tukey ``[Q1 - k*IQR, Q3 + k*IQR]`` fences."""
    q1, q3 = statistics.quantiles(xs, n=4, method="inclusive")[0::2]
    iqr = q3 - q1
    return Bounds(q1 - k * iqr, q3 + k * iqr)


def clamp(val: float, b: Bounds) -> float:
    """Clamp *val* to the inclusive interval described by *b*."""
    return min(b.cap, max(b.floor, val))


def nmad_threshold(
    vals: Sequence[float],
    rule: str = "mad",
    mad_k: float = 3.0,
    iqr_k: float = 1.5,
    bounds_mode: str = "adaptive",
    bounds_k: float = 1.5,
    floor: float = 0.06,
    cap: float = 0.20,
) -> tuple[float, Bounds]:
    """Compute the nMAD decision threshold with optional bounds."""
    xs = [v for v in vals if v > 0]
    if not xs:
        tau = 0.0 if rule != "fixed" else floor
    else:
        xs.sort()
        if rule == "iqr":
            q1, q3 = statistics.quantiles(xs, n=4, method="inclusive")[0::2]
            iqr = q3 - q1
            tau = q3 + iqr_k * iqr
        elif rule == "fixed":
            tau = floor
        else:
            med = statistics.median(xs)
            sigma = 1.4826 * mad(xs)
            tau = med + mad_k * sigma
    if bounds_mode == "adaptive" and len(xs) >= 3:
        b = tukey_bounds(xs, bounds_k)
    elif bounds_mode == "fixed":
        b = Bounds(floor, cap)
    else:
        b = Bounds(float("-inf"), float("inf"))
    return clamp(tau, b), b


def corr_threshold(
    vals: Sequence[float],
    rule: str = "fixed",
    fixed: float = 0.97,
    k: float = 3.0,
    bounds_mode: str = "adaptive",
    bounds_k: float = 1.5,
    floor: float = 0.95,
    cap: float = 0.999,
) -> tuple[float | None, Bounds]:
    """Return correlation guard threshold or ``None`` when disabled."""
    xs = [v for v in vals if 0 < v < 0.999999]
    if rule == "off":
        return None, Bounds(-1.0, 1.0)
    if not xs:
        tau = fixed if rule == "fixed" else 0.0
    else:
        xs.sort()
        if rule == "iqr":
            q1, q3 = statistics.quantiles(xs, n=4, method="inclusive")[0::2]
            iqr = q3 - q1
            tau = q1 - k * iqr
        elif rule == "mad":
            med = statistics.median(xs)
            sigma = 1.4826 * mad(xs)
            tau = med - k * sigma
        else:
            tau = fixed
    if bounds_mode == "adaptive" and len(xs) >= 3:
        b = tukey_bounds(xs, bounds_k)
        b = Bounds(max(-1.0, b.floor), min(1.0, b.cap))
    elif bounds_mode == "fixed":
        b = Bounds(floor, cap)
    else:
        b = Bounds(-1.0, 1.0)
    tau = max(-1.0, min(1.0, tau))
    return clamp(tau, b), b
