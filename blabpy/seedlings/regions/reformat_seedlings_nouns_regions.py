"""
Change the format of the regions.csv file from seedlings-nouns to a more readable one.

The initial version of regions.csv in seedlings-nouns looked like this:

| start | end | region_type |
|-------|-----|-------------|
| 0     | 1   | subregion   |
| 1     | 2   | subregion   |
| 2     | 3   | subregion   |
| 3     | 4   | subregion   |
| 0     | 1   | top-3       |
| 1     | 2   | top-3       |
| 2     | 3   | top-3       |
| 0     | 1   | top-4       |
| 1     | 2   | top-4       |
| 2     | 3   | top-4       |
| 3     | 4   | top-4       |

This is very hard to read, e.g., it isn't obvious whether all time intervals repeat or only some of them, whether (3,
4, top-3) is missing on purpose, why the regions don't follow each other, etc. It is especially hard when start and
end aren't single-digits in the toy example above but are instead 8+-digit numbers of milliseconds.

Also, the format implied that there is a (0, 1) subregion region and there is a (0, 1) top-3 region.
And it is so much more natural to say that (0, 1) is a single region that is both a subregion and a top-3 region.

It'd be much nicer to have:

- Time intervals that are sorted chronologically, don't repeat, and don't overlap at all.
- Region types marked by indicator columns, such as `is_subregion`, `is_top3`, etc.

## Pivoting wider

For the rows with the same time intervals but different region types, we can just collapse the rows with identical
time intervals and have a boolean indicator column for each region type present.

| start | end | region_type |
|-------|-----|-------------|
| 0     | 1   | subregion   |
| 1     | 2   | subregion   |
| 0     | 1   | top-3       |

Would become

| start | end | is_subregion | is_top_3 |
|-------|-----|--------------|----------|
| 0     | 1   | True         | True     |
| 1     | 2   | True         | False    |


Following `dplyr`, I'll refer to this operation as  *pivoting wider*.

## Dealing with partial overlaps

Sometimes, two regions don't have the same boundaries, but they do overlap.
In these case, the overlaps would still be there after pivoting:

| start | end | region_type |
|-------|-----|-------------|
| 0     | 1   | top-3       |
| 0     | 2   | top-4       |

would become

| start | end | is_top_3 | is_top_4 |
|-------|-----|----------|----------|
| 0     | 1   | False    | True     |
| 0     | 2   | True     | False    |


In these cases, we'll split regions into smaller regions that do not overlap before the pivoting.
For example, if we have these regions:

| start | end | region_type |
|-------|-----|-------------|
| 0     | 1   | top-3       |
| 0     | 2   | top-4       |

We'd split the second region into two smaller regions:

| start | end | region_type |
|-------|-----|-------------|
| 0     | 1   | top-3       |
| 0     | 1   | top-4       |
| 1     | 2   | top-4       |

And then pivot as normal:

| start | end | is_top_3 | is_top_4 |
|-------|-----|----------|----------|
| 0     | 1   | True     | True     |
| 1     | 2   | True     | False    |


Note: the initial version is a slight modification of the one-time script in "2023-02-03_pivot_regions_wider/"
"""

import pandas as pd


from blabpy.seedlings.listened_time import RegionType
from blabpy.seedlings.regions.top3_top4_surplus import TOP_3_KIND, TOP_4_KIND, _fillna_with_pseudo_inf, \
    _pseudo_inf_to_na
from blabpy.seedlings.paths import split_recording_id


# =============================================================================
# Find partially overlapping regions


