import random
import shutil
from pathlib import Path

import numpy as np
import pandas as pd

from blabpy.eaf import EafPlus
from blabpy.utils import OutputExistsError
from blabpy.vihi.intervals import templates
from blabpy.vihi.paths import get_lena_recording_path, parse_full_recording_id
from blabpy.utils import df_to_list_of_tuples

_ms_in_a_minute = 60 * 10**3
CONTEXT_BEFORE = 2 * _ms_in_a_minute
CODE_REGION = 2 * _ms_in_a_minute
CONTEXT_AFTER = 1 * _ms_in_a_minute
INTERVALS_FOR_ANNOTATION_COUNT = 15
INTERVALS_EXTRA_COUNT = 5


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


def two_lists_of_intervals_overlap(list1, list2):
    """
    Checks whether two lists of intervals (order tuples of numbers)
    :param list1: list 1
    :param list2: list 2
    :return: boolean
    """
    def overlaps_with_list2(start1, end1):
        return any(start1 < end2 and end1 > start2
                   for start2, end2
                   in list2)

    return any(overlaps_with_list2(start1, end1)
               for start1, end1
               in list1)


# TODO: this function should take a list/dataframe with both code and context region boundaries, the current way is kind
#  of backwards.
def add_annotation_intervals_to_eaf(eaf, intervals):
    """
    Adds annotation intervals to an EafPlus object. The input is list of *full* intervals - including the context.
    :param eaf: EafPlus objects with tiers added, assumed to be empty
    :param intervals: dataframe with at least the following columns:
        'code_onset_wav', 'code_offset_wav', 'context_onset_wav', 'context_offset_wav', 'sampling_type'
    :return: EafPlus object with intervals added.
    """
    # Check for overlaps with existing code intervals
    existing_code_intervals_list = eaf.get_time_intervals('code')
    new_code_intervals_list = df_to_list_of_tuples(intervals[['code_onset_wav', 'code_offset_wav']])
    assert not two_lists_of_intervals_overlap(existing_code_intervals_list, new_code_intervals_list)

    # Figure out which code_num we should start with (it is last_code_num + 1)
    try:
        code_num_values = eaf.get_values('code_num')
        existing_code_nums = [int(code_num) for code_num in code_num_values]
    except ValueError as e:
        msg = f'All code num values should be integers, some of the following weren\'t\n{code_num_values}'
        raise ValueError(msg) from e

    last_code_num = 0 if len(existing_code_nums) == 0 else max(existing_code_nums)
    n_intervals_to_add = intervals.shape[0]
    new_code_nums = list(range(last_code_num + 1, last_code_num + n_intervals_to_add + 1))

    # Sort new intervals by onset and assign code_num
    intervals = (intervals
                 .sort_values(by=['code_onset_wav', 'code_offset_wav'])
                 .assign(code_num=new_code_nums,
                         on_off=lambda df: df.code_onset_wav.astype(str) + '_' + df.code_offset_wav.astype(str)))

    # Add intervals
    for _, row in intervals.iterrows():
        eaf.add_annotation("code", row.code_onset_wav, row.code_offset_wav)
        eaf.add_annotation("code_num", row.code_onset_wav, row.code_offset_wav, value=str(row.code_num))
        eaf.add_annotation("on_off", row.code_onset_wav, row.code_offset_wav, value=row.on_off)
        eaf.add_annotation("context", row.context_onset_wav, row.context_offset_wav)
        eaf.add_annotation("sampling_type", row.code_onset_wav, row.code_offset_wav, value=row.sampling_type)

    return eaf, intervals


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
    tier_ids = ('code', 'context', 'code_num', 'on_off', 'sampling_type')
    for tier_id in tier_ids:
        eaf.add_tier(tier_id=tier_id, ling=transcription_type)

    return eaf


