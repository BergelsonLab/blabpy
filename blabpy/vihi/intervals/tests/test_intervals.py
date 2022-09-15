from pathlib import Path
from random import seed

import pandas as pd
from pandas.testing import assert_frame_equal
import pytest
from pydub.generators import WhiteNoise

import blabpy.vihi.intervals.intervals as intervals_module
from blabpy.eaf import EafPlus
from blabpy.utils import OutputExistsError, text_file_checksum
from blabpy.vihi.intervals.intervals import calculate_energy_in_all_intervals, create_files_with_random_regions, \
    batch_create_files_with_random_regions, make_intervals, select_best_intervals, add_metric, \
    add_annotation_intervals_to_eaf, CONTEXT_BEFORE, CODE_REGION, CONTEXT_AFTER
from blabpy.vihi.paths import compose_full_recording_id
from blabpy.vtc import read_rttm

DATA_PATH = Path(__file__).parent / 'data'
# Intervals already in eaf before we add high-volubility ones
PRE_EXISTING_CODE_INTERVALS = [(353000, 473000), (1200000, 1320000)]


def test_calculate_energy_in_all_intervals():
    seed(24)
    noise = WhiteNoise().to_audio_segment(duration=200)
    intervals = pd.DataFrame.from_dict(dict(start=[0, 50, 150], end=[50, 150, 200]))

    # Without filtering
    energy = calculate_energy_in_all_intervals(intervals=intervals, audio=noise)
    expected_energy = pd.Series({0: 733.6411476029159, 1: 1469.4191753712091, 2: 728.1696980215235})
    assert energy.equals(expected_energy)

    # With filtering
    energy = calculate_energy_in_all_intervals(intervals=intervals, audio=noise, low_freq=300, high_freq=3000)
    expected_energy = pd.Series({0: 82.11954411321199, 1: 187.31203579565587, 2: 81.01795951661462})
    assert energy.equals(expected_energy)


def test_create_files_with_random_regions(monkeypatch, tmp_path):
    # Make sure the test doesn't affect real files
    full_recording_id = 'TD_666_222'
    recording_path = tmp_path / full_recording_id
    recording_path.mkdir()
    monkeypatch.setattr(intervals_module, 'get_lena_recording_path', lambda *args, **kwargs: recording_path)

    # Run the first time
    def run():
        create_files_with_random_regions(full_recording_id=full_recording_id, age=12, length_of_recording=360)

    run()

    # Check that the files have been created
    expected_filenames = ['TD_666_222_selected-regions.csv', 'TD_666_222.eaf', 'TD_666_222.pfsx']
    assert all(recording_path.joinpath(filename).exists for filename in expected_filenames)

    # TODO: check file contents too.

    # Trying to run again should raise an error
    with pytest.raises(OutputExistsError):
        run()


def test_batch_create_files_with_random_regions(monkeypatch, tmp_path):
    # Make sure pn-opus is not touched
    def get_lena_recording_path_(population, subject_id, recording_id):
        return tmp_path / compose_full_recording_id(population, subject_id, recording_id)
    monkeypatch.setattr(intervals_module, 'get_lena_recording_path', get_lena_recording_path_)

    # Prepare the recordings list
    info_spreadsheet_path_1 = tmp_path / 'info_spreadsheet.csv'
    info_spreadsheet_1 = pd.DataFrame(columns='id,age,length_of_recording'.split(','),
                                      data=('VI_666_924,30,960'.split(','),
                                            'VI_777_234,12,360'.split(',')))
    info_spreadsheet_1.to_csv(info_spreadsheet_path_1, index=False)

    # Create the recordings folders
    info_spreadsheet_1.id.apply(lambda full_recording_id: tmp_path.joinpath(full_recording_id).mkdir())

    # Run once
    batch_create_files_with_random_regions(info_spreadsheet_path_1, seed=7)
    
    # Compare the output files
    expected_file_checksums = [('VI_666_924/VI_666_924.eaf', 580209740),
                               ('VI_666_924/VI_666_924.pfsx', 1301328091),
                               ('VI_666_924/VI_666_924_selected-regions.csv', 1260461951),
                               ('VI_777_234/VI_777_234.eaf', 1824613251),
                               ('VI_777_234/VI_777_234.pfsx', 3383994712),
                               ('VI_777_234/VI_777_234_selected-regions.csv', 1815748137)]

    def check_first_run_outputs():
        for relative_path, checksum in expected_file_checksums:
            assert text_file_checksum(tmp_path / relative_path) == checksum

    check_first_run_outputs()

    # Make a list with one recording already processed and one new one
    info_spreadsheet_path_2 = tmp_path / 'info_spreadsheet.csv'
    info_spreadsheet_2 = pd.DataFrame(columns='id,age,length_of_recording'.split(','),
                                      data=('VI_666_924,30,960'.split(','),
                                            'VI_888_098,17,640'.split(',')))
    info_spreadsheet_2.to_csv(info_spreadsheet_path_2, index=False)
    info_spreadsheet_2.id.apply(lambda full_recording_id: tmp_path.joinpath(full_recording_id).mkdir(exist_ok=True))

    # The new run should raise an error, not touch the files created above, and not create new files.
    # No seed this time, so that if the new files do get created, they would be different
    with pytest.raises(FileExistsError):
        batch_create_files_with_random_regions(info_spreadsheet_path_2)

    # No files for the new recording
    assert not any(tmp_path.joinpath('VI_888_098').iterdir())

    # The first-run outputs have not changed
    check_first_run_outputs()


