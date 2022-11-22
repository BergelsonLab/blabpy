import os

import numpy as np
import pandas as pd
import pkg_resources

from blabpy.seedlings.listened_time import RegionType, _account_for_region_overlaps

SPECIAL_CASES = ('20_12', '06_07', '22_07')


def recreate_subregions_from_lena5min(lena5min_df):
    """
    Selects five non-overlapping hour-long intervals based on lena5min.csv. More specifically:

    1. Calculates average of ctc and cvc (ctc_cvc_avg) for every 12-interval-long continuous window of the 5-minute-long
       intervals in lena5min.csv.
    2. Selects a window with the highest ctc_cvc_avg.
    3. Select another window with the highest ctc_cvc_avg out of all windows not overlapping with the already selected
       one(s).
    4. Repeat step 3. until five intervals have been selected in total.
    5. Calculate onset/offset in ms of each selected interval by assuming that the intervals in lena5min.csv correspond
       to consecutive five-minute-long intervals of the wav file with the recording. This assumptions is incorrect but
       we'll gloss over that fact for now.

    :param lena5min_df:
    :return: a 5x3 dataframe with the columns "onset", "offset", "rank"
    """
    # .rolling considers windows of preceding rows, we want succeeding rows so that each row correspond to the start of
    # the hour-long interval. To achieve that, we'll  flip the data twice.
    subregion_starts = (
        lena5min_df
        [['ctc', 'cvc']]
        .iloc[::-1]
        .rolling(12).sum()
        .iloc[::-1].mean(axis='columns')
        .to_frame(name='ctc_cvc_avg')
        .reset_index(drop=True))

    top_5 = list()
    subregion_starts['non_overlapping'] = True
    for i in range(5):
        # Row labels and integer indices coincide in subregion_starts but not in its subsets. So, after removing already
        # selected subregions and subregions overlapping with them, we will want to find the label of the row with
        # the highest ctc_cvc_avg, not its integer index. That's what `.idxmax()` does.
        best_start_index = subregion_starts[subregion_starts.non_overlapping].ctc_cvc_avg.idxmax()
        # For short recordings, we might run out of potential subregions before we get five of them
        if pd.isnull(best_start_index):
            break
        top_5.append(best_start_index)

        # Mark rows we can't use anymore
        start, end = best_start_index - 11, best_start_index + 11  # .loc includes end, unlike range, slice, etc.
        subregion_starts.loc[start:end, 'non_overlapping'] = False

    # Assemble selected subregions info: onset, offset, ctc_cvc_avg
    ms_in_5min = 5 * 60 * 1000
    ms_in_1h = 60 * 60 * 1000
    # Again, not all intervals are 5 minutes long, so this is not exactly correct but we'll ignore that fact
    onsets = [best_start_index * ms_in_5min for best_start_index in top_5]
    offsets = [onset + ms_in_1h for onset in onsets]
    ctc_cvc_avg_values = [subregion_starts.at[best_start_index, 'ctc_cvc_avg'] for best_start_index in top_5]
    subregions_df = pd.DataFrame.from_dict(dict(onset=onsets, offset=offsets, ctc_cvc_avg=ctc_cvc_avg_values))

    # Sort, rank
    subregions_df = (subregions_df
                     .sort_values(by='onset')
                     .assign(subregion_rank=lambda df: df.ctc_cvc_avg
                                                         .rank(ascending=False, method='first')
                                                         .astype(int),
                             position=lambda df: np.arange(len(df)) + 1)
                     .reset_index(drop=True))

    return subregions_df