def create_eaf_from_template(etf_template_path, intervals):
    """
    Writes an eaf file <id>.eaf to the output_dir by adding intervals to the etf template at etf_path.
    :param etf_template_path: path to the .etf template file
    :param intervals: dataframe with at least the following columns:
        'code_onset_wav', 'code_offset_wav', 'context_onset_wav', 'context_offset_wav'
    :return: an EafPlus objects with the code, code_num, on_off, and context annotations.
    code_num is the number of interval within the interval_list
    context onset and offset are those from the intervals_list - it includes the region to annotate
    """
    eaf = prepare_eaf_from_template(etf_template_path)
    eaf, intervals = add_annotation_intervals_to_eaf(eaf=eaf, intervals=intervals)
    return eaf, intervals


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
        'csv': f'selected_regions.csv'
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
    context_onsets, context_offsets = zip(*timestamps)
    intervals = pd.DataFrame.from_dict(dict(context_onset_wav=context_onsets, context_offset_wav=context_offsets))
    intervals.insert(0, 'code_onset_wav', intervals.context_onset_wav + CONTEXT_BEFORE)
    intervals.insert(1, 'code_offset_wav', intervals.context_offset_wav - CONTEXT_AFTER)
    intervals.insert(0, 'full_recording_id', full_recording_id)
    intervals.insert(1, 'sampling_type', 'random')

    # retrieve correct templates for the age
    etf_template_path, pfsx_template_path = templates.choose_template(age_in_months=age)

    # create an eaf object with the selected regions
    eaf, intervals = create_eaf_from_template(etf_template_path, intervals)

    # create the output files
    # eaf with intervals added
    eaf.to_file(output_file_paths['eaf'])
    # copy the pfsx template
    shutil.copy(pfsx_template_path, output_file_paths['pfsx'])
    # csv with the list of selected regions
    intervals.to_csv(output_file_paths['csv'], index=False)


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
    For a given set of intervals calculates vtc_total_speech_duration. Works for a single recording only.

    :param intervals: a dataframe with columns `onset`, `offset`, `onset_wav` (see, e.g., `make_intervals`)
    :param vtc_data: a dataframe with VTC output for the corresponding recording
    :return: copy of intervals with a new column containing the new column 'vtc_total_speech_duration'

    Note: we already calculate energy here, now this metric, it might be a good idea to have a separate `metrics`
    module if we add more metrics.
    """
    # VTC knows nothing about no local time or sub-recordings, just the wav time. So we'll need to know when
    # intervals start and end with respect to the beginning of the wav file.
    original_columns = intervals.columns.to_list()  # we'll need them later to remove all the extra columns
    intervals = intervals.assign(
        duration_ms=lambda df: (df.code_offset - df.code_onset).dt.total_seconds() * 1000,
        code_offset_wav=lambda df: df.code_onset_wav + df.duration_ms)

    vtc_data = (vtc_data
                # We only need the speech segments
                .loc[lambda df: df.voice_type == 'SPEECH']
                # The vtc_data dataframe has 'onset' and 'duration' in seconds and these columns are of type str.
                # We'll need to parse them to floats and convert to ms.
                .assign(vtc_segment_onset_wav=lambda df: (df.onset.astype(float) * 1000).astype(int),
                        duration_ms=lambda df: (df.duration.astype(float) * 1000).astype(int),
                        # Now we can calculate the segment offset in ms
                        vtc_segment_offset_wav=lambda df: df.vtc_segment_onset_wav + df.duration_ms))

    # We'll do a full cartesian product of intervals and VTC segments and then remove pairs that don't overlap.
    return (pd.merge(intervals, vtc_data, how='cross')
            # Keep only overlapping pairs of intervals and segments
            .loc[lambda df: (df.code_onset_wav < df.vtc_segment_offset_wav)
                 & (df.code_offset_wav > df.vtc_segment_onset_wav)]
            # We only want to count the duration of the overlapping part towards the total duration in an interval.
            .assign(overlap_duration=lambda df:
                    df[['code_offset_wav', 'vtc_segment_offset_wav']].min(axis='columns')
                    - df[['code_onset_wav', 'vtc_segment_onset_wav']].max(axis='columns'))
            # Finally, we'll add up durations of the overlapping parts
            .groupby(original_columns, as_index=False)
            .overlap_duration.sum()
            .rename(columns=dict(overlap_duration='vtc_total_speech_duration'))
            # And convert original columns from a multi-index to columns
            .reset_index()
            # Covert to seconds for consistency with `blabr::get_vtc_speaker_stats`
            .assign(vtc_total_speech_duration=lambda df: df.vtc_total_speech_duration / 1000)
            )


def convert_column_to_wav_time(datetimes: pd.Series, code_onset: pd.Series, code_onset_wav: pd.Series):
    """
    Converts datetimes to time in milliseconds from the wav file start.
    :param datetimes: datetimes to convert
    :param code_onset: datetimes for which we now their wav-based version
    :param code_onset_wav: that's code_onset's wav-based version
    :return: pd.Series of integer values
    """
    ms_since_code_onset = ((datetimes - code_onset).dt.total_seconds() * 1000).astype(int)
    return code_onset_wav + ms_since_code_onset


def convert_df_to_wav_time(df):
    """
    Converts 'code_onset', 'code_offset', 'context_onset', 'context_offset' to their *_wav versions and removes them.
    :param df:
    :return:
    """
    datetime_columns = ['code_onset', 'code_offset', 'context_onset', 'context_offset']
    for column in datetime_columns:
        df[f'{column}_wav'] = convert_column_to_wav_time(df[column], df.code_onset, df.code_onset_wav)

    return df.drop(columns=datetime_columns)


def select_best_intervals(intervals, n_to_select, existing_code_intervals=None):
    """
    Select INTERVALS_FOR_ANNOTATION_COUNT intervals, potentially non-overlapping with existing intervals.
    :param intervals: a dataframe with code intervals with vtc_total_speech_duration calculated
    :param n_to_select: how many intervals should be selected
    :param existing_code_intervals: list of (onset_wav, offset_wav) that selected intervals shouldn't overlap with
    :return: (context_intervals, ranks) where
      context_intervals - list of selected intervals as (context_onset, context_offset) tuples sorted by onsets.
      ranks - list of ranks of selected intervals. If there is no overlap with existing_code_intervals, this should be a
      list of numbers from 1 to INTERVALS_FOR_ANNOTATION_COUNT in order corresponding to context_intervals.
    """
    intervals = convert_df_to_wav_time(intervals)
    metric_to_maximize = 'vtc_total_speech_duration'

    # Mark intervals that do not overlap with existing_code_intervals
    if existing_code_intervals is not None:
        is_not_overlapping = (
            intervals
            .apply(lambda row:
                   all(row.code_offset_wav <= existing_onset
                       or row.code_onset_wav >= existing_offset
                       for (existing_onset, existing_offset)
                       in existing_code_intervals),
                   axis='columns'))
    else:
        is_not_overlapping = pd.Series([True] * intervals.shape[0])

    # Check that we have enough intervals to sample from
    assert is_not_overlapping.sum() >= n_to_select

    best_intervals = (
        intervals
        # We'll rank the intervals before removing the overlapping ones so that we have information about how many we
        # had to skip.
        .assign(rank=lambda df: df[metric_to_maximize].rank(method='first', ascending=False))
        .loc[is_not_overlapping]
        .copy()
        .assign(maximized_metric=metric_to_maximize,
                metric_value=lambda df: df[metric_to_maximize],
                # rank2 will be used to select best intervals after removing overlapping ones
                rank2=lambda df: df[metric_to_maximize].rank(method='first', ascending=False))
        .loc[lambda df: df['rank2'] <= n_to_select]
        .drop(columns=[metric_to_maximize, 'rank2'])
        .reset_index(drop=True)
    )

    return best_intervals


def _extract_interval_info(eaf: EafPlus):
    """
    Extracts info from all ACLEW tiers for all intervals already in eaf.
    :param eaf: eaf to extract info from
    :return: pd.DataFrame with the following columns: code_onset, code_offset, context_onset, context_offset, code_num, on_off
    """
    code_intervals = eaf.get_time_intervals('code')
    code_onsets, code_offsets = zip(*code_intervals)

    context_intervals = eaf.get_time_intervals('context')
    context_onsets, context_offsets = zip(*context_intervals)

    code_nums = eaf.get_values('code_num')
    on_offs = eaf.get_values('on_off')
    sampling_types = eaf.get_values('sampling_type')

    return pd.DataFrame.from_dict(dict(
        sampling_type=sampling_types,
        code_onset_wav=code_onsets,
        code_offset_wav=code_offsets,
        context_onset_wav=context_onsets,
        context_offset_wav=context_offsets,
        code_num=code_nums,
        on_off=on_offs))
