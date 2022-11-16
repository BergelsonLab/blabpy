from pathlib import Path

from blabpy.seedlings.regions.top3_top4_surplus import get_top3_top4_surplus_regions, get_top_n_regions, get_surplus_regions
from blabpy.seedlings.pipeline import get_processed_audio_regions

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
