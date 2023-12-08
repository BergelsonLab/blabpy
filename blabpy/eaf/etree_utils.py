"""
Functions to facilitate working with xml.etree.ElementTree.Element objects. There is some repetition and not much
consistency. Consider putting all function in an ElementTreePlus class.
"""

from io import StringIO
from pathlib import Path
from xml.etree import ElementTree as element_tree

import requests


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


def get_all(tree, tag, id_attrib):
    return {element.get(id_attrib): element
            for element in tree.findall(f'.//{tag}')}


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


def get_only_child(element):
    if len(element) != 1:
        raise ValueError(f'Expected one child, got {len(element)}')
    return element[0]
