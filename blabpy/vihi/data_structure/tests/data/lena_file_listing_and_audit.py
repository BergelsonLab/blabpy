"""
To do any kind of testing of LENA (and later the whole VIHI) data structure we need a way to keep it constant, so that
we can know that (a) the results haven't changed after refactoring if the files haven't, (b) the changes are due to the
changes to the code, not the files. So, we do the testing with the help of the following files:

- `lena_file_listing.csv` lists all the files and folder under the LENA folder, except for the contents of the .git
  folders.
- several info sheets from the vihi_data_check folder:
    - 'LENA/expected_recordings.csv' - list (manually updated) of expected recordings, likely redundant,
    - 'VIHI_participant_IDs.csv' - list of all VIHI recordings,
    - 'LENA/extra_information/clan_files_list.csv' - list of the recordings that have been annotated in CLAN
- `lena_audit_results.csv` is the output of audit_all_lena_recordings run on the actual folder.

Once you are happy about the results on the files listed in `lena_file_listing.csv`, run this script to update both
files.
"""

import os
from pathlib import Path
from shutil import copy2

import pandas as pd

from blabpy.vihi.data_structure.lena import audit_all_lena_recordings
from blabpy.vihi.paths import get_lena_path, get_vihi_path

lena_path = get_lena_path()

# 1. Locate the folder for the files to be saved
test_data_dir = Path('blabpy/vihi/data_structure/tests/data')
assert test_data_dir.exists(), 'Run from the repo root instead'


# 2. List all the files in the LENA folder

# Tuples (<path relative to lena_path>, <is it a folder?>)
object_records = list()
# topdown=True allows to modify dirs in place and not walk into ignored folders
for root, dirs, files in os.walk(lena_path, topdown=True):
    root_relpath = os.path.relpath(root, lena_path)
    for file in files:
        object_records.append((os.path.join(root_relpath, file), False))
    for dir_ in dirs:
        object_records.append((os.path.join(root_relpath, dir_), True))

    # Remove .git folder before recursing
    exclude = ['.git']
    dirs[:] = [d for d in dirs if d not in exclude]


lena_file_listing = pd.DataFrame(columns=['relative_path', 'is_folder'], data=object_records)
lena_file_listing.to_csv(test_data_dir / 'lena_file_listing.csv', index=False)

# 3. Copy the info sheets
real_vihi_data_check_path = get_vihi_path() / 'Scripts' / 'vihi_data_check'
relative_paths = ('LENA/expected_recordings.csv', 'VIHI_participant_IDs.csv',
                  'LENA/extra_information/clan_files_list.csv')
for rpath in relative_paths:
    copy_from = real_vihi_data_check_path / rpath
    copy_to = test_data_dir / rpath
    copy_to.parent.mkdir(parents=True, exist_ok=True)
    copy2(copy_from, copy_to)


# 4. Check LENA files and folders

lena_audit_results = audit_all_lena_recordings()
lena_audit_results.to_csv(test_data_dir / 'lena_audit_results.csv', index=False)
