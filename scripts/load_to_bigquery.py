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


def ensure_dataset(client, project_id, dataset_id, location="US"):
    dataset_ref = bigquery.DatasetReference(project_id, dataset_id)
    dataset = bigquery.Dataset(dataset_ref)
    dataset.location = location
    client.create_dataset(dataset, exists_ok=True)


def load_dataframe(client, project_id, dataset_id, table_id, dataframe):
    table_ref = f"{project_id}.{dataset_id}.{table_id}"
    job_config = bigquery.LoadJobConfig(write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE)
    job = client.load_table_from_dataframe(dataframe, table_ref, job_config=job_config)
    job.result()


def _view_queries(project_id, dataset_id):
    fq = f"{project_id}.{dataset_id}"
    return {
        "v_engagement_trend": f"""
CREATE OR REPLACE VIEW `{fq}.v_engagement_trend` AS
SELECT
  fan_id,
  week,
  engagement_score,
  engagement_score - LAG(engagement_score) OVER (PARTITION BY fan_id ORDER BY week) AS score_delta
FROM `{fq}.weekly_snapshots`
""",
        "v_tier_by_plan": f"""
CREATE OR REPLACE VIEW `{fq}.v_tier_by_plan` AS
SELECT
  w.week,
  f.plan_tier,
  AVG(w.engagement_score) AS avg_engagement_score,
  COUNT(*) AS n_fans
FROM `{fq}.weekly_snapshots` w
JOIN `{fq}.fans` f ON w.fan_id = f.fan_id
GROUP BY w.week, f.plan_tier
""",
        "v_at_risk_current": f"""
CREATE OR REPLACE VIEW `{fq}.v_at_risk_current` AS
WITH final_week AS (
  SELECT MAX(week) AS max_week FROM `{fq}.weekly_snapshots`
)
SELECT w.fan_id, w.engagement_score, w.tier
FROM `{fq}.weekly_snapshots` w, final_week
WHERE w.week = final_week.max_week AND w.at_risk = TRUE
ORDER BY w.engagement_score ASC
""",
    }


def create_views(client, project_id, dataset_id):
    for sql in _view_queries(project_id, dataset_id).values():
        client.query(sql).result()
