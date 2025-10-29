import click
import re
from blabpy.paths import get_blab_share_path
from blabpy.pipeline import find_eaf_paths, extract_aclew_data
from blabpy.eaf.eaf_plus import EafPlus
import os
from pyprojroot import find_root
from pathlib import Path
import pandas as pd
from blabpy.utils import convert_ms_to_hms
from datetime import date
from pprint import pprint

# Paths
# BLAB_SHARE_PATH = get_blab_share_path()
# OVS_PATH = BLAB_SHARE_PATH / 'OvSpeech' / 'SubjectFiles' / "Seedlings" / 'overheard_speech'
# VIHI_PATH = BLAB_SHARE_PATH / 'VIHI' / 'SubjectFiles' / 'LENA' 
SPEAKER_PATTERN = re.compile(r'CHI|[MFU][ACI][\dE]|EE1')
TIER_PATTERN = re.compile(r'^\w+@\w\w\w$')
cv_dict = {
    'vcm': ['L', 'Y', 'N', 'C', 'U'],
    'lex': ['W', '0'],
    'mwu': ['M', '1'],
    'xds': ['A', 'C', 'B', 'P', 'O', 'U'],
    'cds': ['T', 'K', 'M', 'X']
}

parent_dict = {
    'vcm': None,
    'lex': 'vcm',
    'mwu': 'lex',
    'xds': None,
    'cds': 'xds'
}

value_dict = {
    'lex': ('vcm', 'C'),
    'mwu': ('lex', 'W'),
    'cds': ('xds', 'C')
}

chi_tiers = ['vcm', 'lex', 'mwu']
other_speaker_tiers = ['xds', 'cds']
other_tiers = ['on_off', 'code', 'code_num', 'context']

@click.group()
def validate():
    """Setting up CLI for blabpy {name of module}"""
    pass


@validate.command()
@click.argument('folder', required=True, type=click.Path(exists=True))
@click.argument('output_folder', required=False, default=None, type=click.Path(file_okay=False))

def setup(folder, output_folder):
    print("setup")
    print(folder)
    print("=====================================")
    paths = find_eaf_paths(folder)
    print(f"Found {len(paths)} .eaf files to validate.")
    pprint(paths[:2])
    if output_folder is None:
        today = date.today().strftime("%Y-%m-%d")
        output_folder = Path(folder) / f'{today}_validation_reports'
        # os.mkdir(output_folder, exist_ok=True)
    print(f"Output folder: {output_folder}")
    print("=====================================")

