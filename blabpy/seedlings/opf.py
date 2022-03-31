import csv
import re
import os
from zipfile import ZipFile, ZIP_DEFLATED
import tempfile
from pathlib import Path

import pandas as pd


# This is not exactly correct. datavyu uses milliseconds and this uses microseconds adding three extra zeros
DATETIME_FORMAT = '%H:%M:%S:%f'


class OPFFile(object):
    SKIP_PREFIXES = ('.DS_Store', '__MACOSX/')

    def __init__(self, path):
        self.path: Path = path
        self.loaded = False
        self.db = None
        self.other_components = None
        self.name_list = None
        self.load()

    def load(self):
        if self.path.is_dir():
            # List all the files skipping macos-specific hidden files
            name_list = [path.name for path in self.path.iterdir()
                         if not any(path.name.startswith(prefix) for prefix in self.SKIP_PREFIXES)]

            # Load the annotations
            assert 'db' in name_list, f'The folder at {self.path} does not contain a "db" file. Not an OPF folder?'
            db = self.path.joinpath('db').read_text(encoding='utf-8')

            # Other files
            other_components = {
                name: self.path.joinpath(name).read_bytes()  # for parity with the archived version (see below)
                for name in name_list
                if name != 'db'
            }

        elif self.path.suffix == '.opf':
            with ZipFile(self.path, 'r') as opf_zipped:
                # List all the files skipping macos-specific hidden files
                name_list = [fn for fn in opf_zipped.namelist()
                             if not any(fn.startswith(prefix) for prefix in self.SKIP_PREFIXES)]
                assert 'db' in name_list, f'The file at {self.path} does not contain "db". Not an OPF file?'

                # Load the annotations
                with opf_zipped.open('db', 'r') as db_zipped:
                    # ZipFile.open reads files in the binary mode
                    db = db_zipped.read().decode('utf-8')

                # Other files
                other_components = {
                    name: opf_zipped.open(name, 'r').read()
                    for name in name_list
                    if name != 'db'}

        else:
            raise ValueError('Can read OPF annotation from .opf files or unzipped folders, the input path is neither:'
                             + str(self.path))

        self.db = db
        self.name_list = name_list
        self.other_components = other_components
        self.loaded = True

    def read_in_editor(self):
        zf = ZipFile(self.path)
        tempdir = tempfile.mkdtemp()
        zf.extractall(tempdir)
        db_path = os.path.join(tempdir, 'db')
        os.system(f'open {db_path}')

    def write(self, path: Path = None, overwrite_original=False, unzipped=False):
        if not path and not overwrite_original:
            raise ValueError('You haven\'t specified the path to write the files. If you want to overwrite the original'
                             ' file, set overwrite_original to True')

        if path and overwrite_original:
            raise ValueError('You\'ve specified the path and set overwrite_original to True - you can only do one of '
                             'those')

        path = path or self.path

        if unzipped:
            if path.exists() and not path.is_dir():
                raise ValueError('Unzipped is set to True but supplied path is not a directory.')
            else:
                path.mkdir(parents=True, exist_ok=True)
                self._write_to_dir(folder_path=path)
        else:
            if not path.name.endswith('.opf'):
                raise ValueError('Supplied path does not end with .opf as expected')
            else:
                self._write_to_opf(path)

    def _write_to_dir(self, folder_path):
        for filename in self.name_list:
            filepath = folder_path / filename
            if filename == 'db':
                with filepath.open('w') as f:
                    f.write(''.join(self.db))
            else:
                with filepath.open('wb') as f:
                    f.write(self.other_components[filename])

    def _write_to_opf(self, path):
        with ZipFile(path, mode='w', compression=ZIP_DEFLATED) as opf_zipped:
            for filename in self.name_list:
                if filename == 'db':
                    opf_zipped.writestr('db', self.db)
                else:
                    opf_zipped.writestr(filename, self.other_components[filename])

    def update_annotations(self, opf_df: 'OPFDataFrame'):
        """
        Updates the annotations based on an OPFDataFrame object with updated data.
        Preserves presence/absence of newline at the end of file to avoid annoying diffs.
        :param opf_df:
        :return:
        """
        newline_at_end_of_file = self.db.endswith('\n')
        self.db = str(opf_df)
        if newline_at_end_of_file:
            self.db = self.db.rstrip('\n') + '\n'


