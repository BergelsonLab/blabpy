import csv
from pathlib import Path

from .opf import OPFFile, OPFDataFrame
from.cha import Parser
from .paths import get_all_opf_paths, get_all_cha_paths


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


def export_all_opfs_to_csv(output_folder: Path, suffix='_processed'):
    """
    Exports all opf files, adds suffix to their names and saves to the output_folder
    :param output_folder: Path p
    :param suffix: str
    :return:
    """
    assert not (output_folder.exists() and any(output_folder.iterdir())), \
            'The output folder should be empty or not yet exist'
    output_folder.mkdir(parents=True, exist_ok=True)

    opf_paths = get_all_opf_paths()

    for opf_path in opf_paths:
        # Add suffix before all extensions
        extensions = ''.join(opf_path.suffixes)
        output_name = opf_path.name.replace(extensions, suffix + '.csv')

        export_opf_to_csv(opf_path=opf_path, csv_path=(output_folder / output_name))


def export_cha_to_csv(cha_path, output_folder):
    """
    Runs parse_clan2 (a version of it) on a cha file at cha_path and outputs the results to a csv_path
    :param cha_path: Path
    :param output_dir: Path to folder that will contain the _processed.csv and _errors.csv files. If None, output is
    saved to the save folder where cha_path is.
    :return: Path|None, if there were known errors, return the error file path. If the file could not be parsed, return
    cha_path
    """
    try:
        # Parser parses implicitly
        parser = Parser(input_path=cha_path, output=output_folder)
        error_file_path = Path(parser.error_file)
        if error_file_path.exists():
            return error_file_path
    except Exception:
        return cha_path


def export_all_chas_to_csv(output_folder: Path, log_path=Path('cha_parsing_errors_log.txt')):
    """
    Exports all cha files to output_folder
    :param output_folder: Path
    :param log_path: Path, file where errors are logged if any
    :return: Path|None, if there were any errors, returns path to the error log file
    """
    assert not (output_folder.exists() and any(output_folder.iterdir())), \
            'The output folder should be empty or not yet exist'
    output_folder.mkdir(parents=True, exist_ok=True)

    # These will hold paths to files with problems if any
    could_not_be_parsed = list()
    parsed_with_errors = list()

    cha_paths = get_all_cha_paths()
    for cha_path in cha_paths:
        problems = export_cha_to_csv(cha_path=cha_path, output_folder=output_folder)
        if not problems:
            continue

        # If there were any problems, take note
        if problems == cha_path:
            could_not_be_parsed.append(problems)
        else:
            parsed_with_errors.append((cha_path, problems))

    # Write errors to the log file
    if could_not_be_parsed or parsed_with_errors:
        with log_path.open('w', encoding='utf-8') as f:

            if could_not_be_parsed:
                f.write('The following files could not be parsed:\n\n')
                for path in could_not_be_parsed:
                    f.write(str(path) + '\n')

            if parsed_with_errors:
                f.write('The following files were parsed with errors:\n\n')
                for cha_path, error_path in parsed_with_errors:
                    f.write(f'Cha file: {str(cha_path.absolute())}\n')
                    f.write(f'Error log: {str(error_path.absolute())}\n')

        return log_path
