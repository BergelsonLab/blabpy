""" Functions in this module check how much time in each audio recording has been listened to for annotation purposes.
They start with the outputs produced by recap_regions_listen_time_compute.py in the `annot_distr` repository
(https://github.com/SeedlingsBabylab/annot_distr/). More specifically, here we use the region boundaries extracted
from each cha file and put into output/cha_structures/<child>_<month>_sparse_code.cha.txt that look approximately like
this:

    subregion starts 1200
    subregion ends 2400
    ...
    surplus starts 4500
    surplus end 5000

    Position: 1, Rank: 1
    Position: 2, Rank: 5
    Position: 3, Rank: 2
    Position: 4, Rank: 4
    Position: 5, Rank: 3

Recordings for months 6 and 7 do not have the subregion information and are already assessed in the annot_distr repo,
so we do not work with them here.

For each subregion, we calculate the amount of time listened to within that subregion accounting for skips and silences.
Starting from the subregion ranked the first on talkativeness, we then assign makeup and extra regions to each subregion
until the total listened time is not at least an hour.
"""
from enum import Enum

import pandas as pd


class RegionType(Enum):
    SUBREGION = 'subregion'
    SILENCE = 'silence'
    SKIP = 'skip'
    MAKEUP = 'makeup'
    EXTRA = 'extra'
    SURPLUS = 'surplus'


# List of values to check with `in`
REGION_TYPES = [rt.value for rt in RegionType]

# Number of decimal places used when converting milliseconds to hours
PRECISION = 2

# Two recordings have four subregions, not five
RECORDINGS_WITH_FOUR_SUBREGIONS = ((21, 14), (45, 10))


def _region_boundaries_to_dataframe(region_lines):
    """
    Converts the region lines from a cha_structure file into a dataframe with three columns: region_type, start, end
    :param region_lines: a list of string read from the first part of a cha structure file
    :return: a pandas dataframe
    """
    boundaries_df = pd.DataFrame(columns=('region_type', 'which_boundary', 'time'),
                                 # Each line is "<region_type> <starts|ends> <timestamp>"
                                 data=[line.split() for line in region_lines])

    assert boundaries_df.region_type.isin(REGION_TYPES).all()

    # For each type, count all starts 1, 2, 3 and count all ends 1, 2, 3 so that we can then match starts to ends.
    boundaries_df['position'] = boundaries_df.groupby(['region_type', 'which_boundary']).cumcount() + 1
    # Match starts to ends and combine
    starts = boundaries_df[boundaries_df.which_boundary == 'starts'].drop(columns='which_boundary')
    ends = boundaries_df[boundaries_df.which_boundary == 'ends'].drop(columns='which_boundary')
    regions = pd.merge(left=starts, right=ends, how='left', on=['region_type', 'position'])
    assert starts.shape[0] == ends.shape[0] == regions.shape[0]

    # Rename and reorder columns
    regions = regions.rename(columns=dict(time_x='start', time_y='end'))[['region_type', 'start', 'end', 'position']]
    regions[['start', 'end']] = regions[['start', 'end']].astype(int)

    return regions


def _subregion_ranks_to_dataframe(subregion_rank_lines, subregion_count=5):
    """
    Converts the subregion lines from a cha_structure file into a dataframe with two columns: position, rank
    :param subregion_rank_lines: a list of strings read from the second part of a cha structure file
    :param subregion_count: for known recordings with four subregions
    :return:
    """
    # Each row looks like "Position: 1, Rank: 1", so we can just extract position and rank using a regular expression
    subregion_ranks = (pd.Series(subregion_rank_lines)
                       .str.extractall(r'Position: (?P<position>\d+), Rank: (?P<rank>\d+)')
                       .reset_index(drop=True))

    # There should always be exactly five subregions and five ranks: 1 to 5
    positions = sorted(subregion_ranks.position.tolist())
    ranks = sorted(subregion_ranks['rank'].tolist())
    assert positions == ranks == [str(i + 1) for i in range(subregion_count)]

    return subregion_ranks


def _read_cha_structure(cha_structure_path, subregion_count=5):
    """
    Reads the files at cha_structure_path and converts it into two dataframes: one with all the regions and one with the
    subregion ranks.
    :param cha_structure_path: a string path to the file
    :param subregion_count: passed to _subregion_ranks_to_dataframe
    :return: (regions, subregion_ranks) - a tuple of pandas dataframes
    """
    region_lines, subregion_rank_lines = list(), list()
    with open(cha_structure_path, 'r') as f:
        # read region boundaries
        for line in f:
            line = line.rstrip()
            if line:
                region_lines.append(line)
            else:  # we reached the empty lines between region boundaries and subregion ranks
                break

        # read subregion ranks
        for line in f:
            line = line.rstrip()
            if line:
                subregion_rank_lines.append(line.rstrip())

    return (_region_boundaries_to_dataframe(region_lines),
            _subregion_ranks_to_dataframe(subregion_rank_lines, subregion_count=subregion_count))


