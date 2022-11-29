import click

from .pipeline import distribute_all_rttm as _distribute_all_rttm


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
