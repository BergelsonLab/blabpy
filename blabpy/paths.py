import os
from pathlib import Path

# Environment variables
PN_OPUS_PATH_ENV = 'PN_OPUS_PATH'
DEFAULT_PN_OPUS_PATHS = ['/Volumes/pn-opus/', 'Z:\\']


def _get_pn_opus_path_error(checked_paths):
    """
    Builds an error raised when `get_pn_opus_path` fails.
    :param checked_paths: Checked paths as a list of strings.
    :return: A ValueError with a hopefully useful message.
    """
    error_message = (
        'Could not locate PN-OPUS at any of the following paths:\n'
        f'\n- {", ".join(checked_paths)}\n'
    )

    troubleshooting_steps = (
        'Follow these steps:\n'
        '- Check that you are connected to the Duke VPN.\n'
        '- Check that PN-OPUS is mounted.\n'
        '- Check that it is mounted to one of the default locations:\n'
        f'\n  - {", ".join(checked_paths)}\n'
        f'\n  If it is mounted elsewhere, either remount it or set an'
        f'\n  environment variable {PN_OPUS_PATH_ENV} to the mount location.'
        '- Check that it has a special `.pn_opus` file in the root. If not,\n'
        'create it (the contents don\'t matter)'
    )

    return ValueError(error_message + '\n' + troubleshooting_steps)


def get_pn_opus_path():
    """
    Tries to find PN-OPUS:
    - At the path set via the environment variable PN_OPUS_PATH if it is set.
    - Tries DEFAULT_PN_OPUS_PATHS.
    :return: Path object pointing to the PN-OPUS network drive if found
    :raises: ValueError if drive not found
    """
    str_pn_opus_path = os.environ.get(PN_OPUS_PATH_ENV)
    if str_pn_opus_path:
        str_paths = [str_pn_opus_path]
    else:
        str_paths = list()
    str_paths = str_paths + DEFAULT_PN_OPUS_PATHS

    for str_path in str_paths:
        path = Path(str_path)
        if path.exists() and (path / '.pn_opus').exists():
            return path
    else:
        raise _get_pn_opus_path_error(checked_paths=str_paths)


def get_blab_data_path():
    """Returns tht path to the BLAB_DATA folder on the local computer"""
    path = Path('~/BLAB_DATA/').expanduser()
    msg = (f'Could not locate BLAB_DATA at {path}.'
           f' You may need to create this folder and clone the necessary repos.')
    assert path.exists(), msg
    return path
