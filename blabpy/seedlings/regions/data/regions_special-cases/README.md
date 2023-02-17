# Regions: Special Cases

Regions for three audio recordings couldn't be extracted directly from the data:

- 20_12, subregion rank 3 was skipped during the annotation process, subregions 4 and 5 were annotated as rank 3 and 4 respectively.
  We'll update the regions to reflect this: subregions ranked 3, 4, and 5 will change rank to 5, 3, and 4 respectively.
- 06_07, 22_07: after excluding silences, the total duration of subregions was less than 4 hours.
  We'll emulate what an annotator would have done in this case: we'll add an extra region (we can't use a makeup region, because there is not time left in the subregions).
- 25_12, makeup regions in subregion ranked 5 weren't marked. We'll add them here until the cha file is fixed.

Files that are in this folder are manually created rows with regions that have to be added/switched when preparing regions for listened_time/top3/top4.
Files in `./original/` are what raw/processed regions for corresponding recordings looked like when the manually created files were created.
These "original" files are used to make sure that the data hasn't changed since then.
If it did, the manually created files need to be updated, so do original files, and then a new version of blabpy needs to be releaseds.
