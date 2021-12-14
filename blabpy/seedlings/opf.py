import os
from zipfile import ZipFile, ZIP_DEFLATED
import tempfile
from pathlib import Path


# This is not exactly correct. datavyu uses milliseconds and this uses microseconds adding three extra zeros
DATETIME_FORMAT = '%H:%M:%S:%f'


class OPFFile(object):
    SKIP_PREFIXES = ('.DS_Store', '__MACOSX/')

    def __init__(self, path):
        self.path = path
        self.loaded = False
        self.db = None
        self.other_components = None
        self.filenames_in_archive = None
        self.load()

    def load(self):
        if self.path.is_dir():
            raise NotImplementedError('Reading unarchived version from a folder is not yet implemented')

        with ZipFile(self.path, 'r') as opf_zipped:
            assert 'db' in opf_zipped.namelist(), f'The file at {self.path} does not contain "db". Not an OPF file?'

            # Annotations
            with opf_zipped.open('db', 'r') as db_zipped:
                # ZipFile.open reads files in the binary mode
                db = db_zipped.read().decode('utf-8')

            filenames_in_archive = opf_zipped.namelist()

            # Skip macos-specific hidden files
            filenames_in_archive = [fn for fn in filenames_in_archive
                                    if not any(fn.startswith(prefix) for prefix in self.SKIP_PREFIXES)]

            other_components = {
                name: opf_zipped.open(name, 'r').read()
                for name in filenames_in_archive
                if name != 'db'}

            self.db = db
            self.filenames_in_archive = filenames_in_archive
            self.other_components = other_components
            self.loaded = True

    def read_in_editor(self):
        zf = ZipFile(self.path)
        tempdir = tempfile.mkdtemp()
        zf.extractall(tempdir)
        db_path = os.path.join(tempdir, 'db')
        os.system(f'open {db_path}')

    def write(self, path: Path = None, overwrite_original=False, unzipped=False):
        if not path and not overwrite_original:
            raise ValueError('You haven\'t specified the path to write the files. If you want to overwrite the original'
                             ' file, set overwrite_original to True')

        if path and overwrite_original:
            raise ValueError('You\'ve specified the path and set overwrite_original to True - you can only do one of '
                             'those')

        path = path or self.path

        if unzipped:
            if path.exists() and not path.is_dir():
                raise ValueError('Unzipped is set to True but supplied path is not a directory.')
            else:
                path.mkdir(parents=True, exist_ok=True)
                self._write_to_dir(folder_path=path)
        else:
            if not path.name.endswith('.opf'):
                raise ValueError('Supplied path does not end with .opf as expected')
            else:
                self._write_to_opf(path)

    def _write_to_dir(self, folder_path):
        for filename in self.filenames_in_archive:
            filepath = folder_path / filename
            if filename == 'db':
                with filepath.open('w') as f:
                    f.write(''.join(self.db))
            else:
                with filepath.open('wb') as f:
                    f.write(self.other_components[filename])

    def _write_to_opf(self, path):
        with ZipFile(path, mode='w', compression=ZIP_DEFLATED) as opf_zipped:
            for filename in self.filenames_in_archive:
                if filename == 'db':
                    opf_zipped.writestr('db', self.db)
                else:
                    opf_zipped.writestr(filename, self.other_components[filename])
