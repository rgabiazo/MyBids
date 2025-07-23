"""
Core data-model declarations for *dicomatic*.

The module centralizes simple containers that are reused across the
code-base (for example, by planner helpers or Click commands). Adding
new models here avoids scattering small `NamedTuple` or ad-hoc
dictionaries in multiple locations, which in turn improves maintenance
and static analysis.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Dict


@dataclass(slots=True)
class DownloadPlan:
    """Planning record for a single ``cfmm2tar`` archive.

    Instances describe where a study will land on disk and which raw study
    dictionary produced it. Planner helpers populate this class and downstream
    utilities consume it without recalculating paths.

    Attributes:
        study: Raw study dictionary returned by
            ``parse_studies_with_demographics``.
        path: Absolute path to the ``.tar`` archive that ``cfmm2tar`` will
            generate or has already generated.
        sub_label: BIDS-formatted subject label, for example ``sub-003``.
        ses_label: BIDS-formatted session label, for example ``ses-01``.
    """

    study: Dict[str, str]
    path: Path
    sub_label: str
    ses_label: str
