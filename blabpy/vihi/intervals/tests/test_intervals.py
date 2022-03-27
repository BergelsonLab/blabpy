from random import seed

from pydub.generators import WhiteNoise
import pandas as pd

from blabpy.vihi.intervals.intervals import calculate_energy_in_all_intervals


def test_calculate_energy_in_all_intervals():
    seed(24)
    noise = WhiteNoise().to_audio_segment(duration=200)
    intervals = pd.DataFrame.from_dict(dict(start=[0, 50, 150], end=[50, 150, 200]))
    energy = calculate_energy_in_all_intervals(intervals=intervals, audio=noise)
    expected_energy = pd.Series({0: 733.6411476029159, 1: 1469.4191753712091, 2: 728.1696980215235})
    assert energy.equals(expected_energy)
