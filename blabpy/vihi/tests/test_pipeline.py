from pathlib import Path

from blabpy.vihi import pipeline
from blabpy.vihi.pipeline import add_intervals_for_annotation
from blabpy.vtc import read_rttm
from blabpy.vihi import paths as vihi_paths
from blabpy.vihi.intervals import intervals as intervals_module


from blabpy.vihi.intervals.tests.test_intervals import _read_intervals_with_metric, _read_sub_recordings


TEST_FULL_RECORDING_ID = 'TEST_123_290'


def _get_test_eaf_path(*args, **kwargs):
    return Path('data/test_eaf.eaf')


def _get_test_vtc_data(*args, **kwargs):
    return read_rttm('data/test_all.rttm')


def _get_expected_eaf_path():
    return Path('data/expected.eaf')


def _test_region_output_files(tmpdir):
    return {
        'eaf': Path(tmpdir / f'{TEST_FULL_RECORDING_ID}.eaf'),
        'pfsx': Path(tmpdir / f'{TEST_FULL_RECORDING_ID}.pfsx'),
        'csv': Path(tmpdir / f'{TEST_FULL_RECORDING_ID}_selected-regions.csv')}


def test_add_intervals_for_annotation(monkeypatch, tmpdir):
    # Monkeypatch functions that look into the VIHI folder on pn-opus.

    # Since we are using a full recording id that can't be in the VIHI folder, the worst thing that can happen,
    # if we forget to patch some functions or `add_intervals_for_annotation` starts using different functions, is the
    # test erroring out before even getting to any assertions.

    region_output_files = _test_region_output_files(tmpdir)

    def __test_region_output_files(*args, **kwargs):
        # The output files need to go to the tempdir
        return region_output_files

    # TODO: that's way too much monkeypatching, break down add_intervals_for_annotation into parts
    monkeypatch.setattr(pipeline, '_region_output_files', __test_region_output_files)
    monkeypatch.setattr(pipeline, 'get_eaf_path', _get_test_eaf_path)
    monkeypatch.setattr(pipeline, 'get_vtc_data', _get_test_vtc_data)
    monkeypatch.setattr(pipeline, 'make_intervals', lambda *args, **kwargs: None)
    monkeypatch.setattr(pipeline, 'gather_recordings', lambda *args, **kwargs: _read_sub_recordings())
    monkeypatch.setattr(pipeline, 'add_metric', lambda *args, **kwargs: _read_intervals_with_metric())
    monkeypatch.setattr(vihi_paths, 'POPULATIONS', ['TEST'])
    monkeypatch.setattr(intervals_module, 'INTERVALS_FOR_ANNOTATION_COUNT', 3)

    # Add intervals
    add_intervals_for_annotation(TEST_FULL_RECORDING_ID)

    # Check the output file
    eaf_path = region_output_files['eaf']
    expected_eaf_path = _get_expected_eaf_path()
    assert eaf_path.read_text() == expected_eaf_path.read_text()
