from random import seed

import pytest
from pydub.generators import WhiteNoise
import pandas as pd

import blabpy.vihi.intervals.intervals as intervals
from blabpy.utils import OutputExistsError
from blabpy.vihi.intervals.intervals import calculate_energy_in_all_intervals, create_files_with_random_regions


def test_calculate_energy_in_all_intervals():
    seed(24)
    noise = WhiteNoise().to_audio_segment(duration=200)
    intervals = pd.DataFrame.from_dict(dict(start=[0, 50, 150], end=[50, 150, 200]))
    energy = calculate_energy_in_all_intervals(intervals=intervals, audio=noise)
    expected_energy = pd.Series({0: 733.6411476029159, 1: 1469.4191753712091, 2: 728.1696980215235})
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
