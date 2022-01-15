import pytest
from pathlib import Path

import pandas as pd

from blabpy.seedlings.paths import ALL_CHILDREN, ALL_MONTHS, MISSING_AUDIO_RECORDINGS


CHA_STRUCTURE_FILENAME_PATTERN = '{child:02}_{month:02}_sparse_code.cha.txt'


@pytest.fixture(scope='module')
def total_listen_time_summary_df(total_listen_time_summary_csv):
    return pd.read_csv(total_listen_time_summary_csv)


@pytest.mark.parametrize(argnames=('child', 'month'),
                         argvalues=[(child, month)
                                    for child in ALL_CHILDREN for month in ALL_MONTHS
                                    if (child, month) not in MISSING_AUDIO_RECORDINGS])
def test_the_whole_thing(total_listen_time_summary_df, cha_structures_folder, child, month):
    cha_structure_path = Path(cha_structures_folder) / CHA_STRUCTURE_FILENAME_PATTERN.format(child=child, month=month)
    assert cha_structure_path.exists()
