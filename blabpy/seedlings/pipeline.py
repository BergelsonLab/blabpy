import csv
import warnings
from pathlib import Path

import pandas as pd

from .cha import Parser
from .gather import gather_all_basic_level_annotations, write_all_basic_level_to_csv, write_all_basic_level_to_feather
from .opf import OPFFile, OPFDataFrame
from .paths import get_all_opf_paths, get_all_cha_paths, get_basic_level_path, _parse_out_child_and_month, \
    ensure_folder_exists_and_empty, AUDIO, VIDEO

# Placeholder value for words without the basic level information
from .scatter import copy_all_basic_level_files_to_subject_files

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
    ensure_folder_exists_and_empty(output_folder)

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
    ensure_folder_exists_and_empty(output_folder)

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
    else:
        log_path = None

    if parsed_with_errors:
        warnings.warn(f'Some cha files were parsed with errors. For details, see:\n {str(log_path.absolute())}')

    if could_not_be_parsed:
        raise Exception(f'Some cha files could not parsed at all. Try exportint them individually. For details, see:\n'
                        f' {str(log_path.absolute())}')

    return log_path


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


def merge_annotations_with_basic_level(exported_annotations_folder, output_folder, mode,
                                       exported_suffix='_processed.csv'):
    """
    Merges all exported annotation files in output_folder and saves them to output_folder which must be empty.
    :param exported_annotations_folder: the input folder
    :param output_folder: the output folder
    :param mode: 'audio'|'video' - which modality these files came from
    :param exported_suffix: the ending of the exported annotation file names, needed because export_cha_to_csv exports
    two files: the actual csv and the errors file
    :return: 
    """
    ensure_folder_exists_and_empty(output_folder)

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


def merge_all_annotations_with_basic_level(
        exported_audio_annotations_folder, exported_video_annotations_folder,
        working_folder, exported_suffix='_processed.csv'):
    """
    Runs merge_annotations_with_basic_level on both audio and video annotations and puts the results to csv files in
    subfolders of working_folder.
    :param exported_audio_annotations_folder: folder to look for exported audio annotations in
    :param exported_video_annotations_folder: folder to look for exported video annotations in
    :param working_folder: the parent folder of the two output folders.
    :param exported_suffix: see merge_annotations_with_basic_level docstring
    :return:
    """
    # Audio
    with_basic_level_audio_folder = working_folder / 'with_basic_level_audio_annotations'
    merge_annotations_with_basic_level(exported_annotations_folder=exported_audio_annotations_folder,
                                       output_folder=with_basic_level_audio_folder,
                                       mode='audio', exported_suffix=exported_suffix)

    # Video
    with_basic_level_video_folder = working_folder / 'with_basic_level_video_annotations'
    merge_annotations_with_basic_level(exported_annotations_folder=exported_video_annotations_folder,
                                       output_folder=with_basic_level_video_folder,
                                       mode='video', exported_suffix=exported_suffix)

    return with_basic_level_audio_folder, with_basic_level_video_folder


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


def is_any_missing_basic_level_data(merged_folder: Path, list_path: Path):
    """
    Runs make_incomplete_basic_level_list, saves it to a file and return whether there were any missing basic levels.
    :param merged_folder:
    :param list_path: where to output a list of rows missing basic level data
    :return: whether there were any rows with missing basic level data
    """
    df = make_incomplete_basic_level_list(merged_folder=merged_folder)
    df.to_csv(list_path, index=False)
    return df.size > 0


