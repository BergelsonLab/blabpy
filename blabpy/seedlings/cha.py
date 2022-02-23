# Initially, an exact copy of https://github.com/SeedlingsBabylab/parse_clan2/blob/master/parse_clan2.py
import csv
import logging
import re
import os
import collections
from pathlib import Path


class Parser:

    def __init__(self, input_path, output=None):

        self.input_file = input_path
        # output == None means we're being called from parse_clan2 main
        if output is None:
            self.output_file = input_path.replace(".cha", "_processed.csv")
            self.error_file = input_path.replace(".cha", "_errors.txt")
        # otherwise, Parser object is being constructed from an external source
        else:
            processed_path = os.path.split(input_path)[1].replace(".cha", "_processed.csv")
            error_path = os.path.split(input_path)[1].replace(".cha", "_errors.txt")
            # self.output_file = os.path.join(output, name)
            logging.info(os.path.join(output, processed_path))
            self.output_file = os.path.join(output, processed_path)
            self.error_file = os.path.join(output, error_path)

        # correct regex for annotations
        re1 = '((?:[a-z][a-z0-9_+]*))'  # the word
        re2 = '(\\s+)'	                # whitespace
        re3 = '(&=)'	                # &=
        re4 = '(.)'	                    # utterance_type
        re5 = '(_+)'	                # _
        re6 = '(.)'	                    # object_present
        re7 = '(_+)'	                # _
        re8 = '((?:[a-z][a-z0-9]*))'    # speaker
        re81 = '(_+)?'
        re82 = '(0x[a-z0-9]{6})?'       # annotid

        # incorrect regexes (for typos and formatting issues)
        self.entry_regx = re.compile(re1+re2+re3+re4+re5+re6+re7+re8+re81+re82, re.IGNORECASE | re.DOTALL)
        self.old_entry_regx = re.compile(re1+re2+'(&)'+re4+'(\\|)'+re6+'(\\|)'+re8+re81+re82, re.IGNORECASE | re.DOTALL)
        self.interval_regx = re.compile("(\025\d+_\d+)")

        self.joined_num_regx = re.compile("(_[yn]_[a-z0-9]{3}\d+)", re.IGNORECASE | re.DOTALL)
        self.joined_entry_wrdcount = re.compile("(_[yn]_[a-z0-9]{3}&=w)", re.IGNORECASE | re.DOTALL)
        # for new format:
        # self.joined_entry_wrdcount = re.compile("([a-f0-9]{6}&=w)", re.IGNORECASE | re.DOTALL)
        self.just_ampersand_regx = re.compile(re1+re2+'(&)'+'([qdiursn])'+re5+re6+re7+re8+re81+re82, re.IGNORECASE | re.DOTALL)

        # someword &=d-y-MOT
        self.dash_not_underscore_all = re.compile(re1+re2+re3+re4+'(-+)'+re6+'(-+)'+re8+re81+re82, re.IGNORECASE | re.DOTALL)
        # someword &=d-y_MOT
        self.dash_not_underscore_first = re.compile(re1+re2+re3+re4+'(-+)'+re6+re7+re8+re81+re82, re.IGNORECASE | re.DOTALL)
        # someword &=d_y-MOT
        self.dash_not_underscore_second = re.compile(re1+re2+re3+re4+re5+re6+'(-+)'+re8+re81+re82, re.IGNORECASE | re.DOTALL)

        re9 = '((?:[a-z][a-z]+))'  # Word 1
        re10 = '(\\s+)'            # White Space 1
        re11 = '(0)'               # Any Single Character 1
        re12 = '(\\s+)'            # White Space 2
        re13 = '(.)'               # Any Single Character 2

        # tummy 0 .
        self.missing_code_just_word = re.compile('(\\s+)'+re9+re10+re11+re12+re13,re.IGNORECASE|re.DOTALL)
        # tummy 0.
        self.missing_code_just_word_zero_period = re.compile('(\\s+)'+re9+re10+'(0.)'+re12+re13,re.IGNORECASE|re.DOTALL)
        # tummy &=w
        self.missing_code_just_word_andcount = re.compile('(\\s+)'+re9+re10+'(&=w)',re.IGNORECASE|re.DOTALL)

        self.one_missing_code_first = re.compile(re1+re2+re3+re5+'([yn])'+re7+re8+re81+re82, re.IGNORECASE|re.DOTALL)
        self.one_missing_code_second = re.compile(re1+re2+re3+re4+re5+re7+re8+re81+re82, re.IGNORECASE|re.DOTALL)
        self.one_missing_code_third = re.compile(re1+re2+re3+'([qdiursn])'+re5+'([yn])'+re7+'(\\s+)',
                                                 re.IGNORECASE|re.DOTALL)  # TODO
        self.one_missing_code_third_joined_count = re.compile(re1+re2+re3+'([qdiursn])'+re5+'([yn])'+re7+'(&=w)',
                                                              re.IGNORECASE|re.DOTALL)  #TODO

        self.missing_underscore_first = re.compile(re3+'([qdiursn])'+'([yn])'+re5+re8+re81+re82, re.IGNORECASE|re.DOTALL)
        self.missing_underscore_second = re.compile(re3+'([qdiursn])'+re5+'([yn])'+re8+re81+re82, re.IGNORECASE|re.DOTALL)

        # self.scrub_regx = re.compile()

        self.skipping = False
        self.begin_skip_start = None
        self.words = []
        self.comments = []          # includes all the comments
        self.curr_personal_block = None
        self.personal_info_groups = []
        self.plain_comments = []    # not including subregion/silence comments

        # list of tuples representing problems that were found.
        # represented as:
        #
        #       ("Description of problem: ...", interval, problem_entry)
        self.problems = []

        # check_intervals() returns false if there was a problem,
        # so we'll break from parsing and not go any further
        if not self.check_intervals():
            return

        self.phonetic_transcriptions = None

        self.parse()
        self.filter_comments()
        self.export()

    def parse(self):
        last_line = ""
        multi_line = ""

        prev_interval = [None, None]
        curr_interval = [None, None]

        inside_personal_block = False

        personal_info_com_start = None
        personal_info_com_end = None

        with open(self.input_file, "rU") as input:
            for index, line in enumerate(input):

                if line.startswith("%com:") and ("|" not in line):
                    if "begin skip" in line:
                        logging.info("Begin skip found in line# " + str(index))  #+ "\n"
                        self.skipping = True
                        self.begin_skip_start = index
                        continue
                    if "end skip" in line:
                        logging.info("End skip found in line# " + str(index) + "\n")
                        self.skipping = False
                        self.begin_skip_start = None
                        continue
                    if "personal" in line or "private" in line:
                        inside_personal_block = True
                        self.check_personal_info_comment(line, index, curr_interval)
                    if "end personal" in line:
                        inside_personal_block = False
                        self.personal_info_groups.append(self.curr_personal_block)

                    # get rid of quotation marks, %com's and newlines
                    comment = line.replace("%com:\t", "")\
                                  .replace("\"", "")\
                                  .replace("\n", "")

                    self.comments.append((comment, curr_interval[0], curr_interval[1]))

                if (line.startswith("%xcom:")) and ("|" not in line):
                    if "begin skip" in line:
                        logging.info("Begin skip starts at line# " + str(index))  #+ "\n"
                        self.skipping = True
                        self.begin_skip_start = index
                        continue
                    if "end skip" in line:
                        logging.info("End skip found in line# " + str(index) + "\n")
                        self.skipping = False
                        self.begin_skip_start = None
                        continue
                    if "personal" in line or "private" in line:
                        inside_personal_block = True
                    # get rid of quotation marks, %xcom's and newlines
                    comment = line.replace("%xcom:\t", "")\
                                  .replace("\"", "")\
                                  .replace("\n", "")

                    self.comments.append((comment, curr_interval[0], curr_interval[1]))

                #
                # if self.skipping:
                #     print "skipping line: " + line
                #     continue

                if line.startswith("*"):

                    # reset multi_line
                    multi_line = ""
                    interval_reg_result = self.interval_regx.search(line)

                    if interval_reg_result is None:
                        logging.info("interval regx returned none. clan line: " + str(index))
                        last_line = line
                        multi_line += line
                        continue
                    # rearrange previous and current intervals
                    prev_interval[0] = curr_interval[0]
                    prev_interval[1] = curr_interval[1]

                    # set the new curr_interval
                    interval_str = interval_reg_result.group().replace("\025", "")
                    interval = interval_str.split("_")
                    curr_interval[0] = int(interval[0])
                    curr_interval[1] = int(interval[1])

                    # find correctly formatted entries
                    entries = self.entry_regx.findall(line)

                    # check for all the possible malformed entry types
                    old_entries = self.old_entry_regx.findall(line)
                    joined_num = self.joined_num_regx.findall(line)
                    joined_entry_wrdcount = self.joined_entry_wrdcount.findall(line)
                    just_ampersand = self.just_ampersand_regx.findall(line)
                    dash_not_underscore_all = self.dash_not_underscore_all.findall(line)
                    dash_not_underscore_first = self.dash_not_underscore_first.findall(line)
                    dash_not_underscore_second = self.dash_not_underscore_second.findall(line)
                    missing_code_just_word = self.missing_code_just_word.findall(line)
                    missing_code_just_word_zero_period = self.missing_code_just_word_zero_period.findall(line)
                    missing_code_just_word_andcount = self.missing_code_just_word_andcount.findall(line)
                    one_missing_code_first = self.one_missing_code_first.findall(line)
                    one_missing_code_second = self.one_missing_code_second.findall(line)
                    one_missing_code_third = self.one_missing_code_third.findall(line)
                    one_missing_code_third_joined_count = self.one_missing_code_third_joined_count.findall(line)
                    missing_underscore_first = self.missing_underscore_first.findall(line)
                    missing_underscore_second = self.missing_underscore_second.findall(line)

                    if line.startswith("*SCR:"):
                        self.parse_scrub_tier(line, index, interval)

                    # e.g. - someword &=d_y_MOT0 .
                    if joined_num:
                        temp = [""] * len(joined_num)

                        for entry_index, entry in enumerate(joined_num):
                            for group in entry:
                                temp[entry_index] += group
                        self.problems.append(("Joined Number and Speaker Code",
                                              "line#: {}".format(index-1),
                                              interval,
                                              temp))

                    # e.g. - someword &d|y|MOT
                    if old_entries:
                        temp = [""] * len(old_entries)

                        for entry_index, entry in enumerate(old_entries):
                            for group in entry:
                                temp[entry_index] += group
                        self.problems.append(("Old Format (.cex) Style Entry Used",
                                              "line#: {}".format(index-1),
                                              interval,
                                              temp))

                    # e.g. -  someword &=d_y_MOT&=w4_50
                    if joined_entry_wrdcount:
                        temp = [""] * len(joined_entry_wrdcount)

                        for entry_index, entry in enumerate(joined_entry_wrdcount):
                            for group in entry:
                                temp[entry_index] += group
                        self.problems.append(("Entry and Word Count are Joined",
                                              "line#: {}".format(index-1),
                                              interval,
                                              temp))

                    # everything except the &= is formatted correctly
                    if just_ampersand:
                        temp = [""] * len(just_ampersand)

                        for entry_index, entry in enumerate(just_ampersand):
                            for group in entry:
                                temp[entry_index] += group
                        self.problems.append(("Ampersand Issue (\"&\" should be \"&=\")",
                                              "line#: {}".format(index-1),
                                              interval,
                                              temp))

                    # there was a "-" used instead of an "_"
                    # (either both of them, or just first/second)
                    if dash_not_underscore_all:
                        temp = [""] * len(dash_not_underscore_all)

                        for entry_index, entry in enumerate(dash_not_underscore_all):
                            for group in entry:
                                temp[entry_index] += group

                        self.problems.append(("Dash Used in Place of Underscore",
                                              "line#: {}".format(index-1),
                                              interval,
                                              temp))

                    if dash_not_underscore_first:
                        temp = [""] * len(dash_not_underscore_first)

                        for entry_index, entry in enumerate(dash_not_underscore_first):
                            for group in entry:
                                temp[entry_index] += group

                        self.problems.append(("Dash Used in Place of Underscore",
                                              "line#: {}".format(index-1),
                                              interval,
                                              temp))

                    if dash_not_underscore_second:
                        temp = [""] * len(dash_not_underscore_second)

                        for entry_index, entry in enumerate(dash_not_underscore_second):
                            for group in entry:
                                temp[entry_index] += group
                        self.problems.append(("Dash Used in Place of Underscore",
                                              "line#: {}".format(index-1),
                                              interval,
                                              temp))

                    if missing_code_just_word:
                        temp = [""] * len(missing_code_just_word)

                        for entry_index, entry in enumerate(missing_code_just_word):
                            for group in entry:
                                temp[entry_index] += group
                        self.problems.append(("Missing codes: &=x_x_XXX",
                                              "line#: {}".format(index-1),
                                              interval,
                                              temp))

                    if missing_code_just_word_zero_period:
                        temp = [""] * len(missing_code_just_word_zero_period)

                        for entry_index, entry in enumerate(missing_code_just_word_zero_period):
                            for group in entry:
                                temp[entry_index] += group
                        self.problems.append(("Missing codes: &=x_x_XXX",
                                              "line#: {}".format(index-1),
                                              interval,
                                              temp))


                    if missing_code_just_word_andcount:
                        temp = [""] * len(missing_code_just_word_andcount)

                        for entry_index, entry in enumerate(missing_code_just_word_andcount):
                            for group in entry:
                                temp[entry_index] += group
                        self.problems.append(("Missing code: &=x_x_XXX",
                                              "line#: {}".format(index-1),
                                              interval,
                                              temp))

                    if one_missing_code_first:
                        temp = [""] * len(one_missing_code_first)

                        for entry_index, entry in enumerate(one_missing_code_first):
                            for group in entry:
                                temp[entry_index] += group
                        self.problems.append(("Missing the first code: &=_x_XXX",
                                              "line#: {}".format(index-1),
                                              interval,
                                              temp))

                    if one_missing_code_second:
                        temp = [""] * len(one_missing_code_second)

                        for entry_index, entry in enumerate(one_missing_code_second):
                            for group in entry:
                                temp[entry_index] += group
                        self.problems.append(("Missing the second code: &=x__XXX",
                                              "line#: {}".format(index-1),
                                              interval,
                                              temp))

                    if one_missing_code_third:
                        temp = [""] * len(one_missing_code_third)

                        for entry_index, entry in enumerate(one_missing_code_third):
                            for group in entry:
                                temp[entry_index] += group
                        self.problems.append(("Missing the third code: &=x_x_",
                                              "line#: {}".format(index-1),
                                              interval,
                                              temp))

                    if one_missing_code_third_joined_count:
                        temp = [""] * len(one_missing_code_third_joined_count)

                        for entry_index, entry in enumerate(one_missing_code_third_joined_count):
                            for group in entry:
                                temp[entry_index] += group
                        self.problems.append(("Missing the third code and joined with word count: &=x_x_&=w",
                                              "line#: {}".format(index-1),
                                              interval,
                                              temp))


                    if missing_underscore_first:
                        temp = [""] * len(missing_underscore_first)

                        for entry_index, entry in enumerate(missing_underscore_first):
                            for group in entry:
                                temp[entry_index] += group
                        self.problems.append(("Missing the first underscore: &=xx_XXX",
                                              "line#: {}".format(index-1),
                                              interval,
                                              temp))

                    if missing_underscore_second:
                        temp = [""] * len(missing_underscore_second)

                        for entry_index, entry in enumerate(missing_underscore_second):
                            for group in entry:
                                temp[entry_index] += group
                        self.problems.append(("Missing the second underscore: &=x_xXXX",
                                              "line#: {}".format(index-1),
                                              interval,
                                              temp))

                    # correctly formatted entries
                    if entries:
                        if self.skipping:
                            logging.warning(
                                f"Object word was found in a skip region. Fix this in the .cha file.\n"
                                f"Line# {str(index)}\n"
                                f"line: {line}")
                            continue
                        else:
                            for entry in entries:
                                self.words.append([line[0:4],
                                                   entry[0],            # word
                                                   entry[3],            # utterance_type
                                                   entry[5],            # object_present
                                                   entry[7],            # speaker
                                                   entry[9],            # annotid
                                                   curr_interval[0],    # onset
                                                   curr_interval[1]])   # offset

                    last_line = line

                # intervals spanning more than 1 line start with a tab (\t)
                if line.startswith("\t"):
                    interval_reg_result = self.interval_regx.search(line)

                    if interval_reg_result is None:
                        multi_line += line
                        continue

                    prev_interval[0] = curr_interval[0]
                    prev_interval[1] = curr_interval[1]

                    # set the new curr_interval
                    interval_str = interval_reg_result.group().replace("\025", "")
                    interval = interval_str.split("_")
                    curr_interval[0] = int(interval[0])
                    curr_interval[1] = int(interval[1])

                    entries = self.entry_regx.findall(multi_line + line)

                    # check for all the possible malformed entry types
                    old_entries = self.old_entry_regx.findall(line)
                    joined_num = self.joined_num_regx.findall(line)
                    joined_entry_wrdcount = self.joined_entry_wrdcount.findall(line)
                    just_ampersand = self.just_ampersand_regx.findall(line)
                    dash_not_underscore_all = self.dash_not_underscore_all.findall(line)
                    dash_not_underscore_first = self.dash_not_underscore_first.findall(line)
                    dash_not_underscore_second = self.dash_not_underscore_second.findall(line)

                    # e.g. - someword &=d_y_MOT0 .
                    if joined_num:
                        temp = [""] * len(joined_num)

                        for entry_index, entry in enumerate(joined_num):
                            for group in entry:
                                temp[entry_index] += group
                        self.problems.append(("Joined Number and Speaker Code",
                                              "line#: {}".format(index-1),
                                              interval,
                                              temp))


                    # e.g. - someword &d|y|MOT
                    if old_entries:
                        temp = [""] * len(old_entries)

                        for entry_index, entry in enumerate(old_entries):
                            for group in entry:
                                temp[entry_index] += group
                        self.problems.append(("Old Format (.cex) Style Entry Used",
                                              "line#: {}".format(index-1),
                                              interval,
                                              temp))


                    # e.g. -  someword &=d_y_MOT&=w4_50
                    if joined_entry_wrdcount:
                        temp = [""] * len(joined_entry_wrdcount)

                        for entry_index, entry in enumerate(joined_entry_wrdcount):
                            for group in entry:
                                temp[entry_index] += group
                        self.problems.append(("Entry and Word Count are Joined",
                                              "line#: {}".format(index-1),
                                              interval,
                                              temp))


                    # everything except the &= is formatted correctly
                    if just_ampersand:
                        temp = [""] * len(just_ampersand)

                        for entry_index, entry in enumerate(just_ampersand):
                            for group in entry:
                                temp[entry_index] += group
                        self.problems.append(("Ampersand Issue (\"&\" should be \"&=\")",
                                              "line#: {}".format(index-1),
                                              interval,
                                              temp))


                    # there was a "-" used instead of an "_"
                    # (either both of them, or just first/second)
                    if dash_not_underscore_all:
                        temp = [""] * len(dash_not_underscore_all)

                        for entry_index, entry in enumerate(dash_not_underscore_all):
                            for group in entry:
                                temp[entry_index] += group
                        self.problems.append(("Dash Used in Place of Underscore",
                                              "line#: {}".format(index-1),
                                              interval,
                                              temp))

                    if dash_not_underscore_first:
                        temp = [""] * len(dash_not_underscore_first)

                        for entry_index, entry in dash_not_underscore_first:
                            for group in entry:
                                temp[entry_index] += group
                        self.problems.append(("Dash Used in Place of Underscore",
                                              "line#: {}".format(index-1),
                                              interval,
                                              temp))

                    if dash_not_underscore_second:
                        temp = [""] * len(dash_not_underscore_second)

                        for entry_index, entry in enumerate(dash_not_underscore_second):
                            for group in entry:
                                temp[entry_index] += group
                        self.problems.append(("Dash Used in Place of Underscore",
                                              "line#: {}".format(index-1),
                                              interval,
                                              temp))

                    if entries:
                        if self.skipping:
                            logging.warning(
                                f"Object word was found in a skip region. Fix this in the .cha file.\n"
                                f"Line# {str(index)}\n"
                                f"line: {line}")
                            continue
                        for entry in entries:
                            self.words.append([last_line[0:4],
                                               entry[0],            # word
                                               entry[3],            # utterance_type
                                               entry[5],            # object_present
                                               entry[7],            # speaker
                                               entry[9],            # annotid
                                               curr_interval[0],    # onset
                                               curr_interval[1]])   # offset

                    multi_line = "" # empty the mutiple line buffer

        self.phonetic_transcriptions = extract_chi_phonetic_transcriptions(self.input_file)

        if self.problems:
            # showwarning("Mistakes Found",
            #             "Fix the mistakes listed in the {} file"
            #             .format(os.path.split(self.error_file)[1]))
            self.output_problems()

    def _get_transcription(self, word):
        """
        Get phonetic transcription for a word entry in self.words
        :param word: a list from self.words
        :return: transcription if there is one, empty string otherwise
        """
        annotids, transcriptions = self.phonetic_transcriptions
        annotid = word[5]
        try:
            annotid_index = annotids.index(annotid)
            return transcriptions[annotid_index]
        except ValueError:
            return ""

    def export(self):

        comment_queue = collections.deque(self.plain_comments)
        if comment_queue:
            curr_comment = comment_queue.popleft()
        else:
            # if there are no comments, just set a dummy variable
            curr_comment = ("no comment", 0, 0)
        with open(self.output_file, "w") as output:
            writer = csv.writer(output)
            writer.writerow(["tier","word","utterance_type","object_present","speaker","annotid","timestamp","basic_level","comment","pho"])
            for entry in self.words:
                transcription = self._get_transcription(word=entry)

                # check to make sure there are comments left on the queue
                # If the current interval has passed the current comment interval,
                # pop the next comment off the queue.
                com = entry[6]
                if comment_queue:
                    if com > curr_comment[1]:
                        curr_comment = comment_queue.popleft()

                if com == curr_comment[1]:
                    writer.writerow([entry[0],
                                    entry[1],
                                    entry[2],
                                    entry[3],
                                    entry[4],
                                    entry[5],
                                    "{}_{}".format(entry[6], entry[7]),
                                    " ",
                                    curr_comment[0],
                                     transcription])

                else:
                    writer.writerow([entry[0],
                                    entry[1],
                                    entry[2],
                                    entry[3],
                                    entry[4],
                                    entry[5],
                                    "{}_{}".format(entry[6], entry[7]),
                                    " ",
                                    "NA",
                                     transcription])

        logging.info("\n\nTotal # of words: {}\n".format(len(self.words)))


    def filter_comments(self):
        """
        Filter out all the subregion and silence comments,
        leaving behind only the actual comments
        """
        for comment in self.comments:
            if ("subregion" not in comment[0]) and\
                    ("silence" not in comment[0]):
                self.plain_comments.append(comment)

    def check_intervals(self):
        """
        Makes sure there is at most 1 timestamp interval on a line
        :return: returns false if we found a problem
        """

        with open(self.input_file, "rU") as input:
            for index, line in enumerate(input):
                regx_result = self.interval_regx.findall(line)
                if regx_result:
                    if len(regx_result) > 1:
                        logging.warning(
                            f"Found more than 1 interval on a single CLAN line.\n"
                            f"Line# {str(index)}\n"
                            f"line: {line}")
                        return False
                    else:
                        continue
            return True

    def output_problems(self):
        with open(self.error_file, "w") as error_file:
            for error in self.problems:
                for element in error:
                    error_file.write(str(element) + "  ")
                error_file.write("\n\n")

    def check_personal_info_comment(self, comment, index, interval):
        if "begin" in comment or "start" in comment:
            if "begin personal information:" not in comment:
                self.problems.append(("Malformed personal info comment: line# {}"
                                      .format(index),
                                      interval,
                                      [comment]))
        if "end" in comment:
            if "end personal information" not in comment:
                self.problems.append(("Malformed personal info comment: line# {}"
                                     .format(index),
                                     interval,
                                     [comment]))

        self.curr_personal_block = PersonalInfoGroup(index)

    def parse_scrub_tier(self, line, index, interval):
        if "Scrub" not in line:
            self.problems.append(("Personal info (scrubbing) tier missing word \"Scrub\": line# {}"
                                  .format(index),
                                  interval,
                                  [line]))

        self.curr_personal_block.start_time = interval[0]
        self.curr_personal_block.end_time = interval[1]
        self.curr_personal_block.tier_line = index


