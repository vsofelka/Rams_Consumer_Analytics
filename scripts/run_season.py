import os
import pandas as pd

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

    events_history = pd.DataFrame(
        columns=["fan_id", "week", "attendance_signal", "digital_signal", "purchase_signal"]
    )
    score_history = pd.DataFrame(columns=["fan_id", "week", "engagement_score", "tier"])
    weekly_snapshots = {}

    for week in range(1, n_weeks + 1):
        week_events = generate_week_events(fans, week, seed=seed)
        events_history = pd.concat([events_history, week_events], ignore_index=True)

        week_scores = compute_weekly_engagement_scores(events_history, current_week=week, window=window)
        score_history = pd.concat([score_history, week_scores], ignore_index=True)

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
