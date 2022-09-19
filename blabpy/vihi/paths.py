from ..paths import get_pn_opus_path


POPULATIONS = ['VI', 'HI', 'TD']


def get_vihi_path():
    """
    Finds the path to the VIHI folder on PN-OPUS
    :return: Path object
    """
    return get_pn_opus_path() / 'VIHI'


def get_subject_files_path():
    """
    Returns the path to the SubjectFiles folder within the VIHI folder
    :return: Path object
    """
    return get_vihi_path() / 'SubjectFiles'


def _get_modality_path(modality):
    """
    Return the path to a modality folder withing the SubjectFiles folder
    :return: Path object
    """
    return get_subject_files_path() / modality


def get_lena_path():
    """
    Returns the path to the LENA folder within the SubjectFiles folder
    :return: Path object
    """
    return _get_modality_path('LENA')


def _id_from_int(id_):
    """
    Converts integer subject and recordings ids to a 3-digit-long zero-paddes string
    :param id_: int
    :return: str
    """
    return f'{id_:03}'


def _check_id_string(id_):
    """
    Checks that the subject or recordings id is formatted correctly by converting to number and back.
    :param id_:
    :return:
    """
    assert isinstance(id_, str)
    assert _id_from_int(int(id_)) == id_


def _check_population(population):
    assert population in POPULATIONS


def compose_full_recording_id(population: str, subject_id: str, recording_id: str):
    """
    Combines population type, subject id, and recording id into a full recording id, e.g., VI_123_456
    :param population: VI/HI/TD
    :param subject_id:
    :param recording_id:
    :return:
    """
    _check_population(population)
    _check_id_string(subject_id)
    _check_id_string(recording_id)
    return f'{population}_{subject_id}_{recording_id}'


def parse_full_recording_id(full_recording_id):
    """
    Parse a full recording id, e.g., VI_123_456, into three constituent parts.
    :param full_recording_id: a string
    :return: a dict with string values and keys population, subject_id, recording_id
    """
    population, subject_id, recording_id = full_recording_id.split('_')
    _check_population(population)
    _check_id_string(subject_id)
    _check_id_string(recording_id)

    return dict(population=population, subject_id=subject_id, recording_id=recording_id)


def get_lena_population_path(population):
    """
    Find the LENA population-level folder
    :param population: one of POPULATIONS
    :return: Path object
    """
    _check_population(population)
    return get_lena_path() / population


def get_lena_subject_path(population, subject_id):
    """
    Find the LENA subject-level folder
    :param population: one of POPULATIONS
    :param subject_id: zero-padded three-digit string
    :return: Path object
    """
    _check_population(population)
    _check_id_string(subject_id)
    return get_lena_population_path(population) / f'{population}_{subject_id}'


def get_lena_recording_path(population, subject_id, recording_id):
    """
    Find the LENA subject-level folder
    :param population: one of POPULATIONS
    :param subject_id: zero-padded three-digit string
    :param recording_id: --//--
    :return: Path object
    """
    _check_population(population)
    _check_id_string(subject_id)
    _check_id_string(recording_id)
    return get_lena_subject_path(population, subject_id) / compose_full_recording_id(population, subject_id, recording_id)


def get_its_path(population, subject_id, recording_id):
    """
    Find the .its file.
    :param population: one of POPULATIONS
    :param subject_id: zero-padded three-digit string
    :param recording_id: --//--
    :return: Path object
    """
    _check_population(population)
    _check_id_string(subject_id)
    _check_id_string(recording_id)

    subject_dir = get_lena_subject_path(population, subject_id)
    assert subject_dir.exists(), 'Can\'t find the subject folder. Check the arguments.'

    full_recording_id = compose_full_recording_id(population, subject_id, recording_id)
    its_path = subject_dir / full_recording_id / f'{full_recording_id}.its'

    return its_path


def get_rttm_path(population, subject_id, recording_id):
    """
    Find the .rttm file with the VTC output for a single recording.
    :param population: one of POPULATIONS
    :param subject_id: zero-padded three-digit string
    :param recording_id: --//--
    :return: Path object
    """
    _check_population(population)
    _check_id_string(subject_id)
    _check_id_string(recording_id)

    lena_path = get_lena_path()
    full_recording_id = compose_full_recording_id(population, subject_id, recording_id)
    rttm_path = lena_path / 'derivatives' / 'vtc' / 'separated' / full_recording_id / 'all.rttm'

    return rttm_path


def get_eaf_path(population, subject_id, recording_id):
    """
    Find the .eaf file with the ACLEW-style annotations for a single recording.
    :param population: one of POPULATIONS
    :param subject_id: zero-padded three-digit string
    :param recording_id: --//--
    :return: Path object
    """
    _check_population(population)
    _check_id_string(subject_id)
    _check_id_string(recording_id)

    subject_dir = get_lena_subject_path(population, subject_id)
    assert subject_dir.exists(), 'Can\'t find the subject folder. Check the arguments.'

    full_recording_id = compose_full_recording_id(population, subject_id, recording_id)
    eaf_path = subject_dir / full_recording_id / f'{full_recording_id}.eaf'

    return eaf_path
