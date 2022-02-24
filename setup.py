from setuptools import setup, find_packages

setup(
    name="blabpy",
    version="0.2.0",
    packages=find_packages(),
    python_requires='>=3.7',
    install_requires=['pandas', 'numpy', 'pyarrow']
)
