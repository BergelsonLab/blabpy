"""
Module with classes and functions for working with ELAN .eaf files. There are two principal ways of working with .eaf
using this module:
- EafPlus class which is just pympi.Eaf plus a few extra methods.
- An assortment of functions that work with .eaf files as XML trees that they are.

Notes:
- It would be cleaner to wrap the XML-tree-based functions in classes at some point.
- Many functions are XML-general and could be moved to a separate module or aggregated in a separate class.

Glossary:
- *Aligned* vs. *referenced* annotations: Aligned annotations are the ones that have their own timestamps, e.g.,
  participant utterances. Referenced don't have their own timestamps, e.g., xds, lex, vcm, etc.
- *Daughter* vs. *parent* annotations: Tiers are organized in a hierachy

TODO:
[ ] Refactor add_* functions to use a single add_element function.
[ ] Currently, many attributes are implicitly hard-coded via `attributes=dict(ATTRIBUTE=value)`. Switch to using
    `attributes={ATTRIBUTE: value}` after defining corresponding constants (ATTRIBUTE = 'ATTRIBUTE' in this case).
"""
import functools
from io import StringIO
from pathlib import Path
from xml.etree import ElementTree as element_tree
from xml.etree.ElementTree import Element

import pandas as pd
import requests
from pympi import Eaf

from blabpy.utils import concatenate_dataframes

# Property values
SYMBOLIC_ASSOCIATION = "Symbolic_Association"

# URLs of external files with controlled vocabularies
ACLEW_ECV_URL = ('https://raw.githubusercontent.com/marisacasillas/DARCLE-AnnSchDev/master/ACLEW/'
                 'External-closed-vocabularies/ACLEW-basic-vocabularies.ecv')
BLAB_ECV_URL = "https://raw.githubusercontent.com/BergelsonLab/public-files/main/ACLEW-blab-vocabularies.ecv"


class EafInconsistencyError(Exception):
    pass


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

        # Empty annotations ('') do not represent anything meaningful: they are just there to be filled by an annotator
        # later.
        daughter_annotations = daughter_annotations[daughter_annotations['annotation'] != '']

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


class EafElement(object):
    """
    Base class for all EAF elements.
    TODO:
    - move __init__(), element(), id(), and validate() here,
    - define mandatory constants (TAG, ID, etc.),
    - define MandatoryAttribute, ConditionalAttribute, and OptionalAttribute classes,
    - move conditional_property() here,
    """
    @property
    def element(self):
        return self._element

    @property
    def id(self):
        return self.element.attrib[self.ID]

    def _validate_no_text(self):
        text = self.element.text
        if text and not text.isspace():
            raise ValueError(f'{self.TAG} element must not have text, had "{text.strip()}" instead.')

    def _validate_no_attributes(self):
        attributes = self.element.attrib
        if attributes:
            raise ValueError(f'{self.TAG} element must not have attributes, had "{attributes}" instead.')


