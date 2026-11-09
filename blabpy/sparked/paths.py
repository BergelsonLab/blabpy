from ..paths import get_blab_share_path

def get_sparked_path():
    """Get the path to the Sparked directory."""
    return get_blab_share_path() / "experimental_projects/SPARKED"

def get_sparked_talkers_path():
    """Get the path to the Sparked talker directory."""
    return get_sparked_path() / "video_annotations/talkers"

def get_sparked_opf_complete_path():
    """Get the path to the Sparked OPF directory."""
    return get_sparked_talkers_path() / "opf_complete"

def get_sparked_opf_in_progress_path():
    """Get the path to the Sparked OPF directory."""
    return get_sparked_talkers_path() / "opf_in_progress"

def get_sparked_opf_original_path():
    """Get the path to the Sparked OPF directory."""
    return get_sparked_talkers_path() / "opf_original"

def normalized_id(id):
    return str(id).zfill(2)

def parse_sparked_id(id_str):
    components = id_str.split("_")
    assert len(components) == 2, f"SPARKED ID must be of the form (talker_id)_(age_in_months) (i.e. 01_13), not {id_str}"
    talker_id, months_in_age = components
    assert normalized_id(int(talker_id)) == talker_id, "The first element of the SPARKED ID must be the talker's id, a 2 digit number with leading zeroes accordingly."
    assert normalized_id(int(months_in_age)) == months_in_age, "The second element of the SPARKED ID must be the talker's age in months, a 2 digit number with leading zeroes accordingly."
    return components

def get_sparked_talker_path(talker_id):
    """Get the path to the Sparked talker folder."""
    return get_sparked_opf_original_path() / f"talker_{normalized_id(talker_id)}"

def get_sparked_talker_opf_path(talker_id, age_in_months, suffix=None):
    """Rewrite this to use in_progress or original path instead"""
    return
    talker_folder = get_sparked_talker_path(talker_id)
    if suffix:
        opf_filename = f"talker_{normalized_id(talker_id)}_{normalized_id(age_in_months)}_{suffix}.opf"
    else:
        opf_filename = f"talker_{normalized_id(talker_id)}_{normalized_id(age_in_months)}.opf"
    return talker_folder / opf_filename

def get_all_sparked_opf_complete_paths():
    #TODO: Check that we are only getting final files (i.e. does not have a suffix) using parse method
    all_paths = []
    opf_folder = get_sparked_opf_complete_path()
    for f in opf_folder.iterdir():
        if f.suffix == ".opf":
            all_paths += f
    return all_paths

def get_gold_standard_path(sparked_id):
    '''
    Get the path to the gold standard file for a given SPARKED ID.
    :param sparked_id: The SPARKED ID of the OPF file, e.g "01_13".
    :return: The path to the gold standard file
    '''
    parse_sparked_id(sparked_id)
    return get_sparked_talkers_path() / "gold_standard" / "templates" / "scoring" / f"talker_{sparked_id}_gs.tsv"

def get_annotator_training_path(sparked_id, annotator):
    '''
    Get the path to the annotator's training file for a given SPARKED ID.
    :param sparked_id: The SPARKED ID of the OPF file, e.g "01_13".
    :param annotator: The annotator's initials, e.g. "jd" for John Doe.
    :return: The path to the annotator's training file

    Note: 
        The training file should be named, say, 'talker_01_12_jh.tsv' if your initial is 'jh' 
        and you're working on file '01_12'. This function checks that the sparked id is correctly formatted and 
        the training folder and file exist.
    '''
    parse_sparked_id(sparked_id)
    annotator = annotator.strip().lower()
    training_folder = get_sparked_talkers_path() / "gold_standard" / f"training_{annotator}"
    assert training_folder.exists(), f"Cannot find training folder. Your OPF file and output should be stored in a folder called, say, 'training_{annotator}' if your initial is '{annotator}'."
    training_file = training_folder / f"talker_{sparked_id}_{annotator}.tsv"
    assert training_file.exists(), f"Cannot find training file. Your OPF file and output should be named, say, 'talker_{sparked_id}_{annotator}.opf' and 'talker_{sparked_id}_{annotator}.tsv' if your initial is '{annotator}' and you're working on file '{sparked_id}'."
    return training_file



