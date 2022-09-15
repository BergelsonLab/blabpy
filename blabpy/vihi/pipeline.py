"""
This module contains function that interact with files - either reading or writing them. The idea is that all the
other function are supposed to be pure. That is not true at all at this time though.
"""
from pathlib import Path

from .intervals.intervals import add_metric, make_intervals, add_annotation_intervals_to_eaf, _region_output_files, \
    select_best_intervals, CONTEXT_BEFORE, CODE_REGION, CONTEXT_AFTER, _extract_interval_info, \
    create_selected_regions_df
from ..its import Its
from .paths import get_its_path, parse_full_recording_id, get_eaf_path
from ..vtc import read_rttm
from ..eaf import EafPlus


INTERVAL_SAMPLE_COUNT = 15


def gather_recordings(full_recording_id):
    """
    Gets sub-recordings for a given single recording. See Its.gather_recordings for details.
    """
    its_path = get_its_path(**parse_full_recording_id(full_recording_id))
    its = Its.from_path(its_path)
    return its.gather_recordings()


# TODO: these function don't need to exist. Just add full_recording_id as an alternative argument to all the get_*
#  functions in vihi.paths. It should be part of the future decorator that checks the arguments (see issue #18).
def get_vtc_data(full_recording_id):
    """
    Get VTC data for a given recording.
    :param full_recording_id: a string of '{population}_{subject}_{recording_id}' format.
    :return: a pandas dataframe with all the data from the VTC outputs (.rttm files).
    """
    rttm_path = get_vtc_data(**parse_full_recording_id(full_recording_id))
    return read_rttm(rttm_path)


def get_eaf_path(full_recording_id):
    """
    Find annotations eaf for a given recording.
    :param full_recording_id:
    :return:
    """
    return get_eaf_path(**parse_full_recording_id(full_recording_id))


class NoPreviousEaf(Exception):
    pass


def _load_eaf(full_recording_id: Path):
    """
    Loads eaf if it exists, otherwise throws an error
    :param full_recording_id: full recording id
    :return: a blabpy.eaf.EafPlus object
    :raises: NoPreviousEaf
    """
    eaf_path = get_eaf_path(full_recording_id)
    try:
        eaf = EafPlus(eaf_path)
    except FileNotFoundError as e:
        raise NoPreviousEaf(f'There is no eaf file where we expected to find it:\n{eaf_path}') from e

    return eaf


# TODO: this function should handle both random and high-volubility sampling
def add_intervals_for_annotation(full_recording_id):
    """
    For a given recording, finds the intervals that maximize vtc_total_speech_duration - total duration of all speech
    segments as classified by VTC.
    Then adds them to the corresponding eaf file.
    :param full_recording_id: full recording id, string
    :return: None
    """
    # Prepare intervals to select from
    intervals = make_intervals(sub_recordings=gather_recordings(full_recording_id))
    vtc_data = get_vtc_data(full_recording_id)
    intervals = add_metric(intervals=intervals, vtc_data=vtc_data)

    # Load existing intervals
    eaf = _load_eaf(full_recording_id)
    intervals_info = _extract_interval_info(eaf)
    existing_code_intervals = list(intervals_info[['code_onset', 'code_offset']].to_records(index=False))

    # Select intervals that maximize vtc_total_speech_duration
    best_intervals = select_best_intervals(intervals, existing_code_intervals=existing_code_intervals)
    # TODO: best intervals is self-contained, everything should be calculated only using data in it, not reapplying the
    #  constants
    context_intervals_list = [
        (code_onset_wav - CONTEXT_BEFORE,
         code_onset_wav + CODE_REGION + CONTEXT_AFTER)
        for code_onset_wav
        in best_intervals.code_onset_wav]
    eaf = add_annotation_intervals_to_eaf(eaf, context_intervals_list)
    all_intervals = _extract_interval_info(eaf)

    # Save files
    output_file_paths = _region_output_files(full_recording_id=full_recording_id)
    eaf.to_file(output_file_paths['eaf'])

    all_context_intervals = list(all_intervals[['context_onset', 'context_offset']].to_records(index=False))
    selected_regions_df = create_selected_regions_df(full_recording_id, context_intervals_list=all_context_intervals,
                                                     code_nums=all_intervals.code_num.to_list())
    selected_regions_df.to_csv(output_file_paths['csv'], index=False)
