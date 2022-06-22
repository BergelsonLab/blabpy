from random import seed

import pandas as pd
import pytest
from pydub.generators import WhiteNoise

import blabpy.vihi.intervals.intervals as intervals
from blabpy.utils import OutputExistsError, text_file_checksum
from blabpy.vihi.intervals.intervals import calculate_energy_in_all_intervals, create_files_with_random_regions, \
    batch_create_files_with_random_regions
from blabpy.vihi.paths import _recording_prefix


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
    recording_prefix = 'TD_666_222'
    recording_path = tmp_path / recording_prefix
    recording_path.mkdir()
    monkeypatch.setattr(intervals, 'get_lena_recording_path', lambda *args, **kwargs: recording_path)

    # Run the first time
    def run():
        create_files_with_random_regions(recording_id=recording_prefix, age=12, length_of_recording=360)

    run()

    # Check that the files have been created
    expected_filenames = ['TD_666_222_selected-regions.csv', 'TD_666_222.eaf', 'TD_666_222.pfsx']
    assert all(recording_path.joinpath(filename).exists for filename in expected_filenames)

    # Trying to run again should raise an error
    with pytest.raises(OutputExistsError):
        run()


def test_batch_create_files_with_random_regions(monkeypatch, tmp_path):
    # Make sure pn-opus is not touched
    def get_lena_recording_path_(population, subject_id, recording_id):
        return tmp_path / _recording_prefix(population, subject_id, recording_id)
    monkeypatch.setattr(intervals, 'get_lena_recording_path', get_lena_recording_path_)

    # Prepare the recordings list
    info_spreadsheet_path_1 = tmp_path / 'info_spreadsheet.csv'
    info_spreadsheet_1 = pd.DataFrame(columns='id,age,length_of_recording'.split(','),
                                      data=('VI_666_924,30,960'.split(','),
                                            'VI_777_234,12,360'.split(',')))
    info_spreadsheet_1.to_csv(info_spreadsheet_path_1, index=False)

    # Create the recordings folders
    info_spreadsheet_1.id.apply(lambda recording_id: tmp_path.joinpath(recording_id).mkdir())

    # Run once
    batch_create_files_with_random_regions(info_spreadsheet_path_1, seed=7)
    
    # Compare the output files
    expected_file_checksums = [('VI_666_924/VI_666_924.eaf', 1320053869),
                               ('VI_666_924/VI_666_924.pfsx', 1301328091),
                               ('VI_666_924/VI_666_924_selected-regions.csv', 840067697),
                               ('VI_777_234/VI_777_234.eaf', 2643756015),
                               ('VI_777_234/VI_777_234.pfsx', 3383994712),
                               ('VI_777_234/VI_777_234_selected-regions.csv', 1291151865)]

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
    info_spreadsheet_2.id.apply(lambda recording_id: tmp_path.joinpath(recording_id).mkdir(exist_ok=True))

    # The new run should raise an error, not touch the files created above, and not create new files.
    # No seed this time, so that if the new files do get created, they would be different
    with pytest.raises(FileExistsError):
        batch_create_files_with_random_regions(info_spreadsheet_path_2)

    # No files for the new recording
    assert not any(tmp_path.joinpath('VI_888_098').iterdir())

    # The first-run outputs have not changed
    check_first_run_outputs()
