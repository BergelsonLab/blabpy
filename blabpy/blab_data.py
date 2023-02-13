from pathlib import Path

from git import Repo
from git.exc import GitCommandError

from blabpy.paths import get_blab_data_path

def get_newest_version(repo):
    """
    Get the newest version of a dataset.
    """
    # Find newest by version number and by commit date. If the result is the same, use t
    # TODO: use a proper versioning library
    newest_version = repo.tags.sort(key=lambda t: tuple(int(n) for n in t.name.split('.')))[-1].name
    newest_tag = repo.tags.sort(key=lambda t: t.commit.committed_datetime)[-1].name
    return repo.tags[-1].name


def get_file_path(dataset_name, version, relative_path):
    """
    Get a file from a dataset.
    """
    blab_data_path = get_blab_data_path()
    repo = Repo(blab_data_path / dataset_name)

    version = version if version else get_newest_version(repo)

    try:
        repo.git.checkout(version)
    except GitCommandError as e:
        raise ValueError(f"Version {version} does not exist for dataset {dataset_name}.") from e

    file_path = Path(repo.working_dir) / relative_path
    if not file_path.exists():
        raise ValueError(f"File {relative_path} does not exist in version {version} of dataset {dataset_name}.")

    return file_path
