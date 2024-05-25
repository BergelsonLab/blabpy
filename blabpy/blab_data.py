from pathlib import Path

from git import Repo
from git.exc import GitCommandError
from semver import Version

from blabpy.paths import get_blab_data_root_path


def _parse_version(version):
    # Remove v prefix if present
    if version.startswith('v'):
        version = version[1:]

    # If version starts with "0.0.0." replace the last zero with 1 and the dot - with a dash
    if version.startswith('0.0.0.'):
        version = version.replace('0.0.0.', '0.0.1-')

    return Version.parse(version)


def get_newest_version(repo):
    """
    Get the newest version of a dataset.
    """
    repo.git.fetch('--tags')

    # Find newest tag by version number and by commit date. If the results are the same, use either.
    # TODO: use a proper versioning library
    newest_version = sorted(repo.tags, key=lambda t: _parse_version(t.name))[-1].name
    newest_tag = sorted(repo.tags, key=lambda t: t.commit.committed_datetime)[-1].name
    if newest_tag == newest_version:
        return newest_version
    else:
        # note: While making sure this is the case is a good idea, it's not clear what anyone is supposed to do with
        #   that error? Presumably, fix the version tags?
        raise ValueError(f"Newest version of dataset {repo} is {newest_version}, but newest tag is {newest_tag}.")


def switch_dataset_to_version(dataset_name, version):
    """
    Switch a dataset to a specific version.
    """
    blab_data_path = get_blab_data_root_path()
    repo = Repo(blab_data_path / dataset_name)

    version = version if version else get_newest_version(repo)

    # Check whether the version tag points at the current head commit - no need to checkout anything otherwise
    if repo.head.commit.hexsha != repo.tags[version].commit.hexsha:
        try:
            repo.git.checkout(version)
        except GitCommandError as e:
            raise ValueError(f"Version {version} does not exist for dataset {dataset_name}.") from e

    return repo, version


def get_file_path(dataset_name, version, relative_path):
    """
    Switches a dataset to a specific version and return the path to a file in that version.
    """
    repo, version = switch_dataset_to_version(dataset_name, version)

    file_path = Path(repo.working_dir) / relative_path
    if not file_path.exists():
        raise ValueError(f"File {relative_path} does not exist in version {version} of dataset {dataset_name}.")

    return file_path
