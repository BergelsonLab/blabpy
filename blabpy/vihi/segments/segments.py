import random
import os
import shutil

import pandas as pd
import pympi

from blabpy.vihi.segments import templates


def _overlap(onset1, onset2, width):
    """
    Do the width-long segments starting with onset1 and onset2 overlap?
    (1, 2) and (2, 3) are considered to be non-overlapping.
    :param onset1: int, onset1 > 0, start of the first segment,
    :param onset2: int, onset2 != onset1 & onset2 > 0, start of the second segment,
    :param width: int, width > 0, their common duration
    :return: True/False
    """
    if onset2 < onset1 < onset2 + width:
        return True
    elif onset2 - width < onset1 < onset2:
        return True
    return False


def select_segments_randomly(total_duration, n=5, t=5, start=30, end=10):
    """
    Randomly selects n non-overlapping regions of length t that start not earlier than at minute start and not later
    than (total_duration - end).
    int total_duration: length of recording in minutes
    int n: number of random segments to choose
    int t: length of region of interest (including context)
    int start: minute at which the earliest segment can start
    return: a list of (onset, offset + t) tuples
    """
    candidate_onsets = list(range(start, min(total_duration - t, total_duration - end)))
    random.shuffle(candidate_onsets)
    selected_onsets = []
    for possible_onset in candidate_onsets:
        # Select onsets until we have the required number of segments
        if len(selected_onsets) >= n:
            break
        # Check that the candidate region would not overlap with any of the already selected ones
        if not any(_overlap(possible_onset, selected_onset, t) for selected_onset in selected_onsets):
            selected_onsets.append(possible_onset)

    return [(onset, onset + t) for onset in selected_onsets]


def create_eaf(etf_path, id, output_dir, segments_list, context_before=120000, context_after=60000):
    """
    Writes an eaf file <id>.eaf to the output_dir by adding segments to the etf template at etf_path.
    :param etf_path:
    :param id:
    :param output_dir:
    :param segments_list:
    :param context_before:
    :param context_after:
    :return:
    """
    eaf = pympi.Eaf(etf_path)

    # Create the tiers
    transcription_type = "transcription"
    eaf.add_tier("code", ling=transcription_type)
    eaf.add_tier("context", ling=transcription_type)
    eaf.add_tier("code_num", ling=transcription_type)
    eaf.add_tier("on_off", ling=transcription_type)

    # Add the segments
    for i, ts in enumerate(segments_list):
        whole_region_onset = ts[0]
        whole_region_offset = ts[1]
        roi_onset = whole_region_onset + context_before
        roi_offset = whole_region_offset - context_after
        eaf.add_annotation("code", roi_onset, roi_offset)
        eaf.add_annotation("code_num", roi_onset, roi_offset, value=str(i + 1))
        eaf.add_annotation("on_off", roi_onset, roi_offset, value="{}_{}".format(roi_onset, roi_offset))
        eaf.add_annotation("context", whole_region_onset, whole_region_offset)

    eaf.to_file(os.path.join(output_dir, "{}.eaf".format(id)))
    return eaf


def create_selected_regions_df(id, segments_list, context_before=120000, context_after=60000):
    selected = pd.DataFrame(columns=['id', 'clip_num', 'onset', 'offset'], dtype=int)
    for i, ts in enumerate(segments_list):
        selected = selected.append({'id': id,
                                    'clip_num': i + 1,
                                    'onset': ts[0] + context_before,
                                    'offset': ts[1] - context_after},
                                   ignore_index=True)
    selected[['clip_num', 'onset', 'offset']] = selected[['clip_num', 'onset', 'offset']].astype(int)
    return selected


def create_eafs_with_random_regions(info_spreadsheet_path, output_dir, seed=None):
    """
    Reads a list of recording for which eafs with randomly selected regions need to be created. Outputs an eaf and pfsx
    file for each row in that list. Additionally, creates a file "selected_regions.csv" which contains the info on the
    selected segments.

    :param info_spreadsheet_path: path to a csv that has the following columns:
     `age` with the child's age in months at the time of the recording,
     `length_of_recording` in minutes,
     `id`: recording identifier, such as VI_018_924
    :param output_dir: a directory where the eaf and pfsx files for each recording will be created and where
     "selected_regions.csv" will be stored as well
    :param seed: int, optional, random seed to be set before selecting random regions. Set only once, before processing
     all the recordings.
    :return: None
    """
    record_list = pd.read_csv(info_spreadsheet_path)
    if seed:
        random.seed(seed)

    for i, record in record_list.iterrows():
        print(record.index)
        # choose regions (5 by default)
        timestamps = select_segments_randomly(int(record.length_of_recording), n=15)
        timestamps = [(x * 60000, y * 60000) for x, y in timestamps]
        timestamps.sort(key=lambda tup: tup[0])
        print(timestamps)

        # retrieve correct templates for the age
        etf_template_path, pfsx_template_path = templates.choose_template(record.age)

        # create the output files
        # eaf with segments added
        create_eaf(etf_template_path, record.id, output_dir, timestamps)
        # copy the pfsx template
        pfsx_output_path = os.path.join(output_dir, f'{record.id}.pfsx')
        shutil.copy(pfsx_template_path, pfsx_output_path)
        # csv with the list of selected regions
        selected_regions_path = os.path.join(output_dir, f'{record.id}_selected-regions.csv')
        create_selected_regions_df(record.id, timestamps).to_csv(selected_regions_path, index=False)
