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
    assert set(scores["tier"].unique()).issubset({"Dormant", "At Risk", "Engaged", "Super Fan"})


def test_partial_window_does_not_error_in_first_week():
    fans = generate_fan_population(n_fans=20, n_planted_churn=2, decline_start_week=6, seed=8)
    events_history = generate_week_events(fans, week=1, seed=8)
    scores = compute_weekly_engagement_scores(events_history, current_week=1, window=6)

    assert len(scores) == 20
    assert not scores["engagement_score"].isna().any()


def test_trailing_window_excludes_weeks_older_than_window():
    fans = generate_fan_population(n_fans=5, n_planted_churn=0, decline_start_week=99, seed=11)

    # Weeks 1-4: fan behavior spikes very high (should be excluded once window=3 and current_week=10)
    old_weeks = []
    for w in range(1, 5):
        events = generate_week_events(fans, week=w, seed=11)
        events[["attendance_signal", "digital_signal", "purchase_signal"]] = 1.0
        old_weeks.append(events)

    # Weeks 8-10: fan behavior is uniformly low
    recent_weeks = []
    for w in range(8, 11):
        events = generate_week_events(fans, week=w, seed=11)
        events[["attendance_signal", "digital_signal", "purchase_signal"]] = 0.0
        recent_weeks.append(events)

    full_history = pd.concat(old_weeks + recent_weeks, ignore_index=True)
    recent_only_history = pd.concat(recent_weeks, ignore_index=True)

    scores_full = compute_weekly_engagement_scores(full_history, current_week=10, window=3)
    scores_recent_only = compute_weekly_engagement_scores(recent_only_history, current_week=10, window=3)

    pd.testing.assert_frame_equal(
        scores_full.sort_values("fan_id").reset_index(drop=True),
        scores_recent_only.sort_values("fan_id").reset_index(drop=True),
    )