class Annotation(EafElement):
    TAG = 'ANNOTATION'
    ID = 'ANNOTATION_ID'

    ALIGNABLE_ANNOTATION = 'ALIGNABLE_ANNOTATION'
    REF_ANNOTATION = 'REF_ANNOTATION'
    ANNOTATION_VALUE = 'ANNOTATION_VALUE'

    ANNOTATION_REF = 'ANNOTATION_REF'
    TIME_SLOT_REF1 = 'TIME_SLOT_REF1'
    TIME_SLOT_REF2 = 'TIME_SLOT_REF2'
    CVE_REF = 'CVE_REF'

    def __init__(self, annotation_element, eaf_tree, tier):
        self._element = annotation_element
        self._eaf_tree = eaf_tree
        self.tier = tier
        self.validate()
        self._children = None

    @property
    def eaf_tree(self):
        return self._eaf_tree

    @property
    def inner_element(self):
        return self.element[0]

    @property
    def id(self):
        return self.inner_element.attrib[self.ID]

    @property
    def annotation_type(self):
        return self.inner_element.tag

    @staticmethod
    def conditional_property(annotation_type):
        def decorator(func):
            @functools.wraps(func)
            def wrapper(self):
                if self.annotation_type != annotation_type:
                    raise ValueError(f'Only {annotation_type}s have {func.__name__}.')
                return func(self)
            return property(wrapper)
        return decorator

    @conditional_property(ALIGNABLE_ANNOTATION)
    def time_slot_ref1(self):
        return self.inner_element.attrib[self.TIME_SLOT_REF1]

    @conditional_property(ALIGNABLE_ANNOTATION)
    def time_slot_ref2(self):
        return self.inner_element.attrib[self.TIME_SLOT_REF2]

    @conditional_property(REF_ANNOTATION)
    def annotation_ref(self):
        return self.inner_element.attrib[self.ANNOTATION_REF]

    @conditional_property(REF_ANNOTATION)
    def parent(self):
        return self.eaf_tree.annotations[self.annotation_ref]

    @conditional_property(REF_ANNOTATION)
    def children(self):
        # Should be a list, possibly an empty one
        if self._children is None:
            raise ValueError(f'The children tiers have not been assigned, tell lab technician.')
        return self._children

    @conditional_property(REF_ANNOTATION)
    def cve_ref(self):
        return self.inner_element.attrib[self.CVE_REF]

    def validate(self):
        """
        Check that the annotation element either looks like this:

        <ANNOTATION>
            <ALIGNABLE_ANNOTATION ANNOTATION_ID="a62" TIME_SLOT_REF1="ts14" TIME_SLOT_REF2="ts15">
                <ANNOTATION_VALUE>hi.</ANNOTATION_VALUE>
            </ALIGNABLE_ANNOTATION>
        </ANNOTATION>

        or like this:

        <ANNOTATION>
            <REF_ANNOTATION ANNOTATION_ID="a926" ANNOTATION_REF="a146" CVE_REF="cveid0">
                <ANNOTATION_VALUE>C</ANNOTATION_VALUE>
            </REF_ANNOTATION>
        </ANNOTATION>

        With the CVE_REF attribute being there iff the tier uses a controlled vocabulary.
        """
        # Validate outer element
        if self.element.tag != self.TAG:
            raise ValueError(f'Annotation element must have {self.TAG} as its tag.')
        if len(self.element) != 1:
            raise ValueError(f'Annotation element must have exactly one child element.')
        self._validate_no_attributes()
        self._validate_no_text()

        # Validate inner element
        inner_element = self.element[0]
        if len(inner_element) != 1:
            raise ValueError(f'Inner annotation element must have exactly one child element.')
        if inner_element.text and not inner_element.text.isspace():
            raise ValueError(f'Inner annotation element must not have text.')

        attribute_names = set(inner_element.attrib.keys())
        if inner_element.tag == self.ALIGNABLE_ANNOTATION:
            if attribute_names != {'ANNOTATION_ID', 'TIME_SLOT_REF1', 'TIME_SLOT_REF2'}:
                raise ValueError(f'ALIGNABLE_ANNOTATION must have {self.ID}, {self.TIME_SLOT_REF1},'
                                 f' and {self.TIME_SLOT_REF2} attributes.')
        elif inner_element.tag == self.REF_ANNOTATION:
            necessary_attributes = {'ANNOTATION_ID', 'ANNOTATION_REF'}
            conditional_attributes = {'CVE_REF'}
            if not necessary_attributes.issubset(attribute_names):
                raise ValueError(f'REF_ANNOTATION must have {self.ID} and {self.ANNOTATION_REF} attributes.')
            if not attribute_names.issubset(necessary_attributes.union(conditional_attributes)):
                raise ValueError(f'REF_ANNOTATION must not have any other attributes than {necessary_attributes} and '
                                 f'{conditional_attributes}.')
        else:
            raise ValueError(f'Unknown annotation type: {inner_element.tag}')

        value_element = inner_element[0]
        if value_element.tag != self.ANNOTATION_VALUE:
            raise ValueError(f'Inner annotation element must have {self.ANNOTATION_VALUE} as its child element.')
        if value_element.attrib:
            raise ValueError(f'Inner annotation element must not have attributes.')

        # For tiers with controlled vocabularies, check that CVE_REF and annotation value are both present and
        # consistent or both absent.
        if self.eaf_tree.validate_cv_entries and self.annotation_type == self.REF_ANNOTATION and self.tier.uses_cv:
            value = value_element.text
            not_empty = value != ''
            cve_ref = self.inner_element.attrib.get(self.CVE_REF)
            has_cve_ref = cve_ref is not None
            if has_cve_ref != not_empty:
                raise ValueError(f'For tiers with controlled vocabularies, {self.CVE_REF} attribute must be present iff '
                                 f'there is a non-empty value.')
            if not_empty and (value != self.tier.cv.entries[cve_ref].value):
                raise ValueError(f'Value {value} does not match the {cve_ref} item in the controlled vocabulary.')


