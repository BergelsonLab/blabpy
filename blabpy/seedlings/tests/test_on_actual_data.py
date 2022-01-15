import pytest

import pandas as pd


@pytest.fixture(scope='module')
def total_listen_time_summary_df(total_listen_time_summary_csv):
    return pd.read_csv(total_listen_time_summary_csv)


def test_the_whole_thing(total_listen_time_summary_df, cha_structures_folder):
    assert False