def get_processed_audio_regions(cha_path, lena5min_df=None):
    """
    Extracts and processes regions from the audio annotations in order to output regions suitable for calculating
    listened time and assigning tokens to top3/top4/surplus.

    There is a number of region types in cha files: subregion, makeup, extra, silence, etc. These regions have a
    hierarchy: e.g., time in makeup is considered to be only belonging to this makeu region and not the subregion it
    is in. This is necessary for calculating time that was listened to by annotators. But we will also use it here,
    because we want tokens within skips not to be counted as belonging to the subregion they are in, etc. We refer to
    the regions that have any overlaps removed according to this hierarchy as "processed" regions.

    The code that reads and processes these regions is in blabpy.seedlings.listen_time. It won't work as is for
    assigning tokens to surplus/top3/top4 regions, because it assumes that months 6 and 7 have no subregions. So we
    will have to do some of the processing ourselves.

    Special cases:
    - 20_02: subregion with rank (and coincidentally position) 3 was skip during annotation.
    Effectively it was treated as a subregion with rank 5 while subregions ranked 4 and 5 were treated as subregions
    with ranks 3 and 4. So, we will pretend as if these were the actual ranks.
    - 06_07, 22_07: all subregions minus
    silent part don't add up to four hours. We will manually add "extra" time to them.
    """
    # TODO: Importing is done here to avoid circular imports/name collisions. Restructure regions/listened_time/pipeline
    #  instead
    from blabpy.seedlings.pipeline import preprocess_region_info
    regions_raw, regions_processed, subregion_ranks, listened_but_empty = preprocess_region_info(cha_path)

    # Datatype conversion to avoid integers becoming floats in the presence of NAs
    regions_raw = regions_raw.convert_dtypes()
    regions_processed = regions_processed.convert_dtypes()

    # Extract month from cha_path
    month = cha_path.name.split('_')[1]
    # We will need lena5min_df for and only for months 06 and 07
    assert (month in ('06', '07')) == (lena5min_df is not None)

    # Months 06 and 07 have no subregions, so we will have to create and process them here
    if month in ('06', '07'):
        subregions = (recreate_subregions_from_lena5min(lena5min_df)
                      .drop(columns='ctc_cvc_avg')
                      # rename columns to match the ones in regions_raw
                      .rename(columns={'onset': 'start', 'offset': 'end'})
                      .assign(region_type=RegionType.SUBREGION.value)
                      .convert_dtypes())

        # Skips in months 06 and 07 were listened to and can be ignored
        regions_raw = regions_raw[~regions_raw.region_type.eq(RegionType.SKIP.value)]
        regions_processed = _account_for_region_overlaps(pd.concat([regions_raw, subregions], ignore_index=True))
        # Drop the annotation_count column - we don't have that information in subregions.csv so it is all NAs
        regions_processed.drop(columns='annotation_count', inplace=True)

    elif month in (f'{m:02}' for m in range(8, 17+1)):
        # Columns in subregion_ranks are strings due to Zhenya's negligence. Won't change preprocess_region_info now to
        # avoid breaking things.
        subregion_ranks = subregion_ranks.astype(int).convert_dtypes()
        # Add subregion ranks
        regions_processed = regions_processed.merge(
            subregion_ranks
            .astype(int)
            .assign(region_type=RegionType.SUBREGION.value)
            .convert_dtypes(),
            on=['region_type', 'position'], how='left')
        # Check that regions have ranks iff they are subregions
        assert (regions_processed.subregion_rank.notnull()
                == regions_processed.region_type.eq(RegionType.SUBREGION.value)).all()

    regions_processed = regions_processed.sort_values(by=['start', 'end']).reset_index(drop=True)

    return regions_processed


