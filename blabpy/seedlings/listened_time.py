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
import re

import pandas as pd

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
                       .str.extractall(r'Position: (?P<position>\d+), Rank: (?P<subregion_rank>\d+)')
                       .reset_index(drop=True))

    # There should always be exactly five subregions and five ranks: 1 to 5
    positions = sorted(subregion_ranks.position.tolist())
    ranks = sorted(subregion_ranks.subregion_rank.tolist())
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
    :return: a new dataframe with one row per each resulting region part or None, if all regions get removed
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

    # If no regions are left after the removal, return None
    if with_interval_removed.size == 0:
        return

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

    # If there are no "other" regions, there is nothing to do. This only happens for recordings from months 6 and 7 that
    # only have skips or only have silences.
    if is_dominant.all():
        return regions

    dominant, nondominant = regions[is_dominant], regions[~is_dominant]
    for row in dominant.itertuples():
        nondominant = _remove_interval_from_regions(nondominant, int(row.start), int(row.end))
        if nondominant is None:
            break

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


# TODO: This is unnecessarily complicated. The plan was to have multiple kinds of conditions: remove a subregion when it
#  strictly partially overlaps with one of the, say, surpluses, contain a surplus that is fully nested, is fully nested
#  within a surplus region, etc. The algorithm has been considerably simplified since then, so we only really need
#  _overlaps_with_interval and it is only ever used once on a single set of `other_region_types` (makeup/surplus). This
#  can all be simplified to something like `_remove_subregions_overlapping_with_makeup_or_surplus`.
#  If you get to this, it might be a good idea to break the process into logical, not technical steps: what we are
#  trying to do is figure out which subregions have been listened to: these are the ones with annotations or a special
#  comment except for those that only have annotations because they were used for makeup, which might have later been
#  renamed as surplus. So, it would make sense to have a `_remove_subregions_not_listened_to` function that would
#  account for annotations, special comments *and* overlapping makeup/surplus regions.
#  Another thing to consider: counting annotations after deoverlapping all the regions would be even better:
#  - annotations in makeup/surplus would not be in the subregions at all (overlaps are removed from subregions during
#    deoverlapping) so we would get the subregions without their own annotations removed for free,
#  - if those subregions have annotations outside of the makeup/surplus regions, we would probably want to know: in
#    such cases, the subregions would not get removed because they would still contain annotations ever after
#    deoverlapping.
#  Close issue https://github.com/BergelsonLab/blabpy/issues/12 when done.
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
                                 other_region_types=[RegionType.SURPLUS, RegionType.MAKEUP])

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


def _process_regions(regions, annotation_timestamps, listened_but_empty):
    """
    Processes regions:
    - removes subregions without annotations (unless they contain a special comment instead),
    - removes any overlaps between different regions in a certain order,
    :param regions:
    :param annotation_timestamps:
    :param listened_but_empty:
    :return:
    """
    # Do not count subregions without annotations, unless they contain a special comment
    regions = _remove_subregions_without_annotations(regions, annotation_timestamps, listened_but_empty)

    # Account for region overlaps
    regions = _account_for_region_overlaps(regions)

    return regions


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
                       region_count=('position', 'nunique')))


