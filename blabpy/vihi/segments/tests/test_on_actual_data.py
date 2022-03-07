from pathlib import Path
import os

from blabpy.utils import text_file_checksum


def test_create_eaf_random_regions(tmpdir):
    """
    Tests that create_eaf_random_regions.py works, produces expected files with expected checksums when run when a
    random seed is set and different checksums when it is not.
    """
    # Prepare inputs to the script
    info_spreadsheet_path = Path(tmpdir) / 'info_spreadsheet.csv'
    with info_spreadsheet_path.open('w') as f:
        f.write('\n'.join(['id,age,length_of_recording',
                           'VI_018_924,30,960']))
    output_dir = tmpdir
    script = 'blabpy.vihi.segments.create_eaf_random_regions'

    def _run_the_script(seed=None):
        no_seed_command = f'python -m {script} {info_spreadsheet_path} {output_dir}'
        if seed:
            command = f'{no_seed_command} {seed}'
        else:
            command = no_seed_command
        os.system(command)

    # Run with a seed
    expected_checksums = {'VI_018_924.eaf': 3088937518,
                          'VI_018_924_selected-regions.csv': 174746390,
                          'VI_018_924.pfsx': 1301328091}
    _run_the_script(seed=15)

    for filename in expected_checksums:
        output_file_path = output_dir.join(filename)
        assert output_file_path.exists()
        assert text_file_checksum(output_file_path) == expected_checksums[filename]
        # Otherwise, a ".bak" version will be created by pympi before writing the new file.
        if output_file_path.basename.endswith('.eaf'):
            output_file_path.remove()

    # Check that there are no other files in the output directory (3 output files minus the .eaf file we just deleted
    # plus info_spreasheet.csv)
    assert len(output_dir.listdir()) == 3

    # Run without a seed
    _run_the_script(seed=None)

    for filename in expected_checksums:
        output_file_path = output_dir.join(filename)
        assert output_file_path.exists()
        if output_file_path.basename.endswith('.pfsx'):
            assert text_file_checksum(output_file_path) == expected_checksums[filename]
        else:
            assert text_file_checksum(output_file_path) != expected_checksums[filename]

    # Check that there are no other files in the output directory
    assert len(output_dir.listdir()) == 4