def report_one_file(eaf_path, output_folder, cv_dict, value_dict):
    """
    Generate a Markdown validation report for a single ELAN (.eaf) file.
    This function reads and validates an ELAN file at `eaf_path` and writes a
    human-readable Markdown report summarizing a set of ACLEW-specific validation
    checks to a file inside `output_folder`. The output filename is derived from
    the input filename by replacing the ".eaf" suffix with "_report.md".
    Validation and report content include:
    - Listing all unique speakers and reporting any speakers that do not conform
        to the ACLEW naming scheme.
    - Validating standard tier hierarchy and reporting dependent-tier errors and
        other tier hierarchy problems.
    - Counting the number of annotations per "interval" and reporting intervals
        containing blank annotations (including annotation onset/offset times).
    - Reporting any annotations that use the project-defined "blank code", with
        the tier and participant where it was found.
    - Validating controlled vocabulary for configured tiers (per `cv_dict`) and
        reporting annotations whose values are not in the allowed vocabulary.
    - Validating parent-tier dependency values for configured tiers (per
        `value_dict`) and reporting annotations whose parent-tier values do not
        match the expected one.

    Parameters
    ----------
    eaf_path : str or pathlib.Path
            Path to the input ELAN (.eaf) file to be validated.
    output_folder : pathlib.Path
            Directory where the generated Markdown report will be written. 
    cv_dict : dict
            Dictionary mapping tier names to lists of allowed controlled vocabulary values.
    value_dict : dict
            Dictionary mapping tier names to tuples of (parent, expected_value) for
            parent-tier expected value.
    """

    eaf = EafPlus(Path(eaf_path))
    annotations, intervals = extract_aclew_data(Path(eaf_path))

    name = str(eaf_path).split('/')[-1].replace('.eaf', '_report.md')
    output_path = output_folder / name

    speakers, speaker_errs = validate_speaker(eaf)
    all_dependent_tiers, all_dependent_errs, other_errs = validate_standard_tiers_hierarchy(eaf)

    anno_by_interval, anno_with_transcriptions = report_number_of_annotations(annotations)

    blanks, blank_cols = validate_blanks(annotations)
    cv_results = dict()
    for tier in cv_dict.keys():
        cv_results[tier] = validate_controlled_vocabulary_by_tier(annotations, tier)

    value_results = dict()
    for tier in value_dict.keys():
        value_results[tier] = validate_parent_tier_values(annotations, tier, value_dict[tier][0], value_dict[tier][1])

    with open(output_path, 'w') as f:
        f.write(f"# Validation report for {name.rstrip('_report.md')}\n\n")
        f.write(f"## Speakers\n\n")
        f.write(f"All unique speakers: {', '.join(speakers)}\n\n")
        if len(speaker_errs) > 0:
            f.write(f"❌ Speakers not conforming to ACLEW scheme: {', '.join(speaker_errs)}\n\n")
        else:
            f.write("✅ All speakers conform to ACLEW scheme.\n\n")

        f.write("## Standard Tiers Hierarchy Validation\n\n")
        for s in all_dependent_tiers.keys():
            if all_dependent_tiers[s] == []:
                f.write(f'### Speaker {s} does not have any valid dependent tiers\n\n')
            else:
                f.write(f'### Speaker {s} has dependent tiers: {", ".join(all_dependent_tiers[s])}\n\n')
            if all_dependent_errs[s] == []:
                f.write(f'✅ All tier dependency validated\n\n')
            else:
                for e in all_dependent_errs[s]:
                    f.write(f"{e}\n\n")
        f.write(f'### Other tiers:\n\n')
        if other_errs != []:
            for e in other_errs:
                f.write(f"{e}\n\n")

        f.write("## Number of Annotations in Each Interval\n\n")
        for code_num in anno_by_interval.index:
            if True in anno_by_interval.columns and pd.notna(anno_by_interval.loc[code_num, True]):
                blank_count = anno_by_interval.loc[code_num, True]
            else:
                blank_count = 0

            if False in anno_by_interval.columns and pd.notna(anno_by_interval.loc[code_num, False]):
                non_blank_count = anno_by_interval.loc[code_num, False]
            else:
                non_blank_count = 0
            f.write(f"#### Interval {code_num}: {int(non_blank_count + blank_count)} annotations\n\n")
            if blank_count != 0:
                f.write(f"❌  {int(blank_count)} blank annotations\n\n")
                for _, row in anno_with_transcriptions.iterrows():
                    if row["code_num"] == code_num:
                        f.write(f"- From {convert_ms_to_hms(row['onset'])} to {convert_ms_to_hms(row['offset'])}\n\n")

        f.write("## Blank Code\n\n")
        if blanks.empty:
            f.write("✅ No blank code found.\n\n")
        else:
            for _, row in blanks.iterrows():
                for col in blank_cols:
                    if row[col]:
                        f.write(f"❌ Blank code found in interval {row['code_num']} from {convert_ms_to_hms(row['onset'])} to {convert_ms_to_hms(row['offset'])}, at tier {col}@{row['participant']}\n\n")

        f.write("## Controlled Vocabulary and Parent Tier Dependency Validation\n\n")
        for tier in cv_results.keys():
            f.write(f"### Tier {tier}\n\n")
            f.write(f'#### Controlled Vocabulary\n\n')
            tier_wrong_value, err_msg = cv_results[tier]
            if err_msg is not None:
                f.write(f"⚠️ {err_msg}\n\n")
            elif tier_wrong_value.empty:
                f.write(f"✅ All annotations in tier {tier} conform to the controlled vocabulary.\n\n")
            else:
                for _, row in tier_wrong_value.iterrows():  
                    f.write(f"❌ Wrong value *{row[tier]}* in interval {row['code_num']} from {convert_ms_to_hms(row['onset'])} to {convert_ms_to_hms(row['offset'])}, should be one of {cv_dict[tier]}\n\n")
            
            if tier in value_results.keys():
                f.write(f'#### Parent Tier Value\n\n')
                if value_results[tier] is not None and not value_results[tier].empty:
                    for _, row in value_results[tier].iterrows():
                        f.write(f"❌ Incorrect parent tier value *{row[value_dict[tier][0]] if row[value_dict[tier][0]] != '' else '<blank>'}* in interval {row['code_num']} from {convert_ms_to_hms(row['onset'])} to {convert_ms_to_hms(row['offset'])}, should be {value_dict[tier][1]}\n\n")
                elif value_results[tier] is not None:
                    f.write(f"✅ All {tier} annotations have correct parent value.\n\n")

