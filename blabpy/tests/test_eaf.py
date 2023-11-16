from unittest import TestCase

import pandas as pd
import pytest

from blabpy.eaf import EafPlus
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
