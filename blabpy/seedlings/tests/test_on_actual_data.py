import pytest
from pathlib import Path

import pandas as pd

from blabpy.seedlings.listened_time import _read_cha_structure, _total_time_per_region_type, RegionType, \
    milliseconds_to_hours, RECORDINGS_WITH_FOUR_SUBREGIONS
from blabpy.seedlings.paths import ALL_CHILDREN, ALL_MONTHS, MISSING_AUDIO_RECORDINGS


CHA_STRUCTURE_FILENAME_PATTERN = '{child:02}_{month:02}_sparse_code.cha.txt'


@pytest.fixture(scope='module')
def total_listen_time_summary_df(total_listen_time_summary_csv):
    return pd.read_csv(total_listen_time_summary_csv)


@pytest.mark.parametrize(argnames=('child', 'month'),
                         argvalues=[(child, month)
                                    for child in ALL_CHILDREN for month in ALL_MONTHS
                                    # TODO: test months 6 and 7 as well
                                    if (child, month) not in MISSING_AUDIO_RECORDINGS and month not in (6, 7)])
def test_the_whole_thing(total_listen_time_summary_df, cha_structures_folder, child, month):
    cha_structure_path = Path(cha_structures_folder) / CHA_STRUCTURE_FILENAME_PATTERN.format(child=child, month=month)
    assert cha_structure_path.exists()

    subregion_count = 5 if (child, month) not in RECORDINGS_WITH_FOUR_SUBREGIONS else 4
    regions_df, _ = _read_cha_structure(cha_structure_path, subregion_count=subregion_count)

    total_times = (_total_time_per_region_type(regions_df)
        .set_index('region_type')
        ['total_time'])
    total_subregion_time_hour = milliseconds_to_hours(total_times[RegionType.SUBREGION.value])
    # It is perfectly ok to not have silence regions at all
    total_silence_time_hour = milliseconds_to_hours(total_times.get(RegionType.SILENCE.value, 0))

    # Compare the total duration of subregions and silences before processing
    correct_total_times = total_listen_time_summary_df.set_index('filename').loc[cha_structure_path.stem]
    assert total_subregion_time_hour == correct_total_times['subregion_raw_hour']
    assert total_silence_time_hour == correct_total_times['silence_raw_hour']
