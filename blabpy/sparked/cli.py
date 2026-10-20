import click
from .reliability import gold_standard_report
from .paths import parse_sparked_id

@click.group()
def sparked():
    """SPARKED scripts."""
    pass

@sparked.command()
@click.option('--annotator', required=True, prompt='Your initials',
              help='Annotator initials, e.g. "jd" for John Doe.')
@click.option('--sparked-id', required=True, prompt='Sparked ID of OPF file', help='Sparked ID, e.g. "01_13".')
def gold_standard(sparked_id, annotator):
    talker_id, age_in_months = parse_sparked_id(sparked_id)
    gold_standard_report(talker_id, age_in_months, annotator)