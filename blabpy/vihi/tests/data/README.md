# Data to test "pipeline" functions

The test of adding high-volubility intervals for annotations currently requires the following files:

- `test_eaf.eaf` - the eaf to which the intervals will be added,
- `test_all.rttm` - the VTC data to calculate the optimized metric.
  Partial copy of an actual .rttm file for the same recording that was used to create sub-recordings in `vihi/intervals/tests/data`.
  Most of the segments outside these modified sub-recordings were manually removed.
  Also, the recording id was replaced by the test one.

Extra:

- `create_test-eaf.py` can be used to recreate `test_eaf.eaf`.
