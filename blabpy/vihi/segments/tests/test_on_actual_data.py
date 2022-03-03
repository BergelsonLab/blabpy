from pathlib import Path
import os


def test_create_eaf_random_regions(tmpdir):
    """
    Tests that create_eaf_random_regions.py works and produces expected files
    """

    info_spreadsheet_path = Path(tmpdir) / 'info_spreadsheet.csv'
    with info_spreadsheet_path.open('w') as f:
        f.write('\n'.join(['id,age,length_of_recording',
                           'VI_018_924,30,960']))
    output_dir = tmpdir
    script = 'blabpy.vihi.segments.create_eaf_random_regions'
    os.system(f'python -m {script} {info_spreadsheet_path} {output_dir}')

    # Check that the output files have been created
    output_files = ['selected_regions.csv', 'VI_018_924.eaf', 'VI_018_924.pfsx']
    for filename in output_files:
        output_file_path = output_dir.join(filename)
        assert output_file_path.exists()

    # Check that there are no other files in the output directory
    assert len(output_dir.listdir()) == 4
