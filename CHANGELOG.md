# Changelog

## [0.38.0] - 2025-11-18

### Added

- New script `validate.py` and command line interfact `blabpy.cli`, which can be called by `validate`
- Initialize `blabpy.ovs` module with simple `paths` method. To be added.

### Fixed

- Resolve issue #33, rename CLI `blabpy -m blabpy.eaf.cli merge` to eaf and create the CLI entry point 

## [0.37.0] - 2025-05-28

### Added

- Module `blabpy.eaf.merge`, mainly function `merge_trees`.
- CLI `blabpy -m blabpy.eaf.cli merge`. A console script hasn't been added yet (see issue #33).
- Extended `blabpy.eaf.eaf_tree.EafTree` functionality in service of merging but useful in general.

### Fixed

- Multiple bugs in `blabpy.eaf.EafTree`.

## [0.36.0] - 2025-03-06

### Fixed

- `vihi annotation start` would intermittently fail with a "the remote end hung up unexpectedly" error. This seems to mostly happen during the push to the annotations repo on Blab share. Now, the script will try harder, and if that doesn't help, just skip the push - we can always do it manually later.
- The error in `blabpy.paths.get_blab_share_path` was incorrectly formatted and ended up being printed as a tuple of string instead of a single string making the message unreadable.

### Added

- A console script to create individual sparsely cloned one_time_scripts folders. See the [one_time_scripts repo](https://github.com/BergelsonLab/one_time_scripts) for details.

## [0.35.0] - 2025-02-26

### Added

- Add method `blabpy.eaf.eaf_tree.Tier.add_alignable_annotation(onset_ms, offset_ms, value=None)`.

### Changed

- Method `blabpy.eaf.eaf_tree.Tier.add_reference_annotation` no longer requires the caller to provide an annotation id for the added annotation.

## [0.34.0] - 2025-02-25

### Added

- Function `blabpy.utils.source` that does something similar to R's `source`. See the function's docstring for details.

## [0.33.1] - 2025-02-21

### Fixed

- Bug in VIHI reliability coding. The code wasn't updated to match the updates to the code that extracts annotations from EAFs as tables: the transcription annotation ID column is now called `transcription_id` instead of `participant_annotation_id`.

### Improved

- When writing EAF files to disk, LF is used for end of line - independent of the platform.

## [0.33.0] - 2024-12-15

### Added

- When updating the seedlings-nouns dataset, we now use hard-coded values for "audio_06_17" sub-recordings and duration.
  This was necessary because the wav file was cropped while .its and .cha weren't edited so we couldn't get the right numbers from the .its.

### Fixed

- Instructions printed to the user for `seedlings nouns update` needed an update.
- A number of outdated references to the Duke network drive name "PN-OPUS". Change to "BLab share".

## [0.32.1] - 2024-06-18

### Changed

- Refactored code in `blabpy.vihi.intervals.intervals` so that it can be at least partially reused for creating EAFs outside the VIHI corpus.
  See "2024-06-18_cds-tiers-for-Jasenia" in "one_time_scripts" for an example.

## [0.32.0] - 2024-06-18

### Fixed

- Make `blabpy.eaf.eaf_tree` work with Python versions before 3.10.
  Before 3.10, class code couldn't refer to the class's static methods which I was doing in `Annotation`: I was using the static method `conditional_property` as a decorator.
  I moved that function outside of the class.
  Ultimately, we should find a better solution instead of using the decorator pattern or simply have two separate classes for alignable and reference annotations.

### Added

- `Annotation`, `Tier`, and `ExternalReferenc` got `__repr__` methods.

## [0.31.3] - 2024-06-14

### Fixed

- Fixed a bug where parallel annotation script would fail on Windows due to the path to the `.../LENA/annotations/` repo having a single slash instead of a double slash before "//sox4.unive...". 

## [0.31.2] - 2024-06-09

Note: 0.31.1 was an unsuccssful attempt to fix the bug described below and I yanked it from PyPI.

### Fixed

- Build: fixed the path to `sub-recordings_special-cases` in setup.py - they weren't being included in the PyPI version (and they wouldn't be included in any non-editable install for that matter).

## [0.31.0] - 2024-06-05

### Added

- Add methods `add_tier` and `drop_tier` to `EafTree`.
  `add_tier` currently only supports adding dependent tiers.

## [0.30.0] - 2024-05-25

### seedlings-nouns v2.0.0-dev.2

#### Changed

