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
    try:
        gs_file = get_gold_standard_path(sparked_id)
        annotator_file = get_annotator_training_path(sparked_id, annotator)

    except Exception as e:
        click.echo(click.style(f"Error with the file name you have inputed:", bg="red"))
        click.echo(click.style(sparked_id, fg="yellow", italic=True))
        click.echo(click.style(annotator, fg="yellow", italic=True))
        click.echo(click.style(e, fg="red"))
        return

    click.echo(click.style(f"Scoring gold standard training for file {sparked_id} by annotator {annotator}...", fg="cyan", bold=True))
    report, score = gold_standard_report(gs_file, annotator_file)

    report_folder = annotator_file.parent / "gold_standard_reports"
    report_folder.mkdir(exist_ok=True)
    report_folder_by_id = report_folder / sparked_id
    report_folder_by_id.mkdir(exist_ok=True)
    report_filepath = report_folder_by_id / f"{annotator_file.stem}.md"
    report_filepath_with_timestamp = save_file_with_timestamp(report_filepath, "\n\n".join(report))

    if score != 4:
        click.echo(click.style(f"⚠️ You have passed {score}/4 columns. Please review your results in {report_filepath_with_timestamp}, fix your mistakes, and attempt the training again.", fg="yellow", italic=True))
    else:
        click.echo(click.style(f"✅ You have PASSED all 4 columns. You can view your results in {report_filepath_with_timestamp}.", fg="green", italic=True))

if __name__ == "__main__":
    sparked()