# Changelog

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
