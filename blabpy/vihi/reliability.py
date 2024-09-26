"""
Module for preparing files for reliability tests and for calculating reliability.
"""
from copy import deepcopy

import numpy as np
import pandas as pd

from ..eaf import EafPlus, EafTree

SAMPLING_TYPES_TO_SAMPLE = ['random', 'high-volubility']


class NoAnnotationsError(Exception):
    pass


def prepare_eaf_for_reliability(eaf_tree: EafTree, eaf: EafPlus, random_seed):
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
    n_sampled_intervals = sampled_intervals_df.shape[0]

    # Remove annotations from other intervals and values of child tiers in the sampled intervals
    is_sampled = annotations_df.code_num.isin(sampled_intervals_df.code_num)
    # This function works with raw elementtree object whereas prune_eaf_tree works with EafTree objects. We'll have to
    # create an EafTree object from eaf_element_tree and then convert it back.
    transcription_ids_keep = annotations_df.loc[is_sampled].transcription_id.to_list()
    eaf_tree = prune_eaf_tree(eaf_tree, transcription_ids_keep=transcription_ids_keep,
                              tier_types_keep=['transcription'])

    # Remove intervals that we are not keeping. Annotations in the corresponding tiers aren't bound to each other (
    # they probably should be, but they currently aren't), so we will use order to identify the intervals we are
    # keeping/discarding.

    # Find indices of the intervals we are keeping
    all_intervals = [[int(annotation.onset), int(annotation.offset)]
                      for annotation in eaf_tree.tiers['code'].annotations.values()]
    sampled_intervals = sampled_intervals_df[['onset', 'offset']].values.tolist()
    sampled_intervals_indices = [all_intervals.index(sample_interval)
                                 for sample_interval in sampled_intervals]
    assert len(sampled_intervals_indices) == n_sampled_intervals

    # Drop all other intervals
    for tier_id in ('code', 'context', 'sampling_type', 'code_num', 'on_off'):
        tier = eaf_tree.tiers[tier_id]
        # Note that we are using ordinal index i, not annotation id.
        annotations_to_drop = [annotation.id for i, annotation in enumerate(tier.annotations.values())
                               if i not in sampled_intervals_indices]
        for a_id in annotations_to_drop:
            eaf_tree.drop_annotation(a_id, recursive=True)
        assert len(tier.annotations) == n_sampled_intervals

    # Return
    sampled_code_nums = sampled_intervals_df.code_num.to_list()
    sampled_sampling_types = sampled_intervals_df.sampling_type.to_list()
    return eaf_tree, (sampled_code_nums, sampled_sampling_types)


def prune_eaf_tree(eaf_tree: EafTree,
                   transcription_ids_keep,
                   tier_types_clear=None, tier_types_keep=None):
    """
    :param eaf_tree: Parsed eaf file as an EafTree object.
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
    annotations_df = eaf_tree.export_annotations()
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
