from dicomatic.utils.cli_parse import parse_session_flags


def test_legacy_pair_parsed():
    assert parse_session_flags(["064", "01"]) == [("sub-064", "ses-01")]


def test_single_token_colon_parsed():
    assert parse_session_flags(["064:01"]) == [("sub-064", "ses-01")]

def test_single_token_ses_prefixed():
    assert parse_session_flags(["ses-03"]) == [(None, "ses-03")]


def test_numeric_token():
    assert parse_session_flags(["02"]) == [(None, "ses-02")]


def test_unpaired_token_ignored():
    assert parse_session_flags(["064"]) == []


def test_mixed_subject_session_token():
    assert parse_session_flags(["64:ses-05"]) == [("sub-064", "ses-05")]
