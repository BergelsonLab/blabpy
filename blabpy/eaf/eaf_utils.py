"""
Functional approach to manipulating EAF files. This module should eventually disappear with its functionality absorbed
by the EafTree class and maybe some other places. This should happen organically as EafTree learns to add new elements
to the tree.

In this module, `tree` refers to an ElementTree object, not an EafTree object.

TODO:
[ ] Refactor add_* functions to use a single add_element function.
[ ] There should be no separate add_CV, and add_CV_and_LingType functions. Instead, add_CV should do all the work.
[ ] Some functions were created very much ad hoc and probably won't be necessary because it will be straightforward to
    do the same thing with EafTree.
[ ] Currently, many attributes are either explicitly hard-coded, e.g., as 'LINGUISTIC_TYPE_REF', or implicitly
hard-coded in function argument names `attributes=dict(ATTRIBUTE=value)`. Get rid of both types.
"""

from xml.etree.ElementTree import Element

from .etree_utils import tree_to_path, ElementAlreadyPresentError, find_element, same_elements, insert_after_last, \
    find_single_element, find_elements, get_only_child, uri_to_tree
from blabpy.eaf.eaf_tree import LinguisticType, ControlledVocabulary, Tier


class EafInconsistencyError(Exception):
    pass


def tree_to_eaf(tree, path):
    tree_to_path(tree, path)


class CvAlreadyPresentError(ElementAlreadyPresentError):
    pass


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


def eaf_to_tree(eaf_uri: str):
    return uri_to_tree(eaf_uri)
