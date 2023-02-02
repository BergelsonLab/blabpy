"""
This module provides constants and functions for reading both specific files (e.g., seedlings_nouns.csv and files in
 general. For the specific files, there are constants containing dictionaries with the data types of the columns. The
 order of the keys is also used to set the order of the columns when creating these files.
"""

import warnings

import pandas as pd

from blabpy.seedlings import UTTERANCE_TYPE_CODES, OBJECT_PRESENT_CODES, SPEAKER_CODES, CHILDREN_STR, MONTHS_STR, \
    TIERS, MODALITIES
from blabpy.seedlings.paths import get_video_recordings_csv_path

# "audio" and "video" are not capitalized in all_basiclevel and further dataframes.
DATETIME_DTYPE_PLACEHOLDER = 'datetime64[ns]'
AUDIO_VIDEO = tuple(map(lambda s: s.lower(), MODALITIES))

ALL_BASICLEVEL_DTYPES = {
    'ordinal':              pd.Int64Dtype(),
    'onset':                pd.Int64Dtype(),
    'offset':               pd.Int64Dtype(),
    'object':               pd.StringDtype(),
    'utterance_type':       pd.CategoricalDtype(categories=UTTERANCE_TYPE_CODES),
    'object_present':       pd.CategoricalDtype(categories=OBJECT_PRESENT_CODES),
    'speaker':              pd.CategoricalDtype(categories=SPEAKER_CODES),
    'basic_level':          pd.StringDtype(),
    'annotid':              pd.StringDtype(),
    'id':                   pd.StringDtype(),
    'subj':                 pd.CategoricalDtype(categories=CHILDREN_STR),
    'month':                pd.CategoricalDtype(categories=MONTHS_STR),
    'SubjectNumber':        pd.StringDtype(),
    'audio_video':          pd.CategoricalDtype(categories=AUDIO_VIDEO),
    'tier':                 pd.CategoricalDtype(categories=TIERS),
    'pho':                  pd.StringDtype()
}

GLOBAL_BASICLEVEL_DTYPES = ALL_BASICLEVEL_DTYPES.copy()
GLOBAL_BASICLEVEL_DTYPES.update(global_bl=pd.StringDtype())

# Columns that are already in GLOBAL_BASICLEVEL_DTYPES are set to None and then will be updated all at once. Columns
# that changed their names reference GLOBAL_BASICLEVEL_DTYPES directly in the definition.
SEEDLINGS_NOUNS_DTYPES = {
    'recording_id': pd.StringDtype(),
    'audio_video': None,
    'subject_month': pd.StringDtype(),
    'child': GLOBAL_BASICLEVEL_DTYPES['subj'],
    'month': None,
    'onset': None,
    'offset': None,
    'annotid': None,
    'ordinal': None,
    'speaker': None,
    'object': None,
    'basic_level': None,
    'global_basic_level': GLOBAL_BASICLEVEL_DTYPES['global_bl'],
    'transcription': GLOBAL_BASICLEVEL_DTYPES['pho'],
    'utterance_type': None,
    'object_present': None,
    'is_top_3_hours': pd.BooleanDtype(),
    'is_top_4_hours': pd.BooleanDtype(),
    'is_surplus': pd.BooleanDtype()}
for column, dtype in SEEDLINGS_NOUNS_DTYPES.items():
    if dtype is None:
        SEEDLINGS_NOUNS_DTYPES[column] = GLOBAL_BASICLEVEL_DTYPES[column]


SEEDLINGS_NOUNS_REGION_TYPES = ['subregion', 'top_3', 'top_4', 'surplus']
SEEDLINGS_NOUNS_REGIONS_DTYPES = {
    'recording_id': SEEDLINGS_NOUNS_DTYPES['recording_id'],
    'region_type': pd.CategoricalDtype(categories=SEEDLINGS_NOUNS_REGION_TYPES),
    'start': pd.Int64Dtype(),
    'end': pd.Int64Dtype(),
    'position': pd.Int64Dtype(),
    'subregion_rank': pd.Int64Dtype()}

SEEDLINGS_NOUNS_SUB_RECORDINGS_DTYPES = {
    'recording_id': SEEDLINGS_NOUNS_DTYPES['recording_id'],
    'start': DATETIME_DTYPE_PLACEHOLDER,
    'end': DATETIME_DTYPE_PLACEHOLDER,
    'start_position_ms': pd.Int64Dtype()}

SEEDLINGS_NOUNS_RECORDINGS_DTYPES = {
    'recording_id': SEEDLINGS_NOUNS_DTYPES['recording_id'],
    'total_recorded_time': pd.Int64Dtype(),
    'total_listened_time': pd.Int64Dtype()}


SEEDLINGS_NOUNS_CODEBOOK_CORE_DTYPES = {
    'column': pd.StringDtype(),
    'data_type': pd.StringDtype(),
    'values': pd.StringDtype(),
    'description': pd.StringDtype()}


