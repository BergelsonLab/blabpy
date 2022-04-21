import argparse
from pathlib import Path

from blabpy.vihi.intervals.intervals import batch_create_files_with_random_regions


def cli_batch_create_files_with_random_regions():
    parser = argparse.ArgumentParser()
    parser.add_argument('info_spreadsheet_path', help='Path to the info_spreadsheet.csv file.')
    parser.add_argument('seed', nargs='?', default=None, help='Optional seed argument. Used mostly for testing.')
    args = parser.parse_args()
    batch_create_files_with_random_regions(Path(args.info_spreadsheet_path), seed=args.seed)


if __name__ == "__main__":
    cli_batch_create_files_with_random_regions()