class Tier(EafElement):
    TAG = 'TIER'
    ID = 'TIER_ID'
    LINGUISTIC_TYPE_REF = 'LINGUISTIC_TYPE_REF'
    PARENT_REF = 'PARENT_REF'
    PARTICIPANT = 'PARTICIPANT'

    def __init__(self, tier_element, eaf_tree):
        self._element = tier_element
        self._eaf_tree = eaf_tree
        annotations = [Annotation(annotation_element, eaf_tree=eaf_tree, tier=self)
                       for annotation_element in tier_element]
        self.annotations = {annotation.id: annotation for annotation in annotations}
        self._children = None

    @property
    def eaf_tree(self):
        return self._eaf_tree

    @property
    def linguistic_type_ref(self):
        return self.element.attrib[self.LINGUISTIC_TYPE_REF]

    @property
    def linguistic_type(self):
        return self.eaf_tree.linguistic_types[self.linguistic_type_ref]

    @property
    def parent_ref(self):
        return self.element.attrib.get(self.PARENT_REF)

    @property
    def parent(self):
        if self.parent_ref is None:
            raise ValueError(f'Tier {self.id} doesn\'t have a parent.')
        return self.eaf_tree.tiers[self.parent_ref]

    @property
    def children(self):
        # Should be a list, possibly an empty one
        if self._children is None:
            raise ValueError(f'The parent tier has not been loaded, tell lab technician.')
        return self._children

    @property
    def participant(self):
        return self.element.attrib.get(self.PARTICIPANT)

    @property
    def uses_cv(self):
        return self.linguistic_type.uses_cv

    @property
    def cv(self):
        return self.linguistic_type.cv

    def validate(self):
        if self.element.tag != self.TAG:
            raise ValueError(f'Tier element must have {self.TAG} as its tag.')
        necessary_attributes = {self.LINGUISTIC_TYPE_REF, self.ID}
        possible_extra_attributes = {self.PARENT_REF, self.PARTICIPANT}
        attribute_names = set(self.element.attrib.keys())
        if not necessary_attributes.issubset(attribute_names):
            raise ValueError(f'Tier element must have {self.LINGUISTIC_TYPE_REF} and {self.ID} attributes.')
        if not attribute_names.issubset(necessary_attributes.union(possible_extra_attributes)):
            raise ValueError(f'Tier element must not have any other attributes than {necessary_attributes} and '
                             f'{possible_extra_attributes}.')
        self._validate_no_text()


class LinguisticType(EafElement):
    TAG = 'LINGUISTIC_TYPE'
    ID = 'LINGUISTIC_TYPE_ID'
    TIME_ALIGNABLE = 'TIME_ALIGNABLE'
    GRAPHIC_REFERENCES = 'GRAPHIC_REFERENCES'
    NECESSARY_ATTRIBUTES = {ID, TIME_ALIGNABLE, GRAPHIC_REFERENCES}

    CONSTRAINTS = 'CONSTRAINTS'
    CONTROLLED_VOCABULARY_REF = 'CONTROLLED_VOCABULARY_REF'
    POSSIBLE_EXTRA_ATTRIBUTES = {CONSTRAINTS, CONTROLLED_VOCABULARY_REF}

    def __init__(self, linguistic_type_element, eaf_tree):
        self._element = linguistic_type_element
        self._eaf_tree = eaf_tree
        self.validate()

    @property
    def eaf_tree(self):
        return self._eaf_tree

    @property
    def time_alignable(self):
        return self.element.attrib[self.TIME_ALIGNABLE]

    @property
    def graphic_references(self):
        return self.element.attrib[self.GRAPHIC_REFERENCES]

    @property
    def constraints(self):
        return self.element.attrib.get(self.CONSTRAINTS)

    @property
    def controlled_vocabulary_ref(self):
        return self.element.attrib.get(self.CONTROLLED_VOCABULARY_REF)

    @property
    def uses_cv(self):
        return self.controlled_vocabulary_ref is not None

    @property
    def cv(self):
        if not self.uses_cv:
            raise ValueError(f'This linguistic type does not use a controlled vocabulary.')
        else:
            return self.eaf_tree.controlled_vocabularies[self.controlled_vocabulary_ref]

    def validate(self):
        if self.element.tag != self.TAG:
            raise ValueError(f'LinguisticType element must have {self.TAG} as its tag.')
        attribute_names = set(self.element.attrib.keys())
        if not self.NECESSARY_ATTRIBUTES.issubset(attribute_names):
            raise ValueError(f'LinguisticType element must have {self.NECESSARY_ATTRIBUTES} attributes.')
        if not attribute_names.issubset(self.NECESSARY_ATTRIBUTES.union(self.POSSIBLE_EXTRA_ATTRIBUTES)):
            raise ValueError(f'LinguisticType element must not have any other attributes than {self.NECESSARY_ATTRIBUTES} '
                             f'and {self.POSSIBLE_EXTRA_ATTRIBUTES}.')
        self._validate_no_text()


