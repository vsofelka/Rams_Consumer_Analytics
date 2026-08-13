import sqlite3
import pandas as pd
from storage.db import create_schema, write_fans, write_weekly_snapshot


def test_create_schema_creates_both_tables():
    conn = sqlite3.connect(":memory:")
    create_schema(conn)
    tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert {"fans", "weekly_snapshots"}.issubset(tables)


def test_write_fans_round_trips_data():
    conn = sqlite3.connect(":memory:")
    create_schema(conn)
    fans = pd.DataFrame({
        "fan_id": [1, 2],
        "tenure_years": [3, 7],
        "plan_tier": ["standard", "premium"],
        "baseline_engagement": [0.4, 0.8],
        "is_planted_churn": [True, False],
        "decline_start_week": [6.0, None],
    })
    write_fans(conn, fans)
    result = pd.read_sql("SELECT * FROM fans ORDER BY fan_id", conn)
    assert len(result) == 2
    assert set(result["fan_id"]) == {1, 2}


def test_write_weekly_snapshot_round_trips_data():
    conn = sqlite3.connect(":memory:")
    create_schema(conn)
    snapshot = pd.DataFrame({
        "fan_id": [1, 2],
        "week": [1, 1],
        "engagement_score": [55.0, 80.0],
        "tier": ["Cooling", "Engaged"],
        "at_risk": [False, False],
    })
    write_weekly_snapshot(conn, snapshot)
    result = pd.read_sql("SELECT * FROM weekly_snapshots ORDER BY fan_id", conn)
    assert len(result) == 2
    assert result.loc[0, "engagement_score"] == 55.0


def test_write_weekly_snapshot_appends_across_multiple_weeks():
    conn = sqlite3.connect(":memory:")
    create_schema(conn)
    week1 = pd.DataFrame({
        "fan_id": [1], "week": [1], "engagement_score": [55.0], "tier": ["Cooling"], "at_risk": [False],
    })
    week2 = pd.DataFrame({
        "fan_id": [1], "week": [2], "engagement_score": [50.0], "tier": ["Cooling"], "at_risk": [False],
    })
    write_weekly_snapshot(conn, week1)
    write_weekly_snapshot(conn, week2)
    result = pd.read_sql("SELECT * FROM weekly_snapshots ORDER BY week", conn)
    assert len(result) == 2
    assert list(result["week"]) == [1, 2]