def _read_sub_recordings():
    return pd.read_csv(f'{DATA_PATH}/sub_recordings.csv',
                       parse_dates=['recording_start', 'recording_end'],
                       dtype=dict(recordings_start_wav=int))


def _read_intervals():
    return pd.read_csv(f'{DATA_PATH}/intervals.csv',
                       parse_dates=['code_onset', 'code_offset', 'context_onset', 'context_offset'],
                       dtype=dict(code_onset_wav=int))


def test_make_intervals():
    sub_recordings = _read_sub_recordings()
    actual_intervals = make_intervals(sub_recordings)
    expected_intervals = _read_intervals()

    assert_frame_equal(expected_intervals, actual_intervals)


def _read_intervals_with_fake_metric():
    return pd.read_csv(f'{DATA_PATH}/intervals_with_fake_metric.csv',
                       parse_dates=['code_onset', 'code_offset', 'context_onset', 'context_offset'],
                       dtype=dict(code_onset_wav=int))


def _read_intervals_with_vtc_total_speech_duration():
    return pd.read_csv(f'{DATA_PATH}/intervals_with_vtc_total_speech_duration.csv',
                       parse_dates=['code_onset', 'code_offset', 'context_onset', 'context_offset'],
                       dtype=dict(code_onset_wav=int))


def _read_test_vtc_data(*args, **kwargs):
    return read_rttm(Path(f'{DATA_PATH}/test_all.rttm'))


def test_add_metric():
    intervals = _read_intervals()
    vtc_data = _read_test_vtc_data()
    actual_intervals_with_metric = add_metric(intervals, vtc_data)
    expected_intervals_with_metric = _read_intervals_with_vtc_total_speech_duration()
    assert_frame_equal(actual_intervals_with_metric, expected_intervals_with_metric)


def _read_best_intervals(version: int):
    return pd.read_csv(f'{DATA_PATH}/best_intervals_{version:02}.csv',
                       dtype=dict(code_onset_wav=int, code_offset_wav=int,
                                  context_onset_wav=int, context_offset_wav=int))


def test_select_best_intervals(monkeypatch):
    # We'll only be sampling 3 intervals here
    monkeypatch.setattr(intervals_module, 'INTERVALS_FOR_ANNOTATION_COUNT', 3)

    intervals_with_metric = _read_intervals_with_fake_metric()

    # Test when there are no pre-existing interval
    actual_best_intervals_1 = select_best_intervals(intervals_with_metric, n_to_select=3)
    expected_best_intervals_1 = _read_best_intervals(1)
    assert_frame_equal(actual_best_intervals_1, expected_best_intervals_1)

    # And when there are some
    actual_best_intervals_2 = select_best_intervals(intervals_with_metric, n_to_select=3,
                                                    existing_code_intervals=PRE_EXISTING_CODE_INTERVALS)
    expected_best_intervals_2 = _read_best_intervals(2)
    assert_frame_equal(actual_best_intervals_2, expected_best_intervals_2)


def _get_test_eaf_path(*args, **kwargs):
    return Path(f'{DATA_PATH}/test_eaf.eaf')


def _get_selected_regions_path():
    return Path(f'{DATA_PATH}/selected_regions.csv')


def _get_expected_eaf_path():
    return Path(f'{DATA_PATH}/expected.eaf')


def _get_expected_with_extra_eaf_path():
    return Path(f'{DATA_PATH}/expected-with-extra.eaf')


def test_add_annotation_intervals_to_eaf(tmpdir):
    # Load inputs
    eaf = EafPlus(_get_test_eaf_path())
    best_intervals = _read_best_intervals(2)
    best_intervals.insert(1, 'sampling_type', 'high-volubility')

    # Add once
    eaf, _ = add_annotation_intervals_to_eaf(eaf, best_intervals)

    actual_eaf_path = Path(tmpdir / 'actual.eaf')
    eaf.to_file(actual_eaf_path)
    expected_eaf_path = _get_expected_eaf_path()
    assert actual_eaf_path.read_text() == expected_eaf_path.read_text()

    # Add a second time
    with pytest.raises(AssertionError):
        add_annotation_intervals_to_eaf(eaf, best_intervals)
