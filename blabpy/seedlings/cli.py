import click

from .pipeline import make_updated_seedlings_nouns as _make_updated_seedlings_nouns


@click.group()
def seedlings():
    """Seedlings scripts."""
    pass


@seedlings.group()
def nouns():
    """Seedlings-nouns scripts."""
    pass


@nouns.command(help=_make_updated_seedlings_nouns.__doc__)
def update():
    _make_updated_seedlings_nouns()
