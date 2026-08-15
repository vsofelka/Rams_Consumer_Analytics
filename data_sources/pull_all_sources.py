import os

import pandas as pd


def already_pulled_sources(csv_path, week_start_date):
    if not os.path.exists(csv_path):
        return set()
    existing = pd.read_csv(csv_path)
    week_str = week_start_date.isoformat()
    return set(existing.loc[existing["week_start_date"] == week_str, "source"].unique())


def append_rows(csv_path, rows):
    if not rows:
        return
    os.makedirs(os.path.dirname(csv_path), exist_ok=True)
    df = pd.DataFrame(rows)
    write_header = not os.path.exists(csv_path)
    df.to_csv(csv_path, mode="a", header=write_header, index=False)
