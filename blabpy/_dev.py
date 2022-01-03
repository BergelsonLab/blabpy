from pkgutil import walk_packages
from importlib import import_module

from IPython import get_ipython


def autoreload_all_modules_in_package(package):
    """
    Registers all modules in packages to be autoreloaded by the autoreload IPython extension. The extension should
    already be loaded before calling this function.
    :param package: module object whose submodule and deeper nested modules should be autoreloaded.
    :return:
    """
    package_name = package.__name__
    run_magic = get_ipython().magic
    modules = [module_info.name for module_info
               in walk_packages(path=package.__path__, prefix=f'{package_name}.')]
    modules.append(package_name)
    for module in modules:
        run_magic(f"aimport {module}")


def turn_on_autoreloading():
    run_magic = get_ipython().magic
    run_magic("load_ext autoreload")
    run_magic("autoreload 1")


def autoreload_blabpy():
    blabpy = import_module('blabpy')
    turn_on_autoreloading()
    autoreload_all_modules_in_package(blabpy)
