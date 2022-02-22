import logging
import warnings
from itertools import product
from pathlib import Path

import pandas as pd

from .cha import export_cha_to_csv
from .gather import gather_all_basic_level_annotations, write_all_basic_level_to_csv, write_all_basic_level_to_feather, \
    check_for_errors
from .listened_time import listen_time_stats_for_report, RECORDINGS_WITH_FOUR_SUBREGIONS, _get_subregion_count
from .merge import create_merged, FIXME
from .opf import export_opf_to_csv
from .paths import get_all_opf_paths, get_all_cha_paths, get_basic_level_path, _parse_out_child_and_month, \
    ensure_folder_exists_and_empty, AUDIO, VIDEO

# Placeholder value for words without the basic level information
from .scatter import copy_all_basic_level_files_to_subject_files


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
    missing_audio_basic_level_path = working_folder / 'missing_basic_level_audio.csv'
    is_missing_audio = is_any_missing_basic_level_data(merged_folder=merged_folder_audio,
                                                       list_path=missing_audio_basic_level_path)

    missing_video_basic_level_path = working_folder / 'missing_basic_level_video.csv'
    is_missing_video = is_any_missing_basic_level_data(merged_folder=merged_folder_video,
                                                       list_path=missing_video_basic_level_path)

    anything_missing = is_missing_audio or is_missing_video
    if anything_missing:
        if raise_error_if_any_missing:
            raise Exception('Some rows have missing basic level data. For details, see:\n'
                            f'{missing_audio_basic_level_path}\n'
                            f'{missing_video_basic_level_path}\n')
        else:
            return True
    else:
        return False


def scatter_all_basic_level(merged_folder_audio, merged_folder_video, working_folder,
                            check_for_missing_basic_levels=True):
    """
    Checks annotations files, freshly exported and merged with basic level data, for any missing basic level. If there
    aren't any, copies the files to their individual child-month locations in Subject_Files.
    :param merged_folder_audio: folder where merge_[all_]annotations_with_basic_level put the outputs
    :param merged_folder_video: ditto for video
    :param working_folder: where to put the list of missing basic level data (FIXMEs)
    :param check_for_missing_basic_levels: should we scatter only when there are no FIXMEs? Mostly, will only make sense
    when restoring from a backup.
    :return:
    """
    if check_for_missing_basic_levels:
        anything_missing = check_all_basic_level_for_missing(
            merged_folder_audio=merged_folder_audio, merged_folder_video=merged_folder_video,
            working_folder=working_folder, raise_error_if_any_missing=False)

        if anything_missing:
            print('\n'.join([
                'There were rows with missing basic level data. Check the csv logs.',
                '- Update the corresponding rows in the individual sparse_code csvs in the following folders:',
                f'  {merged_folder_audio}',
                f'  {merged_folder_video}',
                '\n',
                '- Run',
                f'  scatter_all_basic_level(',
                f'      merged_folder_audio=\'{merged_folder_audio}\',',
                f'      merged_folder_video=\'{merged_folder_video}\',',
                f'      working_folder=\'{working_folder}\',',
                f'      check_for_missing_basic_levels={check_for_missing_basic_levels})'
            ]))
            return

    copy_all_basic_level_files_to_subject_files(updated_basic_level_folder=merged_folder_audio, modality=AUDIO,
                                                backup=True)
    copy_all_basic_level_files_to_subject_files(updated_basic_level_folder=merged_folder_video, modality=VIDEO,
                                                backup=True)


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
    scatter_all_basic_level(merged_folder_audio=with_basic_level_audio,
                            merged_folder_video=with_basic_level_video,
                            working_folder=working_folder,
                            check_for_missing_basic_levels=(not ignore_missing_basic_level))


def finish_updating_basic_level_files_in_seedlings(working_folder=None, ignore_missing_basic_level=False):
    """
    Most of the time update_basic_level_files_in_seedlings will tell you that there are still some files with missing
    data in tha basic_level column. Run this function once you are done fixing those. It will upodate the lists of
    missing files and
    :return:
    """
    working_folder = working_folder or Path('.')

    with_basic_level_audio_folder = working_folder / 'with_basic_level_audio_annotations'
    with_basic_level_video_folder = working_folder / 'with_basic_level_video_annotations'

    scatter_all_basic_level(merged_folder_audio=with_basic_level_audio_folder,
                            merged_folder_video=with_basic_level_video_folder,
                            working_folder=working_folder,
                            check_for_missing_basic_levels=(not ignore_missing_basic_level))


