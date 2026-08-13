import numpy as np
import pandas as pd
import pytest
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


def test_evaluate_churn_detection_matches_between_bool_and_int_flags():
    # SQLite has no native boolean type, so `at_risk` and `is_planted_churn`
    # come back from pd.read_sql as int64 (0/1). `~` on an int64 Series is a
    # bitwise NOT (~0 == -1, ~1 == -2), not a logical NOT, so the flags must be
    # cast to bool before masking rather than relying on 0/1 bit-0 coincidence.
    fan_ids = [1, 2, 3, 4, 5]
    planted_bool = [True, True, True, False, False]
    flagged_bool = [True, False, True, True, False]
    decline_start = [5, 5, 5, np.nan, np.nan]

    bool_result = evaluate_churn_detection(
        pd.DataFrame({"fan_id": fan_ids, "week": [10] * 5, "at_risk": flagged_bool}),
        pd.DataFrame({
            "fan_id": fan_ids,
            "is_planted_churn": planted_bool,
            "decline_start_week": decline_start,
        }),
        week=10,
    )

    int_at_risk = pd.DataFrame({
        "fan_id": fan_ids, "week": [10] * 5, "at_risk": [int(v) for v in flagged_bool],
    })
    int_fans = pd.DataFrame({
        "fan_id": fan_ids,
        "is_planted_churn": [int(v) for v in planted_bool],
        "decline_start_week": decline_start,
    })
    assert int_at_risk["at_risk"].dtype != bool
    assert int_fans["is_planted_churn"].dtype != bool

    int_result = evaluate_churn_detection(int_at_risk, int_fans, week=10)

    assert int_result == bool_result
    # 2 planted fans flagged, 1 non-planted fan flagged, 1 planted fan missed.
    assert int_result["true_positives"] == 2
    assert int_result["false_positives"] == 1
    assert int_result["false_negatives"] == 1
    assert int_result["precision"] == pytest.approx(2 / 3)
    assert int_result["recall"] == pytest.approx(2 / 3)


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
