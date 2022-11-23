import numpy as np
import pandas as pd


def make_codebook_template(df):
    columns = df.columns

    def data_type_to_string(dtype):
        if isinstance(dtype, pd.Int64Dtype):
            return 'integer'
        elif isinstance(dtype, pd.BooleanDtype):
            return 'boolean'
        elif isinstance(dtype, pd.CategoricalDtype):
            return 'categorical'
        elif isinstance(dtype, pd.StringDtype):
            return 'string'
        elif dtype == np.dtype('datetime64[ns]'):
            return 'datetime'
        else:
            raise ValueError(f'unknown datatype {dtype}')

    data_types = list(map(data_type_to_string, df.dtypes))

    def get_values(column, data_type):
        if data_type in ('categorical', 'boolean'):
            column_values = (df[column].sort_values().unique().astype(str).tolist())
            return ', '.join(column_values)
        elif data_type in ('integer', 'datetime'):
            return f'{df[column].min()}...{df[column].max()}'
        elif data_type == 'string':
            return f'{len(df[column].unique())} unique values'
        else:
            raise ValueError(f'unexpected datatype {data_type}')

    values = list(map(get_values, columns, data_types))
    codebook_template = pd.DataFrame(dict(column=columns, data_type=data_types, values=values, description=''))
    return codebook_template
