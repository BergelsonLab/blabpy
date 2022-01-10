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


def _region_boundaries_to_dataframe(region_lines):
    """
    Converts the region lines from a cha_structure file into a dataframe with three columns: region_type, start, end
    :param region_lines: a list of string read from the first part of a cha structure file
    :return: a pandas dataframe
    """
    boundaries_df = pd.DataFrame(columns=('region_type', 'which_boundary', 'time'),
                                 # Each line is "<region_type> <starts|ends> <timestamp>"
                                 data=[line.split() for line in region_lines])
    # For each type, count all starts 1, 2, 3 and count all ends 1, 2, 3 so that we can then match starts to ends.
    boundaries_df['position'] = boundaries_df.groupby(['region_type', 'which_boundary']).cumcount() + 1

    # Match starts to ends and combine
    starts = boundaries_df[boundaries_df.which_boundary == 'starts'].drop(columns='which_boundary')
    ends = boundaries_df[boundaries_df.which_boundary == 'ends'].drop(columns='which_boundary')
    regions = pd.merge(left=starts, right=ends, how='left', on=['region_type', 'position'])
    assert starts.shape[0] == ends.shape[0] == regions.shape[0]

    # Rename and reorder columns
    regions = regions.rename(columns=dict(time_x='start', time_y='end'))[['region_type', 'start', 'end', 'position']]

    return regions


def _subregion_ranks_to_dataframe(subregion_rank_lines):
    """
    Converts the subregion lines from a cha_structure file into a dataframe with two columns: position, rank
    :param subregion_rank_lines: a list of strings read from the second part of a cha structure file
    :return:
    """
    # Each row looks like "Position: 1, Rank: 1", so we can just extract position and rank using a regular expression
    subregion_ranks = (pd.Series(subregion_rank_lines)
                       .str.extractall(r'Position: (?P<position>\d+), Rank: (?P<rank>\d+)')
                       .reset_index(drop=True))

    # There should always be exactly five subregions and five ranks: 1 to 5
    positions = sorted(subregion_ranks.position.tolist())
    ranks = sorted(subregion_ranks['rank'].tolist())
    assert positions == ranks == ['1', '2', '3', '4', '5']

    return subregion_ranks


def _read_cha_structure(cha_structure_path):
    """
    Reads the files at cha_structure_path and converts it into two dataframes: one with all the regions and one with the
    subregion ranks.
    :param cha_structure_path: a string path to the file
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

    return _region_boundaries_to_dataframe(region_lines), _subregion_ranks_to_dataframe(subregion_rank_lines)


def _set_difference_of_intervals(minuend, subtrahend):
    """
    Set-subtracts a closed interval from an open interval. The result is (a possibly empty) list of open intervals.
    :param minuend: (x1, x2) tuple representing the interval to be subtracted from
    :param subtrahend: (y1, y2) tuple representing the interval to be subtracted
    :return: list of 0, 1, or 2 paris of numbers in the natural order
    """
    x1, x2 = minuend
    y1, y2 = subtrahend
    assert x1 < x2 and y1 < y2
    # Subtraction of (y1, y2) is equivalent to the union of subtracting (-Inf, y2] and [y1, Inf):
    # A \ (B1 ∧ B2) = (A \ B1) ∪ (A \ B2)
    # Further, if A = (x1, x2) and B1 = [y1, Inf), A \ B = (x1, min(x2, y1)) := (z1, z2) as long as z1 < z2
    result = [(z1, z2)
              for (z1, z2) in [(x1, min(x2, y1)),  # (x1, x2) \ [y1, Inf)
                               (max(x1, y2), x2)]   # (x1, x2) \ (-Inf, y2]
              if z1 < z2]

    return result


def _remove_silences_and_skips(regions):
    return


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
