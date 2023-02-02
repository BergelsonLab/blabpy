from functools import lru_cache
from pathlib import Path

from . import AUDIO, VIDEO, CHILDREN_INT, MONTHS_INT, ANNOTATION_FILE_COUNT, MISSING_AUDIO_RECORDINGS, \
    MISSING_VIDEO_RECORDINGS
from ..paths import get_pn_opus_path, get_blab_data_path


def ensure_folder_exists_and_empty(folder_path):
    """
    Check that folder is either empty or does not yet exist. In the latter case, creates it.
    :param folder_path:
    :return:
    """
    assert not (folder_path.exists() and any(folder_path.iterdir())), \
        'The folder should be empty or not yet exist'
    folder_path.mkdir(parents=True, exist_ok=True)


def get_seedlings_path():
    """
    Finds the path to the Seedlings folder on PN-OPUS
    :return: Path object
    """
    return get_pn_opus_path() / 'Seedlings'


def _normalize_child_month(child, month):
    """
    Converts child and month code to the two-digit (01,...,10,11,..) string representation
    :param child: int or str
    :param month: int or str
    :return: (str, str) tuple
    """
    month_str = f'{int(month):02}'
    child_str = f'{int(child):02}'
    return child_str, month_str


def get_subject_files_folder():
    return get_seedlings_path() / 'Subject_Files'


def _get_home_visit_folder(child, month):
    child, month = _normalize_child_month(child=child, month=month)
    child_month_dir = get_subject_files_folder() / child / f'{child}_{month}'
    return child_month_dir / 'Home_Visit'


def _get_coding_folder(child, month):
    return _get_home_visit_folder(child=child, month=month) / 'Coding'


def _get_analysis_folder(child, month):
    return _get_home_visit_folder(child=child, month=month) / 'Analysis'


def _check_modality(modality):
    assert modality in (AUDIO, VIDEO), f'Modality must be either Audio or Video but was {modality} instead'


def _check_subject_and_month(modality, subject, month):
    _check_modality(modality)
    if modality == AUDIO:
        missing = MISSING_AUDIO_RECORDINGS
    elif modality == VIDEO:
        missing = MISSING_VIDEO_RECORDINGS

    assert int(subject) in CHILDREN_INT
    assert int(month) in MONTHS_INT
    assert (subject, month) not in missing, f'No {modality} data for subject {subject} and month {month}'


def _get_annotation_path(child, month, modality):
    """
    Finds path to the opf/cha files
    :param modality: 'Audio'/'Video'
    :return: Path object
    """
    coding_folder = _get_coding_folder(child=child, month=month)
    child, month = _normalize_child_month(child=child, month=month)
    _check_modality(modality)
    if modality == AUDIO:
        extension = 'cha'
    elif modality == VIDEO:
        extension = 'opf'

    path = coding_folder / f'{modality}_Annotation' / f'{child}_{month}_sparse_code.{extension}'
    if not path.exists():
        raise FileNotFoundError()

    return path


def get_opf_path(child, month):
    return _get_annotation_path(child=child, month=month, modality=VIDEO)


def get_cha_path(child, month):
    return _get_annotation_path(child=child, month=month, modality=AUDIO)


def _get_all_paths(get_single_file_function, missing_child_month_combinations, **kwargs):
    """
    Runs get_single_file_function on all child-month combinations skipping files that do not exist and checking the
    total number at the end.
    :return: list of Path objects
    """
    paths = [get_single_file_function(child=child, month=month, **kwargs)
             for child in CHILDREN_INT for month in MONTHS_INT
             if (child, month) not in missing_child_month_combinations]
    assert len(paths) == ANNOTATION_FILE_COUNT

    return paths


def get_all_video_paths(get_single_file_function, **kwargs):
    return _get_all_paths(get_single_file_function, MISSING_VIDEO_RECORDINGS, **kwargs)


def get_all_audio_paths(get_single_file_function, **kwargs):
    return _get_all_paths(get_single_file_function, MISSING_AUDIO_RECORDINGS, **kwargs)


