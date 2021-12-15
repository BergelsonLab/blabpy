import csv

from .opf import OPFFile, OPFDataFrame


def export_opf_to_csv(opf_path, csv_path):
    """
    Emulate datavyu export
    :param opf_path: Path to the opf
    :param csv_path: Path to the output csv
    :return:
    """
    # Load the data
    df = OPFDataFrame(OPFFile(opf_path)).df

    # Make sure the index is 0, 1, 2 and make it a column
    df = df.reset_index(drop=True).reset_index()

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
        lines = df.to_csv(index=False, quoting=csv.QUOTE_NONNUMERIC).split('\n')
        suffix = ',\n'
        # Write the column names which should not be quoted
        f.write(lines[0].replace('"', '') + suffix)

        # Write every other line except for the last empty line - we add a newline character anyway
        assert lines[-1] == ''
        for line in lines[1:-1]:
            f.write(line + suffix)
