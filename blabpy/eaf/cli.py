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


def check_existing_temp_files(file_path, logger):
    """Check if temporary versions of files already exist."""
    file_path = Path(file_path).resolve()
    base_path = file_path.with_name(file_path.name + ".BASE")
    ours_path = file_path.with_name(file_path.name + ".OURS")
    theirs_path = file_path.with_name(file_path.name + ".THEIRS")
    
    existing_files = []
    if base_path.exists():
        existing_files.append(base_path)
    if ours_path.exists():
        existing_files.append(ours_path)
    if theirs_path.exists():
        existing_files.append(theirs_path)
    
    return existing_files, base_path, ours_path, theirs_path


def extract_versions_with_git(file_path, logger, reuse_temps=False, recreate_temps=False, force_extract=False):
    """Extract base, ours, and theirs versions using Git."""
    if not force_extract and not _is_file_conflicted(file_path, logger):
        logger.info(f"No conflicts detected in {Path(file_path).name}. Use --force to proceed anyway.")
        return None

    if force_extract:
        logger.info(f"Forcing version extraction for {Path(file_path).name} due to --force flag.")
    else:
        logger.info(f"Extracting versions for conflicted file: {Path(file_path).name}")
    
    # Check for existing temp files
    existing_files, base_path, ours_path, theirs_path = check_existing_temp_files(file_path, logger)
    
    # All three version files exist
    if len(existing_files) == 3:
        if recreate_temps:
            logger.info(f"Recreating existing temporary files at user request.")
            for file_path in existing_files:
                logger.debug(f"Removing existing file: {file_path.name}")
                file_path.unlink()
        elif reuse_temps:
            logger.info(f"Reusing existing temporary files: {base_path.name}, {ours_path.name}, {theirs_path.name}")
            return str(base_path), str(ours_path), str(theirs_path)
        else:
            logger.error("Temporary files already exist. Use --reuse-temps to use these files or --recreate-temps to recreate them.")
            logger.info(f"Existing files: {', '.join(f.name for f in existing_files)}")
            logger.info(f"To remove these files manually: rm {' '.join(str(f) for f in existing_files)}")
            return None
    
    # Some but not all files exist
    elif existing_files:
        if recreate_temps:
            logger.info(f"Recreating partial set of temporary files at user request.")
            for file_path in existing_files:
                logger.debug(f"Removing existing file: {file_path.name}")
                file_path.unlink()
        else:
            logger.error("Some temporary files already exist. Use --recreate-temps to recreate them.")
            logger.info(f"Existing files: {', '.join(f.name for f in existing_files)}")
            logger.info(f"To remove these files manually: rm {' '.join(str(f) for f in existing_files)}")
            return None
    
    # No temp files exist (or they were cleared above), proceed with extraction
    file_path = Path(file_path).resolve()
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
def eaf():
    """EAF file utilities."""
    pass

@eaf.command(help="Check for conflicts in an EAF file, extract versions, and attempt to merge.")
@click.argument('input_file', type=click.Path(exists=True, dir_okay=False))
@click.option('-o', '--output', type=click.Path(dir_okay=False),
              help="Output path for merged file. Defaults to overwriting the input file.")
@click.option('--keep-temps', is_flag=True, help="Don't delete temporary files after merge attempt.")
@click.option('--reuse-temps', is_flag=True, help="Reuse existing temporary files if all three exist.")
@click.option('--recreate-temps', is_flag=True, help="Force recreation of temporary files even if they exist.")
@click.option('-v', '--verbose', is_flag=True, help="Enable verbose output.")
@click.option('--force', is_flag=True, help="Force extraction and merge attempt even if the file is not marked as conflicted by Git.")
def merge(input_file, output, keep_temps, reuse_temps, recreate_temps, verbose, force):
    """Check for conflicts in an EAF file, extract versions, and attempt to merge."""
    logger = setup_logging(verbose)
    input_path = Path(input_file).resolve()

    if output is None:
        output = input_file

    logger.info(f"Processing {input_path.name}")

    # Extract versions using Git
    temp_files = extract_versions_with_git(input_path, logger, reuse_temps, recreate_temps, force_extract=force)

    if not temp_files:
        logger.info("No files to merge. Operation canceled.")
        sys.exit(1)

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
            sys.exit(1)

        # Write the merged result
        logger.info(f"Merge successful. Writing output to {Path(output).name}")
        merged_tree.to_eaf(output)

        # Try reading the merged file to validate it
        try:
            EafTree.from_eaf(output)
        except Exception as e:
            logger.error(f"Error reading merged file '{Path(output).name}' with EafTree.from_eaf: {e}")
            logger.info(f"Temporary files are being kept for inspection: {Path(base_file).name}, {Path(ours_file).name}, {Path(theirs_file).name}")
            sys.exit(1)

        # Clean up temporary files unless --keep-temps was specified
        if not keep_temps:
            logger.debug("Removing temporary files")
            for file_path in [base_file, ours_file, theirs_file]:
                Path(file_path).unlink()
        else:
            logger.info(f"Keeping temporary files: {Path(base_file).name}, {Path(ours_file).name}, {Path(theirs_file).name}")

        logger.info("Merge completed successfully")
        sys.exit(0)

    except Exception as e:
        logger.exception(f"Error during merge: {str(e)}")
        if not keep_temps:
            logger.info("An error occurred, but temporary files will be kept for inspection")
        logger.info(f"Temporary files are: {Path(base_file).name}, {Path(ours_file).name}, {Path(theirs_file).name}")
        sys.exit(1)

def main():
    eaf()

if __name__ == "__main__":
    sys.exit(main())
