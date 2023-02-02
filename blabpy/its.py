"""
Functions to facilitate working with LENA's .its files.
"""
import datetime
from pathlib import Path
from xml.etree.ElementTree import ElementTree, XMLParser

import pandas as pd
import pytz

from blabpy import ANONYMIZATION_DATE


class ItsNoTimeZoneInfo(Exception):
    pass


class Its(object):
    """
    Container for the parsed xml from a single .its file.
    """
    def __init__(self, xml_parsed: ElementTree, forced_timezone=None):
        """
        :param xml_parsed: Parsed xml from an its file.
        :param forced_timezone: if forced_timezone is not None, the timezone in the file will be ignored and this
        one will be used instead. Useful for files with incorrect timezone information or without any information at
        all. Must be a string recognized by `pytz.timezone`, such as 'US/Eastern'. The DST mustn't be baked into the
        timezone, i.e., 'EST'/'EDT' mustn't be used.
        """
        self.xml: ElementTree = xml_parsed
        if forced_timezone is not None:
            forced_timezone = self._parse_forced_timezone(forced_timezone)
        self.forced_timezone = forced_timezone

    @staticmethod
    def _parse_forced_timezone(forced_timezone_str):
        # convert forced_timezone to a pytz timezone object
        try:
            forced_timezone = pytz.timezone(forced_timezone_str)
        except pytz.UnknownTimeZoneError:
            raise ValueError(f'Unknown timezone: {forced_timezone_str}. Timezone must be a string recognized by'
                             ' `pytz.timezone`, such as "US/Eastern".')

        # Check that the timezone doesn't have DST baked into it
        if not isinstance(forced_timezone, pytz.tzinfo.DstTzInfo):
            raise ValueError('Timezone object mustn\'t include DST. I.e., use "US/Eastern" instead of "EST"/"EDT".')

        return forced_timezone

    @classmethod
    def from_string(cls, its_contents: str, forced_timezone=None):
        """
        Parses a string with .its file contents.
        :param its_contents: single string containing contents of an its file.
        :param forced_timezone: see __init__'s docstring
        :return: Its object with its_contents parsed
        """
        parser = XMLParser()
        parser.feed(its_contents)
        xml_parsed = parser.close()

        return Its(xml_parsed=xml_parsed, forced_timezone=forced_timezone)

    @classmethod
    def from_path(cls, its_path, forced_timezone=None):
        """
        Reads and parses an its file.
        :param its_path: path to an its file as a string or as a pathlib.Path object
        :param forced_timezone: see __init__'s docstring
        :return: Its object
        """
        its_path = Path(its_path)
        return cls.from_string(its_contents=its_path.read_text(), forced_timezone=forced_timezone)

    def get_timezone_info(self):
        if self.forced_timezone is not None:
            return self.forced_timezone

        timezone_xml_path = './ProcessingUnit/UPL_Header/TransferredUPL/RecordingInformation/Audio/TimeZone'
        timezone_element = self.xml.find(timezone_xml_path)
        if timezone_element is None:
            raise ItsNoTimeZoneInfo('I wasn\'t able to locate timezone info in this .its file')

        timezone_info = dict(timezone_element.items())
        return dict(seconds_offset=timezone_info['StandardSecondsOffset'], uses_dst=timezone_info['UsesDST'])

    def _convert_utc_to_local(self, clock_time: pd.Series):
        """
        Convert utc timestamps to local timestamps.
        :param clock_time: pd.Series of strings from the .its object
        :return: pd.Series of timezone-naive datetime type.
        """
        # Parse the timestamps
        datetimes = pd.to_datetime(clock_time, format='%Y-%m-%dT%H:%M:%SZ', utc=True)

        # Convert to local time
        timezone_info = self.get_timezone_info()
        if type(timezone_info) is dict:
            datetimes += pd.Timedelta(seconds=int(timezone_info['seconds_offset']))
            # Add an hour if there is daylight savings time used
            if timezone_info['uses_dst']:
                datetimes += pd.Timedelta(hours=1)
        elif isinstance(timezone_info, pytz.tzinfo.DstTzInfo):
            datetimes = datetimes.dt.tz_convert(timezone_info)
        else:
            raise NotImplementedError(f'Unexpected timezone: {timezone_info}')

        # Remove timezone info
        datetimes = datetimes.dt.tz_localize(None)

        return datetimes

    @staticmethod
    def _convert_iso_duration_to_ms(iso_time: pd.Series):
        """
        Converts duration from iso format to the number of milliseconds.
        :param iso_time: pd.Series of ISO duration values
        :return: pd.Series of ints
        """
        return (pd.to_timedelta(iso_time)  # parse ISO-formatted times
                .dt.total_seconds()  # convert to seconds as real numbers
                .multiply(1000)  # convert from s to ms
                .astype(int))  # finally, convert to integers

    def gather_recordings(self, anonymize=False):
        """
        Finds all sub-recordings in the its file.

        This works very similarly to rlena::gather_recordings.

        :return: a pd.DataFrame with the following columns:
        - recording_start, recording_end - datetime columns,
        - recording_start_wav - integer column of when recording started in ms within the wav file.
        """
        # Get raw recordings info
        recordings_xml_path = './ProcessingUnit/Recording'
        recordings_elements = self.xml.findall(path=recordings_xml_path)
        # Each element's items are (key, value) tuples which we'll convert to a dict
        recordings_list = [dict(element.items()) for element in recordings_elements]
        recordings = pd.DataFrame.from_records(recordings_list)
        assert set(recordings.columns) == {'num', 'startClockTime', 'endClockTime', 'startTime', 'endTime'}
        # num - order number
        # *ClockTime - UTC time when recordings started/ended
        # *Time - ISO-formatted duration of time from the start of the wav to the start/end of the recording

        # TODO: consider keeping df.endTime so that we can calculate the duration of the recording from these times and
        #  not from datetime columns whihc lack the millisecond part.
        #  Also: it'd be a good idea to drop "recording_" prefix from the column names.
        # Let's convert *ClockTime to local time and startTime to milliseconds
        recordings = (
            recordings
            .assign(
                recording_start=lambda df: self._convert_utc_to_local(df.startClockTime),
                recording_end=lambda df: self._convert_utc_to_local(df.endClockTime),
                recording_start_wav=lambda df: self._convert_iso_duration_to_ms(df.startTime),)
                # recording_end_wav=lambda df: self.convert_iso_duration_to_ms(df.endTime))
            [['recording_start', 'recording_end', 'recording_start_wav']]  # , 'recording_end_wav']]
            .convert_dtypes())

        if anonymize is True:
            # Aid anonymization by shifting the dates to 1920-01-01
            shift = recordings.recording_start.iloc[0].date() - ANONYMIZATION_DATE
            recordings[['recording_start', 'recording_end']] = recordings[['recording_start', 'recording_end']] - shift

        return recordings
