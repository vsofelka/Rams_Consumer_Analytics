import pandas as pd
import pytest

from scoring.stats import (
    compare_churn_cohort_engagement,
    wilson_confidence_interval,
    hypergeometric_test,
)


def test_compare_churn_cohort_engagement_detects_clear_difference():
    # 5 vs 5 with complete separation: exact one-sided Mann-Whitney p-value is
    # 1/C(10,5) = 1/252 ~= 0.004. (2 vs 2 is NOT enough — the smallest possible
    # exact one-sided p-value with n1=n2=2 is 1/6 ~= 0.167, which can never
    # cross a 0.05 threshold no matter how separated the groups are.)
    fans = pd.DataFrame({
        "fan_id": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
        "is_planted_churn": [True, True, True, True, True, False, False, False, False, False],
    })
    scores = pd.DataFrame({
        "fan_id": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
        "engagement_score": [10.0, 12.0, 14.0, 16.0, 18.0, 70.0, 72.0, 74.0, 76.0, 78.0],
    })
    result = compare_churn_cohort_engagement(scores, fans)
    assert result["p_value"] < 0.05
    assert result["planted_median"] < result["rest_median"]
    assert result["n_planted"] == 5
    assert result["n_rest"] == 5


def test_compare_churn_cohort_engagement_no_difference_is_not_significant():
    # Fully interleaved values: planted and rest ranks alternate, so the U
    # statistic lands right at its expected value under the null (no
    # difference), which should be nowhere close to significant.
    fans = pd.DataFrame({
        "fan_id": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
        "is_planted_churn": [True, False, True, False, True, False, True, False, True, False],
    })
    scores = pd.DataFrame({
        "fan_id": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
        "engagement_score": [48.0, 48.5, 49.0, 49.5, 50.0, 50.5, 51.0, 51.5, 52.0, 52.5],
    })
    result = compare_churn_cohort_engagement(scores, fans)
    assert result["p_value"] > 0.05


def test_wilson_confidence_interval_contains_point_estimate_and_is_bounded():
    result = wilson_confidence_interval(successes=8, n=25, confidence=0.95)
    assert result["point_estimate"] == pytest.approx(0.32)
    assert result["lower"] < result["point_estimate"] < result["upper"]
    assert 0.0 <= result["lower"] < result["upper"] <= 1.0


def test_wilson_confidence_interval_narrows_with_larger_sample_same_proportion():
    small_n = wilson_confidence_interval(successes=8, n=25, confidence=0.95)
    large_n = wilson_confidence_interval(successes=80, n=250, confidence=0.95)
    small_width = small_n["upper"] - small_n["lower"]
    large_width = large_n["upper"] - large_n["lower"]
    assert large_width < small_width


def test_hypergeometric_test_extreme_case_exact_probability():
    # Population of 4 with 2 true churners. Drawing exactly 2 fans and getting
    # both churners is the only way this happens: C(2,2)*C(2,0)/C(4,2) = 1/6.
    result = hypergeometric_test(population_size=4, n_true_churners=2, n_flagged=2, n_true_positives=2)
    assert result["p_value"] == pytest.approx(1 / 6)
    assert result["expected_true_positives_by_chance"] == pytest.approx(1.0)


def test_hypergeometric_test_zero_true_positives_is_certain():
    result = hypergeometric_test(population_size=300, n_true_churners=25, n_flagged=13, n_true_positives=0)
    assert result["p_value"] == pytest.approx(1.0)
