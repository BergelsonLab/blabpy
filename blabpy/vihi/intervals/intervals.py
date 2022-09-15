import random
import shutil
from pathlib import Path

import numpy as np
import pandas as pd

from blabpy.eaf import EafPlus
from blabpy.utils import OutputExistsError
from blabpy.vihi.intervals import templates
from blabpy.vihi.paths import get_lena_recording_path, parse_full_recording_id

_ms_in_a_minute = 60 * 10**3
CONTEXT_BEFORE = 2 * _ms_in_a_minute
CODE_REGION = 2 * _ms_in_a_minute
CONTEXT_AFTER = 1 * _ms_in_a_minute

# Metric that is maximized when selecting high-volubility intervals
# TODO: use an actual metric
METRIC_TO_MAXIMIZE = 'fake_metric'
INTERVALS_FOR_ANNOTATION_COUNT = 15


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


# TODO: this function should take a list/dataframe with both code and context region boundaries, the current way is kind
#  of backwards.
# TODO: check for overlaps
def add_annotation_intervals_to_eaf(eaf, context_intervals_list):
    """
    Adds annotation intervals to an EafPlus object. The input is list of *full* intervals - including the context.
    :param eaf: EafPlus objects with tiers added, assumed to be empty
    :param context_intervals_list: list of (context_onset, context_offset) tuples
    :return: EafPlus object with intervals added.
    """
    # Figure out which code_num we should start with (it is last_code_num + 1)
    code_nums = [int(code_num) for code_num in eaf.get_values('code_num')]
    last_code_num = 0 if len(code_nums) == 0 else max(code_nums)

    # Sort new intervals by onset
    context_intervals_list = sorted(context_intervals_list)

    for i, (context_onset, context_offset) in enumerate(context_intervals_list, last_code_num + 1):
        code_onset = context_onset + CONTEXT_BEFORE
        code_offset = context_offset - CONTEXT_AFTER
        eaf.add_annotation("code", code_onset, code_offset)
        eaf.add_annotation("code_num", code_onset, code_offset, value=str(i))
        eaf.add_annotation("on_off", code_onset, code_offset, value="{}_{}".format(code_onset, code_offset))
        eaf.add_annotation("context", context_onset, context_offset)

    return eaf


def prepare_eaf_from_template(etf_template_path):
    """
    Loads eaf template, adds empty tiers and returns an EafPlus object ready for inserting annotation interval data.
    :param etf_template_path:
    :return: EafPlus object
    """
    # Load
    eaf = EafPlus(etf_template_path)

    # Add tiers
    transcription_type = "transcription"
    tier_ids = ('code', 'context', 'code_num', 'on_off')
    for tier_id in tier_ids:
        eaf.add_tier(tier_id=tier_id, ling=transcription_type)

    return eaf


def prepare_eaf_for_age(age_in_days):
    """
    Finds age-appropriate template and returns an EafPlus object ready for inserting annotation intervals data.
    :param age_in_days: int
    :return: an EafPlus object
    """
    etf_template_path, _ = templates.choose_template(age_in_days)
    return prepare_eaf_from_template(etf_template_path)


def create_eaf_from_template(etf_template_path, context_intervals_list):
    """
    Writes an eaf file <id>.eaf to the output_dir by adding intervals to the etf template at etf_path.
    :param etf_template_path: path to the .etf template file
    :param context_intervals_list: a list of (onset, offset) pairs corresponding to the whole interval, including the
    context.
    :return: an EafPlus objects with the code, code_num, on_off, and context annotations.
    code_num is the number of interval within the interval_list
    context onset and offset are those from the intervals_list - it includes the region to annotate
    """
    eaf = prepare_eaf_from_template(etf_template_path)
    eaf = add_annotation_intervals_to_eaf(eaf=eaf, context_intervals_list=context_intervals_list)
    return eaf


