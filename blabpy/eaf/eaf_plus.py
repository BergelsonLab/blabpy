import pandas as pd
from pympi import Eaf

from blabpy.eaf.eaf_utils import EafInconsistencyError
from blabpy.utils import concatenate_dataframes


class EafPlus(Eaf):
    """
    This class is just pympi.Eaf plus a few extra methods.
    """

    class AnnotationExtractionError(Exception):
        pass

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
        """
        Get aligned annotations for a given tier.
        :param tier_id: tier id, e.g., CHI
        :return: a dataframe with columns onset, offset, annotation, annotation_id
        If the tier exists but there are no annotations, return a dataframe with all Nones.
        """
        # Load times and annotations. If there aren't any, substitute placeholder to return a DataFrame with all Nones
        # in the end.
        # Times
        time_intervals = self.get_time_intervals(tier_id=tier_id)
        onsets, offsets = zip(*time_intervals) if time_intervals else ([None], [None])
        # Annotations
        aligned_annotations, _, _, _ = self.tiers[tier_id]
        aligned_annotations = aligned_annotations or {None: (None, None, None, None)}
        ids, annotations = zip(*[(id_, annotation) for id_, (_, _, annotation, _) in aligned_annotations.items()])

        return pd.DataFrame.from_dict(dict(
            onset=onsets, offset=offsets,
            annotation=annotations,
            annotation_id=ids))

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

    def get_flattened_annotations_for_tier(self, tier_id):
        """
        Return annotations for a given participant tier as a table with one row per annotation and one column per
        each daughter tier (vcm, lex, ...)
        :param tier_id: participant's tier id
        :return: pd.DataFrame with columns onset, offset, annotation, participant_annotation_id, and one column per
        daughter tier. If the tier exists but contains no annotations, return a dataframe with no daughter tier columns
        and all Nones in the other columns.
        """
        annotations_df = self._get_aligned_annotations(tier_id=tier_id)

        # Strip white space from annotations
        annotations_df['annotation'] = annotations_df['annotation'].str.strip()

        # I want to keep the annotation IDs to have a unique identifier. We'll be merging annotations_df with
        # annotations from daughter tiers which will have their own 'annotation_id' column so we'll rename this one.
        annotations_df = annotations_df.rename(columns={'annotation_id': 'participant_annotation_id'})

        # Save the number of annotations to check that we don't duplicate any when we later merge them with daughter
        # tier annotations.
        n_annotations = annotations_df.shape[0]

        # The annotations are in daughter tiers of the participant tier. Their IDs are in the format "xds@CHI".
        daughter_tier_ids = [tier_id_ for tier_id_ in self.tiers if tier_id_.endswith(f'@{tier_id}')]
        if len(daughter_tier_ids) == 0:
            return annotations_df

        # Gather all annotation from daughter tiers
        daughter_annotations = concatenate_dataframes(
            dataframes=[self._get_reference_annotations(tier_id=daughter_tier_id)
                        for daughter_tier_id in daughter_tier_ids],
            keys=daughter_tier_ids,
            key_column_name='daughter_tier_id')

        # If there aren't any daughter annotations, we are done.
        if daughter_annotations.shape[0] == 0:
            return annotations_df

        # Strip white space from annotations
        daughter_annotations['annotation'] = daughter_annotations['annotation'].str.strip()

        # Now, we are going to merge the participant annotations (annotations_df) with the daughter annotations
        # (daughter_annotations) iteratively. Each time, we are going to add all daughter tiers one level deeper
        # down the hierarchy. There can't be more levels that there are daughter tiers, so that's how many times we will
        # try adding more annotations by merging. Each merge will add as many columns as there are daughter tiers on the
        # current level - one column per daughter tier.
        # For example, if we have the following hierarchy:
        # FA1 -> x -> y -> z
        #     \
        #      -> a -> b
        # then the three meaningful merges will add columns (x, a), (y, b), (z).
        annotations_df['deepest_annotation_id'] = annotations_df['participant_annotation_id']
        daughter_annotations = daughter_annotations.rename(columns={'annotation': 'daughter_annotation'})
        for level in range(len(daughter_tier_ids)):
            annotations_df = (
                annotations_df
                .merge(
                    daughter_annotations,
                    how='left',
                    left_on='deepest_annotation_id',
                    right_on='parent_annotation_id',)
                .drop(columns=['deepest_annotation_id', 'parent_annotation_id'])
                .rename(columns={f'annotation_id': 'daughter_annotation_id'})
                .assign(**{'deepest_annotation_id': lambda df: df['daughter_annotation_id']})
                )

            # Due to parallel daughter tier branches, we might need fewer iterations than there are daughter tiers. In
            # that case, we'll have NaNs in the deepest_annotation_id column. We'll remove the empty columns we've just
            # added and stop the loop.
            just_added_columns = 'daughter_tier_id', 'daughter_annotation', 'daughter_annotation_id'
            if annotations_df['deepest_annotation_id'].isna().all():
                annotations_df = annotations_df.drop(columns=list(just_added_columns))
                last_level = level - 1
                break

            else:
                # We are adding `just_added_columns` every time, so we'll add a suffix to distinguish them.
                suffix = f'_{level}'
                annotations_df = annotations_df.rename(columns={col_name: f'{col_name}{suffix}'
                                                                for col_name in just_added_columns})
                last_level = level

        # We only need annotations IDs from one level to keep track of parallel annotations one level deeper. There is
        # no "deeper" for the last level, so we can drop its IDs.
        annotations_df.drop(columns=[f'daughter_annotation_id_{last_level}', 'deepest_annotation_id'], inplace=True)

        # ???
        # We have to go in reverse order because ??? ~otherwise we'll lose parent_annotation_id in case of parallel tier branches~
        for level in reversed(range(last_level + 1)):
            # We need to keep track
            if level == 0:
                parent_annotation_id_column = 'participant_annotation_id'
            else:
                parent_annotation_id_column = f'daughter_annotation_id_{level - 1}'
            annotations_df = (
                annotations_df
                # We need to pivot daughter tier IDs and annotation into columns and their values respectively.
                # Everything else should at most collapse in case of parallel daughter annotation of the same parent
                # annotation and should otherwise stay the same. Importantly, everything else includes the parent
                # annotation ID so that parallel daughter annotations end up in the same row. To keep everything else
                # intact, we'll set it those columns as index first.
                .set_index(
                        [c for c in annotations_df.columns.values if
                         not (c.startswith('daughter_') and c.endswith(f'_{level}'))])
                # Pivot 'daughter_tier_id', 'daughter_annotation' using `parent_annotation_id` as row ID.
                .set_index([f'daughter_tier_id_{level}'], append=True)
                .unstack(level=-1)
                # Unstack saves the names of the pivoted columns in the columns index. We don't need that reminder.
                .droplevel(level=0, axis=1)
                .rename_axis(None, axis=1)
                .reset_index(drop=False)
                # Drop the parent annotation IDs - they are the deepest level IDs now, and we don't need them anymore.
                .drop(columns=(list() if level == 0 else [parent_annotation_id_column]))
                # Some annotations might not have had any daughter annotations at the level we've just unstacked. In
                # that case, we'll have an <NA> column. It will be completely empty, because if daughter annotation
                # IDs are missing, then the corresponding daughter annotations are missing too. We'll drop the column.
                .drop(columns=pd.NA, errors='ignore')
            )

        # The comments might make it seem that we should be done by this point, but we are not. We have all the columns
        # and all the data but there might still be multiple rows per annotation. Here is an example:
        # 'baby', 'a1' - speaker-level annotation.
        # daughter annotations:
        # 'tier_id', 'ann_id', 'parent_ann_id', 'annotation'
        # 'x21@FA1', 'a21',    'a1',            'A'
        # 'x22@FA1', 'a22',    'a1',            'B'
        # 'x31@FA1', 'a31',    'a21'            'C'
        # Merging result:
        # 'ann', 'speaker_ann_id', 'tier_id_0', 'ann_0', 'ann_id_0', 'tier_id_1', 'ann_1', 'ann_id_1'
        # 'baby', 'a1',            'x21@FA1',   'A',     'a21',      'x31@FA1',   'C',     'a31'
        # 'baby', 'a1',            'x22@FA1',   'B',     'a22',      <NA>,        <NA>,    <NA>
        # Unstacking result:
        # 'ann', 'speaker_ann_id', 'x31@FA1', 'x21@FA1', 'x22@FA1'
        # 'baby', 'a1',            C,         'A',       '<NA>'
        # 'baby', 'a1',            <NA>,      <NA>,       'B'
        # We need to collapse the rows with the same annotation and speaker_ann_id. We'll do that by grouping by
        # annotation and speaker_ann_id and concatenating the values in the other columns.
        non_daughter_annotation_columns = [c for c in annotations_df.columns.values if '@' not in c]
        annotations_df = (
            annotations_df
            .set_index(non_daughter_annotation_columns)
            .groupby(non_daughter_annotation_columns)
            .transform(lambda x: sorted(x, key=lambda k: pd.isna(k)))
            .groupby(non_daughter_annotation_columns)
            .last()
            .reset_index(drop=False)
        )

        # Remove the suffixes from the column names: xds@FA1 -> xds
        annotations_df = annotations_df.rename(columns={col_name: col_name.split('@')[0]
                                                        for col_name in annotations_df.columns.values})

        if annotations_df.shape[0] != n_annotations:
            raise self.AnnotationExtractionError('The number of annotations has changed during the extraction process.')

        return annotations_df

    def get_annotations(self, drop_empty_tiers=True):
        """
        All participant-tier annotations, including daughter tiers (xds, vcm, ...). Empty tiers are dropped by default.
        To keep them, set `drop_empty_tiers=False`.
        :param drop_empty_tiers: Whether to drop tiers with no annotations.
        :return: pd.DataFrame with columns participant, onset, offset, annotation, xds ,vcm, ...
        """
        participant_tier_ids = self.get_participant_tier_ids()
        all_annotations = [self.get_flattened_annotations_for_tier(tier_id=participant_tier_id)
                           for participant_tier_id in participant_tier_ids]
        all_annotations_df = (
            pd.concat(objs=all_annotations,
                      keys=participant_tier_ids,
                      names=['participant', 'order'])
            .reset_index('participant', drop=False))

        if drop_empty_tiers:
            all_annotations_df = all_annotations_df[all_annotations_df['annotation'].notna()]

        all_annotations_df = (all_annotations_df
                              .sort_values(by=['onset', 'offset', 'participant'])
                              .reset_index(drop=True)
                              .convert_dtypes())

        if drop_empty_tiers:
            all_annotations_df = all_annotations_df[all_annotations_df['annotation'].notna()]

        return all_annotations_df.sort_values(by=['onset', 'offset', 'participant']).reset_index(drop=True)


    def get_intervals(self):
        """
        Find code, code_num, sampling_type, context tiers and put them into a dataframe.
        :return:
        """
        data = dict()
        for extra_info_type in ('code_num', 'sampling_type'):
            data[extra_info_type] = self.get_values(extra_info_type)
        data['onset'], data['offset'] = zip(*self.get_time_intervals('code'))
        data['context_onset'], data['context_offset'] = zip(*self.get_time_intervals('context'))

        # Check that the onsets and offsets are the same as in the on_off tier which contains the same information
        # but in the format '{onset}_{offset}'. Allow minor differences up to 1000 ms.
        on_off_onsets, on_off_offsets = zip(*(
            map(int, on_off.split('_'))
            for on_off in self.get_values('on_off')))
        for onset, offsets, on_off_onset, on_off_offset in zip(
                data['onset'], data['offset'], on_off_onsets, on_off_offsets):
            if max(abs(onset - on_off_onset), abs(offsets - on_off_offset)) > 1000:
                msg = (f'Onset and offset of the coding interval {onset} - {offsets} do not match the onset and offset '
                       f'in the on_off tier {on_off_onset} - {on_off_offset}.')
                raise EafInconsistencyError(msg)

        intervals_df = (pd.DataFrame.from_dict(data)
                        .sort_values(by='onset')
                        .reset_index(drop=True)
                        .convert_dtypes())
        return intervals_df

    @staticmethod
    def _assign_annotations_to_intervals(annotations, intervals, id_column='code_num'):
        """
        Assigns annotations to intervals they are in.
        Corner cases:
        - Annotation only partially overlaps with an interval - assign to that interval, unless...
        - ...Annotations overlaps with two consecutive intervals - assign to the first one.
        :param annotations: A dataframe with columns `onset` and `offset`.
        :param intervals: A dataframe with columns `onset` and `offset`.
        :param id_column: The name of the column in `intervals` that is a unique identifier of the interval.
        :return: A series with the same index as `annotations` and values from `intervals`' `id_column`.
        """

        def is_timestamp_in_interval(timestamp_series, onset, offset):
            # In case there are two consecutive intervals and there is a timestamp that is exactly on the boundary,
            # we will count it as being in the second interval by checking that timestamps happen strictly before the
            # interval's offset.
            return (onset <= timestamp_series) & (timestamp_series < offset)

        def assign_timestamps_to_intervals(timestamp_series):
            # One boolean column for each interval, code_num values as column names.
            in_which_interval_dummies = pd.DataFrame.from_dict({
                row[id_column]: is_timestamp_in_interval(timestamp_series, row.onset, row.offset)
                for _, row in intervals.iterrows()
            })
            # pd.from_dummies() returns a dataframe with a single column. Initially, I used .squeeze() to convert it to
            # a series, but for a single-row single-column dataframe, squeeze() returns a scalar, not a series.
            in_which_interval = pd.from_dummies(in_which_interval_dummies, default_category='-1').iloc[:, 0]
            in_which_interval.name = id_column
            return in_which_interval

        # Some annotations cross the interval boundary, so we will count an annotation as being in the interval if its
        # onset is in the interval. This will also take care of annotations that overlap with two intervals: onset will
        # only be in one of them.
        assignment_by_onset = assign_timestamps_to_intervals(annotations.onset)

        # At this point, however, we are missing annotations whose onset is not in any interval but whose offset is. So,
        # for each annotation that was not assigned to an interval by onset, we will assign it by offset.
        assignment_by_offset = assign_timestamps_to_intervals(annotations.offset)
        assignment = assignment_by_onset.where(lambda s: s != '-1', other=assignment_by_offset)

        # Finally, there can be placeholder rows with no onset or offset in annotations_df (e.g., placeholder empty
        # annotations for empty tiers). These currently have '-1' assigned, but we are going to replace them with
        # <NA>s to differentiate between annotations outside any interval and these placeholder ones.
        assignment.loc[annotations.onset.isna() | annotations.offset.isna()] = pd.NA

        return assignment

    def get_annotations_and_intervals(self, drop_empty_tiers=True):
        """
        Return annotations and intervals as dataframes. See `get_annotations` and `get_intervals` for details.
        :param drop_empty_tiers: see `get_annotations`
        :return: annotations, intervals where:
         - annotations is the output of `get_annotations` with a new `code_num` column that matches annotations to
           intervals and
         - intervals is the output of `get_intervals`.
        """
        annotations = self.get_annotations(drop_empty_tiers=drop_empty_tiers)
        intervals = self.get_intervals()
        assignment = self._assign_annotations_to_intervals(annotations, intervals)
        annotations[assignment.name] = assignment
        return annotations, intervals
