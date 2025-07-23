"""Helpers for constructing metadata structures."""

from bids_cbrain_runner import __version__

def runner_generatedby_entry() -> dict:
    """Return metadata describing this runner for ``GeneratedBy`` fields."""
    return {
        "Name": "cbrain_bids_pipeline",
        "Version": __version__,
        "CodeURL": "https://github.com/rgabiazo/MyBidsTest/tree/main/code/MyBidsApp/cbrain_bids_pipeline",
    }