def report_number_of_annotations(annotations):
    """
    Report counts of annotations per code interval and any blank transcriptions.
    Parameters
    ----------
    annotations : pandas.DataFrame representation of the eaf files
    Returns
    -------
    anno_by_interval : pandas.DataFrame
        DataFrame indexed by interval 'code_num' with columns corresponding to the boolean values of
        'is_blank' (True for blank transcriptions, False for non-blank). Each cell contains the
        count of annotations for that interval and blank-status. The table is sorted by
        'code_num'.
    anno_with_transcriptions : pandas.DataFrame
        DataFrame containing the columns 'transcription', 'code_num', 'onset', 'offset', and
        an added boolean column 'is_blank'. This returned DataFrame is filtered to only rows
        where 'is_blank' is True (i.e., blank transcriptions).

    Notes
    -----
    - The function sorts intervals by int(code_num) for human-meaningful ordering.
    - Blank transcriptions are defined strictly as the empty string '' (not NaN or None).
    """

    annotations = annotations.sort_values(by = "code_num", key = lambda x: x.astype(int))

    anno_with_transcriptions = annotations[['transcription', 'code_num', "onset", "offset"]]
    anno_with_transcriptions["is_blank"] = (anno_with_transcriptions["transcription"] == '')

    anno_by_interval = anno_with_transcriptions[['transcription', 'code_num', "is_blank"]].groupby(['code_num', "is_blank"]).size().reset_index(name='count')
    anno_by_interval = anno_by_interval.pivot(index='code_num', columns="is_blank", values="count")
    anno_by_interval = anno_by_interval.sort_values(by = "code_num", key = lambda x: x.astype(int))

    anno_with_transcriptions = anno_with_transcriptions[anno_with_transcriptions["is_blank"] == True]

    return anno_by_interval, anno_with_transcriptions

def validate_speaker(eaf):
    """
    Validates that all speaker tiers conform to the ACLEW speaker coding scheme.
    Args:
        eaf (EafPlus): An instance of the EafPlus class representing the ELAN file of the annotation.
    Returns:
        all_speakers (list): List of all unique speaker tiers found in the ELAN file.
        errs (list): List of speaker tiers that do not conform to the ACLEW scheme.
    """
    all_speakers = eaf.get_participant_tier_ids()
    errs = []
    for speaker in all_speakers:
        if not SPEAKER_PATTERN.fullmatch(speaker):
            errs.append(speaker)
    return all_speakers, errs

def validate_blanks(annotations):
    """
    Validates that there are no tiers with blank annotations (i.e., represented by empty strings and not <NA>).
    Args:
        annotations (pd.DataFrame): DataFrame containing annotation data with multiple tiers.
    Returns:
        annotations (pd.DataFrame): DataFrame containing only the intervals with blank annotations, along with
                                   identifying information (eaf_filename, participant, onset, offset, code_num, transcription_id).
        blank_cols (list): List of tier names where blank annotations were found.
    """
    ids = annotations[["eaf_filename", "participant", "onset", "offset", 'code_num', 'transcription', 'transcription_id']]
    blanks = annotations.drop(
        ["eaf_filename", "participant", "onset", "offset", 'code_num', 'transcription', "transcription_id"], axis=1
    ).map(
        lambda x: not pd.isna(x) and x == ''
    )
    blanks = blanks[blanks.any(axis=1)]
    annotations = pd.merge(ids, blanks, left_index=True, right_index=True, how='right')

    return annotations, blanks.columns

