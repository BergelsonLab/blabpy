import sys
import os
import shutil
import random

import pandas as pd

from blabpy.vihi.segments import utils


def main():
    record_list = pd.read_csv(sys.argv[1])
    output_dir = sys.argv[2]
    if len(sys.argv) > 3:
        seed = int(sys.argv[3])
        random.seed(seed)

    selected = pd.DataFrame(columns=['id', 'clip_num', 'onset', 'offset'], dtype=int)

    for i, record in record_list.iterrows():
        print(record.index)
        # choose regions (5 by default)
        timestamps = utils.choose_onsets(int(record.length_of_recording), n=15)
        timestamps = [(x * 60000, y * 60000) for x, y in timestamps]
        timestamps.sort(key=lambda tup: tup[0])
        print(timestamps)

        # retrieve right age templates
        etf_path, pfsx_path = utils.choose_template(record.age)

        # create
        utils.create_eaf(etf_path, record.id, output_dir, timestamps)
        shutil.copy(pfsx_path, os.path.join(output_dir, "{}.pfsx".format(record.id)))

        selected = pd.concat([selected, utils.create_output_csv(record.id, timestamps)])

    selected[['clip_num', 'onset', 'offset']] = selected[['clip_num', 'onset', 'offset']].astype(int)
    selected.to_csv(os.path.join(output_dir, 'selected_regions.csv'), index=False)


if __name__ == "__main__":
    main()
