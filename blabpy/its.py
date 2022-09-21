"""
Functions to facilitate working with LENA's .its files.
"""
from pathlib import Path
from xml.etree.ElementTree import ElementTree, XMLParser

import pandas as pd


class ItsNoTimeZoneInfo(Exception):
    pass


class Its(object):
    """
    Container for the parsed xml from a single .its file.
    """
    def __init__(self, xml_parsed: ElementTree):
        self.xml: ElementTree = xml_parsed

    @classmethod
    def from_string(cls, its_contents: str):
        """
        Parses a string with .its file contents.
        :param its_contents: single string containing contents of an its file.
        :return: Its object with its_contents parsed
        """
        parser = XMLParser()
        parser.feed(its_contents)
        xml_parsed = parser.close()

        return Its(xml_parsed=xml_parsed)

    @classmethod
    def from_path(cls, its_path):
        """
        Reads and parses an its file.
        :param its_path: path to an its file as a string or as a pathlib.Path object
        :return: Its object
        """
        its_path = Path(its_path)
        return cls.from_string(its_contents=its_path.read_text())

    def get_timezone_info(self):
        timezone_xml_path = './ProcessingUnit/UPL_Header/TransferredUPL/RecordingInformation/Audio/TimeZone'
        timezone_element = self.xml.find(timezone_xml_path)
        if timezone_element is None:
            raise ItsNoTimeZoneInfo('I wasn\'t able to locate timezone info in this .its file')

        timezone_info = dict(timezone_element.items())
        return timezone_info

    def convert_utc_to_local(self, clock_time: pd.Series):
        """
        Convert utc timestams to local timestamps.
        :param clock_time: pd.Series of strings from the .its object
        :return: pd.Series of timezone-naive datetime type.
        """
        # Parse
        datetimes = (pd.to_datetime(clock_time, format='%Y-%m-%dT%H:%M:%SZ', utc=True)  # parse date
                     .dt.tz_convert(None))  # remove timezone information

        # Apply the timezone difference
        # Note: I didn't figure out how to use 'GMT-05:00' that is in timezone_info['ZoneNameShort']
        timezone_info = self.get_timezone_info()
        datetimes += pd.Timedelta(seconds=int(timezone_info['StandardSecondsOffset']))

        # Add an hour if there is daylight savings time used
        if timezone_info['UsesDST'] == '1':
            datetimes += pd.Timedelta(hours=1)

        return datetimes

    @staticmethod
    def convert_iso_duration_to_ms(iso_time: pd.Series):
        """
        Converts duration from iso format to the number of milliseconds.
        :param iso_time: pd.Series of ISO duration values
        :return: pd.Series of ints
        """
        return (pd.to_timedelta(iso_time)  # parse ISO-formatted times
                .dt.total_seconds()  # convert to seconds as real numbers
                .multiply(1000)  # convert from s to ms
                .astype(int))  # finally, convert to integers

    def gather_recordings(self):
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

        # Let's convert *ClockTime to local time and startTime to milliseconds
        return recordings.assign(
            recording_start=lambda df: self.convert_utc_to_local(df.startClockTime),
            recording_end=lambda df: self.convert_utc_to_local(df.endClockTime),
            recording_start_wav=lambda df: self.convert_iso_duration_to_ms(df.startTime)
        )[['recording_start', 'recording_end', 'recording_start_wav']]
