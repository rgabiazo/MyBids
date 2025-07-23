from dicomatic.utils.naming import sanitize_for_filename, build_bids_basename


def test_sanitize_for_filename():
    assert sanitize_for_filename('  Foo Bar!! ') == 'Foo_Bar'
    assert sanitize_for_filename('a/b\\c') == 'a_b_c'
    assert sanitize_for_filename('___') == ''


def test_build_bids_basename():
    study = {
        'study_description': 'My Study',
        'study_date': '20230101',
        'patient_name': 'John Doe',
        'study_uid': '1.2.3.4',
    }
    assert build_bids_basename(study) == 'My_Study_20230101_John Doe_1_2_3_4.tar'
