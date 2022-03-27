from pathlib import Path
import os

from blabpy.utils import text_file_checksum


def test_create_eaf_random_regions(tmpdir):
    """
    Tests that create_eaf_random_regions.py:
    - produces some files when run without a seed and these files are different from those created when run with the
      seed from the next check,
    - when run with 15 as the random seed, produces the files with expected contents,
    - if output files already exist, the script errors out, the files do not change.
    """
    # Prepare inputs to the script
    info_spreadsheet_path = Path(tmpdir) / 'info_spreadsheet.csv'
    with info_spreadsheet_path.open('w') as f:
        f.write('\n'.join(['id,age,length_of_recording',
                           'VI_666_924,30,960']))
    output_dir = tmpdir
    script = 'blabpy.vihi.intervals.create_eaf_random_regions'

    def _run_the_script(seed=None):
        no_seed_command = f'python -m {script} {info_spreadsheet_path} {output_dir}'
        if seed:
            command = f'{no_seed_command} {seed}'
        else:
            command = no_seed_command
        return os.system(command)

    # Run without a seed
    _run_the_script(seed=None)

    expected_checksums = {'VI_666_924.eaf': 3088937518,
                          'VI_666_924_selected-regions.csv': 2384423837,
                          'VI_666_924.pfsx': 1301328091}
    for filename in expected_checksums:
        output_file_path = output_dir.join(filename)
        assert output_file_path.exists()
        if output_file_path.basename.endswith('.pfsx'):
            assert text_file_checksum(output_file_path) == expected_checksums[filename]
        else:
            assert text_file_checksum(output_file_path) != expected_checksums[filename]
        # Remove the file for the next run - with a seed
        output_file_path.remove()

    # Check that there are no other files in the output directory (3 output files minus the .eaf file we just deleted
    # plus info_spreasheet.csv)
    assert len(output_dir.listdir()) == 1

    # Run with a seed
    _run_the_script(seed=15)

    def _check_files_and_checksums():
        for filename in expected_checksums:
            output_file_path = output_dir.join(filename)
            assert output_file_path.exists()
            assert text_file_checksum(output_file_path) == expected_checksums[filename]

        # Check that there are no other files in the output directory
        assert len(output_dir.listdir()) == 4

    _check_files_and_checksums()

    # Run when the output files already exist
    return_code = _run_the_script(seed=None)
    assert return_code != 0
    _check_files_and_checksums()