class PersonalInfoGroup:
    def __init__(self, begin_com_index):
        self.start_time = None
        self.end_time = None

        self.tier_line = None
        self.start_line = begin_com_index
        self.end_line = None

        self.start_comment = ""
        self.end_comment = ""


def _extract_chi_annotation_ids_from_cha_line(cha_line: str):
    """
    Extract annotations ids from a line from a CHA file. Only the annotations uttered by CHI are extracted. We'll assume
    that an annotation id is never split over multiple lines.
    :param cha_line: a line from a cha file
    :return: list of annotation ids
    """
    return re.findall(r'_CHI_(?P<annotid>0x[a-z0-9]{6})', cha_line)


# TODO: this can be done while parsing CHA but incorporating this into the Parser class above is rather complicated and
#  so should be done after cleaning the Parser code first
def extract_chi_phonetic_transcriptions(cha_path: Path):
    """
    Extracts all phonetic transcriptions from a CHA file and the corresponding annotation ids. If a word is missing a
    transcription, it will not be included in the output. If the number of transcriptions is not equal to the number of
    CHI-uttered words in the same main tier, a ValueError will be raised. If there is a phonetic transcription, but no
    CHI-uttered words, we let it go.
    :param cha_path: path to the Cha file
    :return: annotids, transcriptions - lists of annotation ids and transcriptions
    """
    with cha_path.open('r') as f:
        lines = f.readlines()

    annotids, transcriptions = list(), list()
    # The main tier can be spread over multiple lines, the first one starting with "*XXX:\t" and the other ones - just
    # with "\t". main_tier_lines will contain all the lines in the last main tier - one or more. in_main_tier flag will
    # let us tell whether we can expect lines starting with a '\t'
    main_tier_lines = list()
    in_main_tier = False
    for line in lines:
        # First line of a main tier
        if line.startswith('*'):
            main_tier_lines = [line]
            in_main_tier = True

        # A continuation line of a main tier
        elif in_main_tier and line.startswith('\t'):
            main_tier_lines.append(line)

        # Not a main tier line
        else:
            in_main_tier = False
            if line.startswith('%pho:\t'):
                annotids_ = [annotid
                             for cha_line in main_tier_lines
                             for annotid in _extract_chi_annotation_ids_from_cha_line(cha_line)]
                # Remove tier type and then tab on the left and a line end on the right
                content = line.replace('%pho:', '').rstrip()
                transcriptions_ = content.split()

                # The numbers of words and transcriptions should be equal. But if there are no annotated words but there
                # are still some transcription, we will ignore it.
                if len(annotids_) != len(transcriptions_) and not (len(annotids_) == 0):
                    raise ValueError('The numbers of annotation ids and the phonetic transcriptions do not match')

                annotids.extend(annotids_)
                transcriptions.extend(transcriptions_)

    return annotids, transcriptions


def export_cha_to_csv(cha_path, output_folder):
    """
    Runs parse_clan2 (a version of it) on a cha file at cha_path and outputs the results to a csv_path
    :param cha_path: Path
    :param output_folder: Path to folder that will contain the _processed.csv and _errors.csv files. If None, output is
    saved to the save folder where cha_path is.
    :return: Path|None, if there were known errors, return the error file path. If the file could not be parsed, return
    cha_path
    """
    try:
        # Parser parses implicitly
        parser = Parser(input_path=cha_path, output=output_folder)
        error_file_path = Path(parser.error_file)
        if error_file_path.exists():
            return error_file_path
    except Exception:
        return cha_path