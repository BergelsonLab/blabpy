import random
import shutil
from pathlib import Path

from pyprojroot import find_root
import pandas as pd

from ..utils import OutputExistsError
from ..vihi.intervals.intervals import _create_objects_with_random_regions
from .paths import get_ovs_annotation_path

# Find the root of the project

OVS_ANNOTAIONS_FOLDER = get_ovs_annotation_path()

def _random_regions_output_files(seedlings_id):
    """
    Adapted from blabpy.vihi.intervals' function of the same name.

    Find the OvS annotations folder for each seedlings_id and list the output files as a dict,
    to be used by random sampling function.

    The output files include an eaf file, a pfsx file, and a csv file with the list of selected regions.
    """
    output_dir = OVS_ANNOTAIONS_FOLDER / f'OvS_{seedlings_id}'
    output_filenames = {
        'eaf': f'{seedlings_id}.eaf',
        'pfsx': f'{seedlings_id}.pfsx',
        'csv': f'selected_regions.csv'
    }
    return {extension: Path(output_dir) / filename
            for extension, filename in output_filenames.items()}


def create_files_with_random_regions(seedlings_id, age, length_of_recording, seed=None):
    """
    Adapted from blabpy.vihi.intervals' function of the same name

    Randomly samples 15 five-min long regions to be annotated and creates three files:
    - <seedlings_id>.eaf - ELAN file with annotations prepared for the sampled intervals,
    - <seedlings_id>.pfsx - ELAN preferences file,
    - <seedlings_id>_selected-regions.csv - a table with onset and offsets of the selected regions.
    Raises an OutputExistsError if any of the files already exists

    :param seedlings_id: id of the original seedlings file used by OvS, e.g. '15_17', '01_SF5', etc.
    :param age: age in months - will be used to select an .etf template
    :param length_of_recording: length of the actual file in minutes
    :param seed: random seed for reproducibility

    :return: None, writes files to the recording folder in VIHI
    """
    if seed:
        random.seed(seed)

    # check that none of the output files already exist
    output_file_paths = _random_regions_output_files(seedlings_id=seedlings_id)

    paths_exist = [path for path in output_file_paths.values() if path.exists()]
    if any(paths_exist):
        raise OutputExistsError(paths=paths_exist)

    eaf, intervals, pfsx_template_path = _create_objects_with_random_regions(age, length_of_recording)
    intervals.insert(0, 'recording_id', seedlings_id)

    # create the output files
    output_file_paths['eaf'].parent.mkdir(parents=True, exist_ok=True)

    # eaf with intervals added
    eaf.to_file(output_file_paths['eaf'])
    # copy the pfsx template
    shutil.copy(pfsx_template_path, output_file_paths['pfsx'])
    # csv with the list of selected regions
    intervals.to_csv(output_file_paths['csv'], index=False)

