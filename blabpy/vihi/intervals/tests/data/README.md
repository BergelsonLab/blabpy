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
