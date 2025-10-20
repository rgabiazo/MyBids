from pathlib import Path
import pandas as pd

from bidscomatic.utils.ops import (
    op_regex_map,
    op_regex_extract,
    op_map_values,
    op_join_membership,
    op_join_value,
    op_exists_to_flag,
    op_flag,
)


def test_events_ops_join() -> None:
    """Verify events OPS join behavior."""
    df = pd.DataFrame(
        {
            'trial_type': ['encoding_pair', 'encoding_pair', 'recog_pair', 'recog_pair'],
            'stim_file': ['foo.bmp', 'bar.bmp', 'foo.bmp', 'baz.bmp'],
            'response': ['n/a', 'n/a', 'HIT', 'FALSE ALARM'],
            'condition': ['pair'] * 4,
            'onset': [0, 1, 2, 3],
        }
    )
    df = op_regex_map(df, newcol='phase', from_col='trial_type', mapping={'encoding': '^encoding', 'recognition': '^recog'})
    df = op_map_values(
        df,
        newcol='acc_label',
        from_col='response',
        mapping={'hit': 'hit', 'false alarm': 'false_alarm', 'n/a': ''},
        casefold=True,
    )
    df = op_join_membership(
        df,
        newcol='probe_type',
        keys=['stim_file'],
        exists_in='phase=="encoding"',
        apply_to='phase=="recognition"',
        true_value='target',
        false_value='lure',
    )
    df = op_join_value(
        df,
        newcol='enc_later_outcome',
        value_from='acc_label',
        keys=['stim_file'],
        from_rows='phase=="recognition"',
        to_rows='phase=="encoding"',
        default='not_tested',
    )
    df = op_exists_to_flag(
        df,
        newcol='enc_is_tested',
        keys=['stim_file'],
        from_rows='phase=="recognition"',
        to_rows='phase=="encoding"',
        true_val=1,
        false_val=0,
    )
    df = op_flag(
        df,
        newcol='analysis_include',
        expr='acc_label in ["hit","correct_rejection"]',
        true=1,
        false=0,
    )

    rec = df[df['phase'] == 'recognition'].reset_index(drop=True)
    enc = df[df['phase'] == 'encoding'].reset_index(drop=True)

    assert list(rec['probe_type']) == ['target', 'lure']
    assert enc.loc[enc['stim_file'] == 'foo.bmp', 'enc_is_tested'].iloc[0] == 1
    assert enc.loc[enc['stim_file'] == 'bar.bmp', 'enc_is_tested'].iloc[0] == 0
    assert enc.loc[enc['stim_file'] == 'foo.bmp', 'enc_later_outcome'].iloc[0] == 'hit'
    assert enc.loc[enc['stim_file'] == 'bar.bmp', 'enc_later_outcome'].iloc[0] == 'not_tested'
    assert list(rec['analysis_include']) == [1, 0]


def test_join_membership_scope(caplog) -> None:
    """Verify join membership scope behavior."""
    import logging

    df = pd.DataFrame(
        {
            'run': [1, 1, 2, 2],
            'trial_type': ['encoding_pair', 'recog_pair', 'encoding_pair', 'recog_pair'],
            'stim_file': ['foo.bmp', 'foo.bmp', 'bar.bmp', 'foo.bmp'],
            'response': ['n/a', 'HIT', 'n/a', 'HIT'],
            'condition': ['pair'] * 4,
            'onset': [0, 1, 0, 1],
        }
    )
    df = op_regex_map(df, newcol='phase', from_col='trial_type', mapping={'encoding': '^encoding', 'recognition': '^recog'})
    res = op_join_membership(
        df,
        newcol='probe_type',
        keys=['condition', 'stim_file'],
        exists_in='phase=="encoding"',
        apply_to='phase=="recognition"',
        true_value='target',
        false_value='lure',
        scope='run',
    )
    rec = res[res['phase'] == 'recognition'].reset_index(drop=True)
    assert rec.loc[0, 'probe_type'] == 'target'
    assert rec.loc[1, 'probe_type'] == 'lure'

    caplog.set_level(logging.WARNING)
    single = df[df['run'] == 1].drop(columns=['run'])
    _ = op_join_membership(
        single,
        newcol='probe_type',
        keys=['condition', 'stim_file'],
        exists_in='phase=="encoding"',
        apply_to='phase=="recognition"',
        true_value='target',
        false_value='lure',
        scope='run',
    )
    assert not caplog.records


def test_join_value_duplicate_keys_warn(caplog) -> None:
    """Verify join value duplicate keys warn behavior."""
    import logging

    df = pd.DataFrame(
        {
            'trial_type': ['encoding_pair', 'recog_pair', 'recog_pair'],
            'stim_file': ['foo.bmp', 'foo.bmp', 'foo.bmp'],
            'response': ['n/a', 'HIT', 'MISS'],
            'condition': ['pair'] * 3,
            'onset': [0, 1, 2],
        }
    )
    df = op_regex_map(df, newcol='phase', from_col='trial_type', mapping={'encoding': '^encoding', 'recognition': '^recog'})
    df = op_map_values(
        df,
        newcol='acc_label',
        from_col='response',
        mapping={'hit': 'hit', 'miss': 'miss', 'n/a': ''},
        casefold=True,
    )
    caplog.set_level(logging.WARNING)
    _ = op_join_value(
        df,
        newcol='enc_later_outcome',
        value_from='acc_label',
        keys=['stim_file'],
        from_rows='phase=="recognition"',
        to_rows='phase=="encoding"',
        default='not_tested',
    )
    assert any('duplicate key' in r.message for r in caplog.records)


