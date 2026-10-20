import os
import pandas as pd
import numpy as np

from . import SPARKED_COLS
from .paths import get_sparked_talker_opf_path
from ..utils import convert_ms_to_hms

from pathlib import Path
from sklearn.metrics import cohen_kappa_score

def wrangle_by_frame_csv(csv_path):
    '''
    Read in tsv files of frame-by-frame opf exports and filter for only frames within the windows of interest
    '''
    sparked_df = pd.read_csv(csv_path, sep = "\t", skip_blank_lines=True)
    sparked_df = sparked_df[sparked_df["windows_of_interest_interval_type"].notna() & 
                            sparked_df["windows_of_interest_window_num"].notna()]
    return sparked_df

def get_kappa_per_col(df1, df2, col, report):
    '''
    Calculate the kappa liability score for column "col" between df1 and df2. 
    The score's description is added to 'report'
    '''
    df1 = df1.fillna("no_code")[f"{col}_code0"].to_numpy()
    df2 = df2.fillna("no_code")[f"{col}_code0"].to_numpy()
    kappa = cohen_kappa_score(df1, df2)
    if kappa < 0.8:
        report.append(f"COHEN'S KAPPA for code {col} is below 0.8: {round(kappa, 3)}. Please review the following differences:")
    else:
        report.append(f"COHEN'S KAPPA for code {col} is above or equal to 0.8: {round(kappa, 3)}. Here are the differences:")
    report.append(f"- ⚠️ marks minor differences. If time difference is ~1s, it can be ignored.")
    report.append(f"- ❌ marks major differences that need to be fixed.")
    return kappa

def compare_to_gold_standard(gs_df, new_df, col, report):
    """
    Compare a code's gold-standard and new frame-level annotations.

    Rows are aligned by frame number and time, then grouped into continuous
    annotated chunks. A readable summary of missing, extra, or differing
    segments is appended to "report".

    Args:
        gs_df: Gold-standard annotation DataFrame.
        new_df: Annotation DataFrame being evaluated.
        col: Code category to compare, such as "gesture".
        report: List of report lines to append the comparison summary to.

    Returns:
        A DataFrame of compared annotated frames, including chunk labels and
        old and new values for the selected code.
    """
    id_cols = ["framenum", "time"]
    cols = [f"{col}_ordinal",
            f"{col}_onset",
            f"{col}_offset",
            f"{col}_code0"]
    new_cols = [f"{x}_new" for x in cols]
    gs_df = gs_df[id_cols + cols].sort_values("time")
    new_df = new_df[id_cols + cols].sort_values("time")
    merged_df = gs_df.merge(new_df, on=id_cols, how = "outer", suffixes = [None, "_new"])
    comparison = merged_df[merged_df[cols[3]].notna() | merged_df[new_cols[3]].notna()].sort_values("time")

    # This is just to label chunks of continuous frames based on framenum only
    comparison["chunk"] = (
        comparison["framenum"].diff().ne(1)
    ).cumsum() 

    # Getting onset and offset of the chunks by getting minimum/maximum time from both old and new annotations
    chunked = (comparison
               .groupby("chunk")
               .agg(onset_old=(cols[1], "min"),
                    offset_old=(cols[2], "max"),
                    onset_new=(new_cols[1], "min"),
                    offset_new=(new_cols[2], "max"))
               .assign(onset=lambda d: d[["onset_old", "onset_new"]].min(axis=1).apply(convert_ms_to_hms),
                       offset=lambda d: d[["offset_old", "offset_new"]].max(axis=1).apply(convert_ms_to_hms))
               .assign(on_off=lambda d: d['onset'] + "-" + d['offset'])
               .reset_index())

    # Mapping the chunk onset and offset back to the comparison dataframe, along with differences in codes
    comparison["chunk_on_off"] = comparison["chunk"].map(chunked.set_index("chunk")["on_off"])
    comparison["missing"] = comparison[new_cols[3]].isna()
    comparison["extra"] = comparison[cols[3]].isna()
    comparison["annotator"] = np.where(
        comparison["missing"], "gs", 
        np.where(comparison["extra"], "new", "both")
    )
    comparison["diff"] = np.where(
        comparison["annotator"] == "both",
        comparison[cols[3]].str.strip().str.lower() != comparison[new_cols[3]].str.strip().str.lower(),
        pd.NA 
    )
    changes_cols = ["chunk", "chunk_on_off", "annotator", "missing", "extra", "diff"] + cols + new_cols
    changes = (comparison
               [changes_cols]
               .drop_duplicates())
    for col in cols[1:3] + new_cols[1:3]:
        changes[col] = changes[col].fillna(0).apply(convert_ms_to_hms)

    for _, sub in changes.groupby("chunk"):
        sub_length = sub[["missing", "extra"]].sum()
        sub_diff = sub["diff"].sum()

        gs_codes = sub[cols].dropna().drop_duplicates()
        new_codes = sub[new_cols].dropna().drop_duplicates()

        if (gs_codes.empty):
            report.append(f"❌ Extra segments not in Gold Standard in {sub['chunk_on_off'].iloc[0]}")
        elif (new_codes.empty):
            report.append(f"❌ Missing segments in your annotations in {sub['chunk_on_off'].iloc[0]}")
        elif (any(sub_length) or sub_diff > 0):
            if (len(gs_codes) != len(new_codes)):
                report.append(f"❌ There's differences of segments in {sub['chunk_on_off'].iloc[0]}")
            elif (sub_length <= len(gs_codes)).all():
                report.append(f"⚠️ There's some differences in {sub['chunk_on_off'].iloc[0]}")
                if sub_diff == 0:
                    report.append(f"The segments have different duration:")
                else:
                    report.append(f"The segments have different durations and codes:")
            else:
                report.append(f"❌ There's differences in {sub['chunk_on_off'].iloc[0]}")
        else:
            report.append(f"✅ No major differences in {sub['chunk_on_off'].iloc[0]}")
        
        report.append(f"\tGold standard segments:")
        report.extend(print_codes(gs_codes, cols))
        report.append(f"\tYour segments:")
        report.extend(print_codes(new_codes, new_cols))

    return changes

def print_codes(df, cols):
    if df.empty:
        return(["\t<No segments>"])
    codes = []
    for _, row in df.iterrows():
        codes.append(f"\t{row[cols[1]]}-{row[cols[2]]}: '{row[cols[3]]}'")
    return codes

def gold_standard_report(talker_id, age_in_months, annotator):
    # gs_file = get_sparked_talker_opf_path(talker_id, age_in_months, suffix="gold_standard")
    # new_file = get_sparked_talker_opf_path(talker_id, age_in_months, suffix=annotator)
    gs_file = Path(f"csv/talker_{talker_id}_{age_in_months}_gold_standard.tsv")
    new_file = Path(f"csv/talker_{talker_id}_{age_in_months}_{annotator}.tsv")
    df1 = wrangle_by_frame_csv(gs_file)
    df2 = wrangle_by_frame_csv(new_file)
    report = []

    for col in SPARKED_COLS:
        report.append("===========================")
        report.append(f"Comparing code {col}")
        get_kappa_per_col(df1, df2, col, report)
        compare_to_gold_standard(df1, df2, col, report)
        report.append("\n")

    return report
    # if not Path("report").exists():
    #     Path("report").mkdir()
    # with open(f"report/report_{id}_{annotator}.txt", "w") as f:
    #     f.write("\n".join(report))