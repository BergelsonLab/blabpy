"""
Module with the EafTree classes that represent EafFile contents as an xml.etree.ElementTree.ElementTree object with
convenient access to all the data. As much as possible, all the data is stored in the ElementTree object itself, so that
that object always represent the current state of data and can be written to disk at any time. Avoiding moving data from
xml representation to internal representation and then recreating xml representation when writing to disk as is done in
pympi.Eaf (and EafPlus) makes it easier to avoid inconsistencies and makes diffs between the input and the output .eaf
files to the minimum.

TODO:
[ ] Add superclasses/mixins:
    [ ] Add a superclass for Annotation and Tier - smth like EafElementWithRelations.
    [ ] Add a superclass for Annotation and ControlledVocabularyEntry - smth like EafElementWithInnerElements
[ ] Do not duplicate functionality from etree_utils, call those functions instead.
"""

import functools
from io import StringIO
from pathlib import Path
from xml.etree import ElementTree as element_tree

import requests

from blabpy.eaf.etree_utils import element_to_string, _make_find_xpath, no_text_in_element


class EafElement(object):
    """
    Base class for all EAF elements.
    TODO:
    - move __init__() and validate() here,
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
        if not no_text_in_element(self.element):
            text = self.element.text
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
    def value_element(self):
        return self.inner_element[0]

    @property
    def value(self):
        return self.value_element.text

    @value.setter
    def value(self, value):
        self.value_element.text = value

    def clear_value(self):
        self.value_element.text = ''

    def value_not_set(self):
        return no_text_in_element(self.value_element)

    @value.setter
    def value(self, value):
        if self.tier.uses_cv:
            cv = self.tier.cv
            cve_ref = cv.get_id_of_value(value)
            self.inner_element.attrib[self.CVE_REF] = cve_ref
        self.value_element.text = value

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

    @property
    def children(self):
        # Should be a list, possibly an empty one
        if self._children is None:
            raise ValueError(f'The children tiers have not been assigned, tell lab technician.')
        return self._children

    @property
    def children_assigned(self):
        return self._children is not None

    def mark_as_childless(self):
        if self._children is not None:
            if len(self._children) > 0:
                raise ValueError(f'Can\'t mark annotation {self.id} as childless because it has children.')
            else:
                raise ValueError(f'Annotation {self.id} has already been marked as childless.')
        self._children = []

    @property
    def onset(self):
        if self.annotation_type == self.ALIGNABLE_ANNOTATION:
            return self.eaf_tree.time_slots[self.time_slot_ref1].time_value
        else:
            return self.parent.onset

    @property
    def offset(self):
        if self.annotation_type == self.ALIGNABLE_ANNOTATION:
            return self.eaf_tree.time_slots[self.time_slot_ref2].time_value
        else:
            return self.parent.offset

    def append_child(self, child):
        self._children = self._children or list()
        self._children.append(child)

    def gather_descendants(self):
        """
        Gather all descendants of this annotation as a list of Annotation objects.
        :return: a list of annotations
        """
        descendants = list()
        for child in self.children:
            descendants.extend([child] + child.gather_descendants())
        return descendants

    @conditional_property(REF_ANNOTATION)
    def cve_ref(self):
        return self.inner_element.attrib[self.CVE_REF]

    @cve_ref.setter
    def cve_ref(self, cve_ref):
        self.inner_element.attrib[self.CVE_REF] = cve_ref

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
        inner_element = self.inner_element
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

        value_element = self.value_element
        if value_element.tag != self.ANNOTATION_VALUE:
            raise ValueError(f'Inner annotation element must have {self.ANNOTATION_VALUE} as its child element.')
        if value_element.attrib:
            raise ValueError(f'Inner annotation element must not have attributes.')

        # For tiers with controlled vocabularies, check that CVE_REF and annotation value are both present and
        # consistent or both absent.
        if self.eaf_tree.validate_cv_entries and self.annotation_type == self.REF_ANNOTATION and self.tier.uses_cv:
            not_empty = not self.value_not_set()
            cve_ref = self.inner_element.attrib.get(self.CVE_REF)
            has_cve_ref = cve_ref is not None
            if has_cve_ref != not_empty:
                raise ValueError(f'For tiers with controlled vocabularies, {self.CVE_REF} attribute must be present iff '
                                 f'there is a non-empty value.')
            if not_empty and (self.value != self.tier.cv.entries[cve_ref].value):
                raise ValueError(f'Value {self.value} does not match the {cve_ref} item in the controlled vocabulary.')


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
    def children_assigned(self):
        return self._children is not None

    def mark_as_childless(self):
        if self._children is not None:
            if len(self._children) > 0:
                raise ValueError(f'Can\'t mark tier {self.id} as childless because it has children.')
            else:
                raise ValueError(f'Tier {self.id} has already been marked as childless.')
        self._children = []

    def append_child(self, child):
        self._children = self._children or list()
        self._children.append(child)

    def gather_descendants(self):
        """
        Gather all descendants of this annotation as a list of Tier objects.
        :return: a list of annotations
        """
        descendants = list()
        for child in self.children:
            descendants.extend([child] + child.gather_descendants())
        return descendants

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

    def get_id_of_value(self, value):
        (cve_id,) = {cve_id for cve_id, cv_entry in self.entries.items() if cv_entry.value == value}
        return cve_id

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


class TimeSlot(EafElement):
    """
    <TIME_ORDER>
        <TIME_SLOT TIME_SLOT_ID="ts1" TIME_VALUE="3060000"></TIME_SLOT>
    """
    TAG = 'TIME_SLOT'
    ID = 'TIME_SLOT_ID'
    TIME_VALUE = 'TIME_VALUE'

    def __init__(self, time_slot_element, eaf_tree):
        self._element = time_slot_element

    @property
    def time_value(self):
        return self.element.attrib[self.TIME_VALUE]


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
        self.time_slots = self._parse_elements(TimeSlot, eaf_tree=self)

        self.assign_children()

    def _parse_elements(self, element_class, *args, **kwargs):
        elements = [element_class(element, *args, **kwargs) for element in self.find_elements(element_class.TAG)]
        return {element.id: element for element in elements}

    def assign_children(self):
        """
        Assigns children to tiers and annotations. For elements that haven't been assigned a single child at the end,
        changes `.
        :return:
        """
        for tier in self.tiers.values():
            if tier.parent_ref is not None:
                tier.parent.append_child(tier)

        for tier in self.tiers.values():
            if tier.children_assigned is False:
                tier.mark_as_childless()

        for annotation in self.annotations.values():
            if annotation.annotation_type == Annotation.REF_ANNOTATION:
                annotation.parent.append_child(annotation)

        for annotation in self.annotations.values():
            if annotation.children_assigned is False:
                annotation.mark_as_childless()