def _find_partially_overlapping_regions(regions_df):
    """
    Finds all pairs of regions in the same recording that overlap partially.
    """
    return (
        regions_df
        .loc[:, ['recording_id', 'region_type', 'start', 'end', 'subregion_rank']]
        .assign(region_id=lambda df: df.index)
        # Pair all regions within the same recording with each other
        .pipe(
            lambda df:
            pd.merge(df, df, on='recording_id', how='inner', suffixes=('_x', '_y')))
        # Let's not compare a region with itself
        .loc[lambda df: df.region_id_x != df.region_id_y]
        # We don't care about fully overlapping regions
        .loc[lambda df: ~df.start_x.eq(df.start_y) | ~df.end_x.eq(df.end_y)]
        # Let's consider each pair only once by taking only the pairs "sorted" by duration
        .loc[lambda df: (df.end_x - df.start_x) <= (df.end_y - df.start_y)]
        # Find overlapping
        .loc[lambda df: (df.start_x < df.end_y) & (df.start_y < df.end_x)]
        # Sort columns
        .loc[:, ['recording_id', 'region_type_x', 'region_type_y', 'start_x', 'end_x',
                 'start_y', 'end_y', 'subregion_rank_x', 'subregion_rank_y', 'region_id_x', 'region_id_y']]
     )


# =============================================================================
# Classify all overlaps


def _triage_overlaps(overlaps_df):
    """
    Classifies all overlaps into one of four categories. Every overlap should belong to exactly one category. These
    are the categories present at the time of writing the initial version of this module. The main purpose of this
    function is to check there aren't any new kinds of overlaps.

    1. Subregion ranked 5 overlaps with surplus/top-4 in month 06-07 regions.

       I left rank-5 subregions in month 06-07 regions because they were listened to (except for the silences). But
       then I called everything in the complement of the top-4 regions "surplus". So, the rank-5 subregions became
       part of the surplus, hence the overlap. In cases, where rank-5 subregions were partially used to make up for
       insufficient top-4 time, the rank-5 subregions also overlaps with the top-4 regions. The most reasonable
       solution is to remove the rank-5 subregions from month 06-07 regions.

    2. Top-3 overlaps with subregion ranked 4 in regions from months 06-13 regions.

        Expected. "Makeup" for top-3 is first taken from subregion ranked 4.

    3. Top-3 overlaps with top-4.

       A whole makeup/extra region was used for top-3 but only part of it was necessary for top-4. That is totally ok.
       The top-4 one just will have to be split into the common part and the rest.

       At the same time, most cases like this would disappear if I allowed top-3 to use makeup to get up to 3:15 total
       duration. Currently, I cut the added makeup regions at 3:00. But there are also ~5 (the number is from another
       version of this analysis in the comments at the bottom) cases where extra 15 minutes wouldn't close the gap.

       If we switched to using subregion 4 to make up for top-3 hours (see point 2 above), then we would introduce new
       cases like this.
    """

    overlaps_with_types = (
        overlaps_df
        .copy()
        .assign(
            month=lambda df: df.recording_id.str.split('_').str[-1],
            one_is_rank_5_subregion=lambda df:
                (df.region_type_x == RegionType.SUBREGION.value) & (df.subregion_rank_x == 5)
                | (df.region_type_y == RegionType.SUBREGION.value) & (df.subregion_rank_y == 5),
            one_is_top_4_or_surplus=lambda df:
                (df.region_type_x == TOP_4_KIND) | (df.region_type_x == RegionType.SURPLUS.value)
                | (df.region_type_y == TOP_4_KIND) | (df.region_type_y == RegionType.SURPLUS.value),
            is_subregion_5_thing=lambda df: df.month.isin(['06', '07'])
                                            & df.one_is_rank_5_subregion
                                            & df.one_is_top_4_or_surplus,
            is_top_3_subregion_4=lambda df:
            df.month.astype(int).between(6, 13)
            & df.region_type_x.eq(TOP_3_KIND)
            & df.region_type_y.eq(RegionType.SUBREGION.value) & df.subregion_rank_y.eq(4),
            is_top_3_top_4=lambda df:
                (df.region_type_x == TOP_3_KIND)
                & (df.region_type_y == TOP_4_KIND)
                & (df.start_x == df.start_y)
                & (df.end_y > df.end_x))
        .drop(columns=['month', 'one_is_rank_5_subregion', 'one_is_top_4_or_surplus']))

    # Let's check that there are still only 3 types of overlaps described above.
    assert (overlaps_with_types
            .loc[:, ['is_subregion_5_thing', 'is_top_3_subregion_4', 'is_top_3_top_4']]
            # each row should belong to exactly one type
            .sum(axis='columns').eq(1).all())

    return overlaps_with_types


