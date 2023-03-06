from xml.etree import ElementTree as element_tree

def _canonicalize_xml(path):
    element_tree.canonicalize(from_file=path, to_file=path)

