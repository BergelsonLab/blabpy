from ..paths import get_blab_share_path

def get_sparked_path():
    """Get the path to the Sparked directory."""
    return get_blab_share_path() / "experimental_projects/SPARKED"

def get_sparked_annotations_path():
    """Get the path to the Sparked talker directory."""
    return get_sparked_path() / "video_annotations/talkers"

def get_sparked_opf_path():
    """Get the path to the Sparked OPF directory."""
    return get_sparked_annotations_path() / "opf"

def get_sparked_opf_in_progress_path():
    """Get the path to the Sparked OPF directory."""
    return get_sparked_annotations_path() / "opf_in_progress"

def normalized_id(id):
    return str(id).zfill(2)

def parse_sparked_id(id_str):
    components = id_str.split("_")
    assert len(components) == 2
    talker_id, months_in_age = components
    assert str(int(talker_id)).zill(2) == talker_id
    assert str(int(months_in_age)).zill(2) == months_in_age
    return components

def get_sparked_talker_path(talker_id):
    """Get the path to the Sparked talker folder."""
    return get_sparked_opf_path() / f"talker_{normalized_id(talker_id)}"

def get_sparked_talker_opf_path(talker_id, age_in_months, suffix=None):
    """Get the path to the Sparked talker OPF file."""
    talker_folder = get_sparked_talker_path(talker_id)
    if suffix:
        opf_filename = f"talker_{normalized_id(talker_id)}_{normalized_id(age_in_months)}_{suffix}.opf"
    else:
        opf_filename = f"talker_{normalized_id(talker_id)}_{normalized_id(age_in_months)}.opf"
    return talker_folder / opf_filename

def get_all_sparked_opf_paths():
    #TODO: Check that we are only getting final files (i.e. does not have a suffix) using parse method
    all_paths = []
    opf_folder = get_sparked_opf_path()
    for dir in opf_folder.iterdir():
        if dir.is_dir() and dir.name.startswith("talker_"):
            for f in dir.iterdir():
                if f.suffix == ".opf":
                    all_paths += f
    return all_paths

    

# TODO: parsed id string, but depends on cases
# def parsed_sparked_id(id_str):
#     pass



