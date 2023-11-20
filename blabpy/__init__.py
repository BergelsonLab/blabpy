# Date to move to for dates that need to be anonymized
import datetime
from importlib import metadata

ANONYMIZATION_DATE = datetime.date(1920, 1, 1)


def version():
    return metadata.version('blabpy')
