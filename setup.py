from setuptools import setup, find_packages

setup(
    name="blabpy",
    version="0.3.0",
    packages=find_packages(),
    python_requires='>=3.7',
    install_requires=['pandas', 'numpy', 'pyarrow', 'pympi-ling'],
    package_data={'blabpy': ['vihi/segments/etf_templates/*.etf',
                             'vihi/segments/etf_templates/*.pfsx']}
)
