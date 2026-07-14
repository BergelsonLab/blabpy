import random
import shutil
from pathlib import Path

from pyprojroot import find_root
import pandas as pd

from ..utils import OutputExistsError
from ..vihi.intervals.intervals import _create_objects_with_random_regions, _overlap
from .paths import get_ovs_annotation_path, get_ovs_annotation_files, parse_ovs_id
from ..eaf.eaf_plus import EafPlus

# Find the root of the project

OVS_ANNOTAIONS_FOLDER = get_ovs_annotation_path()
_ms_in_a_minute = 60 * 10**3
CONTEXT_BEFORE = 2 * _ms_in_a_minute
CODE_REGION = 2 * _ms_in_a_minute
CONTEXT_AFTER = 1 * _ms_in_a_minute

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

def _overlap_different_width(onset1, onset2, offset1, offset2):
    """
    Do the two intervals (onset1, offset1), and (onset2, offset2) overlap?
    Similar to blabpy.vihi.intervals.intervals._overlap(), but for variable length intervals
    (1, 5) and (5, 6) are considered to be non-overlapping.
    :param onset1: int, onset1 > 0, start of the first interval,
    :param onset2: int, onset2 > 0, start of the second interval,
    :param offset1: int, offset1 > onset1 & offset1 > 0, end of the first interval,
    :param offset2: int, offset2 > onset2 & offset2 > 0, end of the second interval,
    :return: True/False
    """
    if onset1 == onset2:
        return True
    return onset1 < offset2 and onset2 < offset1

def select_intervals_with_exclusion(total_duration, excluded_intervals, n=5, t=5, start=30, end=10):
    '''
    Adapted from blabpy.vihi.intervals.intervals.select_intervals_randomly

    :param total_duration: length of recording in minutes
    :param excluded_intervals: a list of (onset, offset) intervals to exclude (in minutes)
    :param n: number of random intervals to choose
    :param t: length of region of interest (including context)
    :param start: minute at which the earliest interval can start
    :return: a list of (onset, offset + t) tuples
    '''
    candidate_onsets = list(range(start, min(total_duration - t, total_duration - end)))
    random.shuffle(candidate_onsets)
    selected_onsets = []
    for possible_onset in candidate_onsets:
        # Select onsets until we have the required number of intervals
        if len(selected_onsets) >= n:
            break
        # Check that the candidate region would not overlap with any of the already selected ones
        if not any(
            _overlap(possible_onset, selected_onset, t) for selected_onset in selected_onsets
        ) and not any(
            _overlap_different_width(possible_onset, possible_onset + t, ex_on, ex_off) for (ex_on, ex_off) in excluded_intervals
        ):
            selected_onsets.append(possible_onset)

    return [(onset, onset + t) for onset in selected_onsets]


def resample_intervals(eaf, excluded_intervals, length_in_minutes, n_new_intervals):
    '''
    Resamples intervals for OvS annotation by selecting new non-overlapping regions of the 
    current eaf file while excluding already annotated intervals 
    and any sections that need to be excluded.

    :param eaf: an EafPlus object representing the transcription file to be resampled
    :param excluded_intervals: list of (onset, offset) tuples in milliseconds to exclude
    :param length_in_minutes: int, total length of recording in minutes
    :param n_new_intervals: int, number of new intervals to sample

    :return: list of (onset, offset) tuples in minutes representing new selected intervals
    '''

    existing_intervals_with_context = eaf.get_time_intervals('context')

    # Generating new intervals
    excluded_intervals += existing_intervals_with_context
    excluded_intervals_min = [(onset / 60000, offset / 60000) for (onset, offset) in excluded_intervals]
    new_intervals = select_intervals_with_exclusion(length_in_minutes, excluded_intervals_min, n=n_new_intervals)

    return new_intervals

def adding_resampled_intervals(full_ovs_id, excluded_intervals, length_in_minutes, n_new_intervals, seed=None):
    """Append resampled annotation intervals to an existing OvS annotation file.

    This function reads the existing OvS annotation files on blab_share, 
    generates new non-overlapping intervals outside the excluded
    regions, and updates both the ELAN (.eaf) and selected regions (.csv) files.

    :param full_ovs_id: full OvS identifier, e.g. 'OvS_15_17'
    :param excluded_intervals: list of (onset, offset) intervals in milliseconds to exclude
    :param length_in_minutes: total recording duration in minutes
    :param n_new_intervals: number of new intervals to sample and add
    :param seed: optional random seed for reproducibility
    :return: None
    """

    if seed:
        random.seed(seed)

    annotation_files = get_ovs_annotation_files(full_ovs_id)
    eaf = EafPlus(annotation_files["eaf"])
    csv = pd.read_csv(annotation_files["csv"])

    subject_id = parse_ovs_id(full_ovs_id)["subject_id"]
    age = parse_ovs_id(full_ovs_id)["age"]
    seedlings_id = f"{subject_id}_{age}"
    
    # Generate new intervals
    new_intervals = resample_intervals(eaf, excluded_intervals, length_in_minutes, n_new_intervals)

    # Creating intervals datafrane
    timestamps = [(x * 60000, y * 60000) for x, y in new_intervals]
    timestamps.sort(key=lambda tup: tup[0])
    context_onsets, context_offsets = zip(*timestamps)
    intervals = pd.DataFrame.from_dict(dict(context_onset_wav=context_onsets, context_offset_wav=context_offsets))
    intervals.insert(0, 'code_onset_wav', intervals.context_onset_wav + CONTEXT_BEFORE)
    intervals.insert(1, 'code_offset_wav', intervals.context_offset_wav - CONTEXT_AFTER)
    intervals.insert(0, 'sampling_type', 'random')
    intervals.insert(0, 'recording_id', seedlings_id)

    # Adding new intervals to eaf and csv file
    # Figure out which code_num we should start with (it is last_code_num + 1)
    try:
        code_num_values = eaf.get_values('code_num')
        existing_code_nums = [int(code_num) for code_num in code_num_values]
    except ValueError as e:
        msg = f'All code num values should be integers, some of the following weren\'t\n{code_num_values}'
        raise ValueError(msg) from e
    
    last_code_num = 0 if len(existing_code_nums) == 0 else max(existing_code_nums)
    new_code_nums = list(range(last_code_num + 1, last_code_num + n_new_intervals + 1))

    # Sort new intervals by onset and assign code_num
    intervals = (intervals
                 .sort_values(by=['code_onset_wav', 'code_offset_wav'])
                 .assign(code_num=new_code_nums,
                         on_off=lambda df: df.code_onset_wav.astype(str) + '_' + df.code_offset_wav.astype(str)))

    # Add intervals to eaf file
    for _, row in intervals.iterrows():
        eaf.add_annotation("code", row.code_onset_wav, row.code_offset_wav)
        eaf.add_annotation("code_num", row.code_onset_wav, row.code_offset_wav, value=str(row.code_num))
        eaf.add_annotation("on_off", row.code_onset_wav, row.code_offset_wav, value=row.on_off)
        eaf.add_annotation("context", row.context_onset_wav, row.context_offset_wav)
        eaf.add_annotation("sampling_type", row.code_onset_wav, row.code_offset_wav, value=row.sampling_type)
    
    # Add intervals to csv selected regions sheet
    csv = pd.concat([csv, intervals], ignore_index=True)

    # Save eaf and csv file
    eaf.to_file(annotation_files["eaf"])
    csv.to_csv(annotation_files["csv"], index=False)



