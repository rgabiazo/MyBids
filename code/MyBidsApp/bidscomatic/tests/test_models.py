# -----------------------------------------------------------------------------
# file: MyBidsApp/tests/test_models.py
# -----------------------------------------------------------------------------
"""Unit tests for models – independent of external I/O.

Each test uses only the public API of :pyfile:`MyBidsApp/bidscomatic/models.py`.
"""
from pathlib import Path

from bidscomatic.models import (
    BIDSPath,
    SubjectID,
    SessionID,
    BIDSEntities,
)


def test_bids_path_filename():
    """Filename should concatenate entities and suffix in order."""
    ents = BIDSEntities(sub="01", ses="01", suffix="T1w")
    bp = BIDSPath(root=Path("/tmp"), datatype="anat", entities=ents)
    assert bp.filename == "sub-01_ses-01_T1w.nii.gz"