def _load_data_for_special_cases(subj_month):
    """
    Loads data for special cases: the three audio recordings for which cha/lena5min weren't enough to extract the
    regions data.

    :param subj_month: '20_12', '06_07', '22_07'
    Returns: (regions_processed_original, regions_processed_amended) - pandas DataFrames with the original and amended
    regions data.
    """
    assert subj_month in SPECIAL_CASES
    special_cases_dir = f'data/regions_special-cases/{subj_month}'
    regions_processed_original_path = os.path.join(special_cases_dir, 'regions_processed_original.csv')
    regions_processed_amended_path = os.path.join(special_cases_dir, 'regions_processed_amended.csv')

    def load_csv(relative_path):
        dtypes = {'subj_month': pd.StringDtype(),
                  'start': pd.Int64Dtype(),
                  'end': pd.Int64Dtype(),
                  'subregion_rank': pd.Int64Dtype(),
                  'position': pd.Int64Dtype(),
                  'region_type': pd.StringDtype()}
        stream = pkg_resources.resource_stream(__name__, relative_path)

        df = pd.read_csv(stream, dtype=dtypes, encoding='utf-8')

        assert df.subj_month.eq(subj_month).all()
        return df.drop(columns='subj_month')

    regions_processed_original = load_csv(regions_processed_original_path)
    regions_processed_amended = load_csv(regions_processed_amended_path)

    return regions_processed_original, regions_processed_amended


def _get_amended_regions(subj_month, regions_processed_auto):
    """
    Amends automatically extracted regions for three special cases.
    :param subj_month: '20_12', '06_07', '22_07'
    :param regions_processed_auto: regions_processed dataframe for the corresponding month
    :return: regions_processed dataframe with the special cases substituted
    """
    regions_processed_original, regions_processed_amended = _load_data_for_special_cases(subj_month)

    # Check that the regions_processed_auto dataframe is the same as the original one
    msg = (f'The {subj_month} audio recording is a special case and regions from it have to be substituted for by the '
           f'ones saved for this recording within the `blabpy` package. However, these substitute regions are no '
           'longer valid because the automatically extracted regions have changed. Tell the lab tech to update the '
           'files in seedlings/data/regions_special-cases/{subj_month}/')
    assert regions_processed_auto.equals(regions_processed_original), msg

    return regions_processed_amended


def calculate_total_recorded_time_ms(recordings):
    """
    Calculates total recorded time in milliseconds for a given recording by adding the durations of all the
    sub-recordings.
    :param recordings: pandas DataFrame with the recordings data
    :return: total recorded time in milliseconds
    """
    # TODO: it probably doesn't matter much but maybe we should use recording_start_wav and recording_end_wav (which
    #  does not exist currently) instead of recording_start and recording_end.The reason being that the former have
    #  millisecond precission and the latter - second precision. This tiny differences never matter until they do in
    #  a hard-to-debug way. See the related comment in Its.gather_recordings
    # `.values.sum()` is used instead of `.sum()` because the latter will return 0 if there NaT elements instead of NaT
    return (recordings.end - recordings.start).values.sum() / np.timedelta64(1, 'ms')


def calculate_total_listened_time_ms(processed_regions, month, recordings):
    """
    Calculates total listened time in milliseconds for a given recording by adding the durations of all the regions
    that were listened to. By the time this function is called, the regions data has already been processed and only
    filtering and adding up time is left to be done.
    :param processed_regions: regions processed by get_processed_audio_regions
    :param month: int/str, month of the recording
    :param recordings: sub-recordings info
    :return: int, total listened time in milliseconds
    """
    if int(month) in (6, 7):
        total_recorded_time_ms = calculate_total_recorded_time_ms(recordings)
        total_silence_time_ms = (processed_regions
                                 .loc[lambda df: df.region_type.eq(RegionType.SILENCE.value)]
                                 .assign(duration=lambda df: df.end - df.start)
                                 .duration.sum())
        total_listened_time_ms = total_recorded_time_ms - total_silence_time_ms

    elif int(month) in range(8, 17+1):
        listened_to_regions = (RegionType.SUBREGION.value,
                               RegionType.MAKEUP.value,
                               RegionType.EXTRA.value)
        total_listened_time_ms = (processed_regions
                                  .loc[lambda df: df.region_type.isin(listened_to_regions)]
                                  .assign(duration=lambda df: df.end - df.start)
                                  .duration.sum()
                                  # convert from numpy.int64 to int
                                  .item())

    return total_listened_time_ms
