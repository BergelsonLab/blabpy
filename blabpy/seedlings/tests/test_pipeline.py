from pathlib import Path
from itertools import product

import pytest

from blabpy.seedlings.pipeline import make_updated_all_basic_level_here, get_amended_audio_regions, \
    get_processed_audio_regions, get_top3_top4_surplus_regions


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