- recordings.csv
  - Add surplus_ms to recordings.csv.
  - Exclude silences when calculating surplus for months 6 and 7, current definition: surplus = all \ (top 4 ⋃ silences).
  - Durations columns in recordings.csv are now called: duration_ms, listened_ms, surplus_ms.
  - Add human-readable durations: duration_time, listened_time, surplurs_time.
  - Millisecond-precision recording durations (used to be based on datetimes).
  - Listened time is now defined as top 4 (06-13) or top 3 (14-17) for all months, incl. 06 and 07. Used to be all minus the silences for months 6 and 7. To get that, add up listened and suprlus durations.

#### Fixed 

- Trimmed subregions that ended past the recording end. These existed because we calculated subregions' onset and offsets based on the 5min.csv files from LENA assuming that each 5 minute interval in them corresponded to 5 minutes of the recording while in reality they corresponded to 5 minutes of the clock time which corresponded to shorter parts of the recording at the boundaries of sub-recordings. E.g., if the recording went continuously from 06:04:00 am to 10:04:00 pm, the 5 min intervals would go from 06:00:00 am to 10:05:00 pm and the subregion spanning the last 12 intervals would end 5 minutes after the recording did.
- Durations (duration_ms and duration_time) in recordings.csv had to be updated (shortened) correspondingly. This trimming resulted in only one recording - 44_08 - to no longer having enough listen time. We will code a 5-min-long makeup region for that recording to get it over 3 h 45 min.
  
### Other

- BLAB_DATA:
  - Avoid putting repos into a headless state unnecessarily. If the commit pointed to by the version tag is already checked out, there is no need to checkout the tag and get the repo off the branch. This is helpful when you are updating the latest version as you don't need to checkout main before committing.


## [0.29.1] - 2024-04-08

### Added

- Switch to the Harvard BLab share when looking up data files.
- Use `get_blab_share_path` to get the path to BLab share.
- `blabpy.eaf.eaf_tree.EafTree.update_cve_refs` that updates the `cve_ref` of all annotations in the EAF file to match the controlled vocabulary.
  Used when the controlled vocabulary definitions have been moved to an external .ecv file and the cve_id's of the entries have been updated.
  Even if they haven't been updated, they will only match one file, so if the CV was defined in multiple ones, you'll still need to do it.
  Load the EAF skipping the CV entry validation, run the method, and save the EAF:

      ```python
      from blabpy.eaf.eaf_tree import EafTree
      eaf_path = ...
      eaf_tree = EafTree.from_eaf(eaf_path, validate_cv_entries=False)
      eaf_tree.update_cve_refs()
      eaf_tree.to_eaf(eaf_path)
      ```
- `blabpy.eaf.eaf_tree.EafTree` now returns a meaningful error message if an annotation on a CV-based tier has a `cve_ref` that is not in the controlled vocabulary.
- `blabpy.vihi.paths.get_eaf_path` now accepts `lena_annotations_path` making it possible to work with local clones of VIHI_LENA.

### Fixed

- `to_eaf` is now in `blabpy.eaf.eaf_tree.EafTree` instead of `blabpy.eaf.eaf_tree.XMLTree` where it was a leftover from a refactoring.
- On Windows, make sure that paths within the BLab share that start with a drive letter have a slash between that letter and the rest of the path.
  Otherwise, for example, annotations-in-progress folders will have a remote url which is not valid as far as git is concerned.
- VIHI annotations-in-progress repos now have correctly set tracking branches.v

### Changed

- VIHI annotations-in-progress folders call the remote "blab_share" instead of "vihi_main" which sound like it referred to the GitHub repo.

### Removed

- Removed `get_pn_opus_path`. Use `get_blab_share_path` from now on.

## [0.29.0]

### Added

- When extracting annotations from VIHI EAF files:
  - Call the columns with transcriptions and their annotation IDs - `transcription` and `transcription_id`, respectively.
  - Strip whitespace from the interval-level tiers.

## [0.28.0]

### Added

When extracting annotations from VIHI EAF files, extract high-volubility interval ranks used when they were selected from `selected_regions.csv` files.

## [0.27.0]

### Added

When extracting annotations from EAF files, extract `is_silent` tier too.

## [0.26.0]

### Added

- When EAF files are exported to pandas dataframes, we now differentiate between missing segments that get "NA" values in the output table and empty segmwents that get "".

### Fixed

- EAF export no longer breaks when an intermediary annotation segment is empty. For example, it is no longer a problem to have a non-empty CDS segment while its parent XDS segment is empty.

## [0.25.2] - 2024-01-24

### Fixed

- For the purposes of testing the reliability of closed-set VIHI annotations, we now consider an interval as annotated only if it has at least one annotated segment that is fully inside the interval.
  Before, intervals that contained one segment that started inside the interval but ended outside of it were considered annotated too and some of those got sample for the reliability testing.

## [0.25.1] - 2024-01-23

### Fixed

