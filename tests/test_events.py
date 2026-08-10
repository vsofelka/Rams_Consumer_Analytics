from season_simulator.fans import generate_fan_population
from season_simulator.events import generate_week_events


def test_generate_week_events_shape_and_bounds():
    fans = generate_fan_population(n_fans=50, n_planted_churn=5, decline_start_week=6, seed=1)
    events = generate_week_events(fans, week=1, seed=1)

    assert len(events) == 50
    expected_columns = {"fan_id", "week", "attendance_signal", "digital_signal", "purchase_signal"}
    assert expected_columns.issubset(events.columns)
    for col in ["attendance_signal", "digital_signal", "purchase_signal"]:
        assert events[col].between(0, 1).all()


def test_planted_churn_fans_decline_after_start_week():
    fans = generate_fan_population(n_fans=50, n_planted_churn=10, decline_start_week=3, seed=2)
    early = generate_week_events(fans, week=3, seed=2)
    late = generate_week_events(fans, week=10, seed=2)

    planted_ids = fans.loc[fans["is_planted_churn"], "fan_id"]
    early_avg = early[early["fan_id"].isin(planted_ids)]["attendance_signal"].mean()
    late_avg = late[late["fan_id"].isin(planted_ids)]["attendance_signal"].mean()

    assert late_avg < early_avg
