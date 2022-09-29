"""
This module contains function that interact with files - either reading or writing them. The idea is that all the
other function are supposed to be pure. That is not true at all at this time though.
"""
from pathlib import Path

import numpy as np
import pandas as pd

from .intervals.intervals import add_metric, make_intervals, add_annotation_intervals_to_eaf, _region_output_files, \
    select_best_intervals, _extract_interval_info, INTERVALS_FOR_ANNOTATION_COUNT, INTERVALS_EXTRA_COUNT
from ..its import Its, ItsNoTimeZoneInfo
from .paths import get_its_path, parse_full_recording_id, get_eaf_path, get_rttm_path
from ..utils import df_to_list_of_tuples
from ..vtc import read_rttm
from ..eaf import EafPlus


def gather_recordings(full_recording_id, forced_timezone=False):
    """
    Gets sub-recordings for a given single recording. See Its.gather_recordings for details.
    """
    its_path = get_its_path(**parse_full_recording_id(full_recording_id))
    its = Its.from_path(its_path, forced_timezone=forced_timezone)
    try:
        return its.gather_recordings()
    except ItsNoTimeZoneInfo as e:
        raise ItsNoTimeZoneInfo(f'No timezone info in \n{its_path}') from e


# TODO: these function don't need to exist. Just add full_recording_id as an alternative argument to all the get_*
#  functions in vihi.paths. It should be part of the future decorator that checks the arguments (see issue #18).
def get_vtc_data(full_recording_id):
    """
    Get VTC data for a given recording.
    :param full_recording_id: a string of '{population}_{subject}_{recording_id}' format.
    :return: a pandas dataframe with all the data from the VTC outputs (.rttm files).
    """
    rttm_path = get_rttm_path(**parse_full_recording_id(full_recording_id))
    return read_rttm(rttm_path)


def get_eaf_path_from_full_recording_id(full_recording_id):
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
    eaf_path = get_eaf_path_from_full_recording_id(full_recording_id)
    try:
        eaf = EafPlus(eaf_path)
    except FileNotFoundError as e:
        raise NoPreviousEaf(f'There is no eaf file where we expected to find it:\n{eaf_path}') from e

    return eaf


# TODO: this function should handle both random and high-volubility sampling
def add_intervals_for_annotation(full_recording_id, forced_timezone=None):
    """
    For a given recording, finds the intervals that maximize vtc_total_speech_duration - total duration of all speech
    segments as classified by VTC.
    Then adds them to the corresponding eaf file.
    :param forced_timezone: in case where timezone info was removed from its or its has incorrect info. See Its.__init__
    :param full_recording_id: full recording id, string
    :return: None
    """
    # Prepare intervals to select from
    intervals = make_intervals(sub_recordings=gather_recordings(full_recording_id, forced_timezone=forced_timezone))
    vtc_data = get_vtc_data(full_recording_id)
    intervals = add_metric(intervals=intervals, vtc_data=vtc_data)

    # Load existing intervals
    eaf = _load_eaf(full_recording_id)
    existing_intervals = _extract_interval_info(eaf)
    if len(existing_intervals) > 15:
        raise ValueError(f'{full_recording_id} has more than 15 intervals already. Likely, you are adding intervals'
                         f' to it for the second time.')
    existing_code_intervals = df_to_list_of_tuples(existing_intervals[['code_onset_wav', 'code_offset_wav']])

    # Select intervals that maximize vtc_total_speech_duration
    best_intervals = select_best_intervals(
        intervals,
        existing_code_intervals=existing_code_intervals,
        n_to_select=(INTERVALS_FOR_ANNOTATION_COUNT + INTERVALS_EXTRA_COUNT))
    sampling_types = np.where(
        # Intervals with the highest value of the metric will be used in the main part, the next
        # INTERVALS_EXTRA_COUNT ones - in the extra part
        best_intervals.metric_value.rank(method='first', ascending=False)
        <= INTERVALS_FOR_ANNOTATION_COUNT,
        'high-volubility',
        'high-volubility-extra')
    best_intervals.insert(0, 'sampling_type', sampling_types)
    eaf, best_intervals = add_annotation_intervals_to_eaf(eaf, best_intervals)

    # Save eaf
    output_file_paths = _region_output_files(full_recording_id=full_recording_id)
    eaf.to_file(output_file_paths['eaf'])

    # Save log
    old_log = pd.read_csv(output_file_paths['csv'])
    best_intervals.insert(0, 'full_recording_id', full_recording_id)
    # TODO: add selected_regions to the test
    selected_regions = pd.concat([old_log, best_intervals], ignore_index=True)
    selected_regions.to_csv(output_file_paths['csv'], index=False)
