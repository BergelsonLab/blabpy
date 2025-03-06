import os
import sys
import click
from datetime import date
from pathlib import Path
from git import GitCommandError

# Import from within blabpy
from .git_utils import sparse_clone


def get_username():
    """
    Gets the current username from environment variables.

    Returns:
        str: Username if found in environment variables.

    Raises:
        ValueError: If username cannot be determined from environment.
    """
    # Try to get username from environment variables
    username = os.environ.get('USER') or os.environ.get('USERNAME')

    if not username:
        raise ValueError(
                "Username could not be determined from environment variables.\n"
                "Please set the USER or USERNAME environment variable, or specify --username when running the command."
        )

    return username


@click.group()
def one_time_script():
    """CLI for setting up and working with one-time scripts."""
    pass


@one_time_script.command()
@click.argument('topic', required=True)
@click.option('--username', help='Your username for branch naming. If not provided, tries to get from environment.')
@click.option('--folder', default='one_time_script',
              help='Name of the outer folder to create. Default: one_time_script')
def setup(topic, username, folder):
    """
    Set up a new one-time script project.

    TOPIC is the name of the project/script you're working on.

    This command:
    - Creates a folder structure
    - Does a sparse clone of the repo
    - Creates a new branch
    - Sets up sparse checkout
    - Pushes the branch to the remote

    Example: one_time_script setup my-new-analysis
    Example with options: one_time_script setup my-new-analysis --folder custom_folder --username johndoe
    """
    try:
        # Determine username
        if not username:
            try:
                username = get_username()
            except ValueError as e:
                click.echo(f"Error: {e}", err=True)
                sys.exit(1)

        # Create outer folder
        outer_folder = Path(folder)
        if outer_folder.exists():
            click.echo(f"Warning: Folder '{outer_folder}' already exists.")
            if not click.confirm("Continue anyway?", default=False):
                click.echo("Aborted.")
                return
        else:
            outer_folder.mkdir()
            click.echo(f"Created folder: {outer_folder}")

        # Move into the outer folder
        os.chdir(outer_folder)
        click.echo(f"Working in: {os.getcwd()}")

        # Create inner folder name with date
        today = date.today().strftime("%Y-%m-%d")
        inner_folder = f"{today}_{topic}"
        inner_folder_path = Path(inner_folder)

        # Create branch name
        branch_name = f"{username}_{topic}"

        # Use sparse_clone to set up the repository
        try:
            click.echo("Setting up repository (this may take a moment)...")
            repo = sparse_clone(
                    remote_uri="https://github.com/BergelsonLab/one_time_scripts.git",
                    folder_to_clone_into=".",
                    checked_out_folder=inner_folder_path,
                    new_branch_name=branch_name,
                    remote_name="origin",
                    source_branch="main",
                    depth=1
            )
            click.echo("Repository setup completed successfully.")
        except (GitCommandError, ValueError) as e:
            click.echo(f"Error setting up repository: {e}", err=True)
            sys.exit(1)

        # Create the inner folder if it doesn't exist
        inner_folder_path.mkdir(exist_ok=True)
        click.echo(f"Created inner folder: {inner_folder}")

        # Success message
        click.echo(f"\nSetup completed successfully!")
        click.echo(f"\nYour project is set up at: {outer_folder}/{inner_folder}")
        click.echo(f"Branch name: {branch_name}")
        click.echo(f"\nNext steps:")
        click.echo(f"  cd {outer_folder}/{inner_folder}")
        click.echo(f"  # Start working on your script")

    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


if __name__ == '__main__':
    one_time_script()
