import random
import shutil
from pathlib import Path

import numpy as np
import pandas as pd
from pprint import pprint

from eaf_plus import EafPlus
from blabpy.vihi.intervals import templates
from blabpy.vihi.intervals.intervals import prepare_eaf_from_template, create_eaf_from_template

'''
Based on code from vihi intervals module, adapted for all eaf related projects and not just vihi
'''

test_file = Path("lobue_04_06.csv")
eaf_file = Path("test_minimal_KN.eaf")
DEFAULT_DURATION_MS = 500  # 500ms

def convert_csv_to_eaf(csv_path: Path, eaf_path: Path, age_in_months: int, has_offset=True):
    """
    Convert a CSV file containing interval annotations to an EAF file.

    Parameters
    ----------
    csv_path : Path
        Path to the input CSV file.
    eaf_path : Path
        Path to the output EAF file.
    age_in_months : int
        Age of the subject in months, used for selecting appropriate templates.
    has_offset : bool
        Whether the CSV contains an offset column.
    """
    # Load CSV data
    df = pd.read_csv(csv_path).dropna()

    # etf_template_path, pfsx_template_path = templates.choose_template(age_in_months=age_in_months)

    eaf = EafPlus()

    for speaker in df["speaker"].unique():
        eaf.add_tier(tier_id=speaker, ling="transcription")
    eaf.remove_tier("default")

    for _, row in df.iterrows():
        tier_name = row["speaker"]
        start_time = int(row["onset"])
        if not has_offset:
            end_time = start_time + DEFAULT_DURATION_MS
        else:
            end_time = int(row["offset"])
        annotation_value = row["annotation"]

        eaf.add_annotation(tier_name, start_time, end_time, value=annotation_value)
    
    eaf.to_file(eaf_path)



if __name__ == "__main__":
    convert_csv_to_eaf(
        csv_path=test_file,
        eaf_path=test_file.with_suffix('.eaf'),
        age_in_months=9,
        has_offset=False
    )

