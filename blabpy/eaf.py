import pandas as pd
from pympi import Eaf


class EafPlus(Eaf):
    """
    This class is just pympi.Eaf plus a few extra methods.
    """

    def get_time_intervals(self, tier_id):
        """
        Get time slot intervals from all tiers with a given id.
        :param tier_id: string with a tier id ('code', 'context', etc.)
        :return: [(start_ms, end_ms), ...]
        """
        # From `help(pympi.Eaf)` for the `tiers` attribute:
        #
        # tiers (dict)
        #
        # Tiers, where every tier is of the form:
        # {tier_name -> (aligned_annotations, reference_annotations, attributes, ordinal)},
        # aligned_annotations of the form: [{id -> (begin_ts, end_ts, value, svg_ref)}],
        # reference annotations of the form: [{id -> (reference, value, previous, svg_ref)}].

        # We only need aligned annotations. And from those we only need begin_ts and end_ts - ids of the time slots
        # which we will convert to timestamps in ms using eaf.timeslots. .eaf files no nothing about sub-recordings,
        # so all the timestamp are in reference to the wav file.
        aligned_annotations = self.tiers[tier_id][0]
        timeslot_ids = [(begin_ts, end_ts) for begin_ts, end_ts, _, _ in aligned_annotations.values()]
        timeslots = [(self.timeslots[begin_ts], self.timeslots[end_ts]) for begin_ts, end_ts in timeslot_ids]

        return timeslots

    def get_values(self, tier_id):
        """
        Get values from a tier.
        :param tier_id:
        :return: list of values
        """
        # Same logic as in get_time_intervals
        aligned_annotations = self.tiers[tier_id][0]
        values = [value for _, _, value, _ in aligned_annotations.values()]

        return values

    def get_participant_tier_ids(self):
        participant_tier_ids = [tier_id
                                for tier_id, (_, _, attributes, _)
                                in self.tiers.items()
                                if 'PARTICIPANT' in attributes
                                and attributes['LINGUISTIC_TYPE_REF'] == 'transcription']
        return participant_tier_ids

    def _get_aligned_annotations(self, tier_id):
        time_intervals = self.get_time_intervals(tier_id=tier_id)
        if len(time_intervals) == 0:
            return None

        onsets, offsets = zip(*time_intervals)
        aligned_annotations, _, _, _ = self.tiers[tier_id]
        if aligned_annotations:
            ids, annotations = zip(*[(id_, annotation)
                                     for id_, (_, _, annotation, _)
                                     in aligned_annotations.items()])
            return pd.DataFrame.from_dict(dict(
                onset=onsets, offset=offsets,
                annotation=annotations,
                annotation_id=ids))
        else:
            return pd.DataFrame(columns=['onset', 'offset', 'annotation', 'annotation_id'])

    def _get_reference_annotations(self, tier_id):
        _, reference_annotations, _, _ = self.tiers[tier_id]
        if reference_annotations:
            parent_ids, daughter_ids, annotations = zip(*[
                (parent_id, daughter_id, annotation)
                for daughter_id, (parent_id, annotation, _, _)
                in reference_annotations.items()])
            return pd.DataFrame.from_dict({
                'annotation': annotations,
                'annotation_id': daughter_ids,
                'parent_annotation_id': parent_ids,})
        else:
            return pd.DataFrame(columns=['annotation', 'annotation_id', 'parent_annotation_id'])

    def get_full_annotations_for_participant(self, tier_id):
        """
        Return annotations for a given participant tier, including daughter annotations (vcm, lex, ...)
        :param tier_id: participant's tier id
        :return: pd.DataFrame with columns onset, offset, annotation, xds (non-chi), or vcm, lex, and mwu (CHI)
        """
        annotations_df = self._get_aligned_annotations(tier_id=tier_id)
        if annotations_df is None:
            return None

        # as we add daughter tiers, deepest_annotation_id column will change to their ids
        annotations_df = annotations_df.rename(columns={'annotation_id': 'deepest_annotation_id'})
        n_annotations = annotations_df.shape[0]

        if tier_id == 'CHI':
            daughter_tier_types = ('vcm', 'lex', 'mwu')
        else:
            daughter_tier_types = ('xds', )

        for daughter_tier_type in daughter_tier_types:
            daughter_tier_id = f'{daughter_tier_type}@{tier_id}'
            daughter_annotations_df = self._get_reference_annotations(tier_id=daughter_tier_id)
            daughter_annotations_df = daughter_annotations_df.rename(columns={'annotation': daughter_tier_type})
            # Merge with previously extracted annotations
            annotations_df = (annotations_df.merge(daughter_annotations_df,
                                 how='left',
                                 left_on='deepest_annotation_id',
                                 right_on='parent_annotation_id')
             .drop(columns=['deepest_annotation_id', 'parent_annotation_id'])
             .rename(columns={'annotation_id': 'deepest_annotation_id'})
             )

        assert annotations_df.shape[0] == n_annotations
        return annotations_df.drop(columns=['deepest_annotation_id'])

    def get_full_annotations(self):
        """
        All participant-tier annotations, including daughter tiers (xds, vcm, ...)
        :return: pd.DataFrame with columns participant, onset, offset, annotation, xds ,vcm, lex, and mwu
        """
        participant_tier_ids = self.get_participant_tier_ids()
        all_annotations = [self.get_full_annotations_for_participant(tier_id=participant_tier_id)
                           for participant_tier_id in participant_tier_ids]
        all_annotations_df = (
            pd.concat(objs=all_annotations,
                      keys=participant_tier_ids,
                      names=['participant', 'order'])
            .reset_index('participant', drop=False)
            .reset_index(drop=True))

        return all_annotations_df.sort_values(by=['onset', 'offset', 'participant'])