class ControlledVocabularyEntry(EafElement):
    TAG = 'CV_ENTRY_ML'
    ID = 'CVE_ID'
    CVE_VALUE = 'CVE_VALUE'
    ALL_ATTRIBUTES = {ID}

    def __init__(self, cv_entry_element):
        """
        <CV_ENTRY_ML CVE_ID="cveid0">
            <CVE_VALUE DESCRIPTION="Present" LANG_REF="und">P</CVE_VALUE>
        </CV_ENTRY_ML>
        """
        self._element = cv_entry_element
        self.validate()

    @property
    def value_element(self):
        return self._element[0]

    @property
    def description(self):
        return self.value_element.attrib['DESCRIPTION']

    @property
    def value(self):
        return self.value_element.text

    def validate(self):
        if self.element.tag != self.TAG:
            raise ValueError(f'Controlled vocabulary entry element must have {self.TAG} as its tag.')
        attribute_names = set(self.element.attrib.keys())
        if self.ALL_ATTRIBUTES != attribute_names:
            raise ValueError(f'Controlled vocabulary entry element must have {self.ALL_ATTRIBUTES} attributes and only'
                             f' them.')

        (self._value_element, ) = self.element
        if self._value_element.tag != self.CVE_VALUE:
            raise ValueError(f'Controlled vocabulary entry element must have {self.CVE_VALUE} as its child element.')
        if self._value_element.attrib.keys() != {'DESCRIPTION', 'LANG_REF'}:
            raise ValueError(f'Controlled vocabulary entry element must have DESCRIPTION and LANG_REF attributes.')
        if not self._value_element.text:
            raise ValueError(f'Controlled vocabulary entry element must have text.')


class ControlledVocabulary(EafElement):
    TAG = 'CONTROLLED_VOCABULARY'
    ID = 'CV_ID'
    DESCRIPTION = 'DESCRIPTION'
    EXT_REF = 'EXT_REF'
    # TODO: it isn't necessary to have EXT_REF, the CV can be defined in the element itself. Allow for that.
    NECESSARY_ATTRIBUTES = {ID}
    POSSIBLE_EXTRA_ATTRIBUTES = {EXT_REF}

    def __init__(self, cv_element, eaf_tree):
        self._element = cv_element
        self._eaf_tree = eaf_tree
        self.validate()
        if not self.ext_ref:
            self._description, self._entries = self.parse()

    @property
    def eaf_tree(self):
        return self._eaf_tree

    @property
    def ext_ref(self):
        return self.element.get(self.EXT_REF)

    @property
    def external_reference(self):
        if self.ext_ref:
            return self.eaf_tree.external_references[self.ext_ref]
        else:
            raise ValueError(f'This controlled vocabulary does not have an external reference.')

    @property
    def external_cv(self):
        return self.external_reference.cv_resource.cvs[self.id]

    @property
    def description(self):
        if self.ext_ref:
            return self.external_cv.description
        else:
            return self._description

    @property
    def entries(self):
        if self.ext_ref:
            return self.external_cv.entries
        else:
            return self._entries

    def validate(self):
        if self.element.tag != self.TAG:
            raise ValueError(f'Controlled vocabulary element must have {self.TAG} as its tag.')
        attribute_names = set(self.element.attrib.keys())
        if not self.NECESSARY_ATTRIBUTES.issubset(attribute_names):
            raise ValueError(f'Controlled vocabulary element must have {self.NECESSARY_ATTRIBUTES} attributes.')
        if not attribute_names.issubset(self.NECESSARY_ATTRIBUTES.union(self.POSSIBLE_EXTRA_ATTRIBUTES)):
            raise ValueError(f'Controlled vocabulary element must not have any other attributes than '
                             f'{self.NECESSARY_ATTRIBUTES} and {self.POSSIBLE_EXTRA_ATTRIBUTES}.')
        self._validate_no_text()

    def parse(self):
        """
        <CONTROLLED_VOCABULARY CV_ID="present">
            <DESCRIPTION LANG_REF="und">generalized flag</DESCRIPTION>
            <CV_ENTRY_ML CVE_ID="cveid0">
                <CVE_VALUE DESCRIPTION="Present" LANG_REF="und">P</CVE_VALUE>
            </CV_ENTRY_ML>
        </CONTROLLED_VOCABULARY>
        """
        (description_element, ) = [el for el in self.element if el.tag == self.DESCRIPTION]
        entry_elements = [ControlledVocabularyEntry(el)
                          for el in self.element if el.tag == ControlledVocabularyEntry.TAG]
        return description_element, {entry.id: entry for entry in entry_elements}


