import click
from .reliability import get_gold_standard_path, get_annotator_training_path, gold_standard_report

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
    report_filepath = annotator_file.with_suffix(".txt")
    if report_filepath.exists():
        response = input(f"The file '{report_filepath}' already exists. Overwrite? (y/n): ").strip().lower()
        if not response in ['y', 'yes']:
            print("Operation cancelled. File not overwritten.")
            exit()
        else:
            print("Overwriting file...")

    with open(report_filepath, "w") as f:
        f.write("\n".join(report))
    click.echo(f"Finish scoring. Check your results in {report_filepath}.")

if __name__ == "__main__":
    sparked()