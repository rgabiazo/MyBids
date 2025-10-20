import math

from bidscomatic.utils.stats import nmad_threshold, corr_threshold


def test_nmad_threshold_mad():
    """Verify nmad threshold MAD behavior."""
    tau, bounds = nmad_threshold([0.1, 0.11, 0.12])
    assert isinstance(tau, float)
    assert bounds.floor <= tau <= bounds.cap


def test_corr_threshold_fixed():
    """Verify corr threshold fixed behavior."""
    tau, _ = corr_threshold([0.95, 0.96, 0.97], rule="fixed", fixed=0.97)
    assert math.isclose(tau, 0.97)
