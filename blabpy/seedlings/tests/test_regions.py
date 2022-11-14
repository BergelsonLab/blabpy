import pytest

from blabpy.seedlings.regions import _load_data_for_special_cases


@pytest.mark.parametrize("subj_num", ('20_12', '06_07', '22_07'))
def test__load_data_for_special_cases(subj_num):
    try:
        _load_data_for_special_cases(subj_num)
    except Exception as e:
        pytest.fail(f"Failed to load data for special case {subj_num}: {e}")
