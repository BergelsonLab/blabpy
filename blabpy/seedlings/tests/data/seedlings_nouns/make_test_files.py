from pathlib import Path
import json

import pandas as pd

from blabpy.seedlings.pipeline import gather_recording_seedlings_nouns

tests_data_dir = Path('blabpy/seedlings/tests/data/')
tokens = pd.read_csv(tests_data_dir/ 'top3_top4_surplus/input_tokens.csv').convert_dtypes()

(regions_for_seedlings_nouns,
 tokens_full,
 recordings,
 total_listened_time_ms,
 total_recorded_time_ms) = gather_recording_seedlings_nouns('Audio', 2, 8, tokens)

seedlings_nouns_test_data_dir = tests_data_dir / 'seedlings_nouns'
regions_for_seedlings_nouns.to_csv(seedlings_nouns_test_data_dir / 'regions_for_seedlings_nouns.csv', index=False)
tokens_full.to_csv(seedlings_nouns_test_data_dir / 'tokens_full.csv', index=False)
recordings.to_csv(seedlings_nouns_test_data_dir / 'recordings.csv', index=False)
with open(seedlings_nouns_test_data_dir / 'total_times.json', 'w') as f:
    json.dump(dict(total_recorded_time_ms=total_recorded_time_ms,
                   total_listened_time_ms=total_listened_time_ms), f)
