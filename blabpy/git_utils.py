from getpass import getuser
from pathlib import Path

from git import Repo, GitCommandError, GitConfigParser, config, RemoteProgress
from tqdm import tqdm

from blabpy.os_utils import get_owner_id


def trust_folder(folder: Path):
    """
    Checks if the current user is the owner of the folder.
    If not, then checks if the folder has already been marked as 'safe.directory' in the global git config.
    If not, marks it that way.
    :param folder: A Path object pointing to the folder in question.

    Git will not run many commands if the user running git is not the owner of the folder that contains the `.git`
    folder. This is almost always the case when we have a repo on a shared drive - even if the user created a folder
    there. To overrule this, git should be configured to trust that folder despite belonging to someone else.
    """
    # If the current user is the owner of the folder, it should already be trusted.
    if get_owner_id(folder) == getuser():
        return

    # The folder might have already been added to the list of trusted folders in the global git config.
    global_config = GitConfigParser(file_or_files=config.get_config_path('global'), read_only=False)
    try:
        safe_directories = global_config.get_values('safe', 'directory')
    except KeyError:
        safe_directories = list()
    for safe_directory in safe_directories:
        if folder.resolve() == Path(safe_directory):
            return

    # Mark the folder as trusted
    posix_path = folder.resolve().as_posix()
    global_config.add_value('safe', 'directory', posix_path)


class TqdmRemoteProgress(RemoteProgress):
    """
    A tqdm progress bar for GitPython operations.

    Note: adapted from https://stackoverflow.com/a/71285627
    """
    OP_CODES = [
        "BEGIN",
        "CHECKING_OUT",
        "COMPRESSING",
        "COUNTING",
        "END",
        "FINDING_SOURCES",
        "RECEIVING",
        "RESOLVING",
        "WRITING",
    ]
    OP_CODE_MAP = {
        getattr(RemoteProgress, _op_code): _op_code for _op_code in OP_CODES
    }

    def __init__(self) -> None:
        super().__init__()
        self.progress_bar = None
        self.curr_op = None

    @classmethod
    def get_curr_op(cls, op_code: int) -> str:
        """Get OP name from OP code."""
        # Extract the operation code from op_code
        op_code_masked = op_code & RemoteProgress.OP_MASK
        return cls.OP_CODE_MAP.get(op_code_masked, "?").title()

    def update(
        self,
        op_code: int,
        cur_count: str | float,
        max_count: str | float | None = None,
        message: str | None = "",
    ) -> None:
        cur_count = float(cur_count)
        max_count = float(max_count)

        # Start new tqdm bar on each BEGIN-flag
        if op_code & self.BEGIN:
            self.curr_op = self.get_curr_op(op_code)
            self.progress_bar = tqdm(total=100, desc=f"{self.curr_op:12}", unit="%",
                                     bar_format='{l_bar}{bar:12}{r_bar}')

        # Calculate the percentage
        if max_count > 0:
            percentage = int((cur_count / max_count) * 100)
        else:
            percentage = 0

        # Update the progress bar
        self.progress_bar.n = percentage
        self.progress_bar.set_postfix_str(f"{percentage}% {message}")

        # End progress monitoring on each END-flag, otherwise the last bar will be stuck at the last reported percentage
        if op_code & RemoteProgress.END:
            self.progress_bar.close()


def try_push_to_remote(repo, remote, branch_name):
    """
    Attempts to push a branch to a remote repository, first with default settings
    and then with optimized settings if the first attempt fails.

    :param repo: The Git repository object
    :param remote: The remote to push to
    :param branch_name: The name of the branch to push
    :return: True if push succeeded, False otherwise
    """
    # First try to push with default settings
    try:
        print("Attempting to push to remote...")
        remote.push(branch_name)
        print(f"Successfully pushed branch '{branch_name}' to remote.")
        return True
    except GitCommandError as e:
        print("Initial push attempt failed. Trying with optimized settings...")

        # If first attempt fails, try with optimized settings
        try:
            # Increase buffer size to handle larger repositories
            repo.git.config('http.postBuffer', '524288000')  # 500MB buffer

            # Add a longer timeout for the push operation
            repo.git.config('http.lowSpeedLimit', '1000')
            repo.git.config('http.lowSpeedTime', '60')

            # Attempt to push again with optimized settings
            remote.push(branch_name)
            print(f"Successfully pushed branch '{branch_name}' to remote with optimized settings.")
            return True
        except GitCommandError as e:
            print(f"Warning: Could not push to remote. This is normal and won't affect your work.")
            print("Your local branch is still configured to track the remote branch.")
            print("You can push your changes manually later with 'git push'.")
            print(f"Technical details: {e}")
            return False


