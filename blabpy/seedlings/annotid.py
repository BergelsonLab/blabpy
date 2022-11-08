ANNOTID_REGEX = r'0x[a-z0-9]{6}'

def connect_to_db():
    """Connect to the annotids database and return the connection and cursor"""
    try:
        connection = mysql.connector.connect(**CONFIG, password=_get_db_password())
