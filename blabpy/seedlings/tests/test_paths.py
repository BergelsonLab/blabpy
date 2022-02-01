import pytest

from blabpy.seedlings.paths import get_seedlings_path, _get_home_visit_folder, _get_coding_folder, _get_analysis_folder, \
    _check_modality, _get_annotation_path, get_opf_path, get_cha_path, _get_all_paths, get_all_opf_paths, \
    get_all_cha_paths, MISSING_AUDIO_RECORDINGS, MISSING_VIDEO_RECORDINGS, get_basic_level_path, \
    get_all_basic_level_paths

TEST_CHILD, TEST_MONTH = 6, 10
AUDIO = 'Audio'
VIDEO = 'Video'
ANNOTATION_FILE_COUNT = 527


def test_get_seedlings_path():
    get_seedlings_path()


@pytest.mark.parametrize(argnames='get_function',
                         argvalues=[_get_home_visit_folder, _get_coding_folder, _get_analysis_folder])
def test_get_child_month_folder(get_function):
    folder = get_function(child=TEST_CHILD, month=TEST_MONTH)
    assert folder.exists()


def test__check_modality():
    _check_modality(AUDIO)
    _check_modality(VIDEO)
    with pytest.raises(AssertionError):
        _check_modality('tactile')


@pytest.mark.parametrize(argnames='modality',
                         argvalues=[AUDIO, VIDEO])
def test__get_annotation_path(modality):
    annotation_path = _get_annotation_path(child=TEST_CHILD, month=TEST_MONTH, modality=modality)
    assert annotation_path.exists()


def test_get_opf_path():
    opf_path = get_opf_path(child=TEST_CHILD, month=TEST_MONTH)
    assert opf_path.exists()


def test_get_cha_path():
    cha_path = get_cha_path(child=TEST_CHILD, month=TEST_MONTH)
    assert cha_path.exists()


@pytest.mark.parametrize(argnames=('get_single_file_function', 'missing_child_month_combinations'),
                         argvalues=((get_cha_path, MISSING_AUDIO_RECORDINGS),
                                    (get_opf_path, MISSING_VIDEO_RECORDINGS)))
def test__get_all_paths(get_single_file_function, missing_child_month_combinations):
    paths = _get_all_paths(get_single_file_function=get_single_file_function,
                           missing_child_month_combinations=missing_child_month_combinations)
    assert len(paths) == ANNOTATION_FILE_COUNT


def test_get_all_opf_paths():
    paths = get_all_opf_paths()
    assert len(paths) == ANNOTATION_FILE_COUNT


def test_get_all_cha_paths():
    paths = get_all_cha_paths()
    assert len(paths) == ANNOTATION_FILE_COUNT


@pytest.mark.parametrize(argnames='modality',
                         argvalues=(AUDIO, VIDEO))
def test_get_basic_level_path(modality):
    path = get_basic_level_path(child=TEST_CHILD, month=TEST_MONTH, modality=modality)
    assert path.exists()


@pytest.mark.parametrize(argnames='modality',
                         argvalues=(AUDIO, VIDEO))
def test_get_all_basic_level_paths(modality):
    paths = get_all_basic_level_paths(modality=modality)
    assert len(paths) == ANNOTATION_FILE_COUNT
