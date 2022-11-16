# Test files for top-3, top-4, surplus

This folder contains test files for top-3, top-4, and surplus functions in `blabpy.seedlings.regions.top3_top4_surplus`.
There is a single input file containing a table with processed regions that we will use for all the months.
And then there are eight files with expected outputs:

- Top-3 regions:
  - output_month_06_top_3.csv
  - output_month_08_top_3.csv
  - output_month_14_top_3.csv
- Top-4 regions:
  - output_month_06_top_4.csv
  - output_month_08_top_4.csv
- Surplus regions:
  - output_month_06_surplus.csv
  - output_month_08_surplus.csv
- All together:
  - output_top3_top4_surplus.csv

The script `make_test_files.py` was used to create these files.
