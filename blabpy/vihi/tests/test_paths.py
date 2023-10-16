from blabpy.vihi.paths import get_vihi_path, get_subject_files_path, get_lena_path, get_lena_annotations_path, \
    compose_full_recording_id, parse_full_recording_id, get_lena_population_path, get_lena_subject_path, \
    get_lena_recording_path, get_raw_data_dir, get_its_dir, get_its_path, get_rttm_path, get_eaf_path, \
    get_lena_annotations_in_progress_path


def _test_get_path_function(function, name, *args, **kwargs):
    path = function(*args, **kwargs)
    assert path.name == name
    assert path.exists()


def test_get_path_functions():
    _test_get_path_function(get_vihi_path, 'VIHI')
    _test_get_path_function(get_subject_files_path, 'SubjectFiles')
    _test_get_path_function(get_lena_path, 'LENA')
    _test_get_path_function(get_lena_annotations_path, 'annotations')
    _test_get_path_function(get_lena_population_path, 'TD', 'TD')
    _test_get_path_function(get_lena_subject_path, 'TD_422', 'TD', '422')
    _test_get_path_function(get_lena_recording_path, 'TD_422_217', 'TD', '422', '217')
    _test_get_path_function(get_raw_data_dir, 'rawish_data')
    _test_get_path_function(get_its_dir, 'its')
    _test_get_path_function(get_its_path, 'TD_422_217.its', 'TD', '422', '217')
    _test_get_path_function(get_rttm_path, 'all.rttm', 'TD', '422', '217')
    assert get_rttm_path('TD', '422', '217').parent.name == 'TD_422_217'
    _test_get_path_function(get_eaf_path, 'TD_422_217.eaf', 'TD', '422', '217')
    _test_get_path_function(get_lena_annotations_in_progress_path, 'annotations-in-progress')


def test_compose_full_recording_id():
    assert compose_full_recording_id('TD', '123', '456') == 'TD_123_456'


def test_parse_full_recording_id():
    assert parse_full_recording_id('TD_123_456') == {'population': 'TD',
                                                     'subject_id': '123',
                                                     'recording_id': '456'}
