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
from pathlib import Path
import re

import pandas as pd

from blabpy.seedlings.paths import get_cha_path, _parse_out_child_and_month

# Two recordings have four subregions, all the other one have five
NO_CODEABLE_WORDS_BUT_LISTENED_COMMENT = 'subregion has been listened to but contains no codeable words'
DEFAULT_SUBREGION_COUNT = 5
RECORDINGS_WITH_FOUR_SUBREGIONS = ((21, 14), (45, 10))


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

# This is a very permissive regex copied from annot_distr,
ANNOTATION_REGEX = re.compile(
    r'([a-zA-Z][a-z+]*)( +)(&=)([A-Za-z]{1})(_)([A-Za-z]{1})(_)([A-Z]{1}[A-Z0-9]{2})(_)?(0x[a-z0-9]{6})?',
    re.IGNORECASE | re.DOTALL)
TIMESTAMP_REGEX = re.compile("\\x15(\d+)_(\d+)\\x15")


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

    # Remove regions that have zero duration
    regions = regions[regions.start != regions.end]

    # Order by onset ascending, then offset descending, then region_type in alphabetical order
    regions = regions.sort_values(by=['start', 'end', 'region_type'],
                                  ascending=[True, False, True]).reset_index(drop=True)

    return regions


def _subregion_ranks_to_dataframe(subregion_rank_lines, subregion_count=DEFAULT_SUBREGION_COUNT):
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


def _remove_overlaps_from_other_regions(regions, dominant_region_type):
    """
    Takes regions of a single kind (e.g., silences) and removes from all other regions all overlapping parts (e.g., from
    each non-silence region removes any part that overlaps with any of the silence regions).
    :param regions: a dataframe with at least region_type, start, and end columns
    :param dominant_region_type: the region type overlaps with which will be removed from other regions.
    :return: copy of the regions dataframe with some of the non-dominant regions modified
    """
    is_dominant = regions.region_type == dominant_region_type
    dominant, nondominant = regions[is_dominant], regions[~is_dominant]
    for row in dominant.itertuples():
        nondominant = _remove_interval_from_regions(nondominant, int(row.start), int(row.end))

    # Combine with the dominant regions and return
    return pd.concat([dominant, nondominant]).reset_index(drop=True)


def _remove_silences_and_skips(regions):
    """
    From each region removes any parts that overlap with silences, then with skips.
    See _remove_interval_from_regions for details of how the removing works.
    :param regions: a pandas dataframe output by _read_cha_structure, for example
    :return: a dataframe with skips and silence removed as regions and the corresponding interval removed from other
    regions
    """
    for region_type in (RegionType.SILENCE.value, RegionType.SKIP.value):
        regions = _remove_overlaps_from_other_regions(regions=regions, dominant_region_type=region_type)

    return regions


def _overlaps_with_interval(regions, start, end):
    return ~((regions.start >= end) | (regions.end <= start))


def _contains_nested(regions, start, end):
    return (regions.start <= start) & (end <= regions.end)


def _remove_subregions(regions, condition_function, other_region_types):
    """
    Remove all subregions that satisfy a given condition depending on overlap with another region, e.g., have at least
    some overlap with silences or skips.
    :param regions: a full regions dataframe
    :param condition_function: a function that takes in regions, start, and end and returns a boolean Series that tells
    us whether each region in regions satisfies a given condition (e.g., partially overlaps, fully nested in, etc.)
    :param other_region_types: which regions should be tested against the condition? A list of RegionType properties.
    :return:
    """
    # Get necessary subsets of regions
    is_subregion = regions.region_type == RegionType.SUBREGION.value
    subregions, not_subregions = regions[is_subregion], regions[~is_subregion]
    # Convert other_region_types to a list of string to test against
    other_region_types_str = [other_region_type.value for other_region_type in other_region_types]
    other_regions = regions[regions.region_type.isin(other_region_types_str)]

    # Do the removal
    for other_region in other_regions.itertuples():
        condition_satisfied = condition_function(subregions, other_region.start, other_region.end)
        subregions = subregions[~condition_satisfied]

    # Combine with the other regions, restore order, return
    return pd.concat([subregions, not_subregions]).sort_index().reset_index(drop=True)


def _assign_makeup_and_extra_to_subregions(regions):
    return


def _aggregate_listen_time(regions, subregion_ranks):
    return