# TODO: This shouldn't be decoupled from creating the corresponding tiers. Do you want contradictory data? Because
#  that's how you get contradictory data.
# TODO: we'll want to use it for high-volubility regions too.
def create_selected_regions_df(full_recording_id, context_intervals_list):
    """
    Creates a dataframe with all the interval data added to an eaf - for logging purposes.
    :param full_recording_id: full recording id
    :param context_intervals_list: a list of (onset, offset) pairs corresponding to the whole interval, including the
    context.
    :return:
    """
    selected = pd.DataFrame(columns=['id', 'clip_num', 'onset', 'offset'], dtype=int)
    for i, ts in enumerate(context_intervals_list):
        selected = selected.append({'id': full_recording_id,
                                    'clip_num': i + 1,
                                    'onset': ts[0] + CONTEXT_BEFORE,
                                    'offset': ts[1] - CONTEXT_AFTER},
                                   ignore_index=True)
    selected[['clip_num', 'onset', 'offset']] = selected[['clip_num', 'onset', 'offset']].astype(int)
    return selected


def _region_output_files(full_recording_id):
    """
    Find the recording folder and list the output files as a dict.
    Factored out so we can check which files are already present during batch processing without creating random regions
    for the recordings that haven't been processed yet.
    :param full_recording_id:
    :return:
    """
    output_dir = get_lena_recording_path(**parse_full_recording_id(full_recording_id))
    output_filenames = {
        'eaf': f'{full_recording_id}.eaf',
        'pfsx': f'{full_recording_id}.pfsx',
        'csv': f'{full_recording_id}_selected-regions.csv'
    }
    return {extension: Path(output_dir) / filename
            for extension, filename in output_filenames.items()}


def create_files_with_random_regions(full_recording_id, age, length_of_recording):
    """
    Randomly samples INTERVALS_FOR_ANNOTATION_COUNT five-min long regions to be annotated and creates three files:
    - <full_recording_id>.eaf - ELAN file with annotations prepared for the sampled intervals,
    - <full_recording_id>.pfsx - ELAN preferences file,
    - <full_recording_id>_selected-regions.csv - a table with onset and offsets of the selected regions.
    Raises an OutputExistsError if any of the files already exist.
    :param full_recording_id: full recording id, e.g. 'TD_123_456'
    :param age: age in months - will be used to select an .etf template
    :param length_of_recording: length of the actual file in minutes
    :return: None, writes files to the recording folder in VIHI
    """
    # check that none of the output files already exist
    output_file_paths = _region_output_files(full_recording_id=full_recording_id)
    paths_exist = [path for path in output_file_paths.values() if path.exists()]
    if any(paths_exist):
        raise OutputExistsError(paths=paths_exist)

    # select random intervals
    timestamps = select_intervals_randomly(int(length_of_recording), n=INTERVALS_FOR_ANNOTATION_COUNT)
    timestamps = [(x * 60000, y * 60000) for x, y in timestamps]
    timestamps.sort(key=lambda tup: tup[0])

    # retrieve correct templates for the age
    etf_template_path, pfsx_template_path = templates.choose_template(age)

    # create an eaf object with the selected regions
    eaf = create_eaf_from_template(etf_template_path, timestamps)

    # create the output files
    # eaf with intervals added
    eaf.to_file(output_file_paths['eaf'])
    # copy the pfsx template
    shutil.copy(pfsx_template_path, output_file_paths['pfsx'])
    # csv with the list of selected regions
    create_selected_regions_df(full_recording_id, timestamps).to_csv(output_file_paths['csv'], index=False)


