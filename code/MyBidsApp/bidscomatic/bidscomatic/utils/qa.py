"""Quality-assurance metrics for the pepolar pipeline."""

from __future__ import annotations

import numpy as np


def nmad(ref: np.ndarray, img: np.ndarray, mask: np.ndarray | None = None) -> float:
    """Return the normalised mean absolute difference between *img* and *ref*."""
    if mask is not None:
        ref = ref[mask > 0]
        img = img[mask > 0]
    return float(np.mean(np.abs(img - ref)) / np.mean(ref))


def corr(ref: np.ndarray, img: np.ndarray, mask: np.ndarray | None = None) -> float:
    """Pearson correlation of two images."""
    if mask is not None:
        ref = ref[mask > 0]
        img = img[mask > 0]
    return float(np.corrcoef(ref, img)[0, 1])
