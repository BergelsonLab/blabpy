import os
import pandas as pd
import numpy as np

from . import SPARKED_COLS
from ..utils import convert_ms_to_hms

from pathlib import Path
from sklearn.metrics import cohen_kappa_score

def get_kappa_per_col(df1, df2, col, report):
    '''
    Calculate the kappa reliability score for column "col" between df1 and df2. 
    The score's description is added to 'report'.
    '''
    new_code_name = "window_num" if col == "windows_of_interest" else "code0"
    df1 = df1.fillna("no_code")[f"{col}_{new_code_name}"].to_numpy()
    df2 = df2.fillna("no_code")[f"{col}_{new_code_name}"].to_numpy()
    kappa = cohen_kappa_score(df1, df2)
    report.append(f"## Kappa Reliability Score")
    report.append(f"Kappa reliability score for code {col}: **{round(kappa, 3)}**")
    if kappa < 0.8:
        report.append(f'<span style="color:red">Your score is below 0.8. Please review the following differences:</span>')
    else:
        report.append(f'<span style="color:green">Your score is above or equal to 0.8. Here are the differences:</span>')
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
    report.append(f"## Differences")

    id_cols = ["framenum", "time"]
    new_code_name = "window_num" if col == "windows_of_interest" else "code0" # window_num column uses different names for its code

    cols = [f"{col}_ordinal",
            f"{col}_onset",
            f"{col}_offset",
            f"{col}_{new_code_name}"]
    new_cols = [f"{x}_new" for x in cols]
    gs_df = gs_df[id_cols + cols].sort_values("time")
    new_df = new_df[id_cols + cols].sort_values("time")
    merged_df = gs_df.merge(new_df, on=id_cols, how = "outer", suffixes = [None, "_new"])

    # Filter to only rows where either the old or new code is not null, and sort by time
    comparison = merged_df[merged_df[cols[3]].notna() | merged_df[new_cols[3]].notna()].sort_values("time")

    # Find continuous chunks of annotated frames and labeling them with a chunk number. 
    # A chunk is defined as a sequence of frames where the frame numbers are consecutive.
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

    # Creating a summary of the differences for each chunk, including missing, extra, and differing segments
    changes_cols = ["chunk", "chunk_on_off", "annotator", "missing", "extra", "diff"] + cols + new_cols
    changes = (comparison
               [changes_cols]
               .drop_duplicates())

    # Formatting the missing and extra times to be more readable (in H:MM:SS format)
    for col in cols[1:3] + new_cols[1:3]:
        changes[col] = changes[col].fillna(0).apply(convert_ms_to_hms)

    # Creating a readable summary of the differences for each chunk and appending it to the report
    # This code attempts to quantify the kind of differences in each chunk by looking at:
    #   1) If the number of annotations are different across the two files 
    #   2) If any frame has a different code between the two files, 
    #   3) If the total number of gaps due to differences in durations are more than the total number of annotations 
    # Point 1 will notify that there are misisng or extra segments (quantity), point 2 will notify that there are segments with different 
    # codes (quality), and point 3 is an approximation of whether the differences in duration is major or not (severity). 
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
                report.append(f"❌ Different number of segments in {sub['chunk_on_off'].iloc[0]}")
            elif (sub_length <= len(gs_codes)).all():
                if sub_diff == 0:
                    report.append(f"⚠️ There're some segments with different durations in {sub['chunk_on_off'].iloc[0]}")
                else:
                    report.append(f"⚠️ There're some segments with different durations and codes in {sub['chunk_on_off'].iloc[0]}")
            else:
                report.append(f"❌ There're differences in {sub['chunk_on_off'].iloc[0]}")
        else:
            report.append(f"✅ No major differences in {sub['chunk_on_off'].iloc[0]}")
            continue
        table_comparison = [f"| Gold Standard | Yours |\n| :--- | :--- |"]
        gs_cells = print_codes(gs_codes, cols)
        your_cells = print_codes(new_codes, new_cols)
        for i in range(max(len(gs_cells), len(your_cells))):
            gs_cell = gs_cells[i] if len(gs_cells) > i else " "
            your_cell = your_cells[i] if len(your_cells) > i else " "
            table_comparison.append(f"| {gs_cell} | {your_cell} |")
        report.append("\n".join(table_comparison))

    return changes

def print_codes(df, cols):
    '''
    Formats how to print out a code cell, combining the cell number, onset, offset, and code.
    :param df: DataFrame of code cells to print
    :param cols: a list of column names that correspond to (in order) the cell number, onset, offset, and code
    :return: a list of formatted strings for each code cell
    '''
    if df.empty:
        return(["No segments"])
    codes = []
    for _, row in df.iterrows():
        codes.append(f"Cell {int(row[cols[0]])} at {row[cols[1]]}-{row[cols[2]]}: '{row[cols[3]]}'")
    return codes

def gold_standard_report(gs_file, new_file):
    '''
    Generate a report comparing the gold standard file and the new file for each code in SPARKED_COLS.
    :param gs_file: Path to the gold standard file
    :param new_file: Path to the new file to compare against the gold standard
    :return: A list of strings containing the report for each code
    '''
    gs_df = pd.read_csv(gs_file, sep = "\t", skip_blank_lines=True)
    your_df = pd.read_csv(new_file, sep = "\t", skip_blank_lines=True)
    report = []

    report.append(f"Gold standard training for file {new_file.stem}")
    report.append(f"Please review your kappa reliability score and list of differences for each code type below.")
    report.append(f"- ⚠️ marks minor differences. If time difference is ~1s, it can be ignored.")
    report.append(f"- ❌ marks major differences that need to be fixed.")

    for col in SPARKED_COLS:
        report.append(f"# Comparing code **{col}**")
        get_kappa_per_col(gs_df, your_df, col, report)
        compare_to_gold_standard(gs_df, your_df, col, report)
        report.append("\n")

    return report
