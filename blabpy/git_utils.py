from pathlib import Path

from git import Repo, GitCommandError


def sparse_clone(remote_uri, folder_to_clone_into,
                 checked_out_folder, new_branch_name=None,
                 remote_name='origin', source_branch='main',
                 depth=1):
    """
    Fetches the last commit from the source ref of a remote repository and does a sparse checkout into a new branch.

    Notes:
    - Fetching of one commit only is done for speed.
    - The parse checkout limits editing of file files that shouldn't be edited.

    :param remote_uri: URL of a cloud-based repo, e.g., on GitHub, or a path to the folder with the repo.
    :param folder_to_clone_into: Folder to clone into. If exists, must be empty.
    :param new_branch_name: Name of the branch to check out. If none, the name of the folder_to_clone_into is used.
    # TODO: allow to checkout multiple folders
    :param checked_out_folder: Which folder to check out. That is the "sparse" part.
    :param source: The repo ref to branch from, defaults to "main".
    :param depth: How many commits to fetch, defaults to 1.
    :return: A git.Repo object.
    """
    # TODO: Use a temporary folder and move/rename it to folder_to_clone_into if successful. This way, if the function
    #  fails, the folder_to_clone_into is not left in a half-finished state, occupuying the path we need for the next
    #  attempt.

    # Make sure that the folder to clone to, exists and is empty.
    # mkdir -p "$folder_to_clone_into" && cd "$folder_to_clone_into" && [ "$(ls -A "$folder_to_clone_into")" ]
    folder_to_clone_into = Path(folder_to_clone_into)
    if Path(folder_to_clone_into).exists():
        if len(list(Path(folder_to_clone_into).iterdir())) > 0:
            raise ValueError(f'The folder {folder_to_clone_into} already exists and is not empty.')
    else:
        folder_to_clone_into.mkdir(parents=True, exist_ok=True)

    # Initialize repo and add $remote_uri as the remote
    # git init
    # git remote add "$remote_name" "$remote_uri"
    repo = Repo.init(folder_to_clone_into)
    remote = repo.create_remote(remote_name, remote_uri)

    # Set up to only check out the checked_out_folder
    # git config core.sparseCheckout true
    # git sparse-checkout init
    # git sparse-checkout set "$checked_out_folder"
    repo.git.config('core.sparsecheckout', 'true')
    repo.git.execute(['git', 'sparse-checkout', 'init'])
    repo.git.execute(['git', 'sparse-checkout', 'set', str(checked_out_folder)])

    # Download the last commit and make a new branch pointing to it
    # git fetch --depth=1 "$remote_name" "$main_branch"
    # git switch -c "new_branch_name" "$remote_name"/"$main_branch" --no-track
    # git push -u "$remote_name" "new_branch_name"
    try:
        # TODO: This is the slowest part of the function, consider adding a progress bar.
        remote.fetch(source_branch, depth=depth)
    except GitCommandError as e:
        raise ValueError(f'Could not find branch `{source_branch}` on {remote_uri}.\n{e}')
    new_branch_name = new_branch_name or folder_to_clone_into.name
    new_branch = repo.create_head(new_branch_name, f'{remote_name}/{source_branch}')
    new_branch.checkout()
    remote.push()

    return repo
