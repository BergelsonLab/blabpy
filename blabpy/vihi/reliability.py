"""
Module for preparing files for reliability tests and for calculating reliability.
"""
from copy import deepcopy
from xml.etree.ElementTree import ElementTree

import numpy as np

from blabpy.eaf.etree_utils import find_single_element
from blabpy.eaf.eaf_utils import find_child_annotation_ids, get_annotations_with_parents
from blabpy.eaf import EafPlus

SAMPLING_TYPES_TO_SAMPLE = ['random', 'high-volubility']


class NoAnnotationsError(Exception):
    pass


def prepare_eaf_for_reliability(eaf_tree: ElementTree, eaf: EafPlus, random_seed):
    """
    Prepare the .eaf files for reliability tests. Select one interval of each type, remove annotation values from all
    child tiers in these intervals, and remove all annotations (aligned and reference) from all the other intervals.

    eaf_tree and eaf should be two representations of the same file.

    Return (eaf_tree, (sampled_code_nums, sampling_types_to_sample)) tuple where eaf_tree is a copy of the input EAF
    tree.
    """
    eaf_tree = deepcopy(eaf_tree)

    if random_seed is not None:
        random_state = np.random.RandomState(random_seed)
    else:
        random_state = None

    # Find all non-empty intervals.
    annotations_df, intervals_df = eaf.get_annotations_and_intervals()
    if annotations_df.shape[0] == 0:
        raise NoAnnotationsError()

    non_empty_intervals_df = intervals_df.loc[lambda df: df.code_num.isin(annotations_df.code_num)]
    sampled_intervals_df = (non_empty_intervals_df
                            .loc[lambda df: df.sampling_type.isin(SAMPLING_TYPES_TO_SAMPLE)]
                            .groupby('sampling_type')
                            .sample(1, random_state=random_state))

    # Delete all annotations that are not in the sampled intervals
    is_sampled = annotations_df.code_num.isin(sampled_intervals_df.code_num)
    annotations_to_remove_df = annotations_df.loc[~is_sampled]
    parent_ids_to_remove = annotations_to_remove_df.participant_annotation_id.to_list()
    # We need to find all child-parent pairs because elements need to be deleted from their parents - ElementTree
    # implementation detail.
    annotations_with_parents = get_annotations_with_parents(eaf_tree)

    def remove_annotations_and_all_descendants(annotation_ids_to_remove):
        """
        Finds and deletes all descendants of the annotations with the given ids.
        :param annotation_ids_to_remove:
        :return:
        """
        children_ids_to_remove = find_child_annotation_ids(eaf_tree, annotation_ids_to_remove)
        for a_id, (annotation, parent) in annotations_with_parents.items():
            if a_id in annotation_ids_to_remove + children_ids_to_remove:
                parent.remove(annotation)

    remove_annotations_and_all_descendants(parent_ids_to_remove)

    # Remove values of the child annotations of the annotations we are keeping
    annotations_to_keep_df = annotations_df.loc[is_sampled]
    parent_ids_to_keep = annotations_to_keep_df.participant_annotation_id.to_list()
    children_ids_to_remove_values = find_child_annotation_ids(eaf_tree, parent_ids_to_keep)

    for a_id, (annotation, parent) in annotations_with_parents.items():
        if a_id in children_ids_to_remove_values:
            annotation.attrib.pop('CVE_REF', None)
            annotation_value = find_single_element(annotation, 'ANNOTATION_VALUE')
            annotation_value.text = ''

    # Remove intervals that we are not keeping. Annotations in the corresponding tiers aren't bound to each other (
    # they probably should be, but they currently aren't), so we will use order to identify the intervals we are
    # keeping/discarding.

    # Find indices of the intervals we are keeping
    code_intervals = [[eaf.timeslots[annotation[0].attrib[time_slot_refx]]
                       for time_slot_refx in ['TIME_SLOT_REF1', 'TIME_SLOT_REF2']]
                      for annotation in find_single_element(eaf_tree, 'TIER', TIER_ID='code')]
    sampled_intervals = sampled_intervals_df[['onset', 'offset']].values.tolist()
    sampled_intervals_indices = [code_intervals.index(sample_interval)
                                 for sample_interval in sampled_intervals]
    assert len(sampled_intervals_indices) == sampled_intervals_df.shape[0]

    # Remove all intervals that we are not keeping and their daughter annotations
    for tier_id in ('code', 'context', 'sampling_type', 'code_num', 'on_off'):
        tier = find_single_element(eaf_tree, 'TIER', TIER_ID=tier_id)
        annotations_ids_to_remove = [annotation[0].attrib['ANNOTATION_ID']
                                     for i, annotation in list(enumerate(tier))
                                     if i not in sampled_intervals_indices]
        remove_annotations_and_all_descendants(annotations_ids_to_remove)
        assert len(tier) == sampled_intervals_df.shape[0]

    sampled_code_nums = sampled_intervals_df.code_num.to_list()
    sampled_sampling_types = sampled_intervals_df.sampling_type.to_list()
    return eaf_tree, (sampled_code_nums, sampled_sampling_types)
