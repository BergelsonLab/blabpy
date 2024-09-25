"""
Module for preparing files for reliability tests and for calculating reliability.
"""
from copy import deepcopy
from xml.etree.ElementTree import ElementTree

import numpy as np
import pandas as pd

from ..eaf.etree_utils import find_single_element
from ..eaf.eaf_utils import find_child_annotation_ids, get_annotations_with_parents
from ..eaf import EafPlus, EafTree

SAMPLING_TYPES_TO_SAMPLE = ['random', 'high-volubility']


class NoAnnotationsError(Exception):
    pass


def prepare_eaf_for_reliability(eaf_element_tree: ElementTree, eaf: EafPlus, random_seed):
    """
    Prepare the .eaf files for reliability tests. Select one interval of each type, remove annotation values from all
    child tiers in these intervals, and remove all annotations (aligned and reference) from all the other intervals.

    eaf_tree and eaf should be two representations of the same file.

    Return (eaf_tree, (sampled_code_nums, sampling_types_to_sample)) tuple where eaf_tree is a copy of the input EAF
    tree.
    """
    eaf_element_tree = deepcopy(eaf_element_tree)

    if random_seed is not None:
        random_state = np.random.RandomState(random_seed)
    else:
        random_state = None

    # Find all non-empty intervals.
    annotations_df, intervals_df = eaf.get_annotations_and_intervals()
    if annotations_df.shape[0] == 0:
        raise NoAnnotationsError()

    # For the purposes of reliability testing, we will consider intervals to be non-empty if they contain at least one
    # annotation that is completely within the bound of that interval.
    non_empty_intervals = (
        pd.merge(annotations_df, intervals_df, on='code_num', how='left', validate='many_to_one',
                 suffixes=('', '_interval'))
        .loc[lambda df: df.onset_interval.le(df.onset) & df.offset.le(df.offset_interval)]
        .code_num.unique().tolist()
     )

    sampled_intervals_df = (intervals_df
                            .loc[lambda df: df.sampling_type.isin(SAMPLING_TYPES_TO_SAMPLE)
                                 & df.code_num.isin(non_empty_intervals)]
                            .groupby('sampling_type')
                            .sample(1, random_state=random_state))

    # Remove annotations from other intervals and values of child tiers in the sampled intervals
    is_sampled = annotations_df.code_num.isin(sampled_intervals_df.code_num)
    # This function works with raw elementtree object whereas prune_eaf_tree works with EafTree objects. We'll have to
    # create an EafTree object from eaf_element_tree and then convert it back.
    eaf_tree = EafTree(eaf_element_tree, validate_cv_entries=False)
    transcription_ids_keep = annotations_df.loc[is_sampled].transcription_id.to_list()
    eaf_tree = prune_eaf_tree(eaf_tree, eaf, transcription_ids_keep=transcription_ids_keep,
                              tier_types_keep=['transcription'])
    eaf_element_tree = eaf_tree.tree

    # Remove intervals that we are not keeping. Annotations in the corresponding tiers aren't bound to each other (
    # they probably should be, but they currently aren't), so we will use order to identify the intervals we are
    # keeping/discarding.

    # Find indices of the intervals we are keeping
    code_intervals = [[eaf.timeslots[annotation[0].attrib[time_slot_refx]]
                       for time_slot_refx in ['TIME_SLOT_REF1', 'TIME_SLOT_REF2']]
                      for annotation in find_single_element(eaf_element_tree, 'TIER', TIER_ID='code')]
    sampled_intervals = sampled_intervals_df[['onset', 'offset']].values.tolist()
    sampled_intervals_indices = [code_intervals.index(sample_interval)
                                 for sample_interval in sampled_intervals]
    assert len(sampled_intervals_indices) == sampled_intervals_df.shape[0]

    # Remove all intervals that we are not keeping and their daughter annotations
    annotations_with_parents = get_annotations_with_parents(eaf_element_tree)

    def remove_annotations_and_all_descendants(annotation_ids_to_remove):
        """
        Finds and deletes all descendants of the annotations with the given ids.
        :param annotation_ids_to_remove:
        :return:
        """
        children_ids_to_remove = find_child_annotation_ids(eaf_element_tree, annotation_ids_to_remove)
        for a_id, (annotation, parent) in annotations_with_parents.items():
            if a_id in annotation_ids_to_remove + children_ids_to_remove:
                parent.remove(annotation)

    for tier_id in ('code', 'context', 'sampling_type', 'code_num', 'on_off'):
        tier = find_single_element(eaf_element_tree, 'TIER', TIER_ID=tier_id)
        annotations_ids_to_remove = [annotation[0].attrib['ANNOTATION_ID']
                                     for i, annotation in list(enumerate(tier))
                                     if i not in sampled_intervals_indices]
        remove_annotations_and_all_descendants(annotations_ids_to_remove)
        assert len(tier) == sampled_intervals_df.shape[0]

    sampled_code_nums = sampled_intervals_df.code_num.to_list()
    sampled_sampling_types = sampled_intervals_df.sampling_type.to_list()
    return eaf_element_tree, (sampled_code_nums, sampled_sampling_types)


def prune_eaf_tree(eaf_tree: EafTree, eaf: EafPlus,
                   transcription_ids_keep,
                   tier_types_clear=None, tier_types_keep=None):
    """
    :param eaf_tree: Parsed eaf file as an EafTree object.
    :param eaf: Parsed EafPlus object.
    :param transcription_ids_keep: List of the parent annotations (transcriptions) ids.
    :param tier_types_clear: Which child tiers (xds, utt, etc.) need their values cleared.
    :param tier_types_keep: Which child tiers need their values kept. Set to an emtpy list to clear all the tiers, set
     to ['transcription'] to keep the transcriptions and clear all the child tiers.
    :param inplace: If True (default), the tree will be modified in-place.
    :return: A copy (unless inplace is True) of eaf_tree with annotations pruned.

    Only one of tier_types_clear and tier_types_keep should be specified.
    """
    if (tier_types_clear is None) == (tier_types_keep is None):
        raise ValueError('Exactly one of tier_types_clear and tier_types_keep should be specified.')

    # Check that the transcription_ids_keep are valid
    annotations_df = eaf.get_annotations(drop_empty_tiers=False)
    if not set(transcription_ids_keep).issubset(annotations_df.transcription_id):
        raise ValueError('Some of the transcription_ids_keep are not present in the EAF.')

    # Copy the EAF tree
    eaf_tree = deepcopy(eaf_tree)

    # Remove annotations we aren't keeping
    transcription_ids_remove = [t_id for t_id in annotations_df.transcription_id
                                if t_id not in transcription_ids_keep]
    for a_id in transcription_ids_remove:
        eaf_tree.drop_annotation(a_id, recursive=True)

    # Find the tiers that need to be cleared
    tiers_clear = list()
    for tier_id, tier in eaf_tree.tiers.items():
        if not tier.participant:
            continue

        tier_type = tier.linguistic_type_ref

        if tier_types_clear is not None and tier_type in tier_types_clear:
            tiers_clear.append(tier)
        elif tier_types_keep is not None and tier_type not in tier_types_keep:
            tiers_clear.append(tier)

    # Clear values in those tiers
    for tier in tiers_clear:
        for annotation in tier.annotations.values():
            annotation.clear_value()

    return eaf_tree
