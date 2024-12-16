from pyprojroot import find_root

from blabpy import ANONYMIZATION_DATE
from blabpy.seedlings.pipeline import get_lena_sub_recordings

sub_recs_special_cases_path = find_root('setup.py') / 'blabpy/seedlings/sub-recordings_special-cases'
# Make sure you are running from somewhere with the blab repo. Or just update the path.
assert sub_recs_special_cases_path.exists()

# # 45_10

recording_id = 'Audio_45_10'
original_sub_recordings, _ = get_lena_sub_recordings(recording_id)
original_sub_recordings.insert(0, 'recording_id', recording_id)

# Drop the first sub-recording
amended_sub_recordings = original_sub_recordings.copy().iloc[1:]

# reshift start_dt and end_dt
shift_dt = amended_sub_recordings.start_dt.iloc[0].date() - ANONYMIZATION_DATE
amended_sub_recordings[['start_dt', 'end_dt']] = amended_sub_recordings[['start_dt', 'end_dt']] - shift_dt

# reshift start_ms, end_ms
shift = amended_sub_recordings.start_ms.iloc[0]
amended_sub_recordings[['start_ms', 'end_ms']] = amended_sub_recordings[['start_ms', 'end_ms']] - shift


# Save to csv
# note: You might need to do os.chdir or edit the folder path.
folder = sub_recs_special_cases_path / recording_id
original_sub_recordings.to_csv(folder / 'sub-recordings_original.csv', index=False)
amended_sub_recordings.to_csv(folder / 'sub-recordings_amended.csv', index=False)

# # 06_17
recording_id2 = 'Audio_06_17'
original_sub_recordings2, _ = get_lena_sub_recordings(recording_id2)
original_sub_recordings2.insert(0, 'recording_id', recording_id2)

# Shorten the only sub-recordings
assert len(original_sub_recordings2) == 1
amended_sub_recordings2 = original_sub_recordings2.copy()
# get the duration from the wav file
# from pydub import AudioSegment
# print(len(AudioSegment.from_file(wav_path)))

amended_sub_recordings2.at[0, 'end_ms'] = 42292638

# Save to csv
# note: You might need to do os.chdir or edit the folder path.
folder2 = sub_recs_special_cases_path / recording_id2
folder2.mkdir(exist_ok=True)
original_sub_recordings2.to_csv(folder2 / 'sub-recordings_original.csv', index=False)
amended_sub_recordings2.to_csv(folder2 / 'sub-recordings_amended.csv', index=False)