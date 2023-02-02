UTTERANCE_TYPE_CODES = ("d", "i", "n", "q", "r", "s", "u", "o")
OBJECT_PRESENT_CODES = ("n", "u", "y", "o")

# "Audio" and "Video" are capitalized in the names of subject files folders. This was where I first worked with those
# words in the code so they stayed capitalized. There is a lot of `modality.lower()` in blabpy. If anyone wants to fix
# it - go for it.
AUDIO = 'Audio'
VIDEO = 'Video'
MODALITIES = (AUDIO, VIDEO)

DROPPED_CHILDREN = (5, 24)
CHILDREN_INT = tuple(child for child in range(1, 46 + 1) if child not in DROPPED_CHILDREN)
MONTHS_INT = tuple(month for month in range(6, 17 + 1))
ANNOTATION_FILE_COUNT = 527
MISSING_AUDIO_RECORDINGS = ((22, 9),)
MISSING_VIDEO_RECORDINGS = ((17, 6),)

SPEAKER_CODES = (
    'AF3', 'AFA', 'AFB', 'AFC', 'AFL', 'AMC', 'AU2', 'AUN', 'BR1', 'BR2', 'BRO', 'BSS', 'CFS', 'CHI', 'CME', 'EFA',
    'EFB', 'EFE', 'EFS', 'EMM', 'FAT', 'FCO', 'FTV', 'FTY', 'GP2', 'GRA', 'GRM', 'GRP', 'GTY', 'MBR', 'MFT', 'MIS',
    'MOT', 'MT2', 'MTV', 'MTY', 'SI1', 'SI2', 'SIS', 'STY', 'TOY', 'TVS', 'UN2', 'UNC', 'AFN', 'AFR', 'AFS', 'AM1',
    'ATV', 'BSK', 'BTY', 'CFA', 'CFE', 'FTS', 'GTV', 'MC2', 'MCO', 'MCU', 'MGM', 'NOT', 'STV', 'AF8', 'AFD', 'AMR',
    'BSE', 'BTV', 'CFR', 'CMD', 'MFU', 'MFV', 'MGP', 'MOY', 'SCU', 'AF1', 'AF2', 'AFH', 'AFM', 'AFP', 'AM2', 'AM3',
    'AMA', 'AMI', 'BSJ', 'CF1', 'CFC', 'CFD', 'CFK', 'CFZ', 'CMH', 'CML', 'CMO', 'FBR', 'FC2', 'MTT', 'AF4', 'AF5',
    'AFE', 'AM4', 'AM5', 'AMM', 'AU3', 'AU4', 'CFL', 'CM1', 'GRO', 'MMT', 'UN4', 'AF6', 'AF7', 'AF9', 'AFT', 'AMB',
    'AME', 'AMJ', 'CCU', 'CFP', 'CH1', 'GGM', 'GUN', 'SST', 'AFG', 'AFK', 'AMS', 'AMT', 'BSD', 'CFH', 'CM2', 'CMJ',
    'GGP', 'GMS', 'MC3', 'UAT', 'UAU', 'UTV', 'X10', 'X11', 'AFJ', 'BSC', 'BSL', 'CFB', 'CFM', 'CMM', 'UN3', 'X12',
    'AMG', 'AMK', 'BSB', 'COU', 'GR2', 'GRF', 'MGG', 'SIU', 'UMT', 'ADM', 'AFY', 'AM6', 'BIS', 'CMT', 'FC3', 'FCU',
    'GRY', 'MST', 'MTO', 'SGP', 'BBT', 'CTY', 'FGA', 'MBT', 'X13'
)
TIERS = ('*CHF', '*CHN', '*CXF', '*CXN',
         '*FAF', '*FAN', '*MAF', '*MAN',
         '*NOF', '*NON', '*OLF', '*OLN',
         '*SIL', '*TVF', '*TVN')

# Some of the .its files don't have the timezone information. We'll force EST with daylight savings determined by the
# date.
MISSING_TIMEZONE_RECORDING_IDS = (
    'Audio_12_17',
    'Audio_18_09',
    'Audio_20_13',
    'Audio_29_16')
MISSING_TIMEZONE_FORCED_TIMEZONE = 'US/Eastern'


def _month_or_child_to_str(month_or_child):
    return f'{int(month_or_child):02}'


def month_to_str(month):
    return _month_or_child_to_str(month)


def child_to_str(child):
    return _month_or_child_to_str(child)


CHILDREN_STR = tuple(child_to_str(child) for child in CHILDREN_INT)
MONTHS_STR = tuple(month_to_str(month) for month in MONTHS_INT)