def assert_numbers(*numbers):
    assert all((isinstance(number, int) or isinstance(number, float) for number in numbers))


def _set_difference_of_intervals(minuend, subtrahend):
    """
    Set-subtracts a closed interval from an open interval. The result is (a possibly empty) list of open intervals.
    :param minuend: (x1, x2) tuple of ints/floats representing the interval to be subtracted from
    :param subtrahend: (y1, y2) tuple of ints/floats representing the interval to be subtracted
    :return: list of 0, 1, or 2 paris of numbers in the natural order
    """
    x1, x2 = minuend
    y1, y2 = subtrahend
    assert_numbers(x1, x2, y1, y2)
    assert x1 < x2 and y1 < y2

    # Subtraction of (y1, y2) is equivalent to the union of subtracting (-Inf, y2] and [y1, Inf):
    # A \ (B1 ∧ B2) = (A \ B1) ∪ (A \ B2)
    # Further, if A = (x1, x2) and B1 = [y1, Inf), A \ B = (x1, min(x2, y1)) := (z1, z2) as long as z1 < z2
    result = [(z1, z2)
              for (z1, z2) in [(x1, min(x2, y1)),  # (x1, x2) \ [y1, Inf)
                               (max(x1, y2), x2)]   # (x1, x2) \ (-Inf, y2]
              if z1 < z2]

    return result


def _remove_interval_from_regions(regions, start, end):
    """
    Removes a time interval from each region in regions. As a results, each region can:
    - disappear totally if it contained within the removed interval,
    - get shortened on one side if only of it ends is within the remove interval,
    - become two shorter regions if the removed interval is fully contained within the region.
    :param regions: a regions dataframe (region_type, start, end columns)
    :param start: int/float, start of the interval to be removed
    :param end: int/float, end of the interval to be removed
    :return: a modified dataframe
    """
    assert_numbers(start, end)
    with_interval_removed = regions.copy()

    # For each region, get a list of starts and ends of its subregions after the removal
    new_starts_and_ends = 'new_starts_and_ends'
    with_interval_removed[new_starts_and_ends] = with_interval_removed.apply(
        lambda row: _set_difference_of_intervals(minuend=(int(row.start), int(row.end)), subtrahend=(start, end)),
        axis='columns')
    # Now, each element in that list should get its own row.
    with_interval_removed = (with_interval_removed
                             .explode(new_starts_and_ends)
                             .dropna(subset=[new_starts_and_ends])  # Empty lists result in an NA row
                             .drop(columns=['start', 'end'])  # The original start and end can be dropped now
                             )
    # Split 'new_start_and_ends' column that contains (start, end) tuples into two columns - start and end.
    with_interval_removed[['start', 'end']] = with_interval_removed.new_starts_and_ends.values.tolist()
    with_interval_removed.drop(columns=[new_starts_and_ends], inplace=True)

    # Finally, restore the original column order, reset index, and return
    return with_interval_removed[regions.columns].reset_index(drop=True)


def _remove_silences_and_skips(regions):
    """
    Takes a regions dataframe, remove skips and silence from it and then removes parts of any regions that overlap with
    any of the skips/silences. See _remove_interval_from_regions for details of how the removing works.
    :param regions: a pandas dataframe output by _read_cha_structure
    :return: a dataframe with skips and silence removed as regions and the corresponding interval removed from other
    regions
    """
    is_silence_or_skip = regions.region_type.isin([RegionType.SILENCE.value, RegionType.SKIP.value])
    remaining_regions, silences_and_skips = regions[~is_silence_or_skip], regions[is_silence_or_skip]
    for row in silences_and_skips.itertuples():
        remaining_regions = _remove_interval_from_regions(remaining_regions, int(row.start), int(row.end))
    return remaining_regions


def _remove_subregions_with_makeup_and_extra(regions):
    return


def _assign_makeup_and_extra_to_subregions(regions):
    return


def _aggregate_listen_time(regions, subregion_ranks):
    return


def calculate_listened_time(cha_structure_path):
    regions, subregion_ranks = _read_cha_structure(cha_structure_path)
    regions = _remove_silences_and_skips(regions)
    regions = _remove_subregions_with_makeup_and_extra(regions)
    regions = _assign_makeup_and_extra_to_subregions(regions, subregion_ranks)
    return _aggregate_listen_time(regions)


def _total_time_per_region_type(regions_df):
    return (regions_df
            .assign(duration=(regions_df.end - regions_df.start))
            .groupby('region_type')
            .aggregate(total_time=('duration', 'sum'))
            .reset_index())


def milliseconds_to_hours(ms):
    return round(ms / (60 * 60 * 1000), PRECISION)
