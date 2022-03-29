import os
import random
import shutil
from pathlib import Path

import numpy as np
import pandas as pd
import pympi

from blabpy.utils import OutputExistsError
from blabpy.vihi.intervals import templates


def _overlap(onset1, onset2, width):
    """
    Do the width-long intervals starting with onset1 and onset2 overlap?
    (1, 2) and (2, 3) are considered to be non-overlapping.
    :param onset1: int, onset1 > 0, start of the first interval,
    :param onset2: int, onset2 != onset1 & onset2 > 0, start of the second interval,
    :param width: int, width > 0, their common duration
    :return: True/False
    """
    if onset2 < onset1 < onset2 + width:
        return True
    elif onset2 - width < onset1 < onset2:
        return True
    return False


def select_intervals_randomly(total_duration, n=5, t=5, start=30, end=10):
    """
    Randomly selects n non-overlapping regions of length t that start not earlier than at minute start and not later
    than (total_duration - end).
    int total_duration: length of recording in minutes
    int n: number of random intervals to choose
    int t: length of region of interest (including context)
    int start: minute at which the earliest interval can start
    return: a list of (onset, offset + t) tuples
    """
    candidate_onsets = list(range(start, min(total_duration - t, total_duration - end)))
    random.shuffle(candidate_onsets)
    selected_onsets = []
    for possible_onset in candidate_onsets:
        # Select onsets until we have the required number of intervals
        if len(selected_onsets) >= n:
            break
        # Check that the candidate region would not overlap with any of the already selected ones
        if not any(_overlap(possible_onset, selected_onset, t) for selected_onset in selected_onsets):
            selected_onsets.append(possible_onset)

    return [(onset, onset + t) for onset in selected_onsets]


def create_eaf(etf_path, intervals_list, context_before=120000, context_after=60000):
    """
    Writes an eaf file <id>.eaf to the output_dir by adding intervals to the etf template at etf_path.
    :param etf_path:
    :param intervals_list:
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

    # Add the intervals
    for i, ts in enumerate(intervals_list):
        whole_region_onset = ts[0]
        whole_region_offset = ts[1]
        roi_onset = whole_region_onset + context_before
        roi_offset = whole_region_offset - context_after
        eaf.add_annotation("code", roi_onset, roi_offset)
        eaf.add_annotation("code_num", roi_onset, roi_offset, value=str(i + 1))
        eaf.add_annotation("on_off", roi_onset, roi_offset, value="{}_{}".format(roi_onset, roi_offset))
        eaf.add_annotation("context", whole_region_onset, whole_region_offset)

    return eaf


def create_selected_regions_df(id, intervals_list, context_before=120000, context_after=60000):
    selected = pd.DataFrame(columns=['id', 'clip_num', 'onset', 'offset'], dtype=int)
    for i, ts in enumerate(intervals_list):
        selected = selected.append({'id': id,
                                    'clip_num': i + 1,
                                    'onset': ts[0] + context_before,
                                    'offset': ts[1] - context_after},
                                   ignore_index=True)
    selected[['clip_num', 'onset', 'offset']] = selected[['clip_num', 'onset', 'offset']].astype(int)
    return selected


def create_files_with_random_regions(recording_id, age, length_of_recording, output_dir):
    # choose regions (5 by default)
    timestamps = select_intervals_randomly(int(length_of_recording), n=15)
    timestamps = [(x * 60000, y * 60000) for x, y in timestamps]
    timestamps.sort(key=lambda tup: tup[0])
    print(timestamps)

    # retrieve correct templates for the age
    etf_template_path, pfsx_template_path = templates.choose_template(age)

    # create an eaf object with the selected regions
    eaf = create_eaf(etf_template_path, timestamps)

    # check that none of the output files already exist
    output_filenames = {
        'eaf': f'{recording_id}.eaf',
        'pfsx': f'{recording_id}.pfsx',
        'csv': f'{recording_id}_selected-regions.csv'
    }
    output_file_paths = {extension: Path(output_dir) / filename
                         for extension, filename in output_filenames.items()}

    paths_exist = [path for path in output_file_paths.values() if path.exists()]
    if any(paths_exist):
        raise OutputExistsError(paths=paths_exist)

    # create the output files
    # eaf with intervals added
    eaf.to_file(os.path.join(output_dir, output_file_paths['eaf']))
    # copy the pfsx template
    shutil.copy(pfsx_template_path, output_file_paths['pfsx'])
    # csv with the list of selected regions
    create_selected_regions_df(recording_id, timestamps).to_csv(output_file_paths['csv'], index=False)


def batch_create_files_with_random_regions(info_spreadsheet_path, output_dir, seed=None):
    """
    Reads a list of recording for which eafs with randomly selected regions need to be created. Outputs an eaf and pfsx
    file for each row in that list. Additionally, creates a file "selected_regions.csv" which contains the info on the
    selected intervals.

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
    if seed:
        random.seed(seed)

    recordings_df = pd.read_csv(info_spreadsheet_path)
    output_exists_errors = []
    for _, recording in recordings_df.iterrows():
        try:
            create_files_with_random_regions(recording_id=recording.id, age=recording.age,
                                             length_of_recording=recording.length_of_recording,
                                             output_dir=output_dir)
        except OutputExistsError as e:
            output_exists_errors.append(e)

    if output_exists_errors:
        raise OutputExistsError(paths=[path for error in output_exists_errors for path in error.paths])


def calculate_energy_in_one_interval(start, end, audio, low_freq: int = 0, high_freq: int = 100000):
    """
    Calculates energy from start to end from a recording loaded into memory.
    NB: The code is copied almost verbatim from ChildProject's energy-based sampler code.
    :param high_freq: upper frequency
    :param low_freq: lower frequency limit
    :param start: start in milliseconds
    :param end: end in milliseconds
    :param audio: pydub.AudioSegment object
    :return: float - energy in the interval
    """
    def compute_energy_loudness(chunk, sampling_frequency: int, low_freq: int = 0, high_freq: int = 100000):
        if low_freq > 0 or high_freq < 100000:
            chunk_fft = np.fft.fft(chunk)
            freq = np.abs(np.fft.fftfreq(len(chunk_fft), 1 / sampling_frequency))
            chunk_fft = chunk_fft[(freq > low_freq) & (freq < high_freq)]
            return np.sum(np.abs(chunk_fft) ** 2) / len(chunk)
        else:
            return np.sum(chunk ** 2)

    channels = audio.channels
    sampling_frequency = int(audio.frame_rate)
    max_value = 256 ** (int(audio.sample_width)) / 2 - 1

    chunk = audio[start:end].get_array_of_samples()
    channel_energies = np.zeros(channels)

    for channel in range(channels):
        data = np.array(chunk[channel::channels]) / max_value
        channel_energies[channel] = compute_energy_loudness(chunk=data, sampling_frequency=sampling_frequency,
                                                            low_freq=low_freq, high_freq=high_freq)

    energy = np.sum(channel_energies)
    return energy


def calculate_energy_in_all_intervals(intervals, audio, low_freq: int = 0, high_freq: int = 100000):
    """
    Calculates energy in audio for each interval in intervals.
    :param high_freq: see calculate_energy_in_one_interval
    :param low_freq: see calculate_energy_in_one_interval
    :param intervals: a pandas dataframe containing "start" and "end" columns in seconds
    :param audio: pydub.AudioSegment object
    :return: a pandas Series object
    """
    return intervals.apply(lambda row:
                           calculate_energy_in_one_interval(start=row.start, end=row.end, audio=audio,
                                                            low_freq=low_freq, high_freq=high_freq),
                           axis='columns')