"""
Subpackage with classes and functions for working with ELAN .eaf files. There are several ways of working with .eaf
using this module:

- EafPlus class which is just pympi.Eaf plus a few extra methods. Has a lot implemented but makes it hard to navigate
  the data and makes editing result in unnecessarily large diffs.
- EafTree class which is a wrapper around an ElementTree object. Good for navigating data and editing but lacks any
  functionality to add new elements.
- An assortment of functions in eaf_utils that work with .eaf files as XML trees that they are. They allow adding new
  elements to eaf files. These functions should eventually be moved to EafTree.

There is also an etree_utils module that contains functions for working with xml.etree.ElementTree.Element objects that
aren't specific to .eaf files.

Glossary:
- *Aligned* vs. *referenced* annotations: Aligned annotations are the ones that have their own timestamps, e.g.,
  participant utterances. Referenced don't have their own timestamps, e.g., xds, lex, vcm, etc.
- *Daughter* vs. *parent* annotations: Tiers are organized in a hierachy
"""
from .eaf_tree import EafTree
from .eaf_plus import EafPlus

# Property values
SYMBOLIC_ASSOCIATION = "Symbolic_Association"

# URLs of external files with controlled vocabularies
ACLEW_ECV_URL = ('https://raw.githubusercontent.com/marisacasillas/DARCLE-AnnSchDev/master/ACLEW/'
                 'External-closed-vocabularies/ACLEW-basic-vocabularies.ecv')
BLAB_ECV_URL = "https://raw.githubusercontent.com/BergelsonLab/public-files/main/ACLEW-blab-vocabularies.ecv"
