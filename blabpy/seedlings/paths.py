from ..paths import get_pn_opus_path

AUDIO = 'Audio'
VIDEO = 'Video'


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


def _get_coding_folder(child, month):
    seedlings_path = get_seedlings_path()
    child, month = _normalize_child_month(child=child, month=month)
    child_month_dir = seedlings_path / 'Subject_Files' / child / f'{child}_{month}'
    return child_month_dir / 'Home_Visit' / 'Coding'


def _get_annotation_path(child, month, modality):
    """
    Finds path to the opf/cha files
    :param modality: 'Audio'/'Video'
    :return: Path object
    """
    coding_folder = _get_coding_folder(child=child, month=month)
    child, month = _normalize_child_month(child=child, month=month)
    assert modality in (AUDIO, VIDEO), f'Modality must be either Audio or Video but was {modality} instead'
    if modality == AUDIO:
        extension = 'cha'
    elif modality == VIDEO:
        extension = 'opf'

    path = coding_folder / f'{modality}_Annotation' / f'{child}_{month}_sparse_code.{extension}'
    assert path.exists()
    return path


def get_opf_path(child, month):
    return _get_annotation_path(child=child, month=month, modality=VIDEO)


def get_cha_path(child, month):
    return _get_annotation_path(child=child, month=month, modality=AUDIO)

