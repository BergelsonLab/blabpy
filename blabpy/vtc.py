"""
Functions to work with the VTC output files.
These files have an ".rttm" extension, they are space-separated text fiels without column names.

VTC - Voice Type Classifier - a set of of voice classification models and the code to apply them.
See https://github.com/MarvinLvn/voice-type-classifier for details.
See GitBook for instructions on how to run VTC on the Duke cluster.
"""

from pathlib import Path

import pandas as pd


RTTM_COLUMNS = ['SPEAKER', 'filename', 'column3',
                'onset', 'duration', 'column6', 'column7',
                'voice_type', 'column9', 'column10']


def read_rttm(path: Path):
    """
    Reads an rttm file output by VTC
    :param path: path to the rttm file
    :return: a pandas dataframe object
    """
    return pd.read_csv(path, delimiter=' ', names=RTTM_COLUMNS, dtype=str, na_filter=False)


def _write_rttm(df: pd.DataFrame, output_path: Path):
    """
    Writes rttm dataframe to a file
    :param df: a pandas dataframe
    :param output_path: output path
    :return: None
    """
    assert df.columns.tolist() == RTTM_COLUMNS
    output_path.parent.mkdir(exist_ok=True, parents=True)
    df.to_csv(output_path, sep=' ', index=False, columns=RTTM_COLUMNS, header=False)


def split_rttm(rttm_path: Path, output_dir: Path):
    """
    Splits VTC's rttm output file into separate files corresponding to the individual input files.

    When VTC is run on a folder with wav files, it will create a single output file with the filename column which is
    not always convenient.

    If some of the files already exist and their contents are different, an error will be raised and nothing will be
    done with any of the files.
    :param rttm_path: path to the common rttm file
    :param output_dir: separate files will be output into output_dir/<filename>/<input file name>
    :return: None

    Sample code:
    from pathlib import Path
    from blabpy.vtc import split_rttm
    split_rttm(Path('all.rttm'), Path('separated'))
    """
    rttm_grouped = read_rttm(rttm_path).groupby('filename')

    def _output_path(filename_):
        return output_dir / filename_ / rttm_path.name

    # Check that the output files either do not exist or contain the same information
    for filename, sub_df in rttm_grouped:
        output_path = _output_path(filename)
        if output_path.exists():
            assert read_rttm(output_path).equals(sub_df.reset_index(drop=True)), (
                f'The following file already exists and contains different information from the input file:'
                f'{output_path}')

    # Write the individual files
    for filename, sub_df in rttm_grouped:
        output_path = _output_path(filename)
        if not output_path.exists():
            _write_rttm(sub_df, _output_path(filename))
