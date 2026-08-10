import numpy as np
import pandas as pd
from scoring.validation import evaluate_churn_detection


def test_evaluate_churn_detection_perfect_match():
    fans = pd.DataFrame({
        "fan_id": [1, 2, 3],
        "is_planted_churn": [True, False, False],
        "decline_start_week": [5, np.nan, np.nan],
    })
    at_risk = pd.DataFrame({
        "fan_id": [1, 2, 3],
        "week": [10, 10, 10],
        "at_risk": [True, False, False],
    })
    result = evaluate_churn_detection(at_risk, fans, week=10)
    assert result["precision"] == 1.0
    assert result["recall"] == 1.0
    assert result["f1"] == 1.0


def test_evaluate_churn_detection_missed_planted_fan():
    fans = pd.DataFrame({
        "fan_id": [1, 2],
        "is_planted_churn": [True, False],
        "decline_start_week": [5, np.nan],
    })
    at_risk = pd.DataFrame({
        "fan_id": [1, 2],
        "week": [10, 10],
        "at_risk": [False, False],
    })
    result = evaluate_churn_detection(at_risk, fans, week=10)
    assert result["recall"] == 0.0
    assert result["true_positives"] == 0
    assert result["false_negatives"] == 1


def test_planted_churn_fan_before_decline_start_is_not_ground_truth_positive():
    fans = pd.DataFrame({
        "fan_id": [1, 2],
        "is_planted_churn": [True, False],
        "decline_start_week": [15, np.nan],
    })
    at_risk = pd.DataFrame({
        "fan_id": [1, 2],
        "week": [10, 10],
        "at_risk": [False, False],
    })
    result = evaluate_churn_detection(at_risk, fans, week=10)
    assert result["true_positives"] == 0
    assert result["false_negatives"] == 0
    assert result["false_positives"] == 0
