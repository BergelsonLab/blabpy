import csv
import warnings
from pathlib import Path

import pandas as pd

from .cha import Parser
from .opf import OPFFile, OPFDataFrame
from .paths import get_all_opf_paths, get_all_cha_paths, get_basic_level_path, _parse_out_child_and_month


# Placeholder value for words without the basic level information
FIXME = '***FIX ME***'


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
        columns, *rows = df.to_csv(index=False, quoting=csv.QUOTE_NONNUMERIC).splitlines()
        # There is an extra comma in the datavyu export for some reason.
        suffix = ',\n'

        # Write the column names which are not quoted in datavyu output
        f.write(columns.replace('"', '') + suffix)

        # And then the lines, in which non-numeric data *are* quoted
        for row in rows:
            f.write(row + suffix)


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
    :param output_folder: Path to folder that will contain the _processed.csv and _errors.csv files. If None, output is
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
    assert not (output_folder.exists() and any(output_folder.iterdir())),\
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

    if parsed_with_errors:
        warnings.warn(f'Some cha files were parsed with errors. For details, see:\n {str(log_path.absolute())}')

    if could_not_be_parsed:
        raise Exception(f'Some cha files could not parsed at all. Try exportint them individually. For details, see:\n'
                        f' {str(log_path.absolute())}')


def create_merged(file_new, file_old, file_merged, mode):
    """
    Merges annotations exported with export_opf_to_csv/export_cha_to_csv with the previously exported file that has
    the basic level of all words already added. Merging is done based on annotation ids (annotid) that each word in both
    files should have. For new or changed words, the basiclevel column will have ***FIX ME***
    :param file_new: path to a csv with exported annotations without basic level data
    :param file_old: path to a previous version of exported annotation with basic level data already added
    :param file_merged: path to the output file
    :param mode: 'audio'|'video' - which modality these files came from
    :return: (old_error, edit_word, new_word) - tuple of boolean values:
        old_error - were there duplicate annotids in the file with basic level data?
        edit_word - were there any changes to any of the words?
        new_word - are there new words in the exported annotations?
    """
    # print(mode)
    # print(file_old)
    # """
    if mode == "audio":
        annotid_col = "annotid"
        word_col = "word"
    elif mode == "video":
        annotid_col = "labeled_object.id"
        word_col = "labeled_object.object"
    else:
        print("Wrong mode value")
        return [], [], []
    # """

    # annotid_col = "annotid"
    # word_col = "word"
    # basic_level_col = "basic_level"

    old_error = False
    edit_word = False
    new_word = False

    old_df = pd.read_csv(file_old, keep_default_na=False, engine='python')
    new_df = pd.read_csv(file_new, keep_default_na=False, engine='python')

    # The basic level column in some video files is called basic_level, in others - labeled_object.basic_level. Let's
    # find which it is.
    # The code below will implicitly break if there are multiple columns whose name contains "basic_level"
    [old_basic_level_col] = old_df.columns[old_df.columns.str.contains('basic_level')]

    # For consistent naming, let's change it to 'basic_level'.
    basic_level_col = 'basic_level'
    old_df.rename(columns={old_basic_level_col: basic_level_col}, inplace=True)

    merged_df = pd.DataFrame(columns=old_df.columns.values)

    # df = df.rename(columns={'oldName1': 'newName1'})
    for index, new_row in new_df.iterrows():

        # word = ''
        to_add = new_row
        annot_id = new_row[annotid_col]
        tmp = old_df[old_df[annotid_col] == annot_id]
        # print(len(tmp.index))

        word = new_row[word_col]
        # tier = new_row['tier']
        # spk = new_row['speaker']
        # utt_type = new_row['utterance_type']
        # obj_pres = new_row['object_present']
        # ts = new_row['timestamp']

        while len(tmp.index) != 0:  # if the id already exists in the old df, check that the words/ts? do match

            if len(tmp.index) > 1:
                print("ERROR: annotid not unique in old version : ", annot_id)  # raise exception
                to_add[basic_level_col] = FIXME
                merged_df = merged_df.append(to_add)
                old_error = True
                break
            old_row = tmp.iloc[0]

            # if new_row[:, new_row.columns != "basic_level"].equals(old_row[:, old_row.columns != "basic_level"]):
            if word == old_row[word_col]:
                # print("old", word)
                # check codes as well to know if something changed?
                to_add[basic_level_col] = old_row[basic_level_col]
                merged_df = merged_df.append(to_add)
                break
            else:
                # print("old but different", word)
                to_add[basic_level_col] = FIXME
                merged_df = merged_df.append(to_add)
                edit_word = True
                break

        else:  # if the id is new: no info to retrieve, add row from new
            # print(word)
            if word != '':
                # print("new", word)
                to_add[basic_level_col] = FIXME
                merged_df = merged_df.append(to_add)
                new_word = True
    # print(merged_df)
    merged_df = merged_df.loc[:, ~merged_df.columns.str.contains('^Unnamed')]
    merged_df.to_csv(file_merged, index=False)

    return old_error, edit_word, new_word


