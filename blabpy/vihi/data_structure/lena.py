"""
This module checks that the LENA folder contains all and only files that we expect to be there.
"""
import re
from enum import auto, unique
from pathlib import Path

import pandas as pd
from strenum import StrEnum

from ..paths import get_lena_path, _recording_prefix, _parse_recording_prefix, get_lena_recording_path, get_vihi_path

# Strings to match literally, and re.Pattern objects to match in the sense of re.match. Add $ to match the full name.
IGNORED = [re.compile(r'~.*\.docx$'), '.DS_Store', '.git']


@unique
class AuditStatus(StrEnum):
    ignored = auto()
    expected = auto()
    unexpected = auto()
    missing = auto()


def _name_matches(path, rule_list):
    """
    Checks if the name of the file at path matches any of the rules
    :param path:
    :param rule_list: a list of strings and re.Pattern objects to match against
    :return: rule_list element that the path name matched if there was a match, None if there were no matches
    """
    name = path.name
    for rule in rule_list:
        if isinstance(rule, str) and name == rule:
            return rule
        elif isinstance(rule, re.Pattern) and rule.match(name):
            return rule
    return


def audit_recording_folder(folder_path: Path, population: str, subject_id: str, recording_id: str):
    """
    Checks a recording folder for
    :param folder_path: path to the folder with the recording
    :param population: population
    :param subject_id: subject id string
    :param recording_id: recording id string
    :return: a dataframe with the status of each file in folder in `path`
    """
    assert folder_path.is_dir()
    recording_id = _recording_prefix(population, subject_id, recording_id)
    assert folder_path.name == recording_id

    expected_objects = [
        f'{recording_id}.eaf',
        f'{recording_id}.its',
        f'{recording_id}.wav',
        f'{recording_id}.pfsx',
        f'{recording_id}.upl',
        f'{recording_id}_lena5min.csv',
        f'VIHI_Coding_Issues_{recording_id}.docx'
    ]

    objects_statuses = list()
    satisfied_rules = list()
    folder_contents = [path.relative_to(folder_path) for path in folder_path.iterdir()]
    for path in folder_contents:
        if _name_matches(path, rule_list=IGNORED):
            objects_statuses.append(AuditStatus.ignored)
            continue

        rule_matched = _name_matches(path, rule_list=expected_objects)
        if rule_matched:
            satisfied_rules.append(rule_matched)
            objects_statuses.append(AuditStatus.expected)
        else:
            objects_statuses.append(AuditStatus.unexpected)

    missing_files = [rule for rule in expected_objects if rule not in satisfied_rules]
    audit_results = ([(path.as_posix(), str(status)) for path, status in zip(folder_contents, objects_statuses)]
                     + [(rule, str(AuditStatus.missing)) for rule in missing_files])

    return (pd.DataFrame(columns=['relative_path', 'status'], data=audit_results)
            .sort_values(by=['status', 'relative_path'])
            .reset_index(drop=True))
