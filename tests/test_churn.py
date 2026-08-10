import pandas as pd
from scoring.churn import apply_churn_rule


def test_at_risk_flag_true_for_consistently_declining_fan():
    score_history = pd.DataFrame({
        "fan_id": [1, 1, 1, 1],
        "week": [1, 2, 3, 4],
        "engagement_score": [80, 60, 40, 20],
    })
    result = apply_churn_rule(score_history, current_week=4, decline_weeks=3, risk_percentile=100.0)
    assert result.loc[result["fan_id"] == 1, "at_risk"].item() == True


def test_at_risk_flag_false_for_fan_without_enough_history():
    score_history = pd.DataFrame({
        "fan_id": [2, 2],
        "week": [3, 4],
        "engagement_score": [50, 45],
    })
    result = apply_churn_rule(score_history, current_week=4, decline_weeks=3, risk_percentile=100.0)
    assert result.loc[result["fan_id"] == 2, "at_risk"].item() == False
