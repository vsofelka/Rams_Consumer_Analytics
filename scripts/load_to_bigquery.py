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
