from ..paths import get_pn_opus_path


def get_seedlings_path():
    """
    Finds the path to the Seedlings folder on PN-OPUS
    :return: Path object
    """
    return get_pn_opus_path() / 'Seedlings'
