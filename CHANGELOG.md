# Changelog

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