SEEDLINGS_NOUNS_SORT_BY = {
    'seedlings-nouns.csv': ['audio_video', 'child', 'month', 'onset'],
    'regions.csv': ['recording_id', 'region_type', 'start', 'end'],
    'sub-recordings.csv': ['recording_id', 'start', 'end'],
    'recordings.csv': ['recording_id']}


def _convert_subject_child_month(df):
    """subject/child, month should always be read as categorical variables with string values"""
    for column in ('subject', 'child', 'month'):
        if column in df.columns:
            # Convert to formatted string values
            df[column] = (df[column].astype(int).apply(lambda subj: f'{subj:02d}'))
            # Convert to categorical
            if column in ('subject', 'child'):
                df[column] = df[column].astype(pd.CategoricalDtype(categories=CHILDREN_STR))
            elif column == 'month':
                df[column] = df[column].astype(pd.CategoricalDtype(categories=MONTHS_STR))

    return df


def blab_read_csv(path, **kwargs):
    # Pandas doesn't allow for a custom dtype for datetime columns, the columns have to be passed to read_csv as
    # parse_dates.
    dtypes = kwargs.get('dtype', {})
    date_columns = [column
                    for column in dtypes
                    if dtypes[column] == DATETIME_DTYPE_PLACEHOLDER]
    for column in date_columns:
        del dtypes[column]
    if date_columns:
        assert 'parse_dates' not in kwargs, 'Can\'t have datetime columns in dtype and parse_dates at the same time'
        kwargs['parse_dates'] = date_columns

    df = pd.read_csv(path, **kwargs).convert_dtypes()

    # Nudge towards specifying all columns
    unspecified_columns = set(df.columns) - set(dtypes.keys()) - set(date_columns)
    if unspecified_columns:
        warnings.warn(f'Data types of column(s) {", ".join(unspecified_columns)} were not specified.')

    # Formats subject/child/month and converts to categorical
    df = _convert_subject_child_month(df)

    return df


def blab_write_csv(dataframe, path, **kwargs):
    kwargs['index'] = kwargs.get('index', False)
    dataframe.to_csv(path, **kwargs)


def read_all_basic_level(path):
    return blab_read_csv(path, dtype=ALL_BASICLEVEL_DTYPES)


def read_global_basic_level(path):
    return blab_read_csv(path, dtype=GLOBAL_BASICLEVEL_DTYPES)


def read_seedlings_nouns(path):
    return blab_read_csv(path, dtype=SEEDLINGS_NOUNS_DTYPES)


def read_seedlings_nouns_regions(path):
    return blab_read_csv(path, dtype=SEEDLINGS_NOUNS_REGIONS_DTYPES)


def read_seedlings_nouns_sub_recordings(path):
    return blab_read_csv(path, dtype=SEEDLINGS_NOUNS_SUB_RECORDINGS_DTYPES)


def read_seedlings_nouns_recordings(path):
    return blab_read_csv(path, dtype=SEEDLINGS_NOUNS_RECORDINGS_DTYPES)


def read_seedlings_nouns_guess(path):
    reading_functions = {'seedlings-nouns.csv': read_seedlings_nouns,
                         'regions.csv': read_seedlings_nouns_regions,
                         'sub-recordings.csv': read_seedlings_nouns_sub_recordings,
                         'recordings.csv': read_seedlings_nouns_recordings}
    return reading_functions[path.name](path)


def read_seedlings_codebook(path):
    """
    Codebooks can have arbitrary extra columns, so we can't specify all the dtypes without reading the file first.
    """
    columns = pd.read_csv(path, nrows=0).columns
    dtypes = SEEDLINGS_NOUNS_CODEBOOK_CORE_DTYPES.copy()
    for column in columns:
        if column not in dtypes:
            dtypes[column] = pd.StringDtype()
    return blab_read_csv(path, dtype=dtypes)


def read_video_recordings_csv(path=None):
    if path is None:
        path = get_video_recordings_csv_path()
    video_recordings_dtypes = dict(subject_month=pd.StringDtype(),
                                   start=DATETIME_DTYPE_PLACEHOLDER,
                                   end=DATETIME_DTYPE_PLACEHOLDER,
                                   duration=pd.StringDtype())
    df = blab_read_csv(path, dtype=video_recordings_dtypes)
    df['duration'] = pd.to_timedelta(df['duration'])

    return df


def _timedelta_to_hhmmss(timedeltas: pd.Series) -> pd.Series:
    """Convert a timedelta to a string in the format HH:MM:SS"""

    total_seconds = timedeltas.dt.total_seconds().round().astype(int)
    components = pd.DataFrame.from_dict(dict(
            hours=total_seconds // 3600,
            minutes=(total_seconds % 3600) // 60,
            seconds=total_seconds % 60))

    return (components
            .apply(lambda x: x.astype(str).str.zfill(2), axis='rows')
            .pipe(lambda x: x.hours + ':' + x.minutes + ':' + x.seconds))


def write_video_recordings_csv(df, path=None):
    """Writing companion for read_video_recordings_csv"""
    if df.duration.dtype == 'timedelta64[ns]':
        df = df.copy().assign(duration=_timedelta_to_hhmmss(df.duration))
    blab_write_csv(df, path, index=False)