- I messed up 0.25.0 and had to force-push the updated version to GitHub and delete the incorrect version from PyPI.
  PyPI doesn't allow re-uploading the same version, so I had to bump the version number.

## [0.25.0] - 2024-01-23

### Fixed

- Parallel annotation is ready to start being used by RAs:
  - Multiple bug fixes.
  - Improved messages.

## [0.24.0] - 2024-01-03

### Added

- `EafTree` now parses timestamps which are accessible via properties `onset` and `offset` of `Annotation`s.

## [0.23.1] - 2024-01-03

### Fixed

- `blabpy.eaf.eaf_tree` now correctly treats annotations with "", None, and all-whitespace value as empty.

## [0.23.0] - 2024-01-03

### Added

- Setters for properties `value` and `cve_ref` of class `Annotation` (in `blabpy.eaf.eaf_tree`) setters that update the XML tree accordingly.
- A convenience method `Annotation.clear_value()` that sets the annotation value to an empty string.

## [0.22.0] - 2023-12-11

### Improved

The progress bar for git operation now creates a new bar for each stage of the operation instead of confusingly resetting several times.

### Fixed

Updated the docstring of `blabpy.git_utils.sparse_clone`: added missing parameters, fixed typos.

## [0.21.1] - 2023-12-08

### Fixed

- `blabpy.eaf` is usable again, after removing circular imports introduced by refactoring it in the previous version.

## [0.21.0] - 2023-12-08

### Added

- `blabpy.eaf.eaf_tree.EafTree` class that allows to work with EAF files as XML trees.
  Easy to navigate that tree because elements are interconnected respecting for the XML and ACLEW hierarchies.
  Editing is controlled so that all changes propagate to all the necessary places in the tree.
  This is great for those of us on the more neurotic side of the spectrum.

## [0.20.1] - 2023-11-30

### Fixed

- When creating reliability assessment files (see `blabpy.vihi.pipeline` and `blabpy.vihi.reliability`), descendants of the removed interval-level annotations (of code, context, etc.) are now removed as well.

## [0.20.0] - 2023-11-30

### Added

- `blabpy.vihi.reliability` module for preparing EAF for reliability coding.
- `blabpy.vihi.pipeline.create_reliability_test_file` that add input-output for this.

## [0.19.1] - 2023-11-27

### Added

- `EafPlus.get_annotations` and `EafPlus.get_annotations_and_intervals` now have a new `drop_empty_tiers` argument that defaults to `True`. If `True`, empty tiers are dropped from the output. If `False`, empty tiers are included in the output as completely empty annotations.

### Fixed

- `EafPlus.get_flattened_annotations_for_tier` (prev.`EafPlus.get_full_annotations_for_tier`) now correctly handles tiers with empty annotations (i.e., the annotation value is an empty string) as empty and these tiers get an empty row in the output table.
- `EafPlus.get_annotations_and_intervals` now correctly handles empty tiers and assigns them code_num of <NA> instead of -1 to differentiate them from filled-in annotations outside any code intervals.
- `EafPlus.get_annotations_and_intervals` has a docstring now.

### Changed

- `EafPlus.get_full_annotations_for_tier` renamed to `EafPlus.get_flattened_annotations_for_tier` because the `full` part was unclear - full as compared to what? Also, `flattened` implies that there is a hierarchy involved, which implicitly says what the function does - returns a table where each row is an utterance and all its annotations.

## [0.19.0] - 2023-11-21

### Added

- Add `get_intervals` and `get_annotations_and_intervals` to `blabpy.eaf.EafPlus`.
- Unrelated: new function `blabpy.utils.chdir_relative_to_project_root` that's useful for one-time scripts.

### Changed

- Renamed:
  - `extract_aclew_annotations` to `extract_aclew_data` in `blabpy.pipeline`. 
  - `get_full_annotations` to `get_annotations` in `blabpy.eaf.EafPlus`.
  - `get_annotations` now sorts the output by onset, offset, and participant for consistency.
- `extract_aclew_data` now return both the annotations and the intervals.

### Fixed

- `get_pn_opus_path` now handles paths with `~`.

## [0.18.0] - 2023-11-08

### Changed

- Update `EafPlus.get_full_annotations_for_participant` to account for branching annotation tiers.

### Added

- New function `blabpy.pipeline.extract_aclew_annotations` that can do that for a single EAF file or for a folder with multiple EAF files.

## [0.17.0] - 2023-10-19

### Added

- Command `vihi annotation start` that sets up an individual annotations-in-progress folder for one annotator and one recording ID.
  See "Parallel Annotation" on GitBook for instructions on how to use.

---
The format of the changelog is (not thoroughly) copied from [keep-a-changelog](https://raw.githubusercontent.com/olivierlacan/keep-a-changelog/main/CHANGELOG.md).
