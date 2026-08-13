import os
import sqlite3
import sys

import pandas as pd

# Running this file directly (`python scripts/run_season.py`) puts scripts/ on
# sys.path rather than the repo root, so the sibling packages below would not be
# importable. Importing it as a module (pytest, notebooks) is unaffected.
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from season_simulator.fans import generate_fan_population
from season_simulator.events import generate_week_events
from scoring.engagement import compute_weekly_engagement_scores
from scoring.churn import apply_churn_rule
from storage.db import create_schema, write_fans, write_weekly_snapshot


def run_season(
    n_fans,
    n_planted_churn,
    decline_start_week,
    n_weeks,
    output_dir,
    window=6,
    decline_weeks=3,
    risk_percentile=25.0,
    seed=42,
    db_path=None,
):
    fans = generate_fan_population(n_fans, n_planted_churn, decline_start_week, seed=seed)
    os.makedirs(output_dir, exist_ok=True)
    fans.to_csv(os.path.join(output_dir, "fans.csv"), index=False)

    db_conn = None
    if db_path is not None:
        # A fresh season overwrites the old one, matching the CSV output's
        # semantics. write_fans appends into a PRIMARY KEY column, so reusing an
        # existing database file would raise a UNIQUE constraint error instead.
        if os.path.exists(db_path):
            os.remove(db_path)
        db_conn = sqlite3.connect(db_path)
        create_schema(db_conn)
        write_fans(db_conn, fans)

    # Accumulate per-week frames in lists and concat them each iteration. Seeding
    # the history with an empty `columns=`-only DataFrame instead would make every
    # column object-dtype and propagate that through each concat.
    event_frames = []
    score_frames = []
    weekly_snapshots = {}

    # Both are reassigned on every iteration below; these placeholders are only
    # returned in the degenerate n_weeks < 1 case, where there is no data to type.
    events_history = pd.DataFrame(
        columns=["fan_id", "week", "attendance_signal", "digital_signal", "purchase_signal"]
    )
    score_history = pd.DataFrame(columns=["fan_id", "week", "engagement_score", "tier"])

    try:
        for week in range(1, n_weeks + 1):
            week_events = generate_week_events(fans, week, seed=seed)
            event_frames.append(week_events)
            events_history = pd.concat(event_frames, ignore_index=True)

            week_scores = compute_weekly_engagement_scores(events_history, current_week=week, window=window)
            score_frames.append(week_scores)
            score_history = pd.concat(score_frames, ignore_index=True)

            week_at_risk = apply_churn_rule(
                score_history, current_week=week, decline_weeks=decline_weeks, risk_percentile=risk_percentile
            )

            snapshot = week_scores.merge(week_at_risk[["fan_id", "at_risk"]], on="fan_id")
            snapshot.to_csv(os.path.join(output_dir, f"week_{week:02d}.csv"), index=False)
            weekly_snapshots[week] = snapshot

            if db_conn is not None:
                write_weekly_snapshot(db_conn, snapshot)
    finally:
        if db_conn is not None:
            db_conn.close()

    return fans, events_history, score_history, weekly_snapshots


if __name__ == "__main__":
    run_season(
        n_fans=300,
        n_planted_churn=25,
        decline_start_week=6,
        n_weeks=18,
        output_dir="data/weekly_snapshots",
        db_path="data/fan_analytics.db",
    )
