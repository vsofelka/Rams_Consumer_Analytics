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


def test_run_season_writes_to_sqlite_when_db_path_given(tmp_path):
    import sqlite3

    db_path = str(tmp_path / "test.db")
    fans, events_history, score_history, snapshots = run_season(
        n_fans=20,
        n_planted_churn=2,
        decline_start_week=3,
        n_weeks=4,
        output_dir=str(tmp_path / "weekly_snapshots"),
        seed=55,
        db_path=db_path,
    )

    conn = sqlite3.connect(db_path)
    fans_count = conn.execute("SELECT COUNT(*) FROM fans").fetchone()[0]
    snapshots_count = conn.execute("SELECT COUNT(*) FROM weekly_snapshots").fetchone()[0]
    conn.close()

    assert fans_count == 20
    assert snapshots_count == 20 * 4


def test_run_season_twice_to_same_db_path_does_not_accumulate_rows(tmp_path):
    # A second run against an existing database file used to raise
    # sqlite3.IntegrityError (UNIQUE constraint failed: fans.fan_id), because
    # write_fans appends into a PRIMARY KEY column. A fresh season replaces the
    # database, the same way it overwrites the CSV output.
    import sqlite3

    db_path = str(tmp_path / "rerun.db")
    kwargs = dict(
        n_fans=10,
        n_planted_churn=1,
        decline_start_week=2,
        n_weeks=2,
        output_dir=str(tmp_path / "weekly_snapshots"),
        seed=57,
        db_path=db_path,
    )

    run_season(**kwargs)
    run_season(**kwargs)

    conn = sqlite3.connect(db_path)
    fans_count = conn.execute("SELECT COUNT(*) FROM fans").fetchone()[0]
    snapshots_count = conn.execute("SELECT COUNT(*) FROM weekly_snapshots").fetchone()[0]
    conn.close()

    assert fans_count == 10
    assert snapshots_count == 10 * 2


def test_run_season_skips_sqlite_when_db_path_omitted(tmp_path):
    fans, events_history, score_history, snapshots = run_season(
        n_fans=10,
        n_planted_churn=1,
        decline_start_week=2,
        n_weeks=2,
        output_dir=str(tmp_path / "weekly_snapshots"),
        seed=56,
    )
    assert len(snapshots) == 2
