from pathlib import Path

import pandas as pd

from blabpy.seedlings.listened_time import _read_cha_structure


def test__read_cha_structure():
    regions_correct = pd.DataFrame.from_dict({
        'region_type': {0: 'surplus',
                        1: 'subregion',
                        2: 'extra',
                        3: 'surplus',
                        4: 'silence',
                        5: 'subregion',
                        6: 'surplus',
                        7: 'subregion',
                        8: 'silence',
                        9: 'silence',
                        10: 'subregion',
                        11: 'subregion',
                        12: 'silence'},
        'start': {0: '3600710',
                  1: '6300000',
                  2: '9900230',
                  3: '10516250',
                  4: '11183120',
                  5: '15300000',
                  6: '15793420',
                  7: '18900000',
                  8: '26255960',
                  9: '27019130',
                  10: '27600000',
                  11: '33600000',
                  12: '44867230'},
        'end': {0: '6301520',
                1: '9900000',
                2: '10200470',
                3: '10800010',
                4: '15599480',
                5: '18900000',
                6: '18900930',
                7: '22500000',
                8: '26733920',
                9: '27504220',
                10: '31200000',
                11: '37200000',
                12: '57599990'},
        'position': {0: 1,
                     1: 1,
                     2: 1,
                     3: 2,
                     4: 1,
                     5: 2,
                     6: 3,
                     7: 3,
                     8: 2,
                     9: 3,
                     10: 4,
                     11: 5,
                     12: 4}})
    subregion_ranks_correct = pd.DataFrame.from_dict({
        'position': {0: '1', 1: '2', 2: '3', 3: '4', 4: '5'},
        'rank': {0: '1', 1: '5', 2: '2', 3: '4', 4: '3'}})

    regions, subregion_ranks = _read_cha_structure('data/test_cha_structure.txt')

    assert regions.equals(regions_correct)
    assert subregion_ranks.equals(subregion_ranks_correct)
