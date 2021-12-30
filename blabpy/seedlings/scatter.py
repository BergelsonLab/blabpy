from datetime import date
from pathlib import Path
from shutil import copy2


def backup_to_old_files(file_path: Path):
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
        raise FileExistsError('Can\'t back up\n'
                              f'\t{file_path.absolute()}\n'
                              '\tto\n'
                              f'\t{backup_path.absolute()}\n'
                              '\tbecause the second path already exists.')

    copy2(file_path, backup_path)