def batch_create_files_with_random_regions(info_spreadsheet_path, seed=None):
    """
    Reads a list of recordings for which eafs with randomly selected regions need to be created. Outputs an eaf, a pfsx,
    and a *_selected_regions.csv files for each recording.
    If any of the output files for any of the recordings already exist, the process is aborted.

    :param info_spreadsheet_path: path to a csv that has the following columns:
     `age` with the child's age in months at the time of the recording,
     `length_of_recording` in minutes,
     `id`: recording identifier, such as VI_018_924
    :param seed: int, optional, random seed to be set before selecting random regions. Set only once, before processing
     all the recordings. For testing purposes mostly.
    :return: None
    """
    if seed:
        random.seed(seed)

    recordings_df = pd.read_csv(info_spreadsheet_path)

    # Check that the output files don't yet exist
    def some_outputs_exist(full_recording_id_):
        return any(path.exists() for path in _region_output_files(full_recording_id=full_recording_id_).values())
    recordings_previously_processed = recordings_df.id[recordings_df.id.apply(some_outputs_exist)]
    if recordings_previously_processed.any():
        msg = ('The following recordings already have random region files:\n'
               + '\n'.join(recordings_previously_processed)
               + '\nAborting!')
        raise FileExistsError(msg)

    # Create random regions
    for _, recording in recordings_df.iterrows():
        create_files_with_random_regions(full_recording_id=recording.id, age=recording.age,
                                         length_of_recording=recording.length_of_recording)
        print(f'{recording.id}: random regions created.')


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
    sampling_frequency = int(audio.frame_rate)

    def compute_energy_loudness(single_channel_chunk):
        if low_freq > 0 or high_freq < 100000:
            chunk_fft = np.fft.fft(single_channel_chunk)
            freq = np.abs(np.fft.fftfreq(len(chunk_fft), 1 / sampling_frequency))
            chunk_fft = chunk_fft[(freq > low_freq) & (freq < high_freq)]
            return np.sum(np.abs(chunk_fft) ** 2) / len(single_channel_chunk)
        else:
            return np.sum(single_channel_chunk ** 2)

    channels = audio.channels
    max_value = 256 ** (int(audio.sample_width)) / 2 - 1

    chunk = audio[start:end].get_array_of_samples()
    channel_energies = np.zeros(channels)

    for channel in range(channels):
        channel_chunk = np.array(chunk[channel::channels]) / max_value
        channel_energies[channel] = compute_energy_loudness(single_channel_chunk=channel_chunk)

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


def _make_intervals_for_sub_recording(first_code_onset, last_code_offset, first_code_onset_wav):
    """
    Creates a sequence of intervals for one sub-recording.
    :param first_code_onset: datetime, onset of the first code region
    :param last_code_offset: datetime, offset of the first code region
    :param first_code_onset_wav: int, onset of the first code region in ms from the statt of the wav file
    :return:
    """
    return (pd.date_range(start=first_code_onset,
                          end=last_code_offset,
                          freq=f'{CODE_REGION}ms')
            .to_frame(index=False, name='code_onset')
            .assign(code_offset=lambda df: df.code_onset + pd.Timedelta(f'{CODE_REGION}ms'),
                    context_onset=lambda df: df.code_onset - pd.Timedelta(f'{CONTEXT_BEFORE}ms'),
                    context_offset=lambda df: df.code_offset + pd.Timedelta(f'{CONTEXT_AFTER}ms'),
                    since_first_code_ms=lambda df: (df.code_onset - first_code_onset).dt.total_seconds() * 1000,
                    code_onset_wav=lambda df: first_code_onset_wav + df.since_first_code_ms.astype(int))
            .drop(columns='since_first_code_ms'))


