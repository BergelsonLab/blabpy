from pathlib import Path

from git import Repo
from git.exc import GitCommandError

from blabpy.paths import get_blab_data_path

def get_file_path(dataset_name, version, relative_path):
    """
    Get a file from a dataset.
    """
    blab_data_path = get_blab_data_path()
    repo = Repo(blab_data_path / dataset_name)
    try:
        repo.git.checkout(version)
    except GitCommandError as e:
        raise ValueError(f"Version {version} does not exist for dataset {dataset_name}.") from e

    file_path = Path(repo.working_dir) / relative_path
    if not file_path.exists():
        raise ValueError(f"File {relative_path} does not exist in version {version} of dataset {dataset_name}.")

    return file_path
