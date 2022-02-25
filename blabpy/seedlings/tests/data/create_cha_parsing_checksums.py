"""
Use this script to update cha_parsing_checksums.csv
"""
import tempfile
from pathlib import Path

import pandas as pd

from blabpy.seedlings.cha import export_cha_to_csv
from blabpy.utils import text_file_checksum


def export_and_get_checksums(cha_path: Path, output_dir):
    input_md5 = text_file_checksum(cha_path)
    export_cha_to_csv(cha_path, output_dir)
    output_path = output_dir / cha_path.name.replace(".cha", "_processed.csv")
    output_md5 = text_file_checksum(output_path)
    return cha_path.name, input_md5, output_md5


test_data_dir = Path('blabpy/seedlings/tests/data/')
assert test_data_dir.exists(), 'Run from the repo root instead'
cha_dir = test_data_dir / 'annotated_cha/annotated_cha/'
cha_paths = list(cha_dir.glob('*.cha'))
assert len(cha_paths) == 527, 'Have you checked out the submodule? Has the actual number of cha files changed?'


with tempfile.TemporaryDirectory() as temporary_directory:
    checksums = [export_and_get_checksums(cha_path, Path(temporary_directory)) for cha_path in cha_paths]


cha_parsing_checksums_df = pd.DataFrame(
    columns=['cha_filename', 'cha_checksum', 'exported_csv_checksum'],
    data=(sorted(checksums))  # sorting is effectively done by child, then month
)

cha_parsing_checksums_df.to_csv(test_data_dir / 'cha_parsing_checksums.csv')
