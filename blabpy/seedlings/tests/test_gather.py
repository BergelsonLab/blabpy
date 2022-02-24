import pandas as pd

from blabpy.seedlings.gather import check_for_errors


def test_check_for_errors():
    columns = ['annotid', 'utterance_type', 'object_present']
    inputs = [
        pd.DataFrame(columns=columns, data=data)
        for data in (
            [('0xa', 'd', 'y'),
             ('0xa', 'r', 'n'),  # same annotation id
             ('0xb', 'y', 'n'),  # invalid utterance type code
             ('0xc', 'd', 'Y')],  # invalid object present code
            [('0xa', 'd', 'y'),
             ('0xa', 'r', 'n')],  # same annotation id
            [('0xa', 'd', 'y'),
             ('0xb', 'y', 'n')],  # invalid utterance type code
            [('0xa', 'd', 'Y'),  # invalid object present code
             ('0xb', 'r', 'n')],
            [('0xa', 'd', 'y'),  # all fine
             ('0xb', 'd', 'y'),
             ('0xc', 'd', 'y'),
             ('0xd', 'r', 'n')]
        )]
    outputs = [
        pd.DataFrame(columns=(['error_type'] + columns), data =data)
        for data in (
            [['duplicate annotation id', '0xa', 'd', 'y'],
             ['duplicate annotation id', '0xa', 'r', 'n'],
             ['invalid utterance type code', '0xb', 'y', 'n'],
             ['invalid object present code', '0xc', 'd', 'Y']],
            [['duplicate annotation id', '0xa', 'd', 'y'],
             ['duplicate annotation id', '0xa', 'r', 'n']],
            [['invalid utterance type code', '0xb', 'y', 'n']],
            [['invalid object present code', '0xa', 'd', 'Y']]
        )]

    for input_, output in zip(inputs[:-1], outputs):
        assert check_for_errors(input_).equals(output)

    assert check_for_errors(inputs[-1]) is None
