from pandas.core.util.hashing import hash_pandas_object

from blabpy.seedlings.paths import get_seedlings_path
from blabpy.pipeline import extract_aclew_annotations
from blabpy.utils import text_file_checksum


def test_extract_aclew_annotations():
    """
    Test that the output stays the same at least for one folder.
    """
    eaf_folder_path = get_seedlings_path() / 'ACLEW/random_sample_project/raw_BER'

    # Check that the inputs haven't changed
    eaf_paths = eaf_folder_path.rglob('*.eaf')
    eaf_checksums = {str(eaf_path.relative_to(eaf_folder_path)): text_file_checksum(eaf_path)
                     for eaf_path in eaf_paths}
    eaf_checksums_expected = {
        '3749.eaf': 3282470484,
        '7758.eaf': 2616913965,
        '1618.eaf': 3472529539,
        '6035.eaf': 902567507,
        '5750.eaf': 938162579,
        '2927.eaf': 2820695506,
        '3895.eaf': 948348733,
        '0396.eaf': 27996118,
        '3749_scrubbed.eaf': 1717865818,
        '1196.eaf': 3382454970,
        '1844.eaf': 232122489}
    assert eaf_checksums == eaf_checksums_expected

    # Run the function
    annotations_df = extract_aclew_annotations(eaf_folder_path)

    # Check the hash of the output. The row order is irrelevant, so adding up the row hashes is enough.
    assert hash_pandas_object(annotations_df, index=False).sum() == -2020487846706632565
