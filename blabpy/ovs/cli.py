import click
import os
from datetime import date
from tqdm import tqdm
from blabpy.pipeline import find_eaf_paths
from pathlib import Path

@click.command()
@click.argument('output_folder', required=False, default=None, type=click.Path(file_okay=False))

def ovs_to_csv(output_folder):
    click.echo("=====================================")
    # paths = find_eaf_paths(folder)
    # click.echo(f"Found {len(paths)} .eaf files to validate.")
    if output_folder is None:
        output_folder = './aggregated_csv'
    if not os.path.exists(output_folder):
        os.mkdir(output_folder)
    # click.echo(f"Output folder: {output_folder}")
    # for path in tqdm(paths):
    #     validate_one_file(path, Path(output_folder))
    # click.echo("=====================================")