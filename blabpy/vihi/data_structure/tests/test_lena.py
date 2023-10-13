from io import StringIO

import pandas as pd

from blabpy.vihi.data_structure.lena import audit_recording_folder, audit_all_recordings


def test_audit_recording_folder(tmp_path):
    population, subject_id, recording_id = 'VI', '018', '924'
    recording_path = tmp_path / f'{population}_{subject_id}_{recording_id}'
    recording_path.mkdir()
    files = [
        'VI_018_924.eaf',
        '.DS_Store',
        'VI_018_924.its',
        'VI_018_924.wav',
        'VI_018_924.pfsx',
        'VIHI_Coding_Issues_VI_018_924_.docx',
        'VI_018_924_lena5min.csv',
        '~$_018_924_Coding_Issues.docx',
        'VI_018_924.upl']
    for filename in files:
        recording_path.joinpath(filename).touch()

    audit_results = audit_recording_folder(folder_path=recording_path, population=population,
                                           subject_id=subject_id, recording_id=recording_id)
    expected_audit_resuls = pd.read_csv(StringIO('\n'.join(
        ['relative_path,status',
         'VI_018_924.eaf,expected',
         'VI_018_924.its,expected',
         'VI_018_924.pfsx,expected',
         'VI_018_924.upl,expected',
         'VI_018_924.wav,expected',
         'VI_018_924_lena5min.csv,expected',
         '.DS_Store,ignored',
         '~$_018_924_Coding_Issues.docx,ignored',
         'VIHI_Coding_Issues_VI_018_924.docx,missing',
         'VIHI_Coding_Issues_VI_018_924_.docx,unexpected'])))
    assert audit_results.equals(expected_audit_resuls)


def test_audit_all_recordings():
    # Check that the function works and returns a pandas dataframe
    audit_results = audit_all_recordings()
    assert isinstance(audit_results, pd.DataFrame)
    assert audit_results.shape[0] > 0
