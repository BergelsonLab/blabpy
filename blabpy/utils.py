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
