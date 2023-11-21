# Changelog

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
