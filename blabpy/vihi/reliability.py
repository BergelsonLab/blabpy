"""
Module for preparing files for reliability tests and for calculating reliability.
"""
from copy import deepcopy
from xml.etree.ElementTree import ElementTree

import numpy as np
import pandas as pd

from blabpy.eaf import EafPlus, get_annotation_values, get_annotations_with_parents, find_child_annotation_ids, \
    find_single_element

SAMPLING_TYPES_TO_SAMPLE = ['random', 'high-volubility']


def _stratified_random_sample(population, types_to_sample, random_seed=None):
    """
    For a list of values, returns a list of indices of randomly sample elements of each type from the other list.
    """
    if random_seed is not None:
        random = np.random.RandomState(random_seed)
    else:
        random = np.random

    sample_indices = list()
    for type_to_sample in types_to_sample:
        type_indices = [i for i, token
                        in enumerate(population)
                        if token == type_to_sample]
        sample_indices.append(random.choice(type_indices))

    return sample_indices


def prepare_eaf_for_reliability(eaf_tree: ElementTree, eaf: EafPlus, random_seed):
    """
    Prepare the .eaf files for reliability tests. Select one interval of each type, remove annotation values from all
    child tiers in these intervals, and remove all annotations (aligned and reference) from all the other intervals.

    eaf_tree and eaf should be two representations of the same file.

    Return (eaf_tree, (sampled_code_nums, sampling_types_to_sample)) tuple where eaf_tree is a copy of the input EAF
    tree.
    """
    eaf_tree = deepcopy(eaf_tree)

    # Select intervals to use
    sampling_types = get_annotation_values(eaf_tree, 'sampling_type')
    code_nums = get_annotation_values(eaf_tree, 'code_num')
    code_intervals = eaf.get_time_intervals("code")

    sampling_types_to_sample = SAMPLING_TYPES_TO_SAMPLE
    sampled_sampling_types_id = _stratified_random_sample(
        sampling_types, sampling_types_to_sample,
        random_seed=random_seed)
    sampled_code_nums = [code_nums[i] for i in sampled_sampling_types_id]
    sampled_intervals = [code_intervals[i] for i in sampled_sampling_types_id]

    # Sort all annotations into two groups: those that are in the sampled intervals and those that aren't
    def is_annotation_in_intervals(intervals):
        """
        For a pd.DataFrame with columns onset and offset, returns a pd.Series with boolean values indicating whether the
        annotation is in any of the intervals. "In" is defined as "overlapping with".
        :param intervals: list of (onset, offset) pairs
        """
        is_in = pd.Series(False, index=annotations_df.index)
        for onset, offset in intervals:
            is_in = is_in | ((annotations_df.onset < offset) & (annotations_df.offset > onset))

        return is_in

    annotations_df = eaf.get_full_annotations().reset_index(drop=True)
    is_in_either = is_annotation_in_intervals(sampled_intervals)

    # Delete all annotations that are not in the sampled intervals
    annotations_to_remove_df = annotations_df.loc[~is_in_either]
    parent_ids_to_remove = annotations_to_remove_df.participant_annotation_id.to_list()
    children_ids_to_remove = find_child_annotation_ids(eaf_tree, parent_ids_to_remove)
    annotations_with_parents = get_annotations_with_parents(eaf_tree)
    for a_id, (annotation, parent) in annotations_with_parents.items():
        if a_id in parent_ids_to_remove + children_ids_to_remove:
            parent.remove(annotation)

    # Remove values of the child annotations of the annotations we are keeping
    annotations_to_keep_df = annotations_df.loc[is_in_either]
    parent_ids_to_keep = annotations_to_keep_df.participant_annotation_id.to_list()
    children_ids_to_remove_values = find_child_annotation_ids(eaf_tree, parent_ids_to_keep)

    for a_id, (annotation, parent) in annotations_with_parents.items():
        if a_id in children_ids_to_remove_values:
            annotation.attrib.pop('CVE_REF', None)
            annotation_value = find_single_element(annotation, 'ANNOTATION_VALUE')
            annotation_value.text = ''

    # Remove intervals that we are not keeping
    for tier_id in ('code', 'context', 'sampling_type', 'code_num', 'on_off'):
        tier = find_single_element(eaf_tree, 'TIER', TIER_ID=tier_id)
        for i, annotation in list(enumerate(tier)):
            if i not in sampled_sampling_types_id:
                tier.remove(annotation)

    return eaf_tree, (sampled_code_nums, sampling_types_to_sample)