class OPFDataFrame(object):
    def __init__(self, opf_file: OPFFile):
        self.opf_file = opf_file
        self.prefix = None
        self.column_definitions = None
        self.df = self._opf_to_pandas_df()
        # assert self._can_be_reversed()

    def _opf_to_pandas_df(self):
        db_lines = self.opf_file.db.splitlines()
        # Sometimes the last line is empty - delete it
        if not db_lines[-1]:
            del db_lines[-1]
        self.prefix = db_lines[0]
        self.column_definitions = db_lines[1]

        # Extract field names
        # There is a single datavyu column "labeled_object" defined in the second line of "db".
        # The format of this line is <column-definition>-<field_definitions>
        field_definitions = self.column_definitions.split('-')[1]
        # Field definitions are comma-separated, each definition has the following format: <field_name>|<field_type>
        field_names = [field_definition.split('|')[0] for field_definition in field_definitions.split(',')]
        # The first two columns contain timestamps
        field_names = ['time_start', 'time_end'] + field_names

        # Extract values
        # Each data row in db is in this format: <time_start>,<time_end>,(<field1>,...,<fieldN>)
        def row_to_values(row):
            values = row.split(',', maxsplit=2)
            # Commas within filed values are escaped by a backslash - we don't want to split on those
            values = values[:2] + re.split(r'(?<!\\),', values[2].strip('()'))
            # If, for some reason, a row is missing commas (not just values!), pad it with empty fields
            values = values + [''] * (len(field_names) - len(values))
            return values

        data = list(map(row_to_values, db_lines[2:]))

        # Bind
        df = pd.DataFrame(columns=field_names, data=data)

        return df

    def __str__(self):
        """
        Converts back to text format
        :return: str
        """
        # Reformat data into single column of the format <time>,<time>,(<col1>,...,<col2>)
        df = self.df
        time_columns = ('time_start', 'time_end')
        other_columns = ~df.columns.isin(time_columns)
        data = (pd.concat([
            # Time columns
            df.loc[:, time_columns],
            # All the other columns put together in parentheses and separated by commas
            df.loc[:, other_columns]
              .astype(str)
              .agg(lambda values: f'({",".join(values)})', axis=1)
            ], axis=1)
            .agg(','.join, axis=1)
        )

        return '\n'.join([self.prefix,
                          self.column_definitions,
                          *data.to_list()])

    def can_be_reversed(self):
        """
        Can we reconstruct the db in the original file up to an empty line at the end?
        :return:
        """
        return str(self) == self.opf_file.db.rstrip()

    @staticmethod
    def time_column_to_milliseconds(time_str: pd.Series):
        dt = pd.to_datetime(time_str, format=DATETIME_FORMAT)
        return ((dt.dt.hour * 60 + dt.dt.minute) * 60 + dt.dt.second) * 1000 + dt.dt.microsecond / 1000


def export_opf_to_csv(opf_path, csv_path):
    """
    Emulate datavyu export
    :param opf_path: Path to the opf
    :param csv_path: Path to the output csv
    :return:
    """
    # Load the data
    df = OPFDataFrame(OPFFile(opf_path)).df

    # Make sure the index is 1, 2, 3 and make it a column
    df = df.reset_index(drop=True).reset_index()
    df['index'] += 1

    # Rename columns
    df.rename(columns={
        'index': 'ordinal',
        'time_start': 'onset',
        'time_end': 'offset'
    }, inplace=True)

    # Convert time to milliseconds
    df['onset'] = OPFDataFrame.time_column_to_milliseconds(df.onset).astype(int)
    df['offset'] = OPFDataFrame.time_column_to_milliseconds(df.offset).astype(int)

    # Prepend "labeled_object." to column names
    df.columns = 'labeled_object.' + df.columns

    # Write the output manually. Specifics of the datavyu export function (adding a comma to the end of each line) make
    # it harder to use df.to_csv directly.
    with csv_path.open('w') as f:
        columns, *rows = df.to_csv(index=False, quoting=csv.QUOTE_NONNUMERIC).splitlines()
        # There is an extra comma in the datavyu export for some reason.
        suffix = ',\n'

        # Write the column names which are not quoted in datavyu output
        f.write(columns.replace('"', '') + suffix)

        # And then the lines, in which non-numeric data *are* quoted
        for row in rows:
            f.write(row + suffix)