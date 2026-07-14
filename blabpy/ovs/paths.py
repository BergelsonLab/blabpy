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

def parse_ovs_id(full_ovs_id):
    components = full_ovs_id.split("_")
    if len(components) != 3:
        raise ValueError(f"A full OvS id needs to be of the form 'OvS_id_age'. Received: {full_ovs_id}.")
    if components[0].upper() != "OVS":
        raise ValueError(f"A full OvS id needs to be of the form 'OvS_id_age', beginning with 'OvS'. Received: {full_ovs_id}.")
    return dict(subject_id=components[1], age=components[2])

def get_ovs_annotation_files(full_ovs_id):
    id_components = parse_ovs_id(full_ovs_id)
    subject_id = id_components["subject_id"]
    age = id_components["age"]
    eaf_path = get_ovs_annotation_path() / full_ovs_id / f"{subject_id}_{age}.eaf"
    intervals_path = get_ovs_annotation_path() / full_ovs_id / "selected_regions.csv"

    return dict(eaf=eaf_path, csv=intervals_path)