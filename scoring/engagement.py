import numpy as np
import pandas as pd

RAW_SIGNAL_COLUMNS = ["attendance_signal", "digital_signal", "purchase_signal"]
CATEGORY_WEIGHTS = {"attendance_signal": 0.4, "digital_signal": 0.3, "purchase_signal": 0.3}


def _trailing_window_average(events_history, current_week, window):
    start_week = max(1, current_week - window + 1)
    windowed = events_history[
        (events_history["week"] >= start_week) & (events_history["week"] <= current_week)
    ].copy()
    windowed["recency_weight"] = windowed["week"] - start_week + 1

    def weighted_avg(group):
        weights = group["recency_weight"]
        return pd.Series({
            col: np.average(group[col], weights=weights) for col in RAW_SIGNAL_COLUMNS
        })

    return windowed.groupby("fan_id").apply(weighted_avg).reset_index()


def compute_weekly_engagement_scores(events_history, current_week, window=6):
    averaged = _trailing_window_average(events_history, current_week, window)

    scored = averaged[["fan_id"]].copy()
    for col in RAW_SIGNAL_COLUMNS:
        scored[f"{col}_pct"] = averaged[col].rank(pct=True) * 100

    scored["engagement_score"] = sum(
        scored[f"{col}_pct"] * weight for col, weight in CATEGORY_WEIGHTS.items()
    )
    scored["week"] = current_week
    scored["tier"] = pd.cut(
        scored["engagement_score"],
        bins=[-0.1, 25, 50, 75, 100],
        labels=["Dormant", "At Risk", "Engaged", "Super Fan"],
    ).astype(str)

    return scored[["fan_id", "week", "engagement_score", "tier"]]
