"""
Functions that let us run certain os/system operations and not think which platform they are run on.
"""
import sys
from pathlib import Path


class UserIdLookupError(Exception):
    pass


def _get_owner_id_win(folder: Path):
    from win32 import win32security
    import pywintypes

    try:
        # Get the security descriptor for the folder
        sd = win32security.GetFileSecurity(str(folder), win32security.OWNER_SECURITY_INFORMATION)

        # Get the owner ID
        owner_sid = sd.GetSecurityDescriptorOwner()

        return str(owner_sid)

    except pywintypes.error:
        raise UserIdLookupError()


def _get_owner_id_not_win(folder: Path):
    return folder.stat().st_uid


def get_owner_id(folder: Path):
    """
    Return user ID of the owner of the folder.
    :param folder: Path to the folder.
    :return: A string with the owner's id.
    """

    if sys.platform == 'win32':
        return _get_owner_id_win(folder)
    else:
        return _get_owner_id_not_win(folder)
