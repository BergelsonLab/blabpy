import pandas as pd

FIXME = '***FIX ME***'


def read_annotations_csv(path):
    """
    Reads an annotation csv file (either a csv exported from cha/opf or a sparse_code csv file) in a specific way: no
    strings are be parsed as NaN and the engine used is python. No idea why the engine bit is important.
    :param path: path to an annotation csv file
    :return: a pandas dataframe
    """
    return pd.read_csv(path, keep_default_na=False, engine='python')


def create_merged(file_new, file_old, file_merged, mode):
    """
    Merges annotations exported with export_opf_to_csv/export_cha_to_csv with the previously exported file that has
    the basic level of all words already added. Merging is done based on annotation ids (annotid) that each word in both
    files should have. For new or changed words, the basiclevel column will have ***FIX ME***
    :param file_new: path to a csv with exported annotations without basic level data
    :param file_old: path to a previous version of exported annotation with basic level data already added
    :param file_merged: path to the output file
    :param mode: 'audio'|'video' - which modality these files came from
    :return: (old_error, edit_word, new_word) - tuple of boolean values:
        old_error - were there duplicate annotids in the file with basic level data?
        edit_word - were there any changes to any of the words?
        new_word - are there new words in the exported annotations?
    """
    # print(mode)
    # print(file_old)
    # """
    if mode == "audio":
        annotid_col = "annotid"
        word_col = "word"
    elif mode == "video":
        annotid_col = "labeled_object.id"
        word_col = "labeled_object.object"
    else:
        print("Wrong mode value")
        return [], [], []
    # """

    # annotid_col = "annotid"
    # word_col = "word"
    # basic_level_col = "basic_level"

    old_error = False
    edit_word = False
    new_word = False

    old_df = read_annotations_csv(file_old)
    new_df = read_annotations_csv(file_new)

    # The basic level column in some video files is called basic_level, in others - labeled_object.basic_level. Let's
    # find which it is.
    # The code below will implicitly break if there are multiple columns whose name contains "basic_level"
    [old_basic_level_col] = old_df.columns[old_df.columns.str.contains('basic_level')]

    # For consistent naming, let's change it to 'basic_level'.
    basic_level_col = 'basic_level'
    old_df.rename(columns={old_basic_level_col: basic_level_col}, inplace=True)

    merged_df = pd.DataFrame(columns=old_df.columns.values)

    # df = df.rename(columns={'oldName1': 'newName1'})
    for index, new_row in new_df.iterrows():

        # word = ''
        to_add = new_row
        annot_id = new_row[annotid_col]
        tmp = old_df[old_df[annotid_col] == annot_id]
        # print(len(tmp.index))

        word = new_row[word_col]
        # tier = new_row['tier']
        # spk = new_row['speaker']
        # utt_type = new_row['utterance_type']
        # obj_pres = new_row['object_present']
        # ts = new_row['timestamp']

        # As far as I can tell, `while` is used here instead of `if` so that we can do `break`.
        # TODO:
        #   1. Rewrite this, so the logic is more clear: there is exactly one branch that leads to using the old word.
        #   2. Switch to using a join.
        while len(tmp.index) != 0:  # if the id already exists in the old df, check that the words/ts? do match

            if len(tmp.index) > 1:
                # One source of multiple matches are empty annotid's that comments might have
                if annot_id != '':
                    print("ERROR: annotid not unique in old version : ", annot_id)  # raise exception
                    old_error = True
                to_add[basic_level_col] = FIXME
                merged_df = merged_df.append(to_add)
                break

            old_row = tmp.iloc[0]

            # if new_row[:, new_row.columns != "basic_level"].equals(old_row[:, old_row.columns != "basic_level"]):
            if word == old_row[word_col]:
                # print("old", word)
                # check codes as well to know if something changed?
                to_add[basic_level_col] = old_row[basic_level_col]
                merged_df = merged_df.append(to_add)
                break
            else:
                # print("old but different", word)
                to_add[basic_level_col] = FIXME
                merged_df = merged_df.append(to_add)
                edit_word = True
                break

        else:  # if the id is new: no info to retrieve, add row from new
            # print(word)
            if word != '':
                # print("new", word)
                to_add[basic_level_col] = FIXME
                merged_df = merged_df.append(to_add)
                new_word = True
    # print(merged_df)
    merged_df = merged_df.loc[:, ~merged_df.columns.str.contains('^Unnamed')]

    # Remove comments from the video annotations where the comments live in separate rows (for audio, there is a
    # "comment" column)
    if mode == "video":
        is_comment = merged_df[word_col].str.startswith('%com')
        merged_df = merged_df[~is_comment]

    merged_df.to_csv(file_merged, index=False)

    return old_error, edit_word, new_word

