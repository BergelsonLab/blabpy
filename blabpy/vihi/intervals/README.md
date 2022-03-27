This subpackage (`blabpy.vihi.intervals`) is, at the moment of the first commit, a copy of the [etf_to_eaf][etf_to_eaf] repository. 

The scripts in the repo created eaf files with randomly distributed intervals that are then annotated.
The point of copying these scripts to blabpy is to unify the distribution of this code and then update it by udpateing blabpy, not files on a shared drive.

# Scripts

## Random samples

### create_eaf_random_regions.py

1. Make sure you have [blabpy][blabpy] installed.
2. Run
    ```
    python -m blabpy.vihi.intervals.create_eaf_random_regions path/to/info_spreadsheet.csv path/to/output_dir [random_seed]
    ```

where:
- `info_spreadsheet.csv` contains (at least) three columns: `id`, `age` and `length_of_recording` (in minutes); you can get that last piece of information using `soxi -D path/to/recording.wav` -- the result will be displayed in seconds.
- `output_dir/` will contain:
   - "<id>.eaf" - the age-specific template with the random regions added,
   - "<id>.pfsx" - the age-specific ELAN preference file, 
   - "<id>_selected_regions.csv" - list of the randomly selected regions.
- [random_seed] integer used as a random seed for reproducible results. 
  The seed will be set once before processing all the recording in `info_spreadsheet.csv`, so the results will only be the same if the contents of `info_spreadsheet.csv` are identical.
  Because of that, only makes sense for the testing purposes.

## _Notes_

- there are different etf templates for different ages, so the info spreadsheet has to contain an `age` column, a `length_of_recording` column and an `id` column containing the name of the recording
- `etf_templates/` contains age-specific ACLEW templates and the corresponding ELAN preference files,
- `templates.py` finds the right template and preference file for a given age,
- `intervals.py` contains the functions necessary to randomly select non overlapping random regions, add them to a template, batch-process "info_spreadsheet.csv".

[etf_to_eaf]: https://github.com/BergelsonLab/etf_to_eaf
[blabpy]: https://github.com/BergelsonLab/blabpy
