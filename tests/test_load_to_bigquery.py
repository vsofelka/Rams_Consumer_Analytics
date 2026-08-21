import sqlite3
from unittest.mock import MagicMock

import pandas as pd
from google.cloud import bigquery

from storage.db import create_schema, write_fans, write_weekly_snapshot
from scripts.load_to_bigquery import read_fans, read_weekly_snapshots, ensure_dataset, load_dataframe, create_views, load_to_bigquery


def _fans_fixture():
    return pd.DataFrame({
        "fan_id": [1, 2],
        "tenure_years": [3, 7],
        "plan_tier": ["standard", "premium"],
        "baseline_engagement": [0.4, 0.8],
        "is_planted_churn": [True, False],
        "decline_start_week": [6.0, None],
    })


def _weekly_snapshots_fixture():
    return pd.DataFrame({
        "fan_id": [1, 2],
        "week": [1, 1],
        "engagement_score": [55.0, 80.0],
        "tier": ["Cooling", "Engaged"],
        "at_risk": [True, False],
    })


def test_read_fans_casts_is_planted_churn_to_bool(tmp_path):
    db_path = str(tmp_path / "test.db")
    conn = sqlite3.connect(db_path)
    create_schema(conn)
    write_fans(conn, _fans_fixture())
    conn.close()

    fans = read_fans(db_path)

    assert fans["is_planted_churn"].dtype == bool
    assert list(fans["is_planted_churn"]) == [True, False]
    assert len(fans) == 2


def test_read_weekly_snapshots_casts_at_risk_to_bool(tmp_path):
    db_path = str(tmp_path / "test.db")
    conn = sqlite3.connect(db_path)
    create_schema(conn)
    write_weekly_snapshot(conn, _weekly_snapshots_fixture())
    conn.close()

    snapshots = read_weekly_snapshots(db_path)

    assert snapshots["at_risk"].dtype == bool
    assert list(snapshots["at_risk"]) == [True, False]
    assert len(snapshots) == 2


def test_ensure_dataset_creates_dataset_with_exists_ok():
    client = MagicMock()

    ensure_dataset(client, "rams-fan-analytics", "rams_fan_analytics", location="US")

    client.create_dataset.assert_called_once()
    args, kwargs = client.create_dataset.call_args
    dataset_arg = args[0]
    assert isinstance(dataset_arg, bigquery.Dataset)
    assert dataset_arg.dataset_id == "rams_fan_analytics"
    assert dataset_arg.location == "US"
    assert kwargs["exists_ok"] is True


def test_load_dataframe_truncates_and_waits_for_job():
    client = MagicMock()
    job = MagicMock()
    client.load_table_from_dataframe.return_value = job
    df = pd.DataFrame({"fan_id": [1, 2]})

    load_dataframe(client, "rams-fan-analytics", "rams_fan_analytics", "fans", df)

    args, kwargs = client.load_table_from_dataframe.call_args
    assert args[0] is df
    assert args[1] == "rams-fan-analytics.rams_fan_analytics.fans"
    assert kwargs["job_config"].write_disposition == bigquery.WriteDisposition.WRITE_TRUNCATE
    job.result.assert_called_once()


def test_create_views_runs_three_create_or_replace_statements():
    client = MagicMock()
    query_job = MagicMock()
    client.query.return_value = query_job

    create_views(client, "rams-fan-analytics", "rams_fan_analytics")

    assert client.query.call_count == 3
    executed_sql = [call.args[0] for call in client.query.call_args_list]
    assert all("CREATE OR REPLACE VIEW" in sql for sql in executed_sql)
    assert any("v_engagement_trend" in sql and "LAG(" in sql for sql in executed_sql)
    assert any("v_tier_by_plan" in sql and "JOIN" in sql for sql in executed_sql)
    assert any("v_at_risk_current" in sql and "WITH final_week" in sql for sql in executed_sql)
    assert query_job.result.call_count == 3


def test_load_to_bigquery_orchestrates_full_load(tmp_path):
    db_path = str(tmp_path / "test.db")
    conn = sqlite3.connect(db_path)
    create_schema(conn)
    write_fans(conn, _fans_fixture())
    write_weekly_snapshot(conn, _weekly_snapshots_fixture())
    conn.close()

    client = MagicMock()
    client.load_table_from_dataframe.return_value = MagicMock()
    client.query.return_value = MagicMock()

    result = load_to_bigquery(db_path, "rams-fan-analytics", "rams_fan_analytics", client=client)

    assert result == {"fans_rows": 2, "weekly_snapshots_rows": 2}
    client.create_dataset.assert_called_once()
    assert client.load_table_from_dataframe.call_count == 2
    assert client.query.call_count == 3