def merge_all_annotations_with_basic_level(exported_annotations_folder, output_folder, mode,
                                           exported_suffix='_processed.csv'):
    """
    Merges all exported annotation files in output_folder and saves them to output_folder which must be empty.
    :param exported_annotations_folder: the input folder
    :param output_folder: the output folder
    :param mode: 'audio'|'video' - which modality these files came from
    :param exported_suffix: the ending of the exported annotation file names
    :return: 
    """
    assert not (output_folder.exists() and any(output_folder.iterdir())), \
        'The output folder should be empty or not yet exist'
    output_folder.mkdir(parents=True, exist_ok=True)

    # Find/assemble all necessary paths
    annotation_files = list(exported_annotations_folder.glob(f'*{exported_suffix}'))
    basic_level_files = [get_basic_level_path(**_parse_out_child_and_month(annotation_file), modality=mode.capitalize())
                         for annotation_file in annotation_files]
    output_files = [output_folder / basic_level_file.name for basic_level_file in basic_level_files]

    # Merge and save
    results = [create_merged(file_new=annotation_file, file_old=basic_level_file, file_merged=output_file, mode=mode)
               for annotation_file, basic_level_file, output_file
               in zip(annotation_files, basic_level_files, output_files)]

    # Output merging log to a csv file
    columns = ['duplicates_in_old_file', 'words_were_edited', 'words_were_added']
    results_df = pd.DataFrame(columns=columns,
                              data=results)
    results_df['exported_annotations_path'] = [annotation_file.absolute() for annotation_file in annotation_files]
    log = Path(f'merging_{mode}_log.csv')
    results_df.to_csv(path_or_buf=log, index=False)

    # Print numbers of files with duplicates, edited words and edited words
    duplicate_count, edited_count, added_count = results_df[columns].sum()
    print(f'There were:\n'
          f'{duplicate_count} basic level files with duplicate annotation ids.\n',
          f'{edited_count} merged files with words that have been edited.\n'
          f'{added_count} merged files with new words.\n\n'
          f'For details, see {log.absolute()}')


def make_incomplete_basic_level_list(merged_folder: Path):
    """
    Looks through all the files in the folder with annotations merged with previous basic level data and counts the
    number of rows that have to be manually updated
    :param merged_folder:
    :return: a pandas dataframe with two columns: filename, fixme_count
    """
    all_fixmes_df = None
    for csv_file in merged_folder.glob('*.csv'):
        fixmes_df = pd.read_csv(csv_file)
        fixmes_df = fixmes_df[fixmes_df.basic_level == FIXME]
        fixmes_df['filename'] = str(csv_file)
        all_fixmes_df = pd.concat([all_fixmes_df, fixmes_df])
    return all_fixmes_df
