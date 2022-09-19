# Tests blabpy.vihi.intervals.cli.cli_batch_create_files_with_random_regions
# I wasn't able to write a proper test so this was run by hand :-(
# Mostly, I was scared to mess up some actual VIHI files.

from pathlib import Path

from blabpy.paths import PN_OPUS, get_pn_opus_path
from blabpy.vihi.paths import get_lena_recording_path, parse_full_recording_id
from blabpy.vihi.intervals.cli import cli_batch_create_files_with_random_regions
from blabpy.utils import modified_environ

import pandas as pd

info_spreadsheet = \
    pd.DataFrame(columns='id,age,length_of_recording'.split(','),
                 data=('VI_666_924,30,960'.split(','),
                       'VI_777_234,12,360'.split(','),
                       'VI_888_098,17,640'.split(',')))

zhenya_pn_opus_mock = Path('/Volumes/pn-opus/VIHI/WorkingFiles/zhenya')

pn_opus_path = get_pn_opus_path()
for row in info_spreadsheet.itertuples():
    path = get_lena_recording_path(**parse_full_recording_id(row.id))
    zhenya_pn_opus_mock.joinpath(path.relative_to(pn_opus_path)).mkdir(exist_ok=True, parents=True)

# Works fine
info_spreadsheet_path = zhenya_pn_opus_mock / 'info_spreadsheet.csv'
info_spreadsheet.iloc[:2].to_csv(info_spreadsheet_path)
with modified_environ(**{PN_OPUS: str(zhenya_pn_opus_mock)}):
    args = [str(info_spreadsheet_path)]
    cli_batch_create_files_with_random_regions(args=args)

# Throws an error
info_spreadsheet.iloc[1:].to_csv(info_spreadsheet_path)
with modified_environ(**{PN_OPUS: str(zhenya_pn_opus_mock)}):
    args = [str(info_spreadsheet_path)]
    cli_batch_create_files_with_random_regions(args=args)
