from dicomatic.utils.planning import build_plans
from dicomatic.utils.naming import build_bids_basename


def _dummy_study():
    return {
        "study_description": "Study",
        "study_date": "20230101",
        "patient_name": "Patient",
        "study_uid": "1.2.3",
    }


def test_numeric_subject_override(tmp_path):
    study = _dummy_study()
    plans = build_plans(
        [study],
        bids_root=tmp_path,
        overrides={"sub": "7", "ses": "1"},
    )
    plan = plans[0]
    assert plan.sub_label == "sub-007"
    expected = tmp_path / "sub-007" / "ses-01" / build_bids_basename(study)
    assert plan.path == expected


def test_partial_subject_override(tmp_path):
    study = _dummy_study()
    plans = build_plans(
        [study],
        bids_root=tmp_path,
        overrides={"sub": "sub-5", "ses": "2"},
    )
    plan = plans[0]
    assert plan.sub_label == "sub-005"
    expected = tmp_path / "sub-005" / "ses-02" / build_bids_basename(study)
    assert plan.path == expected
