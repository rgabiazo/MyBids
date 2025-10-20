from __future__ import annotations

"""Configuration model for the pepolar preprocessing pipeline.

The dataclass collects all knobs that influence how opposite phase-encoding
fieldmaps are derived from functional runs.  Default values mirror the shell
script used historically so that existing behaviour remains unchanged when the
Python pipeline is adopted.
"""

from dataclasses import dataclass


@dataclass(slots=True)
class PepolarConfig:
    """Container for pepolar options with sensible defaults."""

    split_rule: str = "mad"
    mad_k: float = 3.0
    iqr_k: float = 1.5

    nmad_bounds: str = "adaptive"  # adaptive|fixed|none
    nmad_bounds_k: float = 1.5
    split_floor: float = 0.06
    split_cap: float = 0.20

    use_cc: int = 1
    cc_rule: str = "fixed"  # fixed|mad|iqr|off
    cc_min: float = 0.97
    cc_bounds: str = "adaptive"
    cc_bounds_k: float = 1.5
    cc_floor: float = 0.95
    cc_cap: float = 0.999

    split_logic: str = "OR"  # OR|AND
    auto_split: int = 1

    intensity_match: int = 1
    use_brainmask: int = 1
    bet_f: float = 0.30

    geom_enforce: int = 1
    use_bids_uri: int = 0

    dry_run: bool = False
