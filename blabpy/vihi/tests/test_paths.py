from blabpy.vihi.paths import get_vihi_path, get_subject_files_path


def test_get_vihi_path():
    vihi_path = get_vihi_path()
    assert vihi_path.name == 'VIHI'
    assert vihi_path.exists()


def test_get_subject_files_path():
    subject_files_path = get_subject_files_path()
    assert subject_files_path.name == 'SubjectFiles'
    assert subject_files_path.exists
