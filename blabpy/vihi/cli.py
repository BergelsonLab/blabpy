import click

from .pipeline import distribute_all_rttm as _distribute_all_rttm
from .annotating import checkout_recording_for_annotation


@click.group()
def vihi():
    """VIHI scripts."""
    pass


@vihi.command()
def distribute_all_rttm():
    """
    Moves VTC results from the `all.rttm` file output by VTC to the corresponding `all.rttm` files for each recording.
    """
    _distribute_all_rttm()


@vihi.group()
def annotation():
    """Annotation-related scripts."""
    pass


@annotation.command()
@click.option('--name', required=True, prompt='Your name (First Last)',
              help='Annotator name, e.g. "First Last".')
@click.option('--recording-id', required=True, prompt='Recording ID', help='Recording ID, e.g. "XX_MMM_NNN".')
@click.option('--email', required=True, prompt='Your email')
def start(name, recording_id, email):
    """Start annotation."""
    # Confirm that we are starting from scratch.
    click.clear()
    click.echo(f'Hello, {name}!')

    # Checkout the recording folder from BLab share.
    click.echo(f'Making a copy of {recording_id} for {name} to annotate (this may take a few minutes) ...')
    annotation_folder = checkout_recording_for_annotation(full_recording_id=recording_id, annotator_name=name,
                                                          annotator_email=email)
    click.echo(f'Annotation files have been copied into the following folder:'
               f'\n{annotation_folder}')
