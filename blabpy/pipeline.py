from pathlib import Path

from tqdm import tqdm

from blabpy.eaf import EafPlus, EafInconsistencyError
from blabpy.utils import concatenate_dataframes


def _extract_aclew_data_from_one_file(eaf_path):
    """
    Extracts annotations and intervals from an EAF file with ACLEW-style annotations.
    :param eaf_path: pat to the EAF file.
    :return: pandas dataframe with annotations in all participant tiers.
    """
    eaf_path = Path(eaf_path)
    eaf = EafPlus(eaf_path)
    try:
        return eaf.get_annotations_and_intervals()
    except EafInconsistencyError as e:
        raise EafInconsistencyError(f'Error in {eaf_path}') from e


def find_eaf_paths(path, recursive=True):
    """
    Finds EAF files in a directory.
    :param path: path to a folder with EAF files or a single EAF file.
    :param recursive: If path is a folder, whether to search for EAF files recursively - in subfolders, subsubfolders,
    etc.
    :return: list of paths to EAF files.
    """
    if isinstance(path, (str, Path)):
        path = Path(path)
    else:
        raise TypeError('path must be a string or a pathlib.Path object')

    if path.is_file():
        assert path.suffix == '.eaf', 'if a file path, must be a path to an EAF file'
        eaf_paths = [path]
    elif path.is_dir():
        glob_pattern = '*.eaf'
        if recursive:
            glob_pattern = '**/' + glob_pattern
        eaf_paths = sorted(list(path.glob(glob_pattern)))
        assert len(eaf_paths) > 0, 'no EAF files found in {}'.format(path)
    else:
        raise ValueError('path must be a file or a directory')
    return eaf_paths


def extract_aclew_data(path, recursive=True, show_tqdm_pbar=False):
    """
    Extracts annotations from EAF files with ACLEW-style annotations. Returns two tables: annotations and intervals.
    Annotations table has one row per participant-level annotation, all extra annotations (vcm, xds, etc.) are
    in their own columns. Intervals table has one row per coding interval. Tables can be merged using the eaf_filename
    and code_num columns.
    column.
    :param path: path to a folder with EAF files or a single EAF file.
    :param recursive: If path is a folder, whether to search for EAF files recursively - in subfolders, subsubfolders,
    :param show_tqdm_pbar: Should we print a tqdm progress bar?
    etc.
    :return: annotations, intervals - two pandas dataframes.
    """
    eaf_paths = find_eaf_paths(path, recursive=recursive)
    if show_tqdm_pbar:
        eaf_paths = tqdm(eaf_paths)

    def extract_from_one_file(eaf_path):
        # return (annotations, intervals, filename) tuple
        return *_extract_aclew_data_from_one_file(eaf_path), eaf_path.name
    annotations, intervals, filenames = (
        zip(*(extract_from_one_file(eaf_path) for eaf_path in eaf_paths)))

    def concatenate(dataframes):
        return concatenate_dataframes(
            dataframes=dataframes,
            keys=filenames,
            key_column_name='eaf_filename')
    return concatenate(annotations), concatenate(intervals)
