# For setting up Command Line Interface (CLI) for validate.py
# Can be added to for other CLI features that can be used by multiple projects

import click
import os
from datetime import date
from tqdm import tqdm
from blabpy.pipeline import find_eaf_paths
from blabpy.validate import validate_one_file
from pathlib import Path

@click.command()
@click.argument('folder', required=True, type=click.Path(exists=True))
@click.argument('output_folder', required=False, default=None, type=click.Path(file_okay=False))

def validate(folder, output_folder):
    click.echo("setup")
    click.echo(folder)
    click.echo("=====================================")
    paths = find_eaf_paths(folder)
    click.echo(f"Found {len(paths)} .eaf files to validate.")
    if output_folder is None:
        today = date.today().strftime("%Y-%m-%d")
        output_folder = Path(folder) / f'{today}_validation_reports'
    if not os.path.exists(output_folder):
        os.mkdir(output_folder)
    click.echo(f"Output folder: {output_folder}")
    for path in tqdm(paths):
        validate_one_file(path, Path(output_folder))
    click.echo("=====================================")