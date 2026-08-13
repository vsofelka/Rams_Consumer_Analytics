import os
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
):
    fans = generate_fan_population(n_fans, n_planted_churn, decline_start_week, seed=seed)
    os.makedirs(output_dir, exist_ok=True)
    fans.to_csv(os.path.join(output_dir, "fans.csv"), index=False)

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

    return fans, events_history, score_history, weekly_snapshots


if __name__ == "__main__":
    run_season(
        n_fans=300,
        n_planted_churn=25,
        decline_start_week=6,
        n_weeks=18,
        output_dir="data/weekly_snapshots",
    )
