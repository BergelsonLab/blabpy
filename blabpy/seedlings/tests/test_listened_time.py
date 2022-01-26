import pandas as pd
import pytest

from blabpy.seedlings.listened_time import _set_difference_of_intervals, \
    _remove_interval_from_regions, _remove_silences_and_skips, _total_time_and_count_per_region_type, _remove_subregions, \
    _overlaps_with_interval, RegionType, _assert_no_overlaps

test_regions_df = pd.DataFrame(
    columns=['region_type', 'start', 'end', 'position'],
    data=[['surplus', 3600710, 6301520, 1],
          ['subregion', 6300000, 9900000, 1],
          ['extra', 9900230, 10200470, 1],
          ['surplus', 10516250, 10800010, 2],
          ['silence', 11183120, 15599480, 1],
          ['subregion', 15300000, 18900000, 2],
          ['surplus', 15793420, 18900930, 3],
          ['subregion', 18900000, 22500000, 3],
          ['silence', 26255960, 26733920, 2],
          ['silence', 27019130, 27504220, 3],
          ['subregion', 27600000, 31200000, 4],
          ['subregion', 33600000, 37200000, 5],
          ['silence', 44867230, 57599990, 4]])


def test__set_difference_of_intervals():
    # Invalid inputs should raise an error
    with pytest.raises(AssertionError):
        _set_difference_of_intervals((0, 1), (3, 2))
    with pytest.raises(AssertionError):
        _set_difference_of_intervals((1, 0), (2, 3))
    with pytest.raises(AssertionError):
        _set_difference_of_intervals((1, 0), (3, 2))

    # All inputs should be integers
    for minuend, subtrahend in ((('1', 12), (2, 21)),
                                ((1, '12'), (2, 21)),
                                ((1, 12), ('2', 21)),
                                ((1, 12), (2, '21'))):
        with pytest.raises(AssertionError):
            _set_difference_of_intervals(minuend, subtrahend)

    # Check that the output is correct
    minuend = (-1, 1)
    subtrahends, correct_differences = zip(*(
        ((-3, -2), [(-1, 1)]),
        ((-3, -1), [(-1, 1)]),
        ((-3, 0), [(0, 1)]),
        ((-3, 1), []),
        ((-3, 2), []),
        ((-1, 0), [(0, 1)]),
        ((-1, 1), []),
        ((-1, 2), []),
        ((0, 0.5), [(-1, 0), (0.5, 1)]),
        ((0, 1), [(-1, 0)]),
        ((0, 2), [(-1, 0)]),
        ((1, 2), [(-1, 1)]),
        ((2, 3), [(-1, 1)])
    ))
    for subtrahend, correct_difference in zip(subtrahends, correct_differences):
        assert _set_difference_of_intervals(minuend, subtrahend) == correct_difference


def test__remove_interval_from_regions():
    regions_list = [pd.DataFrame.from_dict({'start': [0, 4, 8],
                                            'end': [2, 6, 10],
                                            'arbitrary_column': ['a', 'b', 'c']}),
                    pd.DataFrame.from_dict({'start': [0],
                                            'end': [10],
                                            'arbitrary_column': ['a']})]
    # Interval to be removed
    start, end = 1, 9

    correct_results = [pd.DataFrame.from_dict({'start': [0, 9],
                                               'end': [1, 10],
                                               'arbitrary_column': ['a', 'c']}),
                       pd.DataFrame.from_dict({'start': [0, 9],
                                               'end': [1, 10],
                                               'arbitrary_column': ['a', 'a']})]

    for regions, correct_result in zip(regions_list, correct_results):
        regions_copy = regions.copy()
        assert _remove_interval_from_regions(regions=regions_copy, start=start, end=end).equals(correct_result)
        # Check that the input has not been modified
        assert regions.equals(regions_copy)


def test__remove_silences_and_skips():
    regions = pd.DataFrame(
        columns=['region_type', 'start', 'end', 'position'],
        data=[('subregion', 1, 10, 1),
              ('subregion', 11, 20, 2),
              ('subregion', 22, 30, 3),
              ('silence', 5, 21, 1),
              ('skip', 24, 27, 1),
              ('skip', 32, 37, 2)])

    correct_result = pd.DataFrame(**{
        'columns': ['region_type', 'start', 'end', 'position'],
        'data': [['skip', 24, 27, 1],
                 ['skip', 32, 37, 2],
                 ['silence', 5, 21, 1],
                 ['subregion', 1, 5, 1],
                 ['subregion', 22, 24, 3],
                 ['subregion', 27, 30, 3]]})

    assert _remove_silences_and_skips(regions).equals(correct_result)


def test__total_time_per_region_type():
    correct_result = pd.DataFrame(
        columns=['region_type', 'total_time', 'count'],
        data=[['extra', 300240, 1],
              ['silence', 18112170, 4],
              ['subregion', 18000000, 5],
              ['surplus', 6092080, 3]]).set_index('region_type')
    assert _total_time_and_count_per_region_type(test_regions_df).equals(correct_result)


def test__remove_subregions():
    correct_result = pd.DataFrame(**{
        'columns': ['region_type', 'start', 'end', 'position'],
        'data': [['surplus', 3600710, 6301520, 1],
                 ['extra', 9900230, 10200470, 1],
                 ['surplus', 10516250, 10800010, 2],
                 ['silence', 11183120, 15599480, 1],
                 ['surplus', 15793420, 18900930, 3],
                 ['silence', 26255960, 26733920, 2],
                 ['silence', 27019130, 27504220, 3],
                 ['subregion', 27600000, 31200000, 4],
                 ['subregion', 33600000, 37200000, 5],
                 ['silence', 44867230, 57599990, 4]]})
    result = _remove_subregions(test_regions_df,
                                condition_function=_overlaps_with_interval,
                                other_region_types=[RegionType.SURPLUS])
    assert result.equals(correct_result)


def test__assert_no_overlaps():
    overlapping = pd.DataFrame(columns=['start', 'end'], data=((0, 2), (1, 3)))
    non_overlapping = pd.DataFrame(columns=['start', 'end'], data=((0, 1), (2, 3)))
    with pytest.raises(AssertionError):
        _assert_no_overlaps(overlapping)
    _assert_no_overlaps(non_overlapping)