# ==================================================================================================
# Split overlapping regions

def _get_split_points(interval_to_split, other_interval):
    """
    Find point where an interval needs to be split into sub-intervals that either don't overlap with the other inteval
    or are fully contained in it.
    :param interval_to_split: (start, end) tuple
    :param other_interval: same
    :return: list of points to split at
    """
    (x, y) = interval_to_split
    # interval_to_split will have to be split at each boundary of other_interval that is inside (x, y)
    split_points = [boundary for boundary in other_interval if x < boundary < y]
    return split_points


def _split_an_interval(interval, split_points):
    """
    Splits an interval into sub-intervals at split points.
    :param interval: (start, end) tuple
    :param split_points: an iterable of points to split at
    :return: list of (start, end) tuples
    """
    (x, y) = interval
    if not split_points:
        return [interval]
    else:
        # Check that split points are all inside the interval
        assert all(map(lambda p: x < p < y, split_points))
        all_points = [x] + sorted(split_points) + [y]
        return list(zip(all_points[:-1], all_points[1:]))


def _split_overlapping_regions(regions_df):
    """
    Splits each region that overlaps with another region to remove partial overlaps.
    :param regions_df: seedlings-nouns regions dataframe
    :return:
    """
    overlaps = (regions_df
                .pipe(_find_partially_overlapping_regions)
                .pipe(_triage_overlaps)
                .assign(
                    split_points_x=lambda df: df.apply(lambda row: _get_split_points(
                        (row.start_x, row.end_x), (row.start_y, row.end_y)), axis='columns'),
                    split_points_y=lambda df: df.apply(lambda row: _get_split_points(
                        (row.start_y, row.end_y), (row.start_x, row.end_x)), axis='columns')))

    if overlaps.empty:
        return regions_df

    # Split pairs into separate rows and combine split points that belong to the same region
    split_points_df = (
        pd.concat([
            # TODO (cleaner code): use melt, wide_to_long, something like that
            overlaps
            .loc[:, ['recording_id', 'start_x', 'end_x', 'split_points_x']]
            .rename(columns=lambda name: name.rstrip('_x')),
            overlaps
            .loc[:, ['recording_id', 'start_y', 'end_y', 'split_points_y']]
            .rename(columns=lambda name: name.rstrip('_y'))
        ])
        .loc[lambda df: df.split_points.str.len() > 0]
        .groupby(['recording_id', 'start', 'end'], as_index=False)
        .agg({'split_points': lambda point_lists: set().union(*point_lists)})
    )

    # Split regions that need splitting
    regions_split = (
        regions_df
        .merge(split_points_df, on=['recording_id', 'start', 'end'], how='left')
        .assign(
            split_points=lambda df: df.split_points.where(df.split_points.notnull(), set()),
            sub_intervals=lambda df:
                df.apply(
                    lambda row: _split_an_interval((row.start, row.end), row.split_points),
                    axis='columns'))
        .explode('sub_intervals', ignore_index=True)
        .assign(start=lambda df: df.sub_intervals.str[0],
                end=lambda df: df.sub_intervals.str[1])
        .sort_values(by=['recording_id', 'start'])
    )

    assert (regions_split
            .drop_duplicates(subset=['recording_id', 'start', 'end'])
            .assign(
                all_good=lambda df:
                    (df.start >= df.end.shift(1))
                    | (df.recording_id != df.recording_id.shift(1)))
            .pipe(lambda df: df.all_good.all()))

    # Clean up and return
    return (regions_split
            .loc[:, regions_df.columns]
            .astype(regions_df.dtypes))


