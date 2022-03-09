from csv import QUOTE_NONNUMERIC

import pandas as pd
import numpy as np

from . import VALID_UTTERANCE_TYPE_CODES, VALID_OBJECT_PRESENT_CODES
from .paths import _check_modality, get_all_basic_level_paths, VIDEO, AUDIO


# Maps columns names in basic level files to standardized names.
COLUMN_NAME_MAPPER = {
    # For video, simply remove 'labeled_object.' and change 'id' to 'annotid'
    VIDEO: lambda column_name: (column_name.replace('labeled_object.', '')
                                if column_name != 'labeled_object.id' else 'annotid'),
    # For audio, rename 'word' to 'object'
    AUDIO: lambda column_name: 'object' if column_name == 'word' else column_name
}

COLUMNS_BY_MODALITY = {
    AUDIO: ["tier", "object", "utterance_type", "object_present",
            "speaker", "timestamp", "basic_level", "annotid", 'pho'],
    VIDEO: ["ordinal", "onset", "offset",
            "object", "utterance_type", "object_present",
            "speaker", "basic_level", "annotid", 'pho'],
    'combined': ['ordinal',
                 'onset',
                 'offset',
                 'object',
                 'utterance_type',
                 'object_present',
                 'speaker',
                 'basic_level',
                 'annotid',
                 'id',
                 'subj',
                 'month',
                 'SubjectNumber',
                 'audio_video',
                 'tier',
                 'pho']
}


def load_and_normalize_column_names(basic_level_path, modality):
    """
    Loads individual basic level file and normalizes its column names. For audio, additionally splits timestamp column
    into onset and offset columns.
    :param basic_level_path: path to a basic level file
    :param modality: Audio/Video
    :return:
    """
    _check_modality(modality)
    df = (pd
          .read_csv(basic_level_path)
          .rename(columns=COLUMN_NAME_MAPPER[modality])
          [COLUMNS_BY_MODALITY[modality]]
          .assign(id=basic_level_path.name))

    # Each modality requires a bit of additional manipulation
    if modality == AUDIO:
        # split timestamp (single string separated by "_", e.g. 4567_4589) into onset and offset (4567, 4589)
        df[['onset', 'offset']] = df.timestamp.str.split('_', expand=True).astype(int)
        df.drop(columns='timestamp', inplace=True)

    if modality == VIDEO:
        # set "ordinal" to a type that support missing integer values (by default, pandas can't handle int and NAs in
        # one coumn
        df['ordinal'] = df.ordinal.astype(pd.Int64Dtype())

    # Some basic level data have trailing whitespace which additionally results in "NA " not being recognized as nan
    df['basic_level'] = df.basic_level.str.strip().replace('NA', np.nan)

    return df


def gather_basic_level_annotations(modality):
    """
    Combines all individual child-month basic level files (i.e.,
     <Modality>_Analysis/<child>_<month>_<modality>_sparse_code.csv) into a single dataframe.
    That is, it output half of all_basiclevel.csv.
    :param modality: Audio/Video
    :return: a pandas DataFrame
    """
    _check_modality(modality)
    basic_level_paths = get_all_basic_level_paths(modality=modality)
    return pd.concat([load_and_normalize_column_names(basic_level_path, modality=modality)
                      for basic_level_path in basic_level_paths])


def _combine_basic_level_annotations(all_audio_df, all_video_df):
    # Concatenate
    all_df = pd.concat(objs=[all_video_df, all_audio_df],
                       keys=['video', 'audio'],
                       names=['audio_video', 'index']
                       ).reset_index(0)

    # Add extra columns
    all_df[['subj', 'month']] = all_df.id.str.split('_', expand=True)[[0, 1]]
    all_df['SubjectNumber'] = all_df.subj + '_' + all_df.month

    # Enforce column order
    all_df = all_df[COLUMNS_BY_MODALITY['combined']]

    return all_df