def validate_controlled_vocabulary_by_tier(annotations, tier_name):
    """
    Validates that all non-null annotations in a specified tier conform to a controlled vocabulary.
    Args:
        annotations (pd.DataFrame): DataFrame containing annotation data with multiple tiers.
        tier_name (str): The name of the tier to validate.
    Returns:
        tier_wrong_value (pd.DataFrame or None): DataFrame containing intervals with invalid annotations in the specified tier,
                                                along with identifying information (eaf_filename, participant, onset, offset, code_num).
                                                Returns None if the tier is not found or no controlled vocabulary is defined.
        err_msg (str or None): Error message if the tier is not found or no controlled vocabulary is defined. None if validation is successful.
    """
    if tier_name not in cv_dict:
        return None, f"No controlled vocabulary defined for tier {tier_name}"
    if tier_name not in annotations.columns:
        return None, f"Tier {tier_name} not found in annotations dataframe"

    tier_annotations = annotations[["eaf_filename", "participant", "onset", "offset", "code_num", tier_name]].dropna()
    tier_wrong_value = tier_annotations.query(f"{tier_name} not in {cv_dict[tier_name]} and {tier_name} != ''")

    return tier_wrong_value, None

def validate_parent_tier_values(annotations, tier_name, parent_tier, parent_value):
    """
    Validates that all non-null annotations in a specified tier have the expected value in a parent tier.
    Args:
        annotations (pd.DataFrame): DataFrame containing annotation data with multiple tiers.
        tier_name (str): The name of the tier to validate.
        parent_tier (str): The name of the parent tier whose value should be checked.
        parent_value (str): The expected value in the parent tier.
    Returns:
        tier_incorrect_parent (pd.DataFrame or None): DataFrame containing intervals where the parent tier does not have the expected value,
                                                       along with identifying information (eaf_filename, participant, onset, offset, code_num).
                                                       Returns None if the tier is not found.
    Raises:
        None
    Notes:
        - If the specified tier is not found in the annotations DataFrame, None is returned.
    """

    if tier_name not in annotations.columns:
        return None
    
    all_annotations_of_tier = annotations.loc[
        pd.notna(annotations[tier_name]), [
            "eaf_filename", "participant", "onset", "offset", 'code_num', tier_name, parent_tier
        ]
    ]
    # Check that the parent tier has the correct value
    tier_incorrect_parent = all_annotations_of_tier.query(f"{parent_tier} != '{parent_value}'")
    return tier_incorrect_parent


