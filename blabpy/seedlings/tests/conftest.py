from pathlib import Path

import pytest


@pytest.fixture(scope='module')
def top3_top4_surplus_data_dir():
    return Path(__file__).parent / 'data' / 'top3_top4_surplus'
