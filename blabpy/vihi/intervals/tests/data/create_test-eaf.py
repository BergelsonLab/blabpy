from blabpy.vihi.intervals import templates
from blabpy.vihi.intervals.intervals import create_eaf_from_template, CONTEXT_BEFORE, CONTEXT_AFTER

from blabpy.vihi.intervals.tests.test_intervals import PRE_EXISTING_CODE_INTERVALS
from blabpy.vihi.tests.test_pipeline import TEST_FULL_RECORDING_ID

age_in_days = int(TEST_FULL_RECORDING_ID.split('_')[-1])
# TODO: check if this is correct. Here, it is fine anyway but would be good to know.
age_in_months = int(age_in_days // 30.25)
etf_template_path, pfsx_template_path = templates.choose_template(age_in_months=age_in_months)
# Convert from code intervals to context intervals
context_intervals_list = [(code_onset - CONTEXT_BEFORE,
                           code_offset + CONTEXT_AFTER)
                          for (code_onset, code_offset)
                          in PRE_EXISTING_CODE_INTERVALS]

eaf = create_eaf_from_template(etf_template_path, context_intervals_list=context_intervals_list)
eaf.to_file('test_eaf.eaf')
