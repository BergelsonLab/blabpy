from ..paths import get_pn_opus_path


def get_vihi_path():
    """
    Finds the path to the VIHI folder on PN-OPUS
    :return: Path object
    """
    return get_pn_opus_path() / 'VIHI'


def get_subject_files_path():
    """
    Returns the path to the SubjectFiles folder within the VIHI folder
    :return: Path object
    """
    return get_vihi_path() / 'SubjectFiles'


def _get_modality_path(modality):
    """
    Return the path to a modality folder withing the SubjectFiles folder
    :return: Path object
    """
    return get_subject_files_path() / modality


def get_lena_path():
    """
    Returns the path to the LENA folder within the SubjectFiles folder
    :return: Path object
    """
    return _get_modality_path('LENA')
