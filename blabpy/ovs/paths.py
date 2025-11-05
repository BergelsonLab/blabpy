import re
from pathlib import Path

from ..paths import get_blab_share_path

def get_ovs_path():
    """
    Finds the path to the folder on BLab share that contains the OverheardSpeech project
    :return: Path object
    """
    return get_blab_share_path() / 'OvSpeech' / 'SubjectFiles' / 'Seedlings' / 'overheard_speech'

def get_ovs_annotation_path():
    """
    Finds the path to the folder on BLab share that contains the OverheardSpeech annotation files
    :return: Path object
    """
    return get_ovs_path() / 'annotations'

def get_ovs_annotation_in_progress_path():
    """
    Finds the path to the folder on BLab share that contains the OverheardSpeech annotation files that are in progress
    :return: Path object
    """
    return get_ovs_path() / 'annotations-in-progress'