class ExternalReference(EafElement):
    TAG = 'EXTERNAL_REF'
    ID = 'EXT_REF_ID'
    TYPE = 'TYPE'
    VALUE = 'VALUE'
    NECESSARY_ATTRIBUTES = {ID, TYPE, VALUE}

    def __init__(self, ext_ref_element):
        self._element = ext_ref_element
        self.validate()
        self.cv_resource = self.parse()

    @property
    def ext_ref_id(self):
        return self.element.attrib[self.ID]

    @property
    def type(self):
        return self.element.attrib[self.TYPE]

    @property
    def value(self):
        return self.element.attrib[self.VALUE]

    def validate(self):
        if self.element.tag != self.TAG:
            raise ValueError(f'External reference element must have {self.TAG} as its tag.')
        attribute_names = set(self.element.attrib.keys())
        if not self.NECESSARY_ATTRIBUTES.issubset(attribute_names):
            raise ValueError(f'External reference element must have {self.NECESSARY_ATTRIBUTES} '
                             f'attributes.')
        self._validate_no_text()

    def parse(self):
        return ControlledVocabularyResource.from_uri(self.value)


class XMLTree(object):
    def __init__(self, tree):
        self._tree = tree

    @property
    def tree(self):
        return self._tree

    @classmethod
    def from_path(cls, path, *args, **kwargs):
        with Path(path).open('r') as f:
            return cls(element_tree.parse(f), *args, **kwargs)

    @classmethod
    def from_url(cls, url, *args, **kwargs):
        u = requests.get(url)
        with StringIO() as f:
            f.write(u.content.decode())
            f.seek(0)
            tree = element_tree.parse(f)
        return cls(tree, *args, **kwargs)

    @classmethod
    def from_uri(cls, uri, *args, **kwargs):
        uri = str(uri)
        # TODO: parse the uri with urlparse instead of using startswith
        if uri.startswith('http'):
            return cls.from_url(uri, *args, **kwargs)
        else:
            path = uri.replace('file:', '')
            return cls.from_path(path, *args, **kwargs)

    def to_string(self):
        return element_to_string(self.tree.getroot(), children=True)

    def to_file(self, path):
        Path(path).write_text(self.to_string())

    def to_eaf(self, path):
        self.to_file(path)

    @staticmethod
    def _make_find_xpath(tag, **attributes):
        if attributes:
            attribute_filters = [f'@{name}="{value}"' for name, value in attributes.items()]
            attributes_filter = '[' + ' and '.join(attribute_filters) + ']'
        else:
            attributes_filter = ''
        return f'.//{tag}{attributes_filter}'

    def find_element(self, tag, **attributes):
        return self.tree.find(_make_find_xpath(tag, **attributes))

    def find_elements(self, tag, **attributes):
        return self.tree.findall(_make_find_xpath(tag, **attributes))

    def find_single_element(self, tag, **attributes):
        """
        Find a single element in the tree. Raise an error if there are none or more than one.
        """
        elements = self.find_elements(tag, **attributes)
        if len(elements) == 0:
            raise ValueError(f'Couldn\'t find any elements with tag "{tag}" and attributes {attributes}.')
        elif len(elements) == 1:
            return elements[0]
        else:
            raise ValueError(f'Found more than one element with tag "{tag}" and attributes {attributes}.')


class ControlledVocabularyResource(XMLTree):
    """
    An XML tree representation of a controlled vocabulary resource.
    """
    TAG = 'CV_RESOURCE'

    def __init__(self, cv_resource_tree):
        super().__init__(cv_resource_tree)
        cvs = [ControlledVocabulary(cv_element, eaf_tree=None)
               for cv_element in self.tree.getroot()
               if cv_element.tag == ControlledVocabulary.TAG]
        self._cvs = {cv.id: cv for cv in cvs}
        # TODO: add a class for languages
        self._language = self.find_single_element('LANGUAGE')
        # TODO: validate including xml schemas and such

    @property
    def cvs(self):
        return self._cvs

    @property
    def language(self):
        return self._language


