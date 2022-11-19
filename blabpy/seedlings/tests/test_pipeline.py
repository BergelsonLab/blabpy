import json
from pathlib import Path
from itertools import product

import pandas as pd
import pytest
import numpy as np

from blabpy.seedlings.pipeline import make_updated_all_basic_level_here, get_amended_audio_regions, \
    get_processed_audio_regions, get_top3_top4_surplus_regions, gather_recording_seedlings_nouns


def test_make_updated_all_basic_level_here(tmpdir):
    """
    Only checks that all_basiclevel can be successfully created. Require connection to PN-OPUS.
    """
    with tmpdir.as_cwd():
        make_updated_all_basic_level_here()
        cwd = Path()
        for ending, extension in product(('', '_NA'), ('.csv', '.feather')):
            filename = 'all_basiclevel' + ending + extension
            assert cwd.joinpath(filename).exists()


@pytest.mark.parametrize('subject, month', [(20, 12), (6, 7), (22, 7)])
def test_get_amended_audio_regions(subject, month):
    get_amended_audio_regions(subject, month)


def test_get_processed_audio_regions():
    try:
        get_processed_audio_regions(8, 12)
    except Exception as e:
        pytest.fail(f"Failed to get processed audio regions for 08_12: {e}")

    special_case_regions_auto = get_processed_audio_regions(20, 12, amend_if_special_case=False)
    special_case_regions_amended = get_processed_audio_regions(20, 12, amend_if_special_case=True)
    assert not special_case_regions_auto.equals(special_case_regions_amended)


@pytest.mark.parametrize('subject, month', [(6, 7), (8, 9), (10, 14)])
def test_get_top3_top4_surplus_regions(subject, month):
    get_top3_top4_surplus_regions(subject, month)


@pytest.fixture(scope='module')
def seedlings_nouns_data_dir():
    return Path(__file__).parent / 'data' / 'seedlings_nouns'


def load_test_data(top3_top4_surplus_data_dir, filename, dtype=None, parse_dates=False):
    return pd.read_csv(top3_top4_surplus_data_dir / filename, dtype=dtype, parse_dates=parse_dates).convert_dtypes()


def test_gather_everything_for_seedlings_nouns(top3_top4_surplus_data_dir, seedlings_nouns_data_dir):
    global_basic_level_for_recording = pd.read_csv(top3_top4_surplus_data_dir / 'input_tokens.csv').convert_dtypes()

    (actual_regions_for_seedlings_nouns,
     actual_tokens_full,
     actual_recordings,
     actual_total_listened_time,
     actual_total_recorded_time) = gather_recording_seedlings_nouns('Audio', 2, 8, global_basic_level_for_recording)

    expected_regions_for_seedlings_nouns = load_test_data(seedlings_nouns_data_dir, 'regions_for_seedlings_nouns.csv')
    expected_tokens_full = load_test_data(seedlings_nouns_data_dir, 'tokens_full.csv')
    expected_recordings = load_test_data(seedlings_nouns_data_dir, 'recordings.csv', parse_dates=['start', 'end'])
    total_times = json.load(open(seedlings_nouns_data_dir / 'total_times.json'))
    expected_total_listened_time = total_times['total_listened_time']
    expected_total_recorded_time = total_times['total_recorded_time']

    assert actual_regions_for_seedlings_nouns.equals(expected_regions_for_seedlings_nouns)
    assert actual_tokens_full.equals(expected_tokens_full)
    assert actual_recordings.equals(expected_recordings)
    assert actual_total_listened_time == expected_total_listened_time
    assert actual_total_recorded_time == expected_total_recorded_time
