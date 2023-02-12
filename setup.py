from setuptools import setup, find_packages

setup(
    name="blabpy",
    version="0.16.1",
    packages=find_packages(),
    python_requires='>=3.7',
    install_requires=['pandas', 'numpy', 'pyarrow', 'pympi-ling', 'pydub', 'StrEnum', 'tqdm', 'click'],
    include_package_data=True,
    package_data={'blabpy': ['vihi/intervals/etf_templates/*.etf',
                             'vihi/intervals/etf_templates/*.pfsx',
                             'seedlings/regions/data/regions_special-cases/*/*.csv']},
    entry_points={
        'console_scripts':
            ['vihi_make_random_regions = blabpy.vihi.intervals.cli:cli_batch_create_files_with_random_regions',
             'vihi = blabpy.vihi.cli:vihi',
             'seedlings = blabpy.seedlings.cli:seedlings',
             ]
    }
)
