import sqlite3

import pandas as pd
from google.cloud import bigquery


def read_fans(db_path):
    conn = sqlite3.connect(db_path)
    try:
        fans = pd.read_sql("SELECT * FROM fans", conn)
    finally:
        conn.close()
    fans["is_planted_churn"] = fans["is_planted_churn"].astype(bool)
    return fans


def read_weekly_snapshots(db_path):
    conn = sqlite3.connect(db_path)
    try:
        snapshots = pd.read_sql("SELECT * FROM weekly_snapshots", conn)
    finally:
        conn.close()
    snapshots["at_risk"] = snapshots["at_risk"].astype(bool)
    return snapshots
