import ast

import pytest

import pandas as pd

from blabpy.seedlings.listened_time import RECORDINGS_WITH_FOUR_SUBREGIONS, listen_time_stats_for_report, \
    _get_subregion_count

from blabpy.seedlings.paths import ALL_CHILDREN, ALL_MONTHS, MISSING_AUDIO_RECORDINGS, get_cha_path


CHA_STRUCTURE_FILENAME_PATTERN = '{child:02}_{month:02}_sparse_code.cha.txt'


def _possibly_interpret_as_list(possibly_list):
    if isinstance(possibly_list, str) and possibly_list.startswith('[') and possibly_list.endswith(']'):
        return ast.literal_eval(possibly_list)
    else:
        return possibly_list


@pytest.fixture(scope='module')
def listen_time_stats_df():
    return pd.read_csv('data/listen_time_stats.csv')


@pytest.mark.parametrize(argnames=('child', 'month'),
                         argvalues=[(child, month)
                                    for child in ALL_CHILDREN for month in ALL_MONTHS
                                    # TODO: test months 6 and 7 as well
                                    if (child, month) not in MISSING_AUDIO_RECORDINGS and month not in (6, 7)])
def test_the_whole_thing(listen_time_stats_df, child, month):
    subregion_count = _get_subregion_count(child=child, month=month)
    cha_path = get_cha_path(child=child, month=month)
    stats_correct = listen_time_stats_df.set_index('filename').loc[cha_path.name].to_dict()

    stats = listen_time_stats_for_report(clan_file_text=cha_path.read_text(), subregion_count=subregion_count)

    for key, correct_value in stats_correct.items():
        correct_value = _possibly_interpret_as_list(correct_value)
        assert stats[key] == correct_value
