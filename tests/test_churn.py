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


def test_percentile_threshold_filters_high_scoring_fans_even_if_declining():
    score_history = pd.DataFrame({
        "fan_id": [1, 1, 1, 1, 2, 2, 2, 2, 3, 3, 3, 3, 4, 4, 4, 4],
        "week": [1, 2, 3, 4] * 4,
        "engagement_score": [
            40, 30, 20, 10,    # fan 1: declining, low final score
            60, 50, 40, 30,    # fan 2: declining, low final score
            100, 90, 80, 70,   # fan 3: declining, HIGH final score
            120, 110, 100, 90, # fan 4: declining, HIGH final score
        ],
    })
    result = apply_churn_rule(score_history, current_week=4, decline_weeks=3, risk_percentile=50.0)
    at_risk_by_fan = result.set_index("fan_id")["at_risk"]

    assert at_risk_by_fan[1] == True
    assert at_risk_by_fan[2] == True
    assert at_risk_by_fan[3] == False
    assert at_risk_by_fan[4] == False
