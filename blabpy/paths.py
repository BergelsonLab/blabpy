import os
import platform
from pathlib import Path

# Environment variables
BLAB_SHARE_PATH_ENV = 'BLAB_SHARE_PATH'
BLAB_SHARE_NAME = 'Fas-Phyc-PEB-Lab'
# On macOS
DEFAULT_BLAB_SHARE_MOUNT_POINT = f'/Volumes/{BLAB_SHARE_NAME}/'
# On Windows, we can access the share directly
BLAB_SHARE_NETWORK_PATH = f'//sox4.university.harvard.edu/{BLAB_SHARE_NAME}/'


def get_blab_share_path():
    f"""
    Tries to find the BLab share:
    - Checks if {BLAB_SHARE_PATH_ENV} is set and if it is, tries that.
    - On MacOS, tries {DEFAULT_BLAB_SHARE_MOUNT_POINT}.
    - On Windows, tries {BLAB_SHARE_NETWORK_PATH}.
    :return: Path object pointing to the BLab share if it was found
    :raises: ValueError if it wasn't found
    """
    export_env_var_hint = f'export {BLAB_SHARE_PATH_ENV}=/path/to/BLab/share'
    unset_env_var_hint = f'unset {BLAB_SHARE_PATH_ENV}'

    env_path = os.environ.get(BLAB_SHARE_PATH_ENV)
    if env_path is not None:
        blab_share_path = Path(env_path)
        error_message = (
            f'Could not locate the BLab share at the path specified'
            f' in the environment variable {BLAB_SHARE_PATH_ENV}:\n\n'
            f'{env_path}\n\n'
            f'Please update this value or unset the variable to try the default path. To unset, run:\n\n',
            f'{unset_env_var_hint}\n\n'
            f'Alternatively, you can set the variable to the correct path like this:\n\n'
            f'{export_env_var_hint}\n\n')

    else:
        system = platform.system()
        if system == 'Windows':
            blab_share_path = Path(BLAB_SHARE_NETWORK_PATH)
        else:
            blab_share_path = Path(DEFAULT_BLAB_SHARE_MOUNT_POINT)

        error_message = (
            f'Could not locate the BLab share at\n'
            f'\n'
            f'{blab_share_path}\n'
            f'\n'
            f'Do the following to troubleshoot:\n'
            f'- Check that you are connected to vpn.harvard.edu/bergelsonlab.\n'
            f'  (note the "bergelsonlab" part)\n'
            f'- On MacOS:\n'
            f'  - Check that {BLAB_SHARE_NAME} is mounted.\n'
            f'  - Check that it is mounted to {DEFAULT_BLAB_SHARE_MOUNT_POINT}\n'
            f'\n'
            f'Alternatively, tell blabpy where the BLab share is on your system by setting the environment variable'
            f' {BLAB_SHARE_PATH_ENV} to the correct path like this (works in MacOS terminal with bash or zsh and in'
            f' git-bash:\n'
            f'\n'
            f'{export_env_var_hint}\n'
            f'\n')

    if blab_share_path.exists():
        return blab_share_path

    raise ValueError(error_message)


def get_blab_data_root_path():
    """Returns tht path to the BLAB_DATA fodler on the local computer"""
    path = Path('~/BLAB_DATA/').expanduser()
    msg = (f'Could not locate BLAB_DATA at {path}.'
           f' You may need to create this folder and clone the necessary repos.')
    assert path.exists(), msg
    return path
