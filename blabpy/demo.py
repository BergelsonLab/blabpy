from blabpy.paths import get_blab_data_root_path
import click

@click.group()
def demo():
    """CLI for setting up and working with one-time scripts."""
    pass


@demo.command()
@click.argument('topic', required=True)

def setup(topic):
    print("setup")
    print(topic)
    print("=====================================")

if __name__ == '__main__':
    demo()