"""
Module with classes and functions for working with ELAN .eaf files. There are two principal ways of working with .eaf
using this module:
- EafPlus class which is just pympi.Eaf plus a few extra methods.
- An assortment of functions that work with .eaf files as XML trees that they are.

Notes:
- It would be cleaner to wrap the XML-tree-based functions in classes at some point.
- Many functions are XML-general and could be moved to a separate module or aggregated in a separate class.


TODO:
[ ] Refactor add_* functions to use a single add_element function.
[ ] Currently, many attributes are implicitly hard-coded via `attributes=dict(ATTRIBUTE=value)`. Switch to using
    `attributes={ATTRIBUTE: value}` after defining corresponding constants (ATTRIBUTE = 'ATTRIBUTE' in this case).
"""

from io import StringIO
from pathlib import Path
from xml.etree import ElementTree as element_tree
from xml.etree.ElementTree import Element

import pandas as pd
import requests
from pympi import Eaf


# Element names
EXTERNAL_REF = 'EXTERNAL_REF'
LINGUISTIC_TYPE = 'LINGUISTIC_TYPE'
CONTROLLED_VOCABULARY = 'CONTROLLED_VOCABULARY'
TIER = 'TIER'

# Property names

## Linguistic type properties
CONTROLLED_VOCABULARY_REF = 'CONTROLLED_VOCABULARY_REF'
CONSTRAINTS = 'CONSTRAINTS'
## External reference properties
EXT_REF = 'EXT_REF'
EXT_REF_ID = 'EXT_REF_ID'
## Tier properties
PARENT_REF = 'PARENT_REF'

# Property values
SYMBOLIC_ASSOCIATION = "Symbolic_Association"

# URLs of external files with controlled vocabularies
ACLEW_ECV_URL = ('https://raw.githubusercontent.com/marisacasillas/DARCLE-AnnSchDev/master/ACLEW/'
                 'External-closed-vocabularies/ACLEW-basic-vocabularies.ecv')
BLAB_ECV_URL = "https://raw.githubusercontent.com/BergelsonLab/public-files/main/ACLEW-blab-vocabularies.ecv"


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
        del attributes[CONSTRAINTS]
    if cv_id is None:
        del attributes[CONTROLLED_VOCABULARY_REF]
    element = Element(LINGUISTIC_TYPE, attrib=attributes)

    # Avoid adding the same linguistic type twice
    ling_type_in_eaf = find_element(eaf_tree, LINGUISTIC_TYPE, LINGUISTIC_TYPE_ID=ling_type_id)
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
    cv_in_eaf = find_element(eaf_tree, CONTROLLED_VOCABULARY, CV_ID=cv_id)

    if cv_in_eaf is not None:
        if not exist_identical_ok:
            raise CvAlreadyPresentError(f'Trying to add a "{cv_id}" CV but it is already present.')
        ext_ref_in_eaf = cv_in_eaf.get(EXT_REF)
        if ext_ref_in_eaf == ext_ref:
            return
        else:
            msg = f'CV "{cv_id}" already exists but uses different external reference - "{ext_ref_in_eaf}"'
            raise ValueError(msg)

    add_linguistic_type(eaf_tree=eaf_tree, ling_type_id=ling_type_id, time_alignable=time_alignable,
                        constraints=constraints, cv_id=cv_id, exist_identical_ok=False)

    cv_attributes = dict(CV_ID=cv_id, EXT_REF=ext_ref)
    cv_element = Element(CONTROLLED_VOCABULARY, attrib=cv_attributes)
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
        attributes[PARENT_REF] = parent_ref
    element = Element(TIER, attrib=attributes)
    
    # Avoid adding the same tier twice
    tier_in_eaf = find_element(eaf_tree, TIER, TIER_ID=tier_id)
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