@lru_cache(maxsize=None)  # do this just once
def get_all_opf_paths():
    return _get_all_paths(get_single_file_function=get_opf_path,
                          missing_child_month_combinations=MISSING_VIDEO_RECORDINGS)


@lru_cache(maxsize=None)  # do this just once
def get_all_cha_paths():
    return _get_all_paths(get_single_file_function=get_cha_path,
                          missing_child_month_combinations=MISSING_AUDIO_RECORDINGS)


def get_basic_level_path(child, month, modality):
    _check_modality(modality)
    analysis_folder = _get_analysis_folder(child=child, month=month)
    child, month = _normalize_child_month(child=child, month=month)
    path = analysis_folder / f'{modality}_Analysis' / f'{child}_{month}_{modality.lower()}_sparse_code.csv'

    if not path.exists():
        raise FileNotFoundError(path.absolute())

    return path


def get_lena_5min_csv_path(child, month):
    """
    Returns path to lena5min.csv - a LENA-create file with automatic metrics for each consecutive five-minute interval.
    :return: Path object
    """
    child, month = _normalize_child_month(child=child, month=month)
    filename = f'{child}_{month}_lena5min.csv'

    if int(month) in (6, 7):
        return get_subject_files_folder() / 'lena5min' / filename
    elif int(month) in (8, 9, 10, 11, 12, 13, 14, 15, 16, 17):
        return _get_home_visit_folder(child, month) / 'Processing' / 'Audio_Files' / filename


@lru_cache(maxsize=None)  # do this just once
def get_all_lena_5min_csv_paths():
    return _get_all_paths(get_single_file_function=get_lena_5min_csv_path,
                          missing_child_month_combinations=MISSING_AUDIO_RECORDINGS)


def _parse_out_child_and_month(file_path_or_name):
    file_name = Path(file_path_or_name).name
    child, month, *_ = file_name.split('_')
    return dict(child=int(child), month=int(month))


def split_recording_id(recording_id):
    """
    'Audio_06_12' -> 'Audio', '06', '12'
    :param recording_id: full recording id (e.g. Audio_06_12)
    :return: (str, str, str) tuple
    """
    modality, subject, month = recording_id.split('_')
    subject, month = _normalize_child_month(child=subject, month=month)
    _check_modality(modality)
    _check_subject_and_month(modality, subject, month)
    return modality, subject, month


@lru_cache(maxsize=None)  # do this just once
def get_all_basic_level_paths(modality):
    _check_modality(modality)
    if modality == AUDIO:
        missing_child_month_combinations = MISSING_AUDIO_RECORDINGS
    elif modality == VIDEO:
        missing_child_month_combinations = MISSING_VIDEO_RECORDINGS

    return _get_all_paths(get_single_file_function=get_basic_level_path,
                          missing_child_month_combinations=missing_child_month_combinations, modality=modality)


def get_its_path(child, month):
    child, month = _normalize_child_month(child=child, month=month)
    return _get_home_visit_folder(child=child, month=month) / 'Processing' / 'Audio_Files' / f'{child}_{month}.its'


def get_seedlings_nouns_private_path():
    """
    Returns path to the seedlings-nouns_private repo in BLAB_DATA.
    :return: ^this path.
    """
    path = get_blab_data_path() / 'seedlings-nouns_private/'
    if not path.exists():
        msg = (f'Couldn\'t locate folder\n'
               f'{path.absolute()}\n'
               f'Please clone the seedlings-nouns_private repo into this folder.')
        raise FileNotFoundError(msg)

    return path


def get_video_file_path(child, month, filename):
    """
    Returns path to one of the video files for that subject and month.
    :return: pathlib.Path object
    """
    child, month = _normalize_child_month(child=child, month=month)
    home_folder = _get_home_visit_folder(child=child, month=month)
    return home_folder / 'Processing' / 'Video_Files' / f'{child}_{month}_{filename}'


def get_video_recordings_csv_path():
    """
    Returns path to the video_recordings.csv file with date-times and durations of video recordings.
    :return: pathlib.Path object
    """
    return get_subject_files_folder() / 'video_recordings.csv'