def test_join_membership_missing_keys(caplog) -> None:
    """Verify join membership missing keys behavior."""
    import logging

    df = pd.DataFrame({
        'trial_type': ['encoding_pair', 'recog_pair'],
        'stim_file': ['foo.bmp', 'foo.bmp'],
        'response': ['n/a', 'HIT'],
        'condition': ['pair', 'pair'],
        'onset': [0, 1],
    })
    df = op_regex_map(df, newcol='phase', from_col='trial_type', mapping={'encoding': '^encoding', 'recognition': '^recog'})
    caplog.set_level(logging.WARNING)
    _ = op_join_membership(
        df,
        newcol='probe_type',
        keys=['missing_key'],
        exists_in='phase=="encoding"',
        apply_to='phase=="recognition"',
        true_value='target',
        false_value='lure',
    )
    assert any('missing key column' in r.message for r in caplog.records)


def test_join_ignores_nan_keys(caplog) -> None:
    """Verify join ignores NAN keys behavior."""
    import logging

    df = pd.DataFrame({
        'trial_type': ['encoding_pair', 'encoding_pair', 'recog_pair', 'recog_pair'],
        'stim_file': ['foo.bmp', None, 'foo.bmp', None],
        'response': ['n/a', 'n/a', 'HIT', 'MISS'],
        'condition': ['pair'] * 4,
        'onset': [0, 1, 2, 3],
    })
    df = op_regex_map(df, newcol='phase', from_col='trial_type', mapping={'encoding': '^encoding', 'recognition': '^recog'})
    df = op_map_values(
        df,
        newcol='acc_label',
        from_col='response',
        mapping={'hit': 'hit', 'miss': 'miss', 'n/a': ''},
        casefold=True,
    )
    caplog.set_level(logging.WARNING)
    df = op_join_membership(
        df,
        newcol='probe_type',
        keys=['stim_file'],
        exists_in='phase=="encoding"',
        apply_to='phase=="recognition"',
        true_value='target',
        false_value='lure',
    )
    df = op_join_value(
        df,
        newcol='enc_later_outcome',
        value_from='acc_label',
        keys=['stim_file'],
        from_rows='phase=="recognition"',
        to_rows='phase=="encoding"',
        default='not_tested',
    )
    df = op_exists_to_flag(
        df,
        newcol='enc_is_tested',
        keys=['stim_file'],
        from_rows='phase=="recognition"',
        to_rows='phase=="encoding"',
        true_val=1,
        false_val=0,
    )
    assert not caplog.records

    rec = df[df['phase'] == 'recognition'].reset_index(drop=True)
    enc = df[df['phase'] == 'encoding'].reset_index(drop=True)
    assert rec.loc[0, 'probe_type'] == 'target'
    assert rec.loc[1, 'probe_type'] == 'lure'
    assert enc.loc[1, 'enc_is_tested'] == 0
    assert enc.loc[1, 'enc_later_outcome'] == 'not_tested'


def test_join_value_scope_missing_column(caplog) -> None:
    """Verify join value scope missing column behavior."""
    import logging

    df = pd.DataFrame(
        {
            'trial_type': ['encoding_pair', 'recog_pair'],
            'stim_file': ['foo.bmp', 'foo.bmp'],
            'response': ['n/a', 'HIT'],
            'condition': ['pair', 'pair'],
            'onset': [0, 1],
        }
    )
    df = op_regex_map(df, newcol='phase', from_col='trial_type', mapping={'encoding': '^encoding', 'recognition': '^recog'})
    df = op_map_values(
        df,
        newcol='acc_label',
        from_col='response',
        mapping={'hit': 'hit', 'n/a': ''},
        casefold=True,
    )
    caplog.set_level(logging.WARNING)
    res = op_join_value(
        df,
        newcol='enc_later_outcome',
        value_from='acc_label',
        keys=['stim_file'],
        from_rows='phase=="recognition"',
        to_rows='phase=="encoding"',
        default='not_tested',
        scope='run',
    )
    enc = res[res['phase'] == 'encoding'].reset_index(drop=True)
    assert enc.loc[0, 'enc_later_outcome'] == 'hit'
    assert not caplog.records


def test_exists_to_flag_scope_missing_column(caplog) -> None:
    """Verify exists TO flag scope missing column behavior."""
    import logging

    df = pd.DataFrame(
        {
            'trial_type': ['encoding_pair', 'recog_pair'],
            'stim_file': ['foo.bmp', 'foo.bmp'],
            'response': ['n/a', 'HIT'],
            'condition': ['pair', 'pair'],
            'onset': [0, 1],
        }
    )
    df = op_regex_map(df, newcol='phase', from_col='trial_type', mapping={'encoding': '^encoding', 'recognition': '^recog'})
    caplog.set_level(logging.WARNING)
    res = op_exists_to_flag(
        df,
        newcol='enc_is_tested',
        keys=['stim_file'],
        from_rows='phase=="recognition"',
        to_rows='phase=="encoding"',
        true_val=1,
        false_val=0,
        scope='run',
    )
    enc = res[res['phase'] == 'encoding'].reset_index(drop=True)
    assert enc.loc[0, 'enc_is_tested'] == 1
    assert not caplog.records
