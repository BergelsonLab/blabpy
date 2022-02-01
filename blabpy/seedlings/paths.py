from functools import lru_cache
from pathlib import Path

from ..paths import get_pn_opus_path

AUDIO = 'Audio'
VIDEO = 'Video'
DROPPED_CHILDREN = (5, 24)
ALL_CHILDREN = tuple(child for child in range(1, 46 + 1) if child not in DROPPED_CHILDREN)
ALL_MONTHS = range(6, 17 + 1)
ANNOTATION_FILE_COUNT = 527
MISSING_AUDIO_RECORDINGS = ((22, 9),)
MISSING_VIDEO_RECORDINGS = ((17, 6),)


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


def _get_home_visit_folder(child, month):
    seedlings_path = get_seedlings_path()
    child, month = _normalize_child_month(child=child, month=month)
    child_month_dir = seedlings_path / 'Subject_Files' / child / f'{child}_{month}'
    return child_month_dir / 'Home_Visit'


def _get_coding_folder(child, month):
    return _get_home_visit_folder(child=child, month=month) / 'Coding'


def _get_analysis_folder(child, month):
    return _get_home_visit_folder(child=child, month=month) / 'Analysis'


def _check_modality(modality):
    assert modality in (AUDIO, VIDEO), f'Modality must be either Audio or Video but was {modality} instead'


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
             for child in ALL_CHILDREN for month in ALL_MONTHS
             if (child, month) not in missing_child_month_combinations]
    assert len(paths) == ANNOTATION_FILE_COUNT

    return paths


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


def _parse_out_child_and_month(file_path_or_name):
    file_name = Path(file_path_or_name).name
    child, month, *_ = file_name.split('_')
    return dict(child=int(child), month=int(month))


@lru_cache(maxsize=None)  # do this just once
def get_all_basic_level_paths(modality):
    _check_modality(modality)
    if modality == AUDIO:
        missing_child_month_combinations = MISSING_AUDIO_RECORDINGS
    elif modality == VIDEO:
        missing_child_month_combinations = MISSING_VIDEO_RECORDINGS

    return _get_all_paths(get_single_file_function=get_basic_level_path,
                          missing_child_month_combinations=missing_child_month_combinations, modality=modality)
