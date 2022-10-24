from datetime import date
from pathlib import Path
from shutil import copy2

import pandas as pd

from .paths import _parse_out_child_and_month, get_basic_level_path, _check_modality, AUDIO, VIDEO
from .merge import read_annotations_csv


def backup_to_old_files(file_path: Path, skip_backup_if_exists=False):
    """
    Move file at file_path to the folder "Old_Files" at the same level adding date in the format "_YYYY-MM-DD". The
    "Old_Files" will be created if necessary.
    throw a FileExistsError if there is an already existing backup with the same date.

    Note: a.tar.gz will be renamed to a.tar_2021-12-30.gz

    :param file_path: path to the file to be backed
    """
    assert file_path.is_file()

    date_string = date.today().isoformat()
    backup_path = file_path.parent / 'Old_Files' / f'{file_path.stem}_{date_string}{file_path.suffix}'

    backup_path.parent.mkdir(exist_ok=True)

    if backup_path.exists():
        if skip_backup_if_exists:
            return
        else:
            raise FileExistsError('Can\'t back up\n'
                                  f'\t{file_path.absolute()}\n'
                                  '\tto\n'
                                  f'\t{backup_path.absolute()}\n'
                                  '\tbecause the second path already exists.')

    copy2(file_path, backup_path)


def copy_basic_level_to_subject_files(file_path: Path, modality, backup=True,
                                      skip_backup_if_exists=False):
    """
    Copies the basic level file at file_path to the corresponding folder in the Seedlings folder. The correspondence is
    established based on the child and month number in the filename and the modality argument. The older version is
    backed up first.
    :param file_path: path to the newer basic level file
    :param modality: Auido/Video
    :return: None
    """
    _check_modality(modality)

    # Check that the file looks like an actual basic level file of the right modlaity
    # It is an existing csv file
    assert file_path.exists() and file_path.is_file() and file_path.name.endswith('.csv')
    # With 'basic_level' in the column definitions
    with file_path.open() as f:
        assert 'basic_level' in f.readline()
    # And modality in its name (something like '01_06_audio_sparse_code.csv')
    assert modality.lower() in file_path.name.lower()

    # Sort the rows in the source file and overwrite it. Annotators will sometimes re-sort files in Excel.
    read_annotations_csv(file_path).sort_values(by='ordinal').to_csv(file_path, index=False)

    # Backup the current version
    basic_level_path = get_basic_level_path(**_parse_out_child_and_month(file_path), modality=modality)
    if backup:
        backup_to_old_files(basic_level_path, skip_backup_if_exists=skip_backup_if_exists)

    # Copy the new version
    copy2(file_path, basic_level_path)


def copy_all_basic_level_files_to_subject_files(updated_basic_level_folder: Path, modality, backup=True,
                                                skip_backups_if_exist=False):
    """
    Runs copy_basic_level_to_subject_files on all csv files in a folder.
    :param updated_basic_level_folder: folder with the basic level files
    :param modality: Audio/Video
    :param backup: should csv files be backed up to "Old_Files" first?
    successfully copied would not be attempted to copy again leading to error because a backup file already exists.
    :return: None
    """
    for basic_level_path in updated_basic_level_folder.glob('*.csv'):
        copy_basic_level_to_subject_files(file_path=basic_level_path, modality=modality, backup=backup,
                                          skip_backup_if_exists=skip_backups_if_exist)
