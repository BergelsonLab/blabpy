import pytest

from blabpy.seedlings.regions import _load_data_for_special_cases, _get_amended_regions

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
