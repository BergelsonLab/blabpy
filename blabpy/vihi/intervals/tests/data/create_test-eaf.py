from io import StringIO

import pandas as pd

from blabpy.vihi.intervals import templates
from blabpy.vihi.intervals.intervals import create_eaf_from_template, _extract_interval_info

from blabpy.vihi.tests.test_pipeline import TEST_FULL_RECORDING_ID

age_in_days = int(TEST_FULL_RECORDING_ID.split('_')[-1])
# TODO: check if this is correct. Here, it is fine anyway but would be good to know.
age_in_months = int(age_in_days // 30.25)
etf_template_path, pfsx_template_path = templates.choose_template(age_in_months=age_in_months)


intervals_str = """full_recording_id,sampling_type,code_onset_wav,code_offset_wav,context_onset_wav,context_offset_wav,code_num,on_off
TEST_123_290,random,353000,473000,233000,533000,1,353000_473000
TEST_123_290,random,1200000,1320000,1080000,1380000,2,1200000_1320000"""
intervals_string_i0 = StringIO(intervals_str)
intervals = pd.read_csv(intervals_string_i0)

eaf = create_eaf_from_template(etf_template_path, intervals=intervals)
eaf.to_file('expected.eaf')