def check_all_basic_level_for_missing(merged_folder_audio, merged_folder_video, working_folder,
                                      raise_error_if_any_missing=True):
    """
    Runs is_any_missing_basic_level_data on both the audio and video folder with annotations merged with existing basic
    level data.
    :param merged_folder_audio:
    :param merged_folder_video:
    :param working_folder: the folder where list of missing basic level data will be saved if any
    :param raise_error_if_any_missing: should an error be raise if there are any missing?
    :return: were there any rows with missing basic levels?
    """
    missing_audio_df = working_folder / 'missing_basic_level_audio.csv'
    is_missing_audio = is_any_missing_basic_level_data(merged_folder=merged_folder_audio, list_path=missing_audio_df)

    missing_video_df = working_folder / 'missing_basic_level_video.csv'
    is_missing_video = is_any_missing_basic_level_data(merged_folder=merged_folder_video, list_path=missing_video_df)

    anything_missing = is_missing_audio or is_missing_video
    if anything_missing:
        if raise_error_if_any_missing:
            raise Exception('Some rows have missing basic level data. For details, see:\n'
                            f'{missing_audio_df}\n'
                            f'{missing_video_df}\n')
        else:
            return True
    else:
        return False


def scatter_all_basic_level_if_complete(merged_folder_audio, merged_folder_video, working_folder,
                                        ignore_missing_basic_level=False):
    anything_missing = check_all_basic_level_for_missing(
        merged_folder_audio=merged_folder_audio, merged_folder_video=merged_folder_video,
        working_folder=working_folder, raise_error_if_any_missing=(not ignore_missing_basic_level))

    if (not anything_missing) or ignore_missing_basic_level:
        copy_all_basic_level_files_to_subject_files(updated_basic_level_folder=merged_folder_audio, modality=AUDIO)
        copy_all_basic_level_files_to_subject_files(updated_basic_level_folder=merged_folder_video, modality=VIDEO)


def export_all_annotations_to_csv(working_folder=None, ignore_audio_annotation_problems=False):
    """
    Exports audio and video annotations to csv files in subfolders of working_folder.
    :param working_folder: the parent folder of the output folders
    :param ignore_audio_annotation_problems: if False, will raise an exception if there were some problems when
    exporting audio annotations
    :return: tuple of paths to exported audio and video annotations respectively
    """
    working_folder = working_folder or Path('.')

    # Video annotations
    exported_video_annotations_folder = working_folder / 'exported_video_annotations'
    export_all_opfs_to_csv(exported_video_annotations_folder)

    # Audio annotations
    exported_audio_annotations_folder = working_folder / 'exported_audio_annotations'
    log = export_all_chas_to_csv(exported_audio_annotations_folder)
    if log and not ignore_audio_annotation_problems:
        raise Exception('There were problems during the export of audio annotations.'
                        ' See the following file for details:\n'
                        f'{log.absolute()}')

    return exported_audio_annotations_folder, exported_video_annotations_folder


def update_basic_level_files_in_seedlings(working_folder=None, ignore_audio_annotation_problems=False,
                                          ignore_missing_basic_level=False):
    """
    Updates all individual basic level files in the Seedlings folder:
     - exports all annotations from cha and opf files, checks for exporting errors,
     - uses annotids to find basic level data in the current basic level files, mark rows where new one should be added,
     - if all basic level data is already present, backs up and updates the inividual basic level files
    :return:
    """
    working_folder = working_folder or Path('.')

    # Export
    exported_audio, exported_video = export_all_annotations_to_csv(
        working_folder=working_folder,
        ignore_audio_annotation_problems=ignore_audio_annotation_problems)

    # Merge with current basic level data
    with_basic_level_audio, with_basic_level_video = merge_all_annotations_with_basic_level(
        exported_audio_annotations_folder=exported_audio,
        exported_video_annotations_folder=exported_video,
        working_folder=working_folder
    )

    # Scatter if basic level column is complete everywhere
    scatter_all_basic_level_if_complete(merged_folder_audio=with_basic_level_audio,
                                        merged_folder_video=with_basic_level_video,
                                        working_folder=working_folder,
                                        ignore_missing_basic_level=ignore_missing_basic_level)


def make_updated_all_basic_level_here():
    all_basic_level_df = gather_all_basic_level_annotations()
    output_stem = Path('all_basiclevel')
    write_all_basic_level_to_csv(all_basic_level_df=all_basic_level_df,
                                 csv_path=output_stem.with_suffix('.csv'))
    write_all_basic_level_to_feather(all_basic_level_df=all_basic_level_df,
                                     feather_path=output_stem.with_suffix('.feather'))