def validate_standard_tiers_hierarchy(eaf):
    """
    Validates the hierarchy and usage of tiers in an EAF (ELAN Annotation Format) file according to standard conventions.
    This function checks:
    - That all dependent tiers (of the form xxx@yyy) have the correct parent tier and speaker association.
    - That only standard tier types are used for each speaker.
    - That dependent tiers have the correct parent tier type and speaker tier.
    - That non-dependent tiers are either speaker tiers, standard non-speaker coding tiers, or are reported as non-standard.
    Parameters:
        eaf (EafPlus): An instance of the EafPlus class representing the ELAN file of the annotation.

    Returns:
        tuple:
            - all_dependent_tiers (dict): Mapping of speaker IDs to lists of their dependent tier types.
            - all_dependent_errs (dict): Mapping of speaker IDs to lists of error messages related to their dependent tiers.
            - other_errs (list): List of error messages for other issues found in the tier hierarchy.
    """

    all_tiers = eaf.get_tier_names()
    all_speakers = eaf.get_participant_tier_ids()

    all_dependent_tiers = dict()
    all_dependent_errs = dict()
    other_errs = []

    for speaker in all_speakers:
        all_dependent_tiers[speaker] = []
        all_dependent_errs[speaker] = []

    unused_common_tiers = [tier for tier in other_tiers if tier not in all_tiers]
    for t in unused_common_tiers:
        other_errs.append(f"⚠️ Common tier {t} not used")

    for tier in all_tiers:

        # For dependent tiers (of the form xxx@yyy), check that they have the correct parent tier 
        # and correct speaker tier all throughout
        # e.g. lex@CHI should have parent vcm@CHI
        if TIER_PATTERN.fullmatch(tier):
            params = eaf.get_parameters_for_tier(tier)
            current_tier_type, current_speaker = tier.split('@')

            if current_speaker not in all_dependent_tiers:
                other_errs.append(f"⚠️ Should not have dependent tier {current_tier_type}")
            else:
                # For speaker CHI
                if current_speaker == "CHI":
                    if current_tier_type in chi_tiers:
                        all_dependent_tiers["CHI"].append(current_tier_type)
                    else:
                        all_dependent_errs["CHI"].append(
                            f"❌ Non-standard tier type {current_tier_type}. CHI typically only has {chi_tiers} tiers"
                        )
                    if current_tier_type in ['lex', 'mwu']:
                        all_dependent_errs["CHI"].append(
                            f"⚠️ Tier {current_tier_type} is coded. Check that target child is 8 months or older."
                        )

                # For other speakers
                else:
                    if current_tier_type in other_speaker_tiers:
                        all_dependent_tiers[current_speaker].append(current_tier_type)
                    else:
                        all_dependent_errs[current_speaker].append(
                            f"❌ Non-standard tier type {current_tier_type}. Non-CHI speakers typically only have {other_speaker_tiers} tiers"
                        )
                
                # Check that each tier type has the correct parent tier type and speaker tier
                if current_tier_type not in parent_dict:
                    all_dependent_errs[current_speaker].append(f"⚠️ Non-standard dependent tier type {current_tier_type} with parent {params['PARENT_REF']}")

                # Case where the tier is a direct child tier of a transcription (speaker tier)
                elif not TIER_PATTERN.fullmatch(params['PARENT_REF']):
                    if parent_dict[current_tier_type] is not None:
                        all_dependent_errs[current_speaker].append(
                            f"❌ Tier {current_tier_type} should not be a direct child of a transcription tier"
                        )

                # Otherwise, the parent tier should also have the form xxx@yyy
                else:
                    parent_tier_type, parent_speaker = params['PARENT_REF'].split('@')
                    if parent_dict[current_tier_type] is None:
                        all_dependent_errs[current_speaker].append(
                            f"❌ Tier {current_tier_type} has incorrect parent tier {params['PARENT_REF']}, should be a direct child of a transcription tier"
                        )
                    elif parent_dict[current_tier_type] != parent_tier_type:
                        all_dependent_errs[current_speaker].append(
                            all_dependent_errs[current_speaker].append(
                                f"❌ Tier {current_tier_type} has incorrect parent tier {params['PARENT_REF']}"
                            )   
                        )

                    if current_speaker != parent_speaker:
                        all_dependent_errs[current_speaker].append(
                            f"❌ Tier {current_tier_type} has mismatched speaker {current_speaker} and parent speaker {parent_speaker}"
                        ) 

        # Tiers that are not of the form xxx@yyy are either speaker tiers,
        # standard non-speaker coding tiers 
        # (e.g. is_silent, code_num, on_off)
        # or non-standard tiers (these will be reported)
        else:
            params = eaf.get_parameters_for_tier(tier)
            if tier not in other_tiers and tier not in all_speakers:
                other_errs.append(f"⚠️ Non-standard tier found: {tier} with parent tier {params.get('PARENT_REF')} and is of type {params.get('LINGUISTIC_TYPE_REF')}")

    return all_dependent_tiers, all_dependent_errs, other_errs

if __name__ == '__main__':
    validate()