import pytest
from pathlib import Path

import pandas as pd

from blabpy.seedlings.listened_time import _read_cha_structure, _total_time_per_region_type, RegionType, \
    milliseconds_to_hours, RECORDINGS_WITH_FOUR_SUBREGIONS, _extract_annotation_timestamps, \
    _add_per_region_annotation_count, calculate_total_listened_time
from blabpy.seedlings.paths import ALL_CHILDREN, ALL_MONTHS, MISSING_AUDIO_RECORDINGS, get_cha_path


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

    total_listen_time_values = total_listen_time_summary_df.set_index('filename').loc[cha_structure_path.stem]

    # Compare the total duration of subregions and silences before processing
    total_times = (_total_time_per_region_type(regions_df)
        .set_index('region_type')
        ['total_time'])
    total_subregion_time_hour = milliseconds_to_hours(total_times[RegionType.SUBREGION.value])
    # It is perfectly ok to not have silence regions at all
    total_silence_time_hour = milliseconds_to_hours(total_times.get(RegionType.SILENCE.value, 0))

    assert total_subregion_time_hour == total_listen_time_values['subregion_raw_hour']
    assert total_silence_time_hour == total_listen_time_values['silence_raw_hour']

    # Compare the number of annotations within subregions
    cha_path = get_cha_path(child=child, month=month)
    annotation_timestamps = _extract_annotation_timestamps(cha_path)
    per_region_counts = _add_per_region_annotation_count(regions_df=regions_df,
                                                         annotation_timestamps=annotation_timestamps)
    subregion_counts = (per_region_counts
                        [per_region_counts.region_type == RegionType.SUBREGION.value]
                        .sort_values(by='position')
                        .annotation_count
                        .astype(int)
                        .to_list())
    # Add a 0 for files with four subregions
    if (child, month) in RECORDINGS_WITH_FOUR_SUBREGIONS:
        subregion_counts += [0]

    # The 'counts' column contains a string representation of the count list
    assert str(subregion_counts) == total_listen_time_values['annotation_counts_raw']
