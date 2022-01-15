import pytest


CHA_STRUCTURES_PATH_OPTION = '--cha-structures'
TOTAL_LISTEN_TIME_SUMMARY_OPTION = '--total-listen-time-summary'


def pytest_addoption(parser):
    parser.addoption(CHA_STRUCTURES_PATH_OPTION, action="store", default=None,
                     help="path to the 'cha_structures' folder")
    parser.addoption(TOTAL_LISTEN_TIME_SUMMARY_OPTION, action="store", default=None,
                     help="path to the 'Total_Listen_Time_Summary.csv' file")


@pytest.fixture(scope='module')
def cha_structures_folder(request):
    return request.config.getoption(CHA_STRUCTURES_PATH_OPTION)


@pytest.fixture(scope='module')
def total_listen_time_summary_csv(request):
    return request.config.getoption(TOTAL_LISTEN_TIME_SUMMARY_OPTION)
