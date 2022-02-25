import ast
from pathlib import Path

import pytest
import pandas as pd

from blabpy.seedlings.cha import export_cha_to_csv
from blabpy.seedlings.listened_time import listen_time_stats_for_report, _get_subregion_count
from blabpy.seedlings.paths import ALL_CHILDREN, ALL_MONTHS, MISSING_AUDIO_RECORDINGS, get_cha_path
from blabpy.utils import text_file_checksum


def _possibly_interpret_as_list(possibly_list):
    if isinstance(possibly_list, str) and possibly_list.startswith('[') and possibly_list.endswith(']'):
        return ast.literal_eval(possibly_list)
    else:
        return possibly_list


def _get_test_cha_path(child, month):
    return Path(f'data/annotated_cha/annotated_cha/{child:02}_{month:02}_sparse_code.cha')


@pytest.fixture(scope='module')
def listen_time_stats_df():
    return pd.read_csv('data/listen_time_stats.csv')


@pytest.mark.parametrize(argnames=('child', 'month'),
                         argvalues=[(child, month)
                                    for child in ALL_CHILDREN for month in ALL_MONTHS
                                    if (child, month) not in MISSING_AUDIO_RECORDINGS])
def test_listen_time_stats_for_report(listen_time_stats_df, child, month):
    subregion_count = _get_subregion_count(child=child, month=month)
    cha_path = _get_test_cha_path(child, month)
    stats_correct = listen_time_stats_df.set_index('filename').loc[cha_path.name].to_dict()

    stats = listen_time_stats_for_report(clan_file_text=cha_path.read_text(), subregion_count=subregion_count)

    for key, correct_value in stats_correct.items():
        correct_value = _possibly_interpret_as_list(correct_value)
        assert stats[key] == correct_value


@pytest.fixture(scope='module')
def cha_export_checksums_df():
    return pd.read_csv('data/cha_parsing_checksums.csv').set_index('cha_filename')


@pytest.mark.parametrize(argnames=('child', 'month'),
                         argvalues=[(child, month)
                                    for child in ALL_CHILDREN for month in ALL_MONTHS
                                    if (child, month) not in MISSING_AUDIO_RECORDINGS])
def test_export_cha_to_csv(cha_export_checksums_df, child, month, tmpdir):
    cha_path = _get_test_cha_path(child, month)
    cha_checksum = text_file_checksum(cha_path)
    export_cha_to_csv(cha_path, tmpdir)
    exported_csv_path = tmpdir / cha_path.name.replace(".cha", "_processed.csv")
    exported_csv_checksum = text_file_checksum(exported_csv_path)

    checksums = cha_export_checksums_df.loc[cha_path.name]

    assert cha_checksum == checksums.cha_checksum
    assert exported_csv_path.exists()
    assert exported_csv_checksum == checksums.exported_csv_checksum
