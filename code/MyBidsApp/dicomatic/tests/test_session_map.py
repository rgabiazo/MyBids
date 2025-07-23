import types

from dicomatic.utils import session_map


def test_extract_trailing_basic():
    assert session_map._extract_trailing("2020_01_01_001_baseline") == "baseline"
    assert session_map._extract_trailing("P002_followup") == "followup"
    assert session_map._extract_trailing("misc") is None


def test_detect_trailing_tags_and_build_map():
    studies = [
        {"patient_name": "2020_01_01_001_baseline"},
        {"patient_name": "2020_02_02_001_baseline"},
        {"patient_name": "2020_03_03_001_follow"},
        {"patient_name": "2020_04_04_002_follow"},
        {"patient_name": "2020_05_05_003_follow"},
    ]
    tags = session_map.detect_trailing_tags(studies)
    assert tags == ["follow", "baseline"]

    mapping = session_map.build_session_map(studies)
    assert mapping == {"follow": "01", "baseline": "02"}

    explicit = {"base": "99"}
    assert session_map.build_session_map(studies, explicit=explicit) == explicit


def test_assign_session_label():
    mapping = {"follow": "01", "baseline": "02"}
    assert session_map.assign_session_label("follow", mapping) == "ses-01"
    assert session_map.assign_session_label("unknown", mapping) is None
    assert session_map.assign_session_label(None, mapping) is None