def _extract_timestamps(clan_file_text: str):
    """
    Extract all timestamps from a clan file remembering their positions in text. Raises a ValueError if the onsets or
    offsets are not monotonic increasing.
    :param clan_file_text: clan file as one long string
    :return: a dataframe with one row per timestamp and three columns: onset, offset, 'position_in_text'
    """
    timestamps = pd.DataFrame(
        columns=['onset', 'offset', 'position_in_text'],
        data=[(int(match.group(1)), int(match.group(2)), match.start())
              for match in TIMESTAMP_REGEX.finditer(clan_file_text)],
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


def _extract_annotation_timestamps(clan_file_text: str):
    """
    Find all annotation timestamps in a clan/cha file
    :param clan_file_text: string with the clan file text
    :return: a pandas dataframe with two columns: 'onset' and 'offset'; and one row per each annotation found
    """
    annotation_positions_in_text = pd.Series([match.start() for match in ANNOTATION_REGEX.finditer(clan_file_text)],
                                             name='position_in_text')

    # Add the first timestamps below the annotations in the file
    annotation_timestamps = _match_with_timestamps(
        positions_in_text=annotation_positions_in_text,
        timestamps_df=_extract_timestamps(clan_file_text),
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


def _extract_region_info(clan_file_text: str, subregion_count=DEFAULT_SUBREGION_COUNT):
    """
    Extracts region boundaries, subregions ranks, and info about "listened to, nothing to annotate" from a clan file.
    :param clan_file_text: string with the clan file text
    :return:
    """
    # Find all the comments
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
    # Some files have region comments before the first tier and thus they don't get a timestamp, so it will have
    # NaN as offset, which will force pandas to convert the whole column to 'float64' which will cause problems down the
    # line. So, here, we will convert offset to a special integer datatype that supports NaNs and will fill the ones in
    # the beginning with 0.
    for column in ('onset', 'offset'):
        comments_df[column] = comments_df[column].astype(pd.Int64Dtype())
        comments_df[column].loc[:comments_df[column].first_valid_index()] = 0

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
    if subregion_count > 0:
        subregion_ranks_df = _subregion_ranks_to_dataframe(subregions, subregion_count=subregion_count)
    else:
        subregion_ranks_df = None

    return region_boundaries_df, subregion_ranks_df, listened_but_empty


def listen_time_stats_for_report(clan_file_text: str, subregion_count=DEFAULT_SUBREGION_COUNT):
    """
    Caculates a number of listen time statistics for the rmd report in the annot_distr repository.
    :param clan_file_text: string with the clan file text
    :param subregion_count: the number of subregions to expect, most have 5 but some have 4. Months 6 and 7 have zero.
    :return:
    """
    # Extract the necessary information from the clan file
    annotation_timestamps = _extract_annotation_timestamps(clan_file_text)
    regions_raw, subregion_ranks_df, listened_but_empty = _extract_region_info(
        clan_file_text, subregion_count=subregion_count)

    # Calculate some of the stats before any region manipulation
    totals_raw = _total_time_and_count_per_region_type(regions_raw)
    per_region_timestamp_counts = _add_per_region_timestamp_count(regions_df=regions_raw,
                                                                  timestamps=annotation_timestamps)

    # Process regions. For months 6 and 7, there are no subregions, so we only need to remove the overlapping parts of
    # the regions.
    if subregion_count > 0:
        regions_processed = _remove_subregions_without_annotations(regions_raw, annotation_timestamps,
                                                                   listened_but_empty)
    else:
        regions_processed = regions_raw.copy()
    regions_processed = _account_for_region_overlaps(regions_processed)

    # Repeat stats calculation on the processed regions
    totals_processed = _total_time_and_count_per_region_type(regions_processed)

    # Total time and count for regions that have been added manually. In case there is a makeup region from 0 to 10
    # and there is a skip inside of it from 2 to 8, we want to count it as 1 region with the listened time of 2 + 2 = 4.
    # Therefore, the adding up is based on processed regions, _total_time_and_count_per_region_type already accounts for
    # the fact that this makeup region will have been split into two (0-2 and 8-10).
    additional_regions = (RegionType.MAKEUP.value, RegionType.EXTRA.value, RegionType.SURPLUS.value)
    stats = {f'num_{region_type}_region': totals_processed.region_count.get(region_type, 0)
             for region_type in additional_regions}
    stats.update({f'{region_type}_time': totals_processed.total_time.get(region_type, 0)
                 for region_type in additional_regions})

    # Same for the subregions. The count field is named differently for historical reasons.
    stats['subregion_time'] = totals_processed.total_time.get(RegionType.SUBREGION.value, 0)
    stats['num_subregion_with_annot'] = totals_processed.region_count.get(RegionType.SUBREGION.value, 0)

    # These stats are relevant for total time calculation for months 6 and 7 which were listened to in full. The
    # overlap is actually no longer relevant because overlaps are now removed during processing.
    stats.update(dict(skip_silence_overlap_hour=0,
                      skip_time=totals_processed.total_time.get(RegionType.SKIP.value, 0),
                      silence_time=totals_processed.total_time.get(RegionType.SILENCE.value, 0),
                      silence_raw_hour=milliseconds_to_hours(totals_raw.total_time.get(RegionType.SILENCE.value, 0))))
    # Note: this can probably be optimized because we already extracted timestamps once - when we looked for annotation
    # timestamps
    last_timestamp_offset = _extract_timestamps(clan_file_text).iloc[-1].offset
    stats['end_time'] = last_timestamp_offset

    # The total listen time calculation depends on whether the full recording was listened to (month 6 and 7, excluding
    # silences and skips) or just the subregions (months 8+, additionally makeup, extra, and surplus regions
    if subregion_count > 0:
        stats['total_listen_time'] = _total_eligible_time(regions=regions_processed)
    else:
        stats['total_listen_time'] = stats['end_time'] - stats['skip_time'] - stats['silence_time']

    # Subregion positions and ranks
    if subregion_count > 0:
        stats['positions'] = subregion_ranks_df.position.to_list()
        stats['ranks'] = subregion_ranks_df.subregion_rank.to_list()
    else:
        stats['positions'], stats['ranks'] = list(), list()

    # Stats before processing
    stats['subregion_raw_hour'] = milliseconds_to_hours(totals_raw.total_time.get(RegionType.SUBREGION.value, 0))
    stats['num_raw_subregion'] = milliseconds_to_hours(totals_raw.total_time.get(RegionType.SUBREGION.value, 0))

    # This is not exactly correct: annotations that share their timestamp are only counted once.
    annotation_counts_raw = (per_region_timestamp_counts
                             [per_region_timestamp_counts.region_type == RegionType.SUBREGION.value]
                             .sort_values(by='position')
                             .annotation_count
                             .astype(int)
                             .to_list())
    stats['annotation_counts_raw'] = annotation_counts_raw

    return stats


def _get_subregion_count(child, month):
    if (child, month) in RECORDINGS_WITH_FOUR_SUBREGIONS:
        return 4
    elif month in (6, 7):
        return 0
    else:
        # It is 5, of course, but it is used so often in this module that hard-coding it was not an option.
        return DEFAULT_SUBREGION_COUNT
