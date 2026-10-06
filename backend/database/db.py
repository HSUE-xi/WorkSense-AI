import sqlite3
from pathlib import Path

DATABASE = Path(__file__).with_name("worksense.db")


def get_connection():
    connection = sqlite3.connect(DATABASE)
    connection.row_factory = sqlite3.Row
    return connection
