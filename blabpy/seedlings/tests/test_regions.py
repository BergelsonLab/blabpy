from pathlib import Path

import pandas as pd
import pytest

from blabpy.seedlings.regions import get_top_n_regions, get_surplus_regions, get_top3_top4_surplus_regions
from blabpy.seedlings.regions.regions import _load_data_for_special_cases, _get_amended_regions

SPECIAL_CASES_SUBJ_MONTHS = ('20_12', '06_07', '22_07')


@pytest.mark.parametrize("subj_month", SPECIAL_CASES_SUBJ_MONTHS)
def test__load_data_for_special_cases(subj_month):
    try:
        _load_data_for_special_cases(subj_month)
    except Exception as e:
        pytest.fail(f"Failed to load data for special case {subj_month}: {e}")


@pytest.mark.parametrize("subj_month", SPECIAL_CASES_SUBJ_MONTHS)
def test_get_amended_regions(subj_month):
    regions_processed_original, regions_processed_amended = _load_data_for_special_cases(subj_month)
    try:
        _get_amended_regions(subj_month, regions_processed_auto=regions_processed_original)
    except Exception as e:
        pytest.fail(f"Failed to get amended data for special case {subj_month}: {e}")

    with pytest.raises(AssertionError):
        _get_amended_regions(subj_month, regions_processed_auto=regions_processed_amended.iloc[:-1])


@pytest.fixture(scope='module')
def top3_top4_surplus_data_dir():
    return Path(__file__).parent / 'data' / 'top3_top4_surplus'


def load_test_data(top3_top4_surplus_data_dir, filename):
    return pd.read_csv(top3_top4_surplus_data_dir / filename).convert_dtypes()


@pytest.fixture(scope='module')
def processed_regions(top3_top4_surplus_data_dir):
    return load_test_data(top3_top4_surplus_data_dir, 'input_processed_regions.csv')


@pytest.mark.parametrize('month', ['06', '08', '14'])
@pytest.mark.parametrize('n_hours', [3, 4])
def test_get_top_n_regions(processed_regions, month, n_hours, top3_top4_surplus_data_dir):
    # top-4 is undefined for month 14 for which only three hours were annotated
    if month == '14' and n_hours == 4:
        return

    actual = get_top_n_regions(processed_regions=processed_regions, month=month, n_hours=n_hours)
    expected = load_test_data(top3_top4_surplus_data_dir, f'output_month_{month}_top_{n_hours}.csv')

    assert actual.equals(expected)


@pytest.mark.parametrize('month', ['06', '08'])
def test_get_surplus_regions(processed_regions, month, top3_top4_surplus_data_dir):
    actual = get_surplus_regions(processed_regions=processed_regions, month=month)
    expected = load_test_data(top3_top4_surplus_data_dir, f'output_month_{month}_surplus.csv')

    assert actual.equals(expected)


def test_get_top3_top4_surplus_regions(processed_regions, top3_top4_surplus_data_dir):
    actual = get_top3_top4_surplus_regions(processed_regions=processed_regions, month='08')
    expected = load_test_data(top3_top4_surplus_data_dir, f'output_top3_top4_surplus.csv')

    assert actual.equals(expected)