class EafTree(XMLTree):
    """An XML tree representation of an EAF file."""
    @classmethod
    def from_eaf(cls, eaf_uri: str):
        return cls.from_uri(eaf_uri)

    def __init__(self, tree, validate_cv_entries=True):
        super().__init__(tree)
        self.validate_cv_entries = validate_cv_entries

        self.external_references = self._parse_elements(ExternalReference)
        self.controlled_vocabularies = self._parse_elements(ControlledVocabulary, eaf_tree=self)
        self.linguistic_types = self._parse_elements(LinguisticType, eaf_tree=self)
        self.tiers = self._parse_elements(Tier, eaf_tree=self)
        self.annotations = {id_: annotation
                            for tier in self.tiers.values()
                            for id_, annotation in tier.annotations.items()}

        # TODO: connect parents and children

    def _parse_elements(self, element_class, *args, **kwargs):
        elements = [element_class(element, *args, **kwargs) for element in self.find_elements(element_class.TAG)]
        return {element.id: element for element in elements}


def path_to_tree(path):
    with Path(path).open('r') as f:
        return element_tree.parse(f)


def url_to_tree(url: str):
    u = requests.get(url)
    with StringIO() as f:
        f.write(u.content.decode())
        f.seek(0)
        tree = element_tree.parse(f)
    return tree


def uri_to_tree(uri):
    uri = str(uri)
    # TODO: parse the uri with urlparse instead of using startswith
    if uri.startswith('http'):
        return url_to_tree(uri)
    else:
        path = uri.replace('file:', '')
        return path_to_tree(path)


def eaf_to_tree(eaf_uri: str):
    return uri_to_tree(eaf_uri)


# Copied from xml.etree.ElementTree in Python 3.9
def indent(tree, space="  ", level=0):
    """Indent an XML document by inserting newlines and indentation space
    after elements.
    *tree* is the ElementTree or Element to modify.  The (root) element
    itself will not be changed, but the tail text of all elements in its
    subtree will be adapted.
    *space* is the whitespace to insert for each indentation level, two
    space characters by default.
    *level* is the initial indentation level. Setting this to a higher
    value than 0 can be used for indenting subtrees that are more deeply
    nested inside a document.
    """
    if isinstance(tree, element_tree.ElementTree):
        tree = tree.getroot()
    if level < 0:
        raise ValueError(f"Initial indentation level must be >= 0, got {level}")
    if not len(tree):
        return

    # Reduce the memory consumption by reusing indentation strings.
    indentations = ["\n" + level * space]

    def _indent_children(elem, level):
        # Start a new indentation level for the first child.
        child_level = level + 1
        try:
            child_indentation = indentations[child_level]
        except IndexError:
            child_indentation = indentations[level] + space
            indentations.append(child_indentation)

        if not elem.text or not elem.text.strip():
            elem.text = child_indentation

        for child in elem:
            if len(child):
                _indent_children(child, child_level)
            if not child.tail or not child.tail.strip():
                child.tail = child_indentation

        # Dedent after the last child by overwriting the previous indentation.
        if not child.tail.strip():
            child.tail = indentations[level]

    _indent_children(tree, 0)


def element_to_string(element, children=True):
    if isinstance(element, element_tree.ElementTree):
        element = element.getroot()
    if not children:
        element = element.makeelement(element.tag, element.attrib)
    spacing = 4 * ' '
    indent(element, space=spacing)
    return element_tree.canonicalize(element_tree.tostring(element, xml_declaration=True, encoding='utf-8'))


def tree_to_string(tree):
    return element_to_string(tree.getroot(), children=True)


def tree_to_path(tree, path):
    Path(path).write_text(tree_to_string(tree))


def tree_to_eaf(tree, path):
    tree_to_path(tree, path)


def get_all(eaf_tree, tag, id_attrib):
    return {element.get(id_attrib): element
            for element in eaf_tree.findall(f'.//{tag}')}


def _make_find_xpath(tag, **attributes):
    if attributes:
        attribute_filters = [f'@{name}="{value}"' for name, value in attributes.items()]
        attributes_filter = '[' + ' and '.join(attribute_filters) + ']'
    else:
        attributes_filter = ''
    return f'.//{tag}{attributes_filter}'


def find_element(tree, tag, **attributes):
    return tree.find(_make_find_xpath(tag, **attributes))


def find_elements(tree, tag, **attributes):
    return tree.findall(_make_find_xpath(tag, **attributes))


def find_single_element(tree, tag, **attributes):
    """
    Find a single element in the tree. Raise an error if there are none or more than one.
    """
    elements = find_elements(tree, tag, **attributes)
    if len(elements) == 0:
        raise ValueError(f'Couldn\'t find any elements with tag "{tag}" and attributes {attributes}.')
    elif len(elements) == 1:
        return elements[0]
    else:
        raise ValueError(f'Found more than one element with tag "{tag}" and attributes {attributes}.')


class ElementAlreadyPresentError(Exception):
    pass

class CvAlreadyPresentError(ElementAlreadyPresentError):
    pass


