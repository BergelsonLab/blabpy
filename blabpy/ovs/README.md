# OvS subpackage

This module was created to specifically handle OvS files. Originally, files for OvS were either:
1. Taken from Seedlings. In this case, the files had random intervals generated using the different sampling functions from the VIHI subpackage
2. Taken from VIHI. In this case, the relevant files were just copied wholesale to OvS.

This means that there wasn't a well-established pipeline for handling new files for OvS. Since most of the sampling methods were taken from VIHI, a lot of VIHI quirks could not be personalized to OvS. In addition, all these scripts were kept as one-time-scripts and not easy to traceback. This subpackage was an attempt to give OvS its own pipeline.

`paths.py` and `pipeline.py` are similar to other subpackages. `paths.py` provides utility function for accessing OvS files on blab_share. `pipeline.py` has functions for generating random samples. Now, even though these have been somewhat adapted to OvS, a lot of it is still built upon VIHI functions. I did not feel like merely copying every function into this subpackage just for the sake of having those functions, and so anything that didn't need modification, I just import them from VIHI. As I work on more functionality, I might decide to bring in these functions. Either way, this is a note so that you don't loop back and forth between files. Understand how VIHI sampling works first (in the vihi subpackage) before going through OvS.

`cli.py` provides command line interface for aggregating the finished annotations on blab_share into one csv file.