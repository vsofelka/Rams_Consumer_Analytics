import pandas as pd


def _is_declining(group, decline_weeks):
    group = group.sort_values("week")
    if len(group) < decline_weeks + 1:
        return False
    scores = group["engagement_score"].to_numpy()
    return all(scores[i] < scores[i - 1] for i in range(1, len(scores)))


def apply_churn_rule(score_history, current_week, decline_weeks=3, risk_percentile=25.0):
    recent_weeks = list(range(current_week - decline_weeks, current_week + 1))
    windowed = score_history[score_history["week"].isin(recent_weeks)]

    declining_by_fan = windowed.groupby("fan_id").apply(
        lambda group: _is_declining(group, decline_weeks)
    )

    current_scores = (
        score_history[score_history["week"] == current_week]
        .set_index("fan_id")["engagement_score"]
    )
    risk_threshold = current_scores.quantile(risk_percentile / 100)

    at_risk = pd.DataFrame({
        "fan_id": current_scores.index,
        "week": current_week,
        "engagement_score": current_scores.values,
    })
    at_risk["is_declining"] = at_risk["fan_id"].map(declining_by_fan).fillna(False)
    at_risk["below_risk_threshold"] = at_risk["engagement_score"] <= risk_threshold
    at_risk["at_risk"] = at_risk["is_declining"] & at_risk["below_risk_threshold"]

    return at_risk[["fan_id", "week", "at_risk"]]
