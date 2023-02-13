from pathlib import Path

import pandas as pd

from blabpy.seedlings.pipeline import get_processed_audio_regions, gather_recording_public_info
from blabpy.seedlings.regions.top3_top4_surplus import get_top3_top4_surplus_regions, get_top_n_regions, \
    get_surplus_regions, assign_tokens_to_regions, TOP_3_KIND, SURPLUS_KIND

processed_regions = get_processed_audio_regions(2, 8)
test_dir = Path('/Users/ek221/blab/blabpy/repo/blabpy/seedlings/tests/data/top3_top4_surplus')


processed_regions = get_processed_audio_regions(2, 8)
processed_regions.to_csv(test_dir / 'input_processed_regions.csv', index=False)


# top-3, top-4
for month in ('06', '08', '14'):
    for n_hours in (3, 4):
        # top-4 is undefined for month 14 for which only three hours were annotated
        if month == '14' and n_hours == 4:
            continue
        
        top_n_regions = get_top_n_regions(processed_regions, month=month, n_hours=n_hours)
        top_n_regions.to_csv(test_dir / f'output_month_{month}_top_{n_hours}.csv', index=False)


# surplus
for month in ('06', '08'):
    surplus_regions = get_surplus_regions(processed_regions, month=month)
    surplus_regions.to_csv(test_dir / f'output_month_{month}_surplus.csv', index=False)

# all together
top3_top4_surplus_regions = get_top3_top4_surplus_regions(processed_regions, month='08')
top3_top4_surplus_regions.to_csv(test_dir / 'output_top3_top4_surplus.csv', index=False)


# # Tokens
global_basic_level_path = Path.home().joinpath('blab/one_time_scripts-separate-folders/ek_seedlings_nouns',
                                               '20221003_seedlings_nouns/data/global-basic-level.csv')
global_basic_level_audio = (
    pd.read_csv(global_basic_level_path,
                dtype=dict(ordinal=pd.Int64Dtype(), tier=str, pho=str, subj=str, month=str))
    .loc[lambda df: df.audio_video == 'audio'])

tokens = (global_basic_level_audio
          .loc[lambda df: df.SubjectNumber == '02_08']
          [['annotid', 'onset']]
          .sample(frac=0.05, random_state=7))
tokens.to_csv(test_dir / 'input_tokens.csv', index=False)


assigned_tokens_month_13 = assign_tokens_to_regions(tokens, top3_top4_surplus_regions, '13')
assigned_tokens_month_13.to_csv(test_dir / 'output_assigned_tokens_month_13.csv', index=False)

# Months 14-17 are not supposed to have top-4 regions/tokens
top3_surplus_regions = top3_top4_surplus_regions.loc[lambda df: df.kind.isin([TOP_3_KIND, SURPLUS_KIND])]
top3_surplus_annotids = assigned_tokens_month_13.loc[lambda df: ~df.is_top_4_hours | df.is_top_3_hours].annotid
top3_surplus_tokens = tokens.loc[lambda df: df.annotid.isin(top3_surplus_annotids)]

assigned_tokens_month_14 = assign_tokens_to_regions(top3_surplus_tokens, top3_surplus_regions, '14')
assigned_tokens_month_14.to_csv(test_dir / 'output_assigned_tokens_month_14.csv', index=False)
