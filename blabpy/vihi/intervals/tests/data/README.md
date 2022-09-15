# Tests for functions that manipulate intervals within day-long recordings

These files are use in `test_intervals.py` and `test_pipline.py`.

## Files

- sub_recordings.csv - slightly edited sub-recordings from an actual file.
- intervals.csv - all intervals that could potentially be sampled from sub_recordings.
  See `make_intervals` for details.

To select high-volubility intervals, we'll need to calculate a metric for each interval.
The following file has arbitrary numbers as the metric:

- intervals_with_metric.csv

If we select the best of these intervals then depending on whether there are already code regions in the eaf, we'll get either of these two:

- best_intervals_01.csv
- best_intervals_02.csv

And if we want to calculat the real deal, we'll need
- `test_all.rttm` - the VTC data to calculate vtc_total_speech_duration for the intervals above.
  Partial copy of an actual .rttm file for the same recording that was used to create sub-recordings above.
  Most of the segments outside these modified sub-recordings were manually removed.
  Also, the recording id was replaced by the test one.
