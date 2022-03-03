from importlib.resources import path

import blabpy.vihi.segments.etf_templates as etf_templates


def _get_etf_template(filename):
    """
    I don't know why but the path function returns a context manager, not a path.
    :param filename: a template filename
    :return:
    """
    with path(etf_templates, filename) as p:
        return p


basic_00_07 = _get_etf_template('ACLEW-basic-template_00-07mo.etf')
basic_08_18 = _get_etf_template('ACLEW-basic-template_08-18mo.etf')
basic_19_36 = _get_etf_template('ACLEW-basic-template_19-36mo.etf')
basic_00_07_pfsx = _get_etf_template('ACLEW-basic-template_00-07mo.pfsx')
basic_08_18_pfsx = _get_etf_template('ACLEW-basic-template_08-18mo.pfsx')
basic_19_36_pfsx = _get_etf_template('ACLEW-basic-template_19-36mo.pfsx')
