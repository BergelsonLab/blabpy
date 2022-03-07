import sys
from pathlib import Path

from blabpy.vihi.segments.segments import create_eafs_with_random_regions


if __name__ == "__main__":
    info_spreadsheet_path = Path(sys.argv[1])
    output_dir = sys.argv[2]
    seed = None if len(sys.argv) <= 3 else int(sys.argv[3])
    create_eafs_with_random_regions(info_spreadsheet_path, output_dir, seed=seed)
