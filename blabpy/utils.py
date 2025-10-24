from datetime import timedelta, datetime
from functools import lru_cache, wraps
import hashlib
from zlib import adler32
from pathlib import Path
import contextlib
import importlib.util
import sys
import os

from pyprojroot import find_root
import pandas as pd


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
        super().__init__(message)


# copied from
@contextlib.contextmanager
def modified_environ(*remove, **update):
    """
    Temporarily updates the ``os.environ`` dictionary in-place.
    The ``os.environ`` dictionary is updated in-place so that the modification
    is sure to work in all situations.
    :param remove: Environment variables to remove.
    :param update: Dictionary of environment variables and values to add/update.
    """
    env = os.environ
    update = update or {}
    remove = remove or []

    # List of environment variables being updated or removed.
    stomped = (set(update.keys()) | set(remove)) & set(env.keys())
    # Environment variables and values to restore on exit.
    update_after = {k: env[k] for k in stomped}
    # Environment variables and values to remove on exit.
    remove_after = frozenset(k for k in update if k not in env)

    try:
        env.update(update)
        [env.pop(k, None) for k in remove]
        yield
    finally:
        env.update(update_after)
        [env.pop(k) for k in remove_after]


def df_to_list_of_tuples(df):
    return list(df.to_records(index=False))


def pandas_df_hash(df):
    return hashlib.sha256(df.to_csv().encode()).hexdigest()


def timed_lru_cache(seconds: int, maxsize: int = None):
    """
    Cache the results of a function for a specified number of seconds. Upon expiration, clear the whole cache,
    not one value at a time.

    Copied verbatim from https://www.mybluelinux.com/pyhon-lru-cache-with-time-expiration/
    :param seconds: number of seconds the cache will persist, resets after cache expires.
    :param maxsize: as in lru_cache
    :return:
    """
    def wrapper_cache(func):
        print('I will use lru_cache')
        func = lru_cache(maxsize=maxsize)(func)
        print('I\'m setting func.lifetime')
        func.lifetime = timedelta(seconds=seconds)
        print('I\'m setting func.expiration')
        func.expiration = datetime.utcnow() + func.lifetime

        @wraps(func)
        def wrapped_func(*args, **kwargs):
            print('Check func expiration')
            print(f'datetime.utcnow(): {datetime.utcnow()}, func.expiration: {func.expiration}')
            if datetime.utcnow() >= func.expiration:
                print('func.expiration lru_cache lifetime expired')
                func.cache_clear()
                func.expiration = datetime.utcnow() + func.lifetime

            return func(*args, **kwargs)

        return wrapped_func

    return wrapper_cache


def concatenate_dataframes(dataframes, keys, key_column_name):
    """
    Concatenates dataframes with the same columns. The resulting dataframe will have an additional column identifying
    the dataframe from which each row originated.
    :param dataframes: A list of dataframes to concatenate.
    :param keys: A list of keys to identify the dataframes. Must be the same length as dataframes.
    :param key_column_name: The name of the column with the dataframe identifiers.
    :return: A dataframe with the concatenated dataframes. The dataframe has as many rows as the sum of the number of
    rows in the dataframes and an additional column with the dataframe identifiers.
    """
    assert len(dataframes) == len(keys), 'Dataframes and keys must have the same length.'
    concatenated = (pd.concat(objs=dataframes,
                              keys=keys,
                              names=[key_column_name, 'sub_df_index'])
                    .reset_index(key_column_name, drop=False)
                    .reset_index(drop=True))
    concatenated[key_column_name] = concatenated[key_column_name].astype(pd.StringDtype())
    return concatenated


def chdir_relative_to_project_root(relative_path, criterion='.git'):
    """
    Given a path relative to the project root, changes the current working directory to that path.
    :param relative_path: Path of the desired working directory relative to the project root.
    :return: None
    """
    this_folder = find_root('.git') / relative_path
    os.chdir(str(this_folder))


def ensure_folder_exists_and_empty(folder_path):
    """
    Check that folder is either empty or does not yet exist. In the latter case, creates it.
    :param folder_path:
    :return:
    """
    assert not (folder_path.exists() and any(folder_path.iterdir())), \
        'The folder should be empty or not yet exist'
    folder_path.mkdir(parents=True, exist_ok=True)


def source(filepath, modulename=None):
    """
    Source a python script (almost) R-style.

    Why "almost": the variables from a script 'x.py' will be accessible as 'x.variable', not as `variable`. After
    sourcing, you can also do `from x import variable, fun` and then do `foo = fun(variable)` without prepending `x.`

    If your script name is long or not a valid Python name (e.g., contains "." or "-"), you will need to supply the
    modulename argument. Something like:

    ```py
    source('bad-name.py', modulename='good_name')
    good_name.fun()
    ```

    Args:
        filepath (str): The path to the Python script.
        modulename (str, optional): The name to register the module under.
                                    If None, the name is derived from the file name.

    Returns:
        The loaded module object.
    """
    if modulename is None:
        script_stem = os.path.splitext(os.path.basename(filepath))[0]
        if not script_stem.isidentifier():
            raise ValueError(f"Script's name \"{script_stem}\" is not a valid Python script. Either supply a valid "
                             "identifier as the modulename parameter or rename the script.")
        modulename = script_stem
    else:
        if not modulename.isidentifier():
            raise ValueError(f"Supplied module name \"{modulename}\" is not a valid Python identifier.")

    # Create a module spec from the file location
    spec = importlib.util.spec_from_file_location(modulename, filepath)
    module = importlib.util.module_from_spec(spec)

    # Execute the module in its own namespace
    spec.loader.exec_module(module)

    # Register the module in sys.modules for future imports
    sys.modules[modulename] = module
    return module

def convert_ms_to_hms(milliseconds):
    """
    Converts a duration in milliseconds to hours, minutes, and seconds.
    Returns a string in the format "H:MM:SS".
    """
    # Create a timedelta object with the milliseconds
    duration = timedelta(milliseconds=milliseconds)
    
    # Extract the components
    total_seconds = int(duration.total_seconds())
    
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    
    
    return f"{hours}:{minutes:02}:{seconds:02}"