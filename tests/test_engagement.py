import pandas as pd
from season_simulator.fans import generate_fan_population
from season_simulator.events import generate_week_events
from scoring.engagement import compute_weekly_engagement_scores


def test_engagement_score_in_valid_range():
    fans = generate_fan_population(n_fans=30, n_planted_churn=3, decline_start_week=6, seed=5)
    events_history = pd.concat(
        [generate_week_events(fans, week=w, seed=5) for w in range(1, 4)],
        ignore_index=True,
    )
    scores = compute_weekly_engagement_scores(events_history, current_week=3, window=6)

    assert len(scores) == 30
    assert scores["engagement_score"].between(0, 100).all()
    assert set(scores["tier"].unique()).issubset({"Dormant", "Cooling", "Engaged", "Super Fan"})


def test_partial_window_does_not_error_in_first_week():
    fans = generate_fan_population(n_fans=20, n_planted_churn=2, decline_start_week=6, seed=8)
    events_history = generate_week_events(fans, week=1, seed=8)
    scores = compute_weekly_engagement_scores(events_history, current_week=1, window=6)

    assert len(scores) == 20
    assert not scores["engagement_score"].isna().any()


def test_trailing_window_average_excludes_weeks_older_than_window():
    from scoring.engagement import _trailing_window_average

    events_history = pd.DataFrame({
        "fan_id": [1, 1, 1, 1, 1, 1, 1],
        "week": [1, 2, 3, 4, 8, 9, 10],
        "attendance_signal": [1.0, 1.0, 1.0, 1.0, 0.0, 0.0, 0.0],
        "digital_signal": [1.0, 1.0, 1.0, 1.0, 0.0, 0.0, 0.0],
        "purchase_signal": [1.0, 1.0, 1.0, 1.0, 0.0, 0.0, 0.0],
    })

    averaged = _trailing_window_average(events_history, current_week=10, window=3)

    fan_1 = averaged[averaged["fan_id"] == 1].iloc[0]
    assert fan_1["attendance_signal"] == 0.0
    assert fan_1["digital_signal"] == 0.0
    assert fan_1["purchase_signal"] == 0.0
