""" Functions in this module check how much time in each audio recording has been listened to for annotation purposes.
They start with the outputs produced by recap_regions_listen_time_compute.py in the `annot_distr` repository
(https://github.com/SeedlingsBabylab/annot_distr/). More specifically, here we use the region boundaries extracted
from each cha file and put into output/cha_structures/<child>_<month>_sparse_code.cha.txt that look approximately like
this:

    subregion starts 1200
    subregion ends 2400
    ...
    surplus starts 4500
    surplus end 5000

    Position: 1, Rank: 1
    Position: 2, Rank: 5
    Position: 3, Rank: 2
    Position: 4, Rank: 4
    Position: 5, Rank: 3

Recordings for months 6 and 7 do not have the subregion information and are already assessed in the annot_distr repo,
so we do not work with them here.

For each subregion, we calculate the amount of time listened to within that subregion accounting for skips and silences.
Starting from the subregion ranked the first on talkativeness, we then assign markup and extra regions to each subregion
until the total listened time is not at least an hour.
"""


def _read_cha_structure(cha_structure_path):
    return None, None


def _remove_silences_and_skips(regions):
    return


def _remove_subregions_with_markup_and_extra(regions):
    return


def _assign_markup_and_extra_to_subregions(regions):
    return


def _aggregate_listen_time(regions, subregion_ranks):
    return


def calculate_listened_time(cha_structure_path):
    regions, subregion_ranks = _read_cha_structure(cha_structure_path)
    regions = _remove_silences_and_skips(regions)
    regions = _remove_subregions_with_markup_and_extra(regions)
    regions = _assign_markup_and_extra_to_subregions(regions, subregion_ranks)
    return _aggregate_listen_time(regions)