def insert_after_last(tree, element):
    """
    Inserts an element after the last element with the same tag. Helpful to keep elements of the same type together.
    :param tree: element_tree.ElementTree to insert the element into
    :param element: element_tree.Element to insert
    :return:
    """
    root = tree.getroot()

    last_element_position = None
    for i, child in enumerate(root):
        if child.tag == element.tag:
            last_element_position = i

    if last_element_position is None:
        root.append(element)
    else:
        root.insert(last_element_position + 1, element)


def same_elements(element1, element2):
    """
    Shallow comparison: tag, attributes, text
    :param element1:
    :param element2:
    :return:
    """
    return element1.tag == element2.tag and element1.attrib == element2.attrib and element1.text == element2.text


def add_linguistic_type(eaf_tree, ling_type_id, time_alignable, constraints, cv_id, exist_identical_ok=False):
    """
    Add a linguistic type to an EAF file.
    :param eaf_tree: ElementTree of the EAF file.
    :param ling_type_id: ID of the linguistic type.
    :param time_alignable: Whether the linguistic type is time alignable.
    :param constraints: Constraints on the linguistic type, set to None if no constraints.
    :param cv_id: ID of the controlled vocabulary, set to None if no controlled vocabulary.
    :param exist_identical_ok: Whether to raise an error if the linguistic type already exists. Will still raise an
    error if the element exists but has different attributes.
    :return: The added element.

    Example (ling_type_id: "XDS", time_alignable: False, constraints: "Symbolic_Association")
    <LINGUISTIC_TYPE CONSTRAINTS="Symbolic_Association" GRAPHIC_REFERENCES="false" LINGUISTIC_TYPE_ID="XDS"
     TIME_ALIGNABLE="false"></LINGUISTIC_TYPE>
    """
    # Create the element
    time_alignable = "true" if time_alignable else "false"
    attributes = dict(CONSTRAINTS=constraints,
                      CONTROLLED_VOCABULARY_REF=cv_id,
                      GRAPHIC_REFERENCES="false",
                      LINGUISTIC_TYPE_ID=ling_type_id,
                      TIME_ALIGNABLE=time_alignable)
    if constraints is None:
        del attributes[LinguisticType.CONSTRAINTS]
    if cv_id is None:
        del attributes[LinguisticType.CONTROLLED_VOCABULARY_REF]
    element = Element(LinguisticType.TAG, attrib=attributes)

    # Avoid adding the same linguistic type twice
    ling_type_in_eaf = find_element(eaf_tree, LinguisticType.TAG, LINGUISTIC_TYPE_ID=ling_type_id)
    if ling_type_in_eaf is not None:
        if not exist_identical_ok:
            msg = f'Trying to add a "{ling_type_id}" linguistic type but it is already present.'
            raise ElementAlreadyPresentError(msg)
        if same_elements(element, ling_type_in_eaf):
            return
        else:
            msg = f'Linguistic type "{ling_type_id}" already exists but isn\'t the same as the one you are trying to ' \
                  f'add. '
            raise ValueError(msg)

    # Add the element
    insert_after_last(eaf_tree, element)
    return element


def add_cv_and_linguistic_type(eaf_tree, cv_id, ext_ref, ling_type_id, time_alignable, constraints,
                               exist_identical_ok=False):
    """
    Add a controlled vocabulary and a linguistic type to an EAF file.
    :param eaf_tree: ElementTree of the EAF file.
    :param cv_id: ID of the controlled vocabulary.
    :param ext_ref: External reference of the controlled vocabulary.
    :param ling_type_id: ID of the linguistic type.
    :param time_alignable: Whether the linguistic type is time alignable.
    :param constraints: Constraints on the linguistic type, set to None if no constraints.
    :param exist_identical_ok: Whether to raise an error if the CV already exists. Will still raise an error if the
    element exists but has different attributes.

    Example (cv_id: "xds", ling_type_id: "XDS", ext_ref: "BLab", time_alignable: False,
             constraints: "Symbolic_Association")
    <LINGUISTIC_TYPE CONSTRAINTS="Symbolic_Association" CONTROLLED_VOCABULARY_REF="xds"
     GRAPHIC_REFERENCES="false" LINGUISTIC_TYPE_ID="XDS" TIME_ALIGNABLE="false"></LINGUISTIC_TYPE>
    <CONTROLLED_VOCABULARY CV_ID="xds" EXT_REF="BLab"></CONTROLLED_VOCABULARY>
    """
    # Avoid adding the same CV twice
    cv_in_eaf = find_element(eaf_tree, ControlledVocabulary.TAG, CV_ID=cv_id)

    if cv_in_eaf is not None:
        if not exist_identical_ok:
            raise CvAlreadyPresentError(f'Trying to add a "{cv_id}" CV but it is already present.')
        ext_ref_in_eaf = cv_in_eaf.get(ControlledVocabulary.EXT_REF)
        if ext_ref_in_eaf == ext_ref:
            return
        else:
            msg = f'CV "{cv_id}" already exists but uses different external reference - "{ext_ref_in_eaf}"'
            raise ValueError(msg)

    add_linguistic_type(eaf_tree=eaf_tree, ling_type_id=ling_type_id, time_alignable=time_alignable,
                        constraints=constraints, cv_id=cv_id, exist_identical_ok=False)

    cv_attributes = dict(CV_ID=cv_id, EXT_REF=ext_ref)
    cv_element = Element(ControlledVocabulary.TAG, attrib=cv_attributes)
    insert_after_last(eaf_tree, cv_element)


