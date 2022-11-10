import numpy as np
import pandas as pd


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