def _account_for_region_overlaps(regions):
    """
    Removes some subregions, modifies some other regions so that the resulting regions do not overlap and can be counted
    towards total listened time.
    1. Removes any subregions that overlap with any surplus region.
    2. Removes any subregions that contain in them nested makeup/surplus regions.
    3. Removes overlaps starting by removing overlaps with silences, then with skips, etc.
    :param regions: a regions dataframe such as the one output by _read_cha_structure
    :return:
    """
    # Some subregions need to be removed completely
    regions = _remove_subregions(regions, condition_function=_overlaps_with_interval,
                                 other_region_types=[RegionType.SURPLUS])
    regions = _remove_subregions(regions, condition_function=_contains_nested,
                                 other_region_types=[RegionType.MAKEUP, RegionType.SURPLUS])

    # All other regions need to have parts of them remove dwhere they overlap with other regions.
    # The order matters, e.g. if you remove silences first, the silence will remain in their original form.
    # Deliberately manually placed regions should always trump the automatic ones.
    # Out of those, if a skip overlaps with any of the other ones, the skip should carry more weight and be left intact.
    # Makeup, surplus, extras should not overlap at all so their order does not matter.
    dominant_region_types = [RegionType.SKIP,
                             RegionType.SURPLUS, RegionType.MAKEUP, RegionType.EXTRA,
                             RegionType.SILENCE]
    # The list above should contain everything but subregions
    assert len(dominant_region_types) == len(REGION_TYPES) - 1
    # Check that surplus, makeup, and extra regions do not overlap
    _assert_no_overlaps(regions[regions.region_type.isin(
        [RegionType.SURPLUS.value, RegionType.MAKEUP.value, RegionType.EXTRA.value])])

    for dominant_region_type in dominant_region_types:
        regions = _remove_overlaps_from_other_regions(regions, dominant_region_type.value)
    return regions


def _remove_subregions_without_annotations(regions, annotation_timestamps, listened_but_empty):
    """
    This function has to be run before any region adjustments because it does not account for possible splits resulting
    from having, for example, a skip in the middle.
    :param regions: a regions dataframe
    :param annotation_timestamps: dataframe with unique annotation timestamps
    :param listened_but_empty: list of additional timestamp offset corresponding to the special comments that mark
    subregions that were listened to but did not have any codeable words
    :return: regions with possibly a few rows removed
    """
    # Check that no subregions have been split yet
    assert regions[regions.region_type == RegionType.SUBREGION.value].duplicated(subset=['position']).sum() == 0

    # Merge annotation timestamps with the additional offsets (they will become both onsets and offsets)
    listened_but_empty_df = pd.DataFrame(columns=('onset', 'offset'), data=zip(*([listened_but_empty] * 2)))
    timestamps = pd.concat([annotation_timestamps, listened_but_empty_df], ignore_index=True)

    regions = _add_per_region_timestamp_count(regions, timestamps)
    regions = regions[(regions.annotation_count > 0) | (regions.region_type != RegionType.SUBREGION.value)]
    return regions.drop(columns='annotation_count')


def _assert_no_overlaps(regions):
    """
    Assert that none of the regions overlap, being back-to-back is fine.
    :param regions: a pandas DataFrame with start and end columns
    :return:
    """
    boundaries = regions.sort_values(by=['start', 'end'], ascending=[True, False])[['start', 'end']]
    previous_end = boundaries.end.shift(fill_value=-1)
    assert (boundaries.start >= previous_end).all()


def _total_eligible_time(regions):
    """
    Sums up duration of all regions except for silences, skips and surpluses. Assumes that the regions have been
    de-overlapped.
    :param regions: a regions dataframe that has already been de-overlapped
    :return: total duration as an integer
    """
    _assert_no_overlaps(regions)
    region_types_to_exclude = [RegionType.SURPLUS.value, RegionType.SILENCE.value, RegionType.SKIP.value]
    total_time_per_region = _total_time_and_count_per_region_type(regions_df=regions[
        ~regions.region_type.isin(region_types_to_exclude)])
    return total_time_per_region.total_time.sum()


def calculate_total_listened_time(regions, listened_but_empty, child, month):
    """
    Calculates total listen time by:
    - removing subregions without annotations (unless they contain a special comment instead),
    - removing any overlaps between different regions in a certain order,
    :param regions: a dataframe with region_type, start, end, position columns
    :param listened_but_empty: a list of offsets of the special comments
    :param child: child number
    :param month: month number
    :return:
    """
    # Extract timestamps
    clan_file_path = get_cha_path(child=child, month=month)
    annotation_timestamps = _extract_annotation_timestamps(clan_file_path)

    # Do not count subregions without annotations, unless they contain a special comment
    regions = _remove_subregions_without_annotations(regions, annotation_timestamps, listened_but_empty)

    # Account for region overlaps
    regions = _account_for_region_overlaps(regions)

    # Add up durations of all eligible regions
    total_listen_time = _total_eligible_time(regions)

    return total_listen_time


