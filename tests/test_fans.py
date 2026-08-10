import pandas as pd
from season_simulator.fans import generate_fan_population


def test_generate_fan_population_shape_and_columns():
    fans = generate_fan_population(n_fans=100, n_planted_churn=10, decline_start_week=6, seed=1)
    assert len(fans) == 100
    expected_columns = {
        "fan_id", "tenure_years", "plan_tier",
        "baseline_engagement", "is_planted_churn", "decline_start_week",
    }
    assert expected_columns.issubset(fans.columns)
    assert fans["is_planted_churn"].sum() == 10
    assert fans["baseline_engagement"].between(0, 1).all()


def test_generate_fan_population_is_reproducible_with_seed():
    fans_a = generate_fan_population(n_fans=50, n_planted_churn=5, decline_start_week=6, seed=7)
    fans_b = generate_fan_population(n_fans=50, n_planted_churn=5, decline_start_week=6, seed=7)
    pd.testing.assert_frame_equal(fans_a, fans_b)
