"""
storage.py  -  saves the OPTIONAL anonymous results that workers choose to share.

Only these things are saved: the date, the state, the type of work, and how much
pay was missing (as a percent and in rupees).  NO names, NO employer, NO place.
SQLite is built into Python, so nothing extra needs to be installed.
"""
import sqlite3
from datetime import date

import pandas as pd

DB_FILE = "shared_entries.db"


def _connect():
    return sqlite3.connect(DB_FILE)


def init_db():
    con = _connect()
    con.execute(
        """CREATE TABLE IF NOT EXISTS entries (
               added_on TEXT,
               state TEXT,
               industry TEXT,
               shortfall_percent REAL,
               shortfall_amount REAL
           )"""
    )
    con.commit()
    con.close()


def add_entry(state, industry, shortfall_percent, shortfall_amount):
    init_db()
    con = _connect()
    con.execute(
        "INSERT INTO entries VALUES (?, ?, ?, ?, ?)",
        (date.today().isoformat(), state, industry,
         float(shortfall_percent), float(shortfall_amount)),
    )
    con.commit()
    con.close()


def load_entries():
    init_db()
    con = _connect()
    df = pd.read_sql_query("SELECT * FROM entries", con)
    con.close()
    return df
