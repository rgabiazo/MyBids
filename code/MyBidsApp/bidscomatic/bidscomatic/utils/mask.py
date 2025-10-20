"""Simple brain-mask helpers used in tests."""

from __future__ import annotations

import numpy as np


def percentile_mask(data: np.ndarray, low: float = 2.0, high: float = 98.0) -> np.ndarray:
    """Return a binary mask using a percentile threshold.

    The mask contains ``1`` for voxels above ``low + 0.2*(high-low)`` and ``0``
    elsewhere.  It is intentionally small and deterministic for unit tests.
    """
    p2 = np.percentile(data, low)
    p98 = np.percentile(data, high)
    thr = p2 + 0.2 * (p98 - p2)
    return (data > thr).astype("uint8")
