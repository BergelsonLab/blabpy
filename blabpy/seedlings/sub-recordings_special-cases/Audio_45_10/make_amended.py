from pathlib import Path

from blabpy import ANONYMIZATION_DATE
from blabpy.seedlings.pipeline import get_lena_sub_recordings

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
folder = Path('blabpy/seedlings/sub-recordings_special-cases/Audio_45_10')
original_sub_recordings.to_csv(folder / 'sub-recordings_original.csv', index=False)
amended_sub_recordings.to_csv(folder / 'sub-recordings_amended.csv', index=False)
