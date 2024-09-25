import filecmp
from pathlib import Path

import pytest

from blabpy.eaf import EafTree, EafPlus
from blabpy.eaf.eaf_utils import eaf_to_tree, tree_to_eaf
from blabpy.vihi.reliability import prepare_eaf_for_reliability


@pytest.fixture(scope='module')
def eaf_path():
    return Path('data/test.eaf')

@pytest.fixture(scope='module')
def eaf_as_element_tree(eaf_path):
    return eaf_to_tree(eaf_path)

@pytest.fixture(scope='module')
def eaf(eaf_path):
    return EafPlus(eaf_path)


def test_prepare_eaf_for_reliability(eaf_as_element_tree, eaf, tmp_path):
    random_seed = [84, 68, 95, 52, 54, 52, 95, 49, 56, 56]
    eaf_tree, (sampled_code_nums, sampled_sampling_types) = (
        prepare_eaf_for_reliability(eaf_as_element_tree, eaf, random_seed=random_seed))
    temp_file_path = tmp_path / 'temp_output.eaf'
    tree_to_eaf(eaf_tree, temp_file_path)

    expected_file_path = Path('data/test_interval_sample.eaf')
    expected_code_nums = ['34', '11']
    expected_sampling_types = ['high-volubility', 'random']

    assert filecmp.cmp(temp_file_path, expected_file_path, shallow=False)
    assert sampled_code_nums == expected_code_nums
    assert sampled_sampling_types == expected_sampling_types
