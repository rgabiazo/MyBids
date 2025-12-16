"""Configuration model for the pepolar preprocessing pipeline.

The dataclass collects all knobs that influence how opposite phase-encoding
fieldmaps are derived from functional runs. Default values mirror the shell
script used historically so that existing behaviour remains unchanged when the
Python pipeline is adopted.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict

# Default mapping between BIDS ``dir-`` entity values and their opposites.
# These defaults cover the common phase-encode pairs used by EPI sequences.
_DEFAULT_DIR_PAIRS: Dict[str, str] = {
    "AP": "PA",
    "PA": "AP",
    "LR": "RL",
    "RL": "LR",
    "SI": "IS",
    "IS": "SI",
}


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

    # Mapping from `dir-<X>` label to its opposite (e.g., AP->PA, LR->RL).
    # The pipeline uses this map to determine which `dir-` label should be
    # derived when only one side of a PEPOLAR pair exists.
    dir_pairs: Dict[str, str] = field(default_factory=lambda: dict(_DEFAULT_DIR_PAIRS))

    dry_run: bool = False
