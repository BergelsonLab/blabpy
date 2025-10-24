import click
import re
from blabpy.paths import get_blab_share_path
from blabpy.pipeline import find_eaf_paths, extract_aclew_data
from blabpy.eaf.eaf_plus import EafPlus
import os
from pyprojroot import find_root
from pathlib import Path
import pandas as pd
from utils import convert_ms_to_hms

# Paths
BLAB_SHARE_PATH = get_blab_share_path()
OVS_PATH = BLAB_SHARE_PATH / 'OvSpeech' / 'SubjectFiles' / "Seedlings" / 'overheard_speech'
VIHI_PATH = BLAB_SHARE_PATH / 'VIHI' / 'SubjectFiles' / 'LENA' 
SPEAKER_PATTERN = re.compile(r'CHI|[MFU][ACI][\dE]|EE1')
TIER_PATTERN = re.compile(r'^\w+@\w\w\w$')
cv_dict = {
    'vcm': ['L', 'Y', 'N', 'C', 'U'],
    'lex': ['W', '0'],
    'mwu': ['M', '1'],
    'xds': ['A', 'C', 'B', 'P', 'O', 'U'],
    'cds': ['T', 'K', 'M', 'X']
}

parent_dict = {
    'vcm': None,
    'lex': 'vcm',
    'mwu': 'lex',
    'xds': None,
    'cds': 'xds'
}

value_dict = {
    'lex': ('vcm', 'C'),
    'mwu': ('lex', 'W'),
    'cds': ('xds', 'C')
}

chi_tiers = ['vcm', 'lex', 'mwu']
other_speaker_tiers = ['xds', 'cds']
other_tiers = ['on_off', 'code', 'code_num', 'context']

@click.group()
def demo():
    """CLI for setting up and working with one-time scripts."""
    pass


@demo.command()
@click.argument('folder', required=True)

def setup(folder):
    print("setup")
    print(folder)
    print("=====================================")

# If you add a function with no add command thingy, it will be accessible anywhere
# def helper(param):
#     print("This is a helper function.", param)



if __name__ == '__main__':
    demo()