def make_updated_all_basic_level_here():
    """
    Gathers all basic level files, checks for some errors, and - if there were no errors - writes four files:
    - all_basiclevel.csv
    - all_basiclevel.feather
    - all_basiclevel_NA.csv
    - all_basiclevel_NA.feather
    The files differ in whether they contain rows that have NA as the basic level and their format (csv/feather).
    The files are created in the current working directory. If the files already exist, they will be deleted first. This
    is done so there is a difference between:
    - everything went well, but there are no changes (files are the same, git status sees no changes) and
    - something went wrong (files are missing, git status will show that much).
    :return: None
    """
    # Delete current files
    output_paths = [Path(f'all_basiclevel{suffix}{extension}')
                    for suffix, extension in product(('', '_NA'), ('.csv', '.feather'))]
    for output_path in output_paths:
        try:
            output_path.unlink()
        except FileNotFoundError:
            pass

    # Gather all individual basic level files
    df_with_na = gather_all_basic_level_annotations(keep_basic_level_na=True)

    # Check for errors
    errors_df = check_for_errors(df_with_na)
    if errors_df:
        errors_file = 'errors.csv'
        logging.warning(f'The were errors found, the corresponding rows are in "{errors_file}".')
        errors_df.to_csv(errors_file)
        return

    # Write the four files
    def _write_to_csv_and_feather(all_basic_level_df, output_stem):
        write_all_basic_level_to_csv(all_basic_level_df=all_basic_level_df,
                                     csv_path=output_stem.with_suffix('.csv'))
        write_all_basic_level_to_feather(all_basic_level_df=all_basic_level_df,
                                         feather_path=output_stem.with_suffix('.feather'))
    # Without NAs
    output_stem_without_na = Path('all_basiclevel')
    df_without_na = df_with_na[~df_with_na.basic_level.isna()].reset_index(drop=True)
    # The feather version contains categorical information, so we need to remove categories that no longer exist - as if
    # the categories were set after removing NAs.
    for column_name in df_without_na.columns:
        if df_without_na[column_name].dtype.name == 'category':
            df_without_na[column_name] = df_without_na[column_name].cat.remove_unused_categories()
    _write_to_csv_and_feather(df_without_na, output_stem_without_na)

    # With NAs
    output_stem_with_na = output_stem_without_na.with_name(output_stem_without_na.name + '_NA')
    _write_to_csv_and_feather(df_with_na, output_stem_with_na)

    # Check that the output files have been created
    for output_path in output_paths:
        assert output_path.exists()
    print(f'all_basiclevel has been created and checked for errors, files have been written to.')


def calculate_listen_time_stats_for_cha_file(cha_path):
    """
    Runs listened_time.listen_time_stats_for_report on a single file accounting for files with four subregions.
    :param cha_path: path to the clan file
    :return: see listened_time.listen_time_stats_for_report
    """
    subregion_count = _get_subregion_count(**_parse_out_child_and_month(cha_path))
    clan_file_text = Path(cha_path).read_text()
    return listen_time_stats_for_report(clan_file_text=clan_file_text, subregion_count=subregion_count)


def calculate_listen_time_stats_for_all_cha_files():
    """
    Runs calculate_listen_time_stats_for_cha_file on all cha files.
    :return: a pandas DataFrame with the calculated states and an additional column 'filename'
    """
    cha_paths = get_all_cha_paths()
    stats = [calculate_listen_time_stats_for_cha_file(cha_path) for cha_path in cha_paths]

    # Check uniqueness of the keys in all returned dicts
    [keys] = {tuple(stats_.keys()) for stats_ in stats}
    # Check that the keys are what we expect them to be
    expected_keys = ('num_makeup_region',
                     'num_extra_region',
                     'num_surplus_region',
                     'makeup_time',
                     'extra_time',
                     'surplus_time',
                     'subregion_time',
                     'num_subregion_with_annot',
                     'skip_silence_overlap_hour',
                     'skip_time',
                     'silence_time',
                     'silence_raw_hour',
                     'end_time',
                     'total_listen_time',
                     'positions',
                     'ranks',
                     'subregion_raw_hour',
                     'num_raw_subregion',
                     'annotation_counts_raw')
    assert keys == expected_keys

    # Combine into a dataframe and return
    return pd.DataFrame(
        index=pd.Index(data=[cha_path.name for cha_path in cha_paths], name='filename'),
        data=stats,
        columns=expected_keys).reset_index()