def _total_time_and_count_per_region_type(regions_df):
    """
    Calculates total duration and region count for each region type. Counts split regions only once.
    :param regions_df: a regions dataframe with columns region_type, start, end, and position
    :return:
    """
    return (regions_df
            .assign(duration=(lambda df: df.end - df.start))
            .groupby('region_type')
            .aggregate(total_time=('duration', 'sum'),
                       count=('position', 'nunique')))


def _extract_timestamps(clan_file_content: str):
    """
    Extract all timestamps from a clan file remembering their positions in text. Raises a ValueError if the onsets or
    offsets are not monotinc increasing.
    :param clan_file_content: clan file as one long string
    :return: a dataframe with one row per timestamp and three columns: onset, offset, 'position_in_text'
    """
    timestamps = pd.DataFrame(
        columns=['onset', 'offset', 'position_in_text'],
        data=[(int(match.group(1)), int(match.group(2)), match.start())
              for match in TIMESTAMP_REGEX.finditer(clan_file_content)],
        dtype=int)

    if not timestamps.onset.is_monotonic:
        # TODO: uncomment or delete once timestamp inconsistencies have been dealt with
        # not (timestamps.onset.is_monotonic and timestamps.offset.is_monotonic and
        # (timestamps.onset <= timestamps.offset).all()):
        raise ValueError('Timestamps are not in the right order.')

    return timestamps


def _match_with_timestamps(positions_in_text, timestamps_df, above=None, below=None):
    """
    For each row in a DataFrame/Series that has a 'position_in_text' integer column finds the last timestamp before that
    position (if before is True) or the first one after (if after is True).
    :param positions_in_text: an arbitrary dataframe with a 'position_in_text' integer column which must be monotonic
    increasing
    :param timestamps_df: same, but normally it is a dataframe as output by _extract_timestamps
    :param above: if True, look for the last timestamp above
    :param below: if True, look for the first timestamp below
    :return: a copy of df_with_position_in_text with two additional columns: onset and offset
    """
    if below and not above:
        direction = 'forward'
    elif above and not below:
        direction = 'backward'
    else:
        raise ValueError('Exactly one of `above` and `below` arguments must evaluate to True')

    # Check that the positions are monotonic increasing
    if isinstance(positions_in_text, pd.Series):
        assert positions_in_text.name == 'position_in_text'
        assert positions_in_text.is_monotonic
    elif isinstance(positions_in_text, pd.DataFrame):
        assert positions_in_text.position_in_text.is_monotonic
    assert timestamps_df.position_in_text.is_monotonic

    return pd.merge_asof(positions_in_text, timestamps_df,
                         on='position_in_text', direction=direction)


def _extract_annotation_timestamps(clan_file_path):
    """
    Find all annotation timestamps in a clan/cha file
    :param clan_file_path: path to the file
    :return: a pandas dataframe with two columns: 'onset' and 'offset'; and one row per each annotation found
    """
    clan_file_content = Path(clan_file_path).read_text()
    annotation_positions_in_text = pd.Series([match.start() for match in ANNOTATION_REGEX.finditer(clan_file_content)],
                                             name='position_in_text')

    # Add the first timestamps below the annotations in the file
    annotation_timestamps = _match_with_timestamps(
        positions_in_text=annotation_positions_in_text,
        timestamps_df=_extract_timestamps(clan_file_content),
        below=True)

    # Here, we are only interested in unique timestamps, not unique annotations, so we should remove the duplicates
    annotation_timestamps = (annotation_timestamps
                             [['onset', 'offset']]
                             .drop_duplicates(keep='first')
                             .reset_index(drop=True))

    return annotation_timestamps


def _add_per_region_timestamp_count(regions_df, timestamps):
    """
    Count annotations that start and end within each subregions
    :param regions_df: a dataframe with 'start' and 'end' numeric columns
    :param timestamps: a dataframe with 'onset' column
    :return: regions_df with an additional column 'annotation_count'
    """
    regions_df_columns = regions_df.columns.tolist()
    # Brute-force solution: take a cross-product of regions and annotations and filter out rows where annotation is not
    # within region boundaries
    with_annotation_counts = (
        regions_df
        # There is no cross join in pandas AFAIK, so we'll have to join on a dummy constant column
        .assign(cross_join=0)
        .merge(timestamps.assign(cross_join=0), on='cross_join')
        # The onset should within region boundaries
        .query('start <= onset and onset < end')
        .groupby(regions_df_columns)
        .size()
        .rename('annotation_count')
        .reset_index()
        # Above, we lost regions that do not have any annotations in them, let's put them back with the count of 0
        .merge(regions_df, on=regions_df_columns, how='right')
        .fillna(dict(annotation_count=0)))

    return with_annotation_counts


