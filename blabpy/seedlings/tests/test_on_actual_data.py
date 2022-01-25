import pytest

import pandas as pd

from blabpy.seedlings.listened_time import _total_time_per_region_type, RegionType, \
    milliseconds_to_hours, RECORDINGS_WITH_FOUR_SUBREGIONS, _extract_annotation_timestamps, \
    _add_per_region_annotation_count, calculate_total_listened_time, _extract_region_info
from blabpy.seedlings.paths import ALL_CHILDREN, ALL_MONTHS, MISSING_AUDIO_RECORDINGS, get_cha_path


CHA_STRUCTURE_FILENAME_PATTERN = '{child:02}_{month:02}_sparse_code.cha.txt'


@pytest.fixture(scope='module')
def listen_time_stats_df():
    return pd.read_csv('data/listen_time_stats.csv')


@pytest.mark.parametrize(argnames=('child', 'month'),
                         argvalues=[(child, month)
                                    for child in ALL_CHILDREN for month in ALL_MONTHS
                                    # TODO: test months 6 and 7 as well
                                    if (child, month) not in MISSING_AUDIO_RECORDINGS and month not in (6, 7)])
def test_the_whole_thing(listen_time_stats_df, child, month):
    subregion_count = 5 if (child, month) not in RECORDINGS_WITH_FOUR_SUBREGIONS else 4
    cha_path = get_cha_path(child=child, month=month)
    regions_df, subregion_ranks, _ = _extract_region_info(clan_file_path=cha_path, subregion_count=subregion_count)

    this_file_listen_time_stats = listen_time_stats_df.set_index('filename').loc[cha_path.name]

    # Compare the total duration of subregions and silences before processing
    total_times = (_total_time_per_region_type(regions_df)
        .set_index('region_type')
        ['total_time'])
    total_subregion_time_hour = milliseconds_to_hours(total_times[RegionType.SUBREGION.value])
    # It is perfectly ok to not have silence regions at all
    total_silence_time_hour = milliseconds_to_hours(total_times.get(RegionType.SILENCE.value, 0))

    assert total_subregion_time_hour == this_file_listen_time_stats['subregion_raw_hour']
    assert total_silence_time_hour == this_file_listen_time_stats['silence_raw_hour']

    # Compare the number of annotations within subregions
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
    assert str(subregion_counts) == this_file_listen_time_stats['annotation_counts_raw']

    # Compare the total listened time
    total_listen_time = calculate_total_listened_time(regions=regions_df, child=child, month=month)
    total_listen_time_correct = (this_file_listen_time_stats['total_listen_time']
                                 - this_file_listen_time_stats['surplus_time'])
    # We will ignore differences on a couple of files, we do not need to have exactly the same results as annot_distr
    # But we will check that our calculation has not changed since the last time.
    KNOWN_TOTAL_TIME_DIFFERENCES = {
        (22, 13): 15410310,
        (42, 17): 10800750,
        (40, 11): 12424570,
        (41, 17): 10802430}
    total_listen_time_correct = KNOWN_TOTAL_TIME_DIFFERENCES.get((child, month)) or total_listen_time_correct
    assert abs(total_listen_time - total_listen_time_correct) < 5000
