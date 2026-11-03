import click
from .paths import get_gold_standard_path, get_annotator_training_path
from .reliability import gold_standard_report
from ..utils import save_file_with_timestamp

@click.group()
def sparked():
    """SPARKED scripts."""
    pass

@sparked.command()
@click.option('--sparked-id', required=True, prompt='Sparked ID of OPF file', help='Sparked ID, e.g. "01_13".')
@click.option('--annotator', required=True, prompt='Your initials (lowercase)',
              help='Annotator initials, e.g. "jd" for John Doe.')
def gold_standard(sparked_id, annotator):
    gs_file = get_gold_standard_path(sparked_id)
    annotator_file = get_annotator_training_path(sparked_id, annotator)

    click.echo(f"Scoring gold standard training for file {sparked_id} by annotator {annotator}...")
    report = gold_standard_report(gs_file, annotator_file)
    report_filepath = annotator_file.with_suffix(".md")
    report_filepath_with_timestamp = save_file_with_timestamp(report_filepath, "\n\n".join(report))

    click.echo(f"Finish scoring. Check your results in {report_filepath_with_timestamp}.")

if __name__ == "__main__":
    sparked()