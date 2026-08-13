import sqlite3
import pandas as pd

FANS_SCHEMA = """
CREATE TABLE IF NOT EXISTS fans (
    fan_id INTEGER PRIMARY KEY,
    tenure_years INTEGER,
    plan_tier TEXT,
    baseline_engagement REAL,
    is_planted_churn INTEGER,
    decline_start_week REAL
)
"""

WEEKLY_SNAPSHOTS_SCHEMA = """
CREATE TABLE IF NOT EXISTS weekly_snapshots (
    fan_id INTEGER,
    week INTEGER,
    engagement_score REAL,
    tier TEXT,
    at_risk INTEGER,
    PRIMARY KEY (fan_id, week),
    FOREIGN KEY (fan_id) REFERENCES fans(fan_id)
)
"""


def create_schema(conn: sqlite3.Connection) -> None:
    conn.execute(FANS_SCHEMA)
    conn.execute(WEEKLY_SNAPSHOTS_SCHEMA)
    conn.commit()


def write_fans(conn: sqlite3.Connection, fans: pd.DataFrame) -> None:
    fans.to_sql("fans", conn, if_exists="append", index=False)
    conn.commit()


def write_weekly_snapshot(conn: sqlite3.Connection, snapshot: pd.DataFrame) -> None:
    snapshot.to_sql("weekly_snapshots", conn, if_exists="append", index=False)
    conn.commit()
