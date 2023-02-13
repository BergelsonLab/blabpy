import pandas as pd
import pytest


from blabpy.blab_data import get_file_path
from blabpy.seedlings.io import read_seedlings_nouns_regions
from blabpy.seedlings.regions import get_top_n_regions, get_surplus_regions, get_top3_top4_surplus_regions
from blabpy.seedlings.regions.reformat_seedlings_nouns_regions import reformat_seedlings_nouns_regions
from blabpy.seedlings.regions.regions import _load_data_for_special_cases, _get_amended_regions
from blabpy.seedlings.regions.top3_top4_surplus import assign_tokens_to_regions, TOP_3_KIND, SURPLUS_KIND
from blabpy.utils import text_file_checksum, pandas_df_hash

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


def load_test_data(top3_top4_surplus_data_dir, filename, dtype=None):
    return pd.read_csv(top3_top4_surplus_data_dir / filename, dtype=dtype).convert_dtypes()


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


def test_are_tokens_in_top3_top4_surplus(top3_top4_surplus_data_dir):
    tokens = load_test_data(top3_top4_surplus_data_dir, 'input_tokens.csv')
    top3_top4_surplus_regions = load_test_data(top3_top4_surplus_data_dir, 'output_top3_top4_surplus.csv')

    # Month 13
    actual_month_13 = assign_tokens_to_regions(tokens, top3_top4_surplus_regions, month='13')
    expected_month_13 = load_test_data(top3_top4_surplus_data_dir, 'output_assigned_tokens_month_13.csv')
    assert actual_month_13.equals(expected_month_13)

    # Month 14
    # Months 14-17 only have three hours annotated, so top-4 is undefined
    top3_surplus_regions = top3_top4_surplus_regions.loc[lambda df: df.kind.isin([TOP_3_KIND, SURPLUS_KIND])]
    top3_surplus_annotids = actual_month_13.loc[lambda df: ~df.is_top_4_hours | df.is_top_3_hours].annotid
    top3_surplus_tokens = tokens.loc[lambda df: df.annotid.isin(top3_surplus_annotids)]

    actual_month_14 = assign_tokens_to_regions(top3_surplus_tokens, top3_surplus_regions, month='14')
    expected_month_14 = load_test_data(top3_top4_surplus_data_dir, 'output_assigned_tokens_month_14.csv',
                                       dtype={'is_top_4_hours': pd.BooleanDtype()})
    assert actual_month_14.equals(expected_month_14)


@pytest.fixture(scope='module')
def seedlings_nouns_regions():
    regions_csv_path = get_file_path('seedlings-nouns_private', '0.0.0.9002', 'public/regions.csv')
    assert text_file_checksum(regions_csv_path) == 1085037431
    return read_seedlings_nouns_regions(regions_csv_path)


def test_reformat_seedling_nouns_regions(seedlings_nouns_regions):
    regions = reformat_seedling_nouns_regions(seedlings_nouns_regions)
    assert regions.shape == (3010, 9)
    assert pandas_df_hash(regions) == '4ceeb8d675c5bbbf323fa21044ffbc3ed109c8e6047cbbffa2264b874e753e91'
