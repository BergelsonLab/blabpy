import pandas as pd
from pandas.testing import assert_frame_equal

from blabpy.vihi.intervals.intervals import make_intervals


def _read_sub_recordings():
    return pd.read_csv('data/sub_recordings.csv',
                       parse_dates=['recording_start', 'recording_end'],
                       dtype=dict(recordings_start_wav=int))


def _read_intervals():
    return pd.read_csv('data/intervals.csv',
                       parse_dates=['code_onset', 'code_offset', 'context_onset', 'context_offset'],
                       dtype=dict(code_onset_wav=int))


def test_make_intervals():
    sub_recordings = _read_sub_recordings()
    actual_intervals = make_intervals(sub_recordings)
    expected_intervals = _read_intervals()

    assert_frame_equal(expected_intervals, actual_intervals)