def setup_branch_tracking(repo, remote_name, branch_name):
    """
    Sets up tracking for a local branch to its remote counterpart.
    Checks if the remote branch already exists and warns if it does.

    :param repo: The Git repository object
    :param remote_name: The name of the remote
    :param branch_name: The name of the branch to configure
    :return: True if successful, False if remote branch already exists
    """
    # Check if remote branch exists
    try:
        # Try to get info about the remote branch
        remote_refs = repo.git.ls_remote('--heads', remote_name, branch_name).strip()
        if remote_refs:
            print(f"WARNING: The remote branch '{branch_name}' already exists!")
            print("This could indicate someone else is already annotating this recording.")
            print("Please contact your lab technician for assistance.")
            return False
    except GitCommandError:
        # If ls-remote fails, we assume it's because there's no such branch
        pass

    # Configure the local branch to track the future remote branch
    repo.git.config(f'branch.{branch_name}.remote', remote_name)
    repo.git.config(f'branch.{branch_name}.merge', f'refs/heads/{branch_name}')
    print(f"Configured local branch '{branch_name}' to track future remote branch.")
    return True


def sparse_clone(remote_uri, folder_to_clone_into,
                 checked_out_folder, new_branch_name=None,
                 remote_name='origin', source_branch='main',
                 mark_folder_as_safe=False,
                 depth=1,
                 show_fetch_progress=True):
    """
    Fetches the last commit from the source ref of a remote repository and does a sparse checkout into a new branch.

    Notes:
    - Fetching of one commit only is done for speed.
    - The parse checkout limits editing of file files that shouldn't be edited.

    :param remote_uri: URL of a cloud-based repo, e.g., on GitHub, or a path to the folder with the repo.
    :param folder_to_clone_into: Folder to clone into. If exists, must be empty.
    :param new_branch_name: Name of the branch to check out. If none, the name of the folder_to_clone_into is used.
    :param remote_name: Name of the remote to add to the repo. Defaults to 'origin'.
    :param source_branch: Name of the branch to fetch. Defaults to 'main'.
    # TODO: allow to checkout multiple folders
    :param checked_out_folder: Which folder to check out. That is the "sparse" part.
    :param mark_folder_as_safe: In case folder_to_clone_into is owned by someone other than the current user, should
    this folder be marked as 'safe.directory'? Potentially unsafe, so defaults to False.
    :param depth: How many commits to fetch, defaults to 1.
    :param show_fetch_progress: The slowest part is fetching. Should a progress bar be shown?
    :return: A git.Repo object.
    """
    # TODO: Use a temporary folder and move/rename it to folder_to_clone_into if successful. This way, if the function
    #  fails, the folder_to_clone_into is not left in a half-finished state, occupying the path we need for the next
    #  attempt.

    # Make sure that the folder to clone to, exists and is empty.
    # mkdir -p "$folder_to_clone_into" && cd "$folder_to_clone_into" && [ "$(ls -A "$folder_to_clone_into")" ]
    folder_to_clone_into = Path(folder_to_clone_into)
    if Path(folder_to_clone_into).exists():
        if len(list(Path(folder_to_clone_into).iterdir())) > 0:
            raise ValueError(f'The folder {folder_to_clone_into} already exists and is not empty.')
    else:
        folder_to_clone_into.mkdir(parents=True, exist_ok=True)

    # Tell git to trust the folder even if it is owned by someone other than the current user.
    if mark_folder_as_safe:
        trust_folder(folder_to_clone_into)

    # Initialize repo
    # git init
    # Note: context manager is used so that repo is closed automatically, otherwise Windows doesn't release some files.
    with Repo.init(folder_to_clone_into) as repo:
        # Set up the remote
        # git remote add "$remote_name" "$remote_uri"
        remote = repo.create_remote(remote_name, remote_uri)

        # Set up to only check out the checked_out_folder
        # git sparse-checkout set "$checked_out_folder"
        repo.git.execute(['git', 'sparse-checkout', 'set', checked_out_folder.as_posix(), '--cone'])

        # Download the last commit and make a new branch pointing to it
        # git fetch --depth=1 "$remote_name" "$main_branch"
        # git switch -c "new_branch_name" "$remote_name"/"$main_branch" --no-track
        try:
            progress = TqdmRemoteProgress() if show_fetch_progress else None
            remote.fetch(source_branch, depth=depth, progress=progress)
        except GitCommandError as e:
            raise ValueError(f'Could not find branch `{source_branch}` on {remote_uri}.\n{e}')

        new_branch_name = new_branch_name or folder_to_clone_into.name
        new_branch = repo.create_head(new_branch_name, f'{remote_name}/{source_branch}')
        new_branch.checkout()

        # Set up tracking for the new branch
        if setup_branch_tracking(repo, remote_name, new_branch_name):
            # Try to push to remote
            try_push_to_remote(repo, remote, new_branch_name)

    return repo


def set_user_name_and_email_for_repo(repo_path: Path, user_name: str, user_email: str):
    with Repo(repo_path) as repo:
        repo.config_writer().set_value("user", "name", user_name).release()
        repo.config_writer().set_value("user", "email", user_email).release()
