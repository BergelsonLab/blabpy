from zlib import adler32
from pathlib import Path


def text_file_checksum(path: Path):
    """
    Returns the adler32 hash of the contents of a text file. Adler32 was used because it was faster than md5, there are
    certainly faster alternative I don't know about.
    :param path: path to the text file
    :return:
    """
    encoding = 'utf-8'
    # Decoding/encoding is done to stay invariant to different line endings.
    return adler32(path.read_text(encoding=encoding).encode(encoding=encoding))


class OutputExistsError(Exception):
    """
    Raised when a function crates output files and some of them already exist.
    """
    def __init__(self, paths):
        """
        Paths
        :param paths: the paths to the output files that already exist.
        """
        self.paths = paths
        message = 'Some of the output files already exist'
        if paths:
            message += ':\n\n' + '\n'.join((str(path.absolute()) for path in paths))
        super().__init__()
