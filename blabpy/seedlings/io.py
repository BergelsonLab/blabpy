import warnings

import pandas as pd

from blabpy.seedlings import UTTERANCE_TYPE_CODES, OBJECT_PRESENT_CODES, SPEAKER_CODES, CHILDREN_STR, MONTHS_STR, \
    TIERS, MODALITIES

# "audio" and "video" are not capitalized in all_basiclevel and further dataframes.
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
    df = pd.read_csv(path, **kwargs).convert_dtypes()
    try:
        dtypes = kwargs['dtype']
        unspecified_columns = set(df.columns) - set(dtypes.keys())
        if unspecified_columns:
            warnings.warn(f'Data types of column(s) {unspecified_columns} were not specified.')
    except KeyError:
        warnings.warn('No data types specified. This can lead to unexpected results.')

    df = _convert_subject_child_month(df)

    return df


def blab_write_csv(dataframe, path, **kwargs):
    kwargs['index'] = kwargs.get('index', False)
    dataframe.to_csv(path, **kwargs)


def read_all_basic_level(path):
    return blab_read_csv(path, dtype=ALL_BASICLEVEL_DTYPES)


def read_global_basic_level(path):
    return blab_read_csv(path, dtype=GLOBAL_BASICLEVEL_DTYPES)
