import click
from ..pipeline import extract_aclew_data
from .paths import get_ovs_path, get_ovs_annotation_path
from pathlib import Path
import os
from pyprojroot import find_root
import csv

@click.group()
def ovs():
    """OVS file utilities."""
    pass

@ovs.command()
@click.argument('output_folder', required=False, default=None, type=click.Path(file_okay=False))

def aggregate(output_folder):
    """Aggregate OvS annotations into one CSV file."""
    root_dir = find_root('.git')
    OVS_PATH = get_ovs_path()
    ANNOTATION_PATH = get_ovs_annotation_path()
    if root_dir != OVS_PATH:
        raise ValueError("Please run this script from the OvS project root directory.")
    
    click.echo("=====================================")
    click.echo(f"\nExtracting OvS annotations:")

    annotations, intervals = extract_aclew_data(ANNOTATION_PATH, show_tqdm_pbar=True)
    click.echo(f"\nFinished extracting annotations.")

    if output_folder is None:
        output_folder = Path('./aggregated_data')

    if os.path.exists(output_folder):
        click.echo(
            click.style(
                f"\nThis process will override existing files in folder: {output_folder}." 
                "\nMake sure the data has been committed to GitHub or backed up elsewhere if needed."
            , fg='red')
        )
        click.confirm('\nDo you want to continue?', abort=True)

    click.echo(f"\nWriting aggregated annotations to CSV in folder: {output_folder}")
    ovs_to_csv(annotations, output_folder / 'annotations.csv')
    ovs_to_csv(intervals, output_folder / 'intervals.csv')
    click.echo(f"\nFinished writing aggregated annotations to CSV.")

    click.echo("=====================================")

def ovs_to_csv(df, path):
    '''This function is adapted from https://github.com/BergelsonLab/vihi_annotations/scripts/update.py: to_csv() method,"
    which was adapted from blabpy.seedlings.gather.write_all_basic_level_to_csv which, in turn, was adapted from a reddit
    post.

    Write to csv with the following conventions:
    - NA/NaN values are written as `NA` (no quotes).
    - Empty strings are written as `""` (empty pair of quotes).
    - Non-NA strings are quoted.
    - Numeric types are not quoted.

    There are several reasons why we do it like that:
    - If you have `1` in one column and `"1"` in another, pd.to_csv() will, by default, write both as `1` losing the
      data type information. That information would also be lost if we were to quote all values. The above way cleary
      distinguishes between numeric and string values in the text of the csv file.
    - By default, pd.read_csv() will write both `""` and NA string values as empty strings. And if you specify
      `na_rep` (e.g., `na_rep="NA"`), it will write the same value both for `""` and NA string values as `NA` even
      though `isna()` and friends do **not** consider `""` to be NA. Obviously, dealing with blank vs. missing strings
      is a mess not just in pandas but that inconsistency is particularly annoying.
    - Finally, this way is more consistent with `readr::write_csv` and `tidyverse` in general and `readr` in particular
      are overall better at being internally consistent.    
    '''
    na = type("NaN", (float,), dict(__str__=lambda _: "NA"))()
    df.to_csv(path, index=False, quoting= csv.QUOTE_NONNUMERIC, na_rep=na)