def gather_all_basic_level_annotations(keep_comments=False, keep_basic_level_na=False):
    """

    :param keep_comments: whether to keep the comments
    :param keep_basic_level_na: whether to keep rows where basic level was manually set to NA by an annotator, must be
    True if keep
    :return:
    """
    # Keep behavior consistent with the previous R code
    if keep_comments and not keep_basic_level_na:
        raise ValueError('When keeping comments, keep empty basic level as well')

    all_audio_df = gather_basic_level_annotations(modality=AUDIO)
    all_video_df = gather_basic_level_annotations(modality=VIDEO)
    all_df = _combine_basic_level_annotations(all_audio_df=all_audio_df, all_video_df=all_video_df)

    # Remove comments
    if not keep_comments:
        all_df = all_df[~all_df.object.str.startswith('%com:')]

    # Remove rows without the basic level information
    if not keep_basic_level_na:
        all_df = all_df[~all_df.basic_level.isna()]

    # Sort by modality, month and subject for consistency with the older R code.
    # And then by ordinal (relevent for opfs only), onset, offset, and annotid for semi-consistency between versions
    all_df = all_df.sort_values(by=['audio_video', 'month', 'subj', 'ordinal', 'onset', 'offset', 'annotid'],
                                ascending=[False, True, True, True, True, True, True])

    # Convert a subset of the columns to factors (categorical in the pandas's terms)
    factor_columns = ['object', 'utterance_type',
                      'object_present', 'speaker', 'basic_level', 'id', 'subj',
                      'month', 'SubjectNumber', 'audio_video', 'tier']
    all_df[factor_columns] = all_df[factor_columns].astype('category')

    all_df.reset_index(drop=True, inplace=True)

    return all_df


def check_for_errors(all_basic_level_df: pd.DataFrame):
    """
    Checks the all_basic_level dataframe for:
    1. Duplicate annotation ids.
    2. Invalid "object present".
    3. Invalid utterance type.
    :param all_basic_level_df:
    :return: None if there were no errors. Otherwise, return a subset of all_basic_level_df with additional "error_type"
    column. The subset contains all the rows with errors.
    """
    df = all_basic_level_df

    # Find duplicate annotation ids
    # keep=False - mark all duplicates as such
    duplicates = df[df.duplicated(subset=['annotid'], keep=False)]

    # Invalid codes
    invalid_utterance_type = df[~df.utterance_type.isin(VALID_UTTERANCE_TYPE_CODES)]
    invalid_object_present = df[~df.object_present.isin(VALID_OBJECT_PRESENT_CODES)]

    all_errors = pd.concat(
        objs=[duplicates, invalid_utterance_type, invalid_object_present],
        keys=['duplicate annotation id', 'invalid utterance type code', 'invalid object present code'],
        names=['error_type', 'index']).reset_index(0)

    if len(all_errors.index) > 0:
        return all_errors
    else:
        return None


def write_all_basic_level_to_csv(all_basic_level_df, csv_path):
    """
    Write the output of gather_all_basic_level_annotations to a csv file in a way consistent with the older R code.
    The result is still not fully consistent but it is close enough.
    (readr::write_csv writes number 10000 as 1e+5 which was too silly to emulate)
    :param all_basic_level_df: a pandas DataFrame
    :param csv_path: a path to the csv or None if you want to return the string that would have been written
    :return:
    """
    # For consistency with readr::write_csv that quotes strings but does not quote NAs, we'll have to use the following
    # trick from https://www.reddit.com/r/Python/comments/mu65ms/quoting_of_npnan_with_csvquote_nonnumeric_in/
    # This way, NAs will be considered numeric and won't be quoted.
    na = type("NaN", (float,), dict(__str__=lambda _: "NA"))()
    return all_basic_level_df.to_csv(csv_path, index=False, quoting=QUOTE_NONNUMERIC, na_rep=na)


def write_all_basic_level_to_feather(all_basic_level_df, feather_path):
    """
    Write the output of gather_all_basic_level_annotations to a feather file.
    :param all_basic_level_df: a pandas DataFrame
    :return:
    """
    all_basic_level_df.to_feather(feather_path)
