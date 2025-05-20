#!/usr/bin/env python3
import click
import logging
import sys
from pathlib import Path
import subprocess

from blabpy.eaf.eaf_tree import EafTree
from blabpy.eaf.merge import merge_trees


def setup_logging(verbose=False):
    """Configure logging based on verbosity level."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    return logging.getLogger('eafmerge')


def _is_file_conflicted(file_path, logger):
    """Check if file has Git conflict markers."""
    try:
        output = subprocess.run(
            ['git', 'ls-files', '--unmerged', file_path],
            check=False, capture_output=True, text=True
        ).stdout.strip()
        return bool(output)
    except Exception as e:
        logger.error(f"Error checking if file is conflicted: {e}")
        return False


def extract_versions_with_git(file_path, logger):
    """Extract base, ours, and theirs versions using Git."""
    if not _is_file_conflicted(file_path, logger):
        logger.info(f"No conflicts detected in {Path(file_path).name}")
        return None

    logger.info(f"Extracting versions for conflicted file: {Path(file_path).name}")
    file_path = Path(file_path).resolve()
    base_path = file_path.with_name(file_path.name + ".BASE")
    ours_path = file_path.with_name(file_path.name + ".OURS")
    theirs_path = file_path.with_name(file_path.name + ".THEIRS")

    rel_path = file_path.relative_to(Path.cwd()).as_posix()

    try:
        # Extract base version (common ancestor)
        with open(base_path, 'w', encoding='utf-8') as f:
            subprocess.run([
                'git', 'show', f':1:{rel_path}'
            ], check=True, stdout=f, stderr=subprocess.PIPE)

        # Extract our version
        with open(ours_path, 'w', encoding='utf-8') as f:
            subprocess.run([
                'git', 'show', f':2:{rel_path}'
            ], check=True, stdout=f, stderr=subprocess.PIPE)

        # Extract their version
        with open(theirs_path, 'w', encoding='utf-8') as f:
            subprocess.run([
                'git', 'show', f':3:{rel_path}'
            ], check=True, stdout=f, stderr=subprocess.PIPE)

        logger.debug(f"Created version files: {base_path.name}, {ours_path.name}, {theirs_path.name}")
        return str(base_path), str(ours_path), str(theirs_path)

    except subprocess.CalledProcessError as e:
        logger.error(f"Error extracting versions: {e}")
        return None


@click.group()
def cli():
    """EAF file utilities."""
    pass

@cli.command(help="Check for conflicts in an EAF file, extract versions, and attempt to merge.")
@click.argument('input_file', type=click.Path(exists=True, dir_okay=False))
@click.option('-o', '--output', type=click.Path(dir_okay=False),
              help="Output path for merged file. Defaults to overwriting the input file.")
@click.option('--keep-temps', is_flag=True, help="Don't delete temporary files after merge attempt.")
@click.option('-v', '--verbose', is_flag=True, help="Enable verbose output.")
def merge(input_file, output, keep_temps, verbose):
    """Check for conflicts in an EAF file, extract versions, and attempt to merge."""
    logger = setup_logging(verbose)
    input_path = Path(input_file).resolve()

    if output is None:
        output = input_file

    logger.info(f"Processing {input_path.name}")

    # Extract versions using Git
    temp_files = extract_versions_with_git(input_path, logger)

    if not temp_files:
        logger.info("No conflicts to merge. File is unchanged.")
        return 0

    base_file, ours_file, theirs_file = temp_files

    try:
        # Load the three versions into EafTree objects
        logger.debug("Loading EAF files into EafTree objects")
        base_tree = EafTree.from_eaf(base_file)
        ours_tree = EafTree.from_eaf(ours_file)
        theirs_tree = EafTree.from_eaf(theirs_file)

        # Merge the trees
        logger.info("Attempting to merge EAF files")
        merged_tree, problems = merge_trees(base_tree, ours_tree, theirs_tree)

        if problems:
            logger.error("Merge failed with the following problems:")
            for problem in problems:
                logger.error(f"  - {problem}")
            logger.info(f"The three extracted versions have been kept: {Path(base_file).name}, {Path(ours_file).name}, {Path(theirs_file).name}")
            return 1

        # Write the merged result
        logger.info(f"Merge successful. Writing output to {Path(output).name}")
        merged_tree.to_eaf(output)

        # Clean up temporary files unless --keep-temps was specified
        if not keep_temps:
            logger.debug("Removing temporary files")
            for file_path in [base_file, ours_file, theirs_file]:
                Path(file_path).unlink()
        else:
            logger.info(f"Keeping temporary files: {Path(base_file).name}, {Path(ours_file).name}, {Path(theirs_file).name}")

        logger.info("Merge completed successfully")
        return 0

    except Exception as e:
        logger.exception(f"Error during merge: {str(e)}")
        if not keep_temps:
            logger.info("An error occurred, but temporary files will be kept for inspection")
        logger.info(f"Temporary files are: {Path(base_file).name}, {Path(ours_file).name}, {Path(theirs_file).name}")
        return 1

def main():
    cli()

if __name__ == "__main__":
    sys.exit(main())