def _pivot_regions_wider(regions_df):
    """
    Instead of having a region_type column and time intervals present for multiple region types, we pivot the table
    wider: fewer rows, unique time intervals, extra "is_*" indicator column for each region type.
    Different from reformat_seedling_nouns_regions in that it ignores overlaps.
    :param regions_df: The seedlings-nouns regions table.
    :return: The pivoted table.
    """
    # TODO: Instead of unstacking, create flag columns before pivoting then merge over recording_id, start, and end.
    #  Here is a start:
    #  (pd
    #   .get_dummies(regions, columns=['region_type'], prefix='is')
    #   .groupby(['recording_id', 'start', 'end'])
    #   .aggregate(lambda df: df.aggregate(
    #          {col: 'any' if col.startswith('is_') else ['min', 'max'] for col in df.columns.values}))
    #   )

    # These columns have different values for different region types of the same time interval (subregions
    # have them filled, other types don't). That makes it harder to merge rows with the same time intervals. We'll set
    # them aside and merge them back in later.
    subregion_specific_columns = ['subregion_rank', 'position']

    return (regions_df
            .drop(columns=subregion_specific_columns)
            # Make an index of all the columns except the ones that we just dropped
            .pipe(lambda df: df.set_index(df.columns.tolist()))
            # We need a value column to unstack. After the unstacking, it should tell us whether the combination of
            # a given time interval and region type is present in the original data. So we set the new column to
            # `True` for all rows (each row is a combination that is present in the original data).
            .assign(is_that_region=True)
            # pivot_table is more concise but does implicit aggregating and I don't want to lose any values.
            .unstack(level='region_type', fill_value=False)
            # unstack() adds a level to column names: ('is_that_region', 'top_3'), ('is_that_region', 'top_4'), the
            # first level is called None, the second - "region_type". We don't need the first level, and we don't need
            # them to have names either.
            .droplevel(None, axis='columns')
            .rename_axis(None, axis='columns')
            .rename(columns=lambda x: f'is_{x}')
            # Add back subregion positions and ranks.
            # TODO: That's overly complicated, just put the subregions into a separate dataframe before unstacking.
            .pipe(
                lambda df:
                df.reset_index()
                  .merge(regions_df
                         .loc[lambda df_: df_.region_type.eq(RegionType.SUBREGION.value)]
                         .drop(columns='region_type'),
                         on=df.index.names,
                         how='left'))
            .sort_values(['recording_id', 'start', 'end'])
            )


def _postprocess_pivoted(regions_df_wide):
    """
    Converts dtypes to nullable, sets is_top_4 to NA for months 14-17
    :param regions_df_wide: The pivoted regions table.
    :return: The postprocessed table.
    """
    # Convert is_* columns to pandas data types
    for column_name in regions_df_wide.columns:
        if column_name.startswith('is_'):
            regions_df_wide[column_name] = regions_df_wide[column_name].convert_dtypes()

    # Change is_top_4 to NA for months 14-17
    regions_df_wide = regions_df_wide.assign(
            month=lambda df:
            df.recording_id.apply(lambda recording_id: int(split_recording_id(recording_id)[2])))
    # Check that there are no top_4 regions in months 14-17 - that would mean there was a bug somewhere
    assert not regions_df_wide.is_top_4.where(regions_df_wide.month.between(14, 17), False).any()
    regions_df_wide['is_top_4'] = regions_df_wide.is_top_4.where(~regions_df_wide.month.between(14, 17), None)
    return regions_df_wide.drop(columns='month')


def reformat_seedlings_nouns_regions(regions_df):
    """
    Merges all time intervals that belong to multiple region types into a single row with an "is_*" indicator column
    for each region type. The time intervals in the output do not overlap and follow one another in time within each
    recording.
    :param regions_df: The seedlings-nouns regions table.
    :return: The pivoted table.
    """
    regions_df = regions_df.copy().assign(end=lambda df: _fillna_with_pseudo_inf(df.end))

    regions_df = (
        regions_df
        .pipe(_split_overlapping_regions)
        .pipe(_pivot_regions_wider)
        .pipe(_postprocess_pivoted))

    regions_df = regions_df.assign(end=lambda df: _pseudo_inf_to_na(df.end))

    # Check that regions within a recording follow each other in time and don't overlap
    assert (regions_df
            .assign(
                all_good=lambda df:
                    (df.start >= df.end.shift(1))
                    | (df.recording_id != df.recording_id.shift(1)))
            .all_good.all())

    return regions_df