def make_intervals(sub_recordings):
    """
    Creates a population of all possible intervals to be sampled from.

    Assumptions that might become parameters later:

    - 2 minutes of buffer for context before the interval,
    - 2 minutes for the actual interval,
    - 1 minute of context after the interval,
    - start at hh:mm:00 where mm is divisible by CODE_REGION converted to minutes,
    - intervals sequence is continuous within each sub-recording and non-overlapping.

    :param sub_recordings: list of starts and ends of all sub-recordings as datetime columns `onset` and `offset` and
    an integer column `onset_wav` with the onset in ms from the start of the wav file.

    :return: pd.DataFrame with the following datetime columns: `code_onset`, `code_offset`, `context_onset`,
    and `context_offset` and an integer column `code_onset_wav` with the onset in ms from the start of the wav file.
    """
    # Find where first code region starts and last code region ends in each sub-recording
    starts_and_ends = (
        sub_recordings
        .assign(
            # Narrow the boundaries, so that there is enough space for the context.
            first_code_onset=lambda df: df.recording_start + pd.Timedelta(f'{CONTEXT_BEFORE}ms'),
            last_code_offset=lambda df: df.recording_end - pd.Timedelta(f'{CONTEXT_AFTER}ms'))
        .assign(
            # Round starts up and ends down to the closes whole number of code region durations:
            # (1:02:03, 7:45:00) -> (1:04:00, 7:44:00)
            first_code_onset=lambda df: df.first_code_onset.dt.ceil(f'{CODE_REGION}ms'),
            last_code_offset=lambda df: df.last_code_offset.dt.floor(f'{CODE_REGION}ms'),
            # Add first code region onset as ms from the wav start
            first_code_onset_recording=lambda df: (df.first_code_onset - df.recording_start).dt.total_seconds() * 1000,
            first_code_onset_wav=lambda df:
                df.recording_start_wav + df.first_code_onset_recording.astype(int)))

    # Create intervals within the boundaries we calculate above
    intervals = pd.concat(
        (_make_intervals_for_sub_recording(row.first_code_onset,
                                           row.last_code_offset,
                                           row.first_code_onset_wav)
         for _, row in starts_and_ends.iterrows()),
        ignore_index=True)

    return intervals


def add_metric(intervals, vtc_data):
    """
    For a given set of intervals calculates a metric based on VTC (.rttm) data. Works for a single recording only.

    Assumptions that might become parameters later:

    - the data source is vtc data for a single recording,
    - the metric is hard-coded.

    :param intervals: a dataframe with columns `onset`, `offset`, `onset_wav` (see, e.g., `make_intervals`)
    :param vtc_data: a dataframe with enough information to calculate the metric for a single recording.
    :return: copy of intervals with a new column containing the metric and being named after that metric

    Note: we already calculate energy here, now this metric, it might be a good idea to have a separate `metrics`
    module if we add more metrics.
    """
    # TODO: implement an actual metric
    return intervals.assign(**{METRIC_TO_MAXIMIZE: [2, 4, 3, 5, 1]})


# TODO: update after switching from context to dataframes with all interval data (code, context, code_num, etc.)
def select_best_intervals(intervals, not_overlapping_with=None):
    """
    Select INTERVALS_FOR_ANNOTATION_COUNT intervals, potentially non-overlapping with existing intervals.
    :param intervals: a dataframe with code intervals with metric calculated
    :param not_overlapping_with: list of (onset_wav, offset_wav) that selected intervals shouldn't overlap with
    :return: (context_intervals, ranks) where
      context_intervals - list of selected intervals as (context_onset, context_offset) tuples sorted by onsets.
      ranks - list of ranks of selected intervals. If there is no overlap with not_overlapping_with, this should be a
      list of numbers from 1 to INTERVALS_FOR_ANNOTATION_COUNT in order corresponding to context_intervals.
    """
    # Mark intervals that do not overlap with not_overlapping_with
    if not_overlapping_with is not None:
        is_not_overlapping = (
            intervals
            .assign(code_offset_wav=lambda df: df.code_onset_wav + CODE_REGION)
            .apply(lambda row:
                   all(row.code_offset_wav <= existing_onset
                       or row.code_onset_wav >= existing_offset
                       for (existing_onset, existing_offset)
                       in not_overlapping_with),
            axis='columns'))
    else:
        is_not_overlapping = pd.Series([True] * intervals.shape[0])

    # Check that we have enough intervals to sample from
    assert is_not_overlapping.sum() >= INTERVALS_FOR_ANNOTATION_COUNT

    best_intervals = (
        intervals[is_not_overlapping]
        .copy()
        .assign(maximized_metric=METRIC_TO_MAXIMIZE,
                value=lambda df: df[METRIC_TO_MAXIMIZE],
                rank=lambda df: df[METRIC_TO_MAXIMIZE].rank(method='first', ascending=False))
        .loc[lambda df: df['rank'] <= INTERVALS_FOR_ANNOTATION_COUNT]
        .drop(columns=METRIC_TO_MAXIMIZE)
        .reset_index(drop=True)
    )

    return best_intervals
