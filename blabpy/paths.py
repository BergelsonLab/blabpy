import os
from pathlib import Path

# Environment variables
PN_OPUS = 'PN_OPUS_PATH'


def get_pn_opus_path():
    """
    Tries to find PN-OPUS at the path set via an environment variable.
    If it is not set, looks at the standard mount point on MacOS: /Volumes/pn-opus
    :return: Path object pointing to the PN-OPUS network drive if found
    :raises: ValueError if drive not found
    """
    default_path = Path('/Volumes/pn-opus/')
    if PN_OPUS in os.environ:
        path = Path(os.environ[PN_OPUS])
    else:
        path = default_path

    if path.exists():
        return path
    else:
        raise ValueError(f'Could not locate PN-OPUS at {path}, check that VPN is connected and PN-OPUS is mounted.\n'
                         f'If this is not the correct location, set/update environment/shell variable {PN_OPUS}')
