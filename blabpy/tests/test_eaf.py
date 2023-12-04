import tempfile
import xml

import pandas as pd
import pytest

from blabpy.eaf import EafPlus, EafTree
from blabpy.vihi.intervals.templates import basic_00_07 as sample_etf_path
from blabpy.vihi.paths import get_eaf_path


@pytest.fixture(scope="module")
def eaf_path():
    return get_eaf_path('VI', '001', '676')


@pytest.fixture(scope="module")
def eaf(eaf_path):
    return EafPlus(eaf_path)


class TestEafPlus:
    def test_get_time_intervals(self, eaf_path, eaf):
        csv_path = eaf_path.parent / 'selected_regions.csv'
        original_intervals = (
            pd.read_csv(csv_path, dtype={'code_num': 'string'})
            .convert_dtypes()
            .loc[:, ['code_num', 'sampling_type',
                     'code_onset_wav', 'code_offset_wav',
                     'context_onset_wav', 'context_offset_wav']]
            .rename(columns={'code_onset_wav': 'onset', 'code_offset_wav': 'offset',
                             'context_onset_wav': 'context_onset', 'context_offset_wav': 'context_offset'})
            .sort_values(['onset', 'offset']).reset_index(drop=True)
        )
        extracted_intervals = eaf.get_intervals()
        assert extracted_intervals.equals(original_intervals)

    def test_get_annotations_and_intervals(self, eaf):
        """Does it run at all? Do we at least get two non-empty dataframes?"""
        annotations, intervals = eaf.get_annotations_and_intervals()

        assert isinstance(annotations, pd.DataFrame)
        assert isinstance(intervals, pd.DataFrame)
        assert not annotations.empty
        assert not intervals.empty


class TestEafTree:
    def test_from_path(self):
        EafTree.from_path(sample_etf_path)

    def test_from_url(self):
        # TODO: Implement
        assert True

    def test_from_uri(self):
        EafTree.from_path(sample_etf_path)

    def test_from_eaf(self):
        EafTree.from_path(sample_etf_path)

    @pytest.fixture(scope='module')
    def sample_eaf_tree(self):
        return EafTree.from_path(sample_etf_path)

    def test_to_string(self, sample_eaf_tree):
        sample_eaf_tree.to_string()

    def test_to_file(self, sample_eaf_tree):
        # Create a temporary file path
        # Note: I have no idea why delete=False is necessary, but it is. At least on Win 11. I assume that the context
        # manager will still delete the file when it exits but I haven't checked.
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
            # Write the EafTree to the temporary file
            sample_eaf_tree.to_file(f.name)

    def test_to_eaf(self, sample_eaf_tree):
        self.test_to_file(sample_eaf_tree)

    def test_find_element(self, sample_eaf_tree):
        first_ling_type = sample_eaf_tree.find_element('LINGUISTIC_TYPE')
        assert type(first_ling_type) == xml.etree.ElementTree.Element

    def test_find_elements(self, sample_eaf_tree):
        ling_types = sample_eaf_tree.find_elements('LINGUISTIC_TYPE')
        assert type(ling_types) == list
        assert len(ling_types) == 5

    def test_find_single_element(self, sample_eaf_tree):
        sample_eaf_tree.find_single_element('EXTERNAL_REF')
        # Test that an error is raised if there is more than one element
        with pytest.raises(ValueError):
            sample_eaf_tree.find_single_element('LINGUISTIC_TYPE')
        # Test that an error is raised if there are no elements
        with pytest.raises(ValueError):
            sample_eaf_tree.find_single_element('ANNOTATION')
