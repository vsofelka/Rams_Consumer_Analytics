from scripts.run_season import run_season
from scoring.validation import evaluate_churn_detection


def test_run_season_produces_weekly_snapshot_files(tmp_path):
    output_dir = tmp_path / "weekly_snapshots"
    fans, events_history, score_history, snapshots = run_season(
        n_fans=40,
        n_planted_churn=5,
        decline_start_week=3,
        n_weeks=5,
        output_dir=str(output_dir),
        seed=99,
    )

    assert len(list(output_dir.glob("week_*.csv"))) == 5
    assert (output_dir / "fans.csv").exists()
    week_5 = snapshots[5]
    assert len(week_5) == 40
    expected_columns = {"fan_id", "week", "engagement_score", "tier", "at_risk"}
    assert expected_columns.issubset(week_5.columns)


def test_run_season_flags_some_planted_churn_fans_by_final_week(tmp_path):
    fans, events_history, score_history, snapshots = run_season(
        n_fans=60,
        n_planted_churn=10,
        decline_start_week=3,
        n_weeks=10,
        output_dir=str(tmp_path / "weekly_snapshots"),
        seed=100,
    )

    final_week = 10
    at_risk_final = snapshots[final_week][["fan_id", "week", "at_risk"]]
    result = evaluate_churn_detection(at_risk_final, fans, week=final_week)
    assert result["recall"] > 0