def milliseconds_to_hours(ms):
    return round(ms / (60 * 60 * 1000), PRECISION)


def _extract_subregion_info(comment):
    """
    Extracts subregion position, rank, offset from a comment line from a clan (cha) file.
    :param comment: a string from the subregion boundary comment in a cha file
    :return: position, rank, offset
    """
    subregion_position_regex = re.compile(r'subregion (\d+) of (\d+)')
    subregion_rank_regex = re.compile(r'ranked (\d+) of (\d+)')
    subregion_time_regex = re.compile(r'at (\d+)')
    position = subregion_position_regex.search(comment).group(1)
    rank = subregion_rank_regex.search(comment).group(1)
    offset = int(subregion_time_regex.findall(comment)[0])

    return position, rank, offset


def _extract_region_info(clan_file_path, subregion_count=DEFAULT_SUBREGION_COUNT):
    """
    Extracts region boundaries, subregions ranks, and info about "listened to, nothing to annotate" from a clan file.
    :param clan_file_path:
    :return:
    """
    # Find all the comments
    clan_file_text = Path(clan_file_path).read_text()
    comment_line_regex = r'^%x?com:.*?(?=^[^\t])'
    comments_df = pd.DataFrame(
        columns=('text', 'position_in_text'),
        data=[(match.group(), match.start())
              for match in re.finditer(comment_line_regex, clan_file_text, flags=re.MULTILINE + re.DOTALL)])
    # Remove LENA comments, counting '|' solution comes from pyclan
    comments_df = comments_df[comments_df.text.str.count('\|') <= 3]
    # Add timestamp info
    comments_df = _match_with_timestamps(
        positions_in_text=comments_df,
        timestamps_df=_extract_timestamps(clan_file_text),
        above=True)
    # Some files have the first subregion comment before the first tier so they don't get a timestamp, so it will have
    # NaN as offset, which will force pandas to convert the whole column to 'float64' which will cause problems down the
    # line. So, here, we will convert offset to a special integer datatype that supports NaN at the same time.
    comments_df['offset'] = comments_df.offset.astype(pd.Int64Dtype())

    subregions = []  # List of strings of the format 'Position: {}, Rank: {}'
    region_boundaries = []  # List of strings of the format
    listened_but_empty = []  # List of integers - offsets of the corresponding comments

    # Code below is copied from annot_distr
    for comment_row in comments_df.itertuples():
        comment = comment_row.text
        row_offset = comment_row.offset
        if 'subregion' in comment:
            if NO_CODEABLE_WORDS_BUT_LISTENED_COMMENT in comment:
                listened_but_empty.append(row_offset)
            else:
                sub_pos, sub_rank, offset = _extract_subregion_info(comment)
                if 'starts' in comment:
                    region_boundaries.append(('subregion starts', offset))
                # Only adding after ends in order to not add the position and rank info twice to the subregions list.
                elif 'ends' in comment:
                    region_boundaries.append(('subregion ends', offset))
                    subregions.append('Position: {}, Rank: {}'.format(sub_pos, sub_rank))

            continue

        if 'extra' in comment:
            if 'begin' in comment:
                region_boundaries.append(('extra starts', row_offset))
            elif 'end' in comment:
                region_boundaries.append(('extra ends', row_offset))
        elif 'silence' in comment:
            if 'start' in comment:
                region_boundaries.append(('silence starts', row_offset))
            elif 'end' in comment:
                region_boundaries.append(('silence ends', row_offset))
        elif 'skip' in comment:
            if 'begin' in comment:
                region_boundaries.append(('skip starts', row_offset))
            elif 'end' in comment:
                region_boundaries.append(('skip ends', row_offset))
        elif 'makeup' in comment or 'make-up' in comment or 'make up' in comment:
            if 'begin' in comment:
                region_boundaries.append(('makeup starts', row_offset))
            elif 'end' in comment:
                region_boundaries.append(('makeup ends', row_offset))
        elif 'surplus' in comment:
            if 'begin' in comment:
                region_boundaries.append(('surplus starts', row_offset))
            elif 'end' in comment:
                region_boundaries.append(('surplus ends', row_offset))

    # The code below emulates reading from cha_structures files that annot_distr creates
    region_boundaries_df = _region_boundaries_to_dataframe([' '.join(map(str, rb)) for rb in region_boundaries])
    subregion_ranks_df = _subregion_ranks_to_dataframe(subregions, subregion_count=subregion_count)

    return region_boundaries_df, subregion_ranks_df, listened_but_empty