def add_tier(eaf_tree, ling_type_ref, tier_id, parent_ref, exist_identical_ok=False):
    """
    Add a tier to an EAF file.
    :param eaf_tree: ElementTree of the EAF file.
    :param ling_type_ref: Linguistic type reference of the tier.
    :param tier_id: ID of the tier.
    :param parent_ref: Parent reference of the tier, set to None if no parent.
    :param exist_identical_ok: Whether to raise an error if the tier already exists. Will still raise an error if the
    element exists but has different attributes.
    :return: The added element.
    """
    # Create the element
    attributes = dict(LINGUISTIC_TYPE_REF=ling_type_ref, TIER_ID=tier_id)
    if parent_ref is not None:
        attributes[Tier.PARENT_REF] = parent_ref
    element = Element(Tier.TAG, attrib=attributes)
    
    # Avoid adding the same tier twice
    tier_in_eaf = find_element(eaf_tree, Tier.TAG, TIER_ID=tier_id)
    if tier_in_eaf is not None:
        if not exist_identical_ok:
            msg = f'Trying to add a "{tier_id}" tier but it is already present.'
            raise ElementAlreadyPresentError(msg)
        if same_elements(element, tier_in_eaf):
            return
        else:
            msg = f'Tier "{tier_id}" already exists but isn\'t the same as the one you are trying to add. '
            raise ValueError(msg)

    # Add the element
    insert_after_last(eaf_tree, element)
    return element


def get_annotation_values(tree, tier_id):
    """
    Return all the annotation values in the given tier.
    """
    tier = find_single_element(tree, 'TIER', TIER_ID=tier_id)
    annotation_values = [find_single_element(annotation, 'ANNOTATION_VALUE').text
                         for annotation in find_elements(tier, 'ANNOTATION')]
    return annotation_values


def find_child_annotation_ids(eaf_tree, parent_annotation_ids):
    """
    Find all the children of the given annotations (recursively).
    :param eaf_tree: etree.ElementTree
    :param parent_annotation_ids: iterable of strings with parent annotation ids
    :return: list of etree.Element
    """
    ref_annotations = find_elements(eaf_tree, 'REF_ANNOTATION')
    ref_annotation_parent_ids = [ref_annotation.attrib['ANNOTATION_REF']
                                 for ref_annotation in ref_annotations]
    ref_annotation_ids = [ref_annotation.attrib['ANNOTATION_ID']
                          for ref_annotation in ref_annotations]

    # We'll make a list of both the parent and child ids first
    ids_to_add = parent_annotation_ids  # IDs of the annotations whose children we haven't added yet
    parents_and_children_ids = list()
    while len(ids_to_add) > 0:
        parents_and_children_ids.extend(ids_to_add)
        ids_just_added = ids_to_add.copy()  # this is unnecessary but makes the code easier to read
        ids_to_add = [annotation_id
                      for annotation_id, parent_id
                      in zip(ref_annotation_ids, ref_annotation_parent_ids)
                      if parent_id in ids_just_added]

    children_ids = [annotation_id
                    for annotation_id in parents_and_children_ids
                    if annotation_id not in parent_annotation_ids]

    return children_ids


def get_only_child(element):
    if len(element) != 1:
        raise ValueError(f'Expected one child, got {len(element)}')
    return element[0]


def get_annotations_with_parents(tree):
    """
    Finds all (aligned and reference) annotations in the tree and returns them in a dictionary with annotation IDs as
    keys and (annotation, parent_tier) tuples as values.
    Useful when you need to delete annotations.
    """
    return {get_only_child(annotation).attrib['ANNOTATION_ID']: (annotation, parent_tier)
            for parent_tier in find_elements(tree, 'TIER')
            for annotation in parent_tier}
