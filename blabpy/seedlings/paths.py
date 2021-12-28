from functools import lru_cache
from pathlib import Path

from ..paths import get_pn_opus_path

AUDIO = 'Audio'
VIDEO = 'Video'
ALL_CHILDREN = range(1, 46 + 1)
ALL_MONTHS = range(6, 17 + 1)
ANNOTATION_FILE_COUNT = 527


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
     return _get_home_visit_folder() / 'Coding'


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


def _get_all_annotation_paths(modality):
    """
    Finds all the annotation files for given modality
    :return: list of Path objects
    """
    _check_modality(modality)
    if modality == AUDIO:
        get_path_function = get_cha_path
    elif modality == VIDEO:
        get_path_function = get_opf_path

    # Not all child-month combinations actually exist, so we want to catch any errors that this may cause and return
    # None instead.
    def try_to_get_path(child, month):
        try:
            return get_path_function(child=child, month=month)
        except FileNotFoundError:
            return None

    paths = [try_to_get_path(child=child, month=month)
             for child in ALL_CHILDREN for month in ALL_MONTHS]
    # Remove None's
    paths = [path for path in paths if path]

    # Check the count
    assert len(paths) == ANNOTATION_FILE_COUNT
    return paths


@lru_cache(maxsize=None)  # do this just once
def get_all_opf_paths():
    return _get_all_annotation_paths(modality=VIDEO)


@lru_cache(maxsize=None)  # do this just once
def get_all_cha_paths():
    return _get_all_annotation_paths(modality=AUDIO)


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
