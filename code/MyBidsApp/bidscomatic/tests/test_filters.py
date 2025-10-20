# ---------------------------------------------------------------------------
# code/MyBidsApp/tests/test_filters.py        ★ NEW regression test ★
# ---------------------------------------------------------------------------
from pathlib import Path

from bidscomatic.utils.filters import (
    filter_subject_session_paths,
    filter_subject_sessions,
)
from bidscomatic.pipelines.types import SubjectSession


def test_filter_paths(tmp_path: Path):
    """Verify filter paths behavior."""
    roots = [
        tmp_path / "sub-001/ses-01",
        tmp_path / "sub-001/ses-02",
        tmp_path / "sub-002/ses-01",
    ]
    # create dummy dirs so Path.exists() is True if code/tests rely on it
    for r in roots:
        r.mkdir(parents=True, exist_ok=True)

    keep = filter_subject_session_paths(roots, subs=("001",), sess=("01",))
    assert keep == [tmp_path / "sub-001/ses-01"]


def test_filter_subject_sessions():
    """Verify filter subject sessions behavior."""
    ss_all = [
        SubjectSession(root=Path("/tmp"), sub="sub-001", ses="ses-01"),
        SubjectSession(root=Path("/tmp"), sub="sub-001", ses="ses-02"),
        SubjectSession(root=Path("/tmp"), sub="sub-002", ses="ses-01"),
    ]
    kept = filter_subject_sessions(ss_all, subs=("001",), sess=("01",))
    assert len(kept) == 1
    assert kept[0].sub == "sub-001" and kept[0].ses == "ses-01"
