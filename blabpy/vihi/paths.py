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
