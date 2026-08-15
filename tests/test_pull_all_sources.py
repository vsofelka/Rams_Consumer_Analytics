import datetime
import os

import pandas as pd

from data_sources.pull_all_sources import already_pulled_sources, append_rows


def test_already_pulled_sources_returns_empty_set_when_csv_does_not_exist(tmp_path):
    csv_path = str(tmp_path / "weekly_data.csv")

    result = already_pulled_sources(csv_path, datetime.date(2026, 8, 10))

    assert result == set()


def test_already_pulled_sources_returns_sources_present_for_that_week(tmp_path):
    csv_path = str(tmp_path / "weekly_data.csv")
    pd.DataFrame([
        {"week_start_date": "2026-08-10", "source": "seatgeek", "metric_name": "listing_count", "value": 10},
        {"week_start_date": "2026-08-03", "source": "wikipedia_pageviews", "metric_name": "pageview_count", "value": 500},
    ]).to_csv(csv_path, index=False)

    result = already_pulled_sources(csv_path, datetime.date(2026, 8, 10))

    assert result == {"seatgeek"}


def test_append_rows_creates_csv_with_header_when_missing(tmp_path):
    csv_path = str(tmp_path / "weekly_data.csv")

    append_rows(csv_path, [{"week_start_date": "2026-08-10", "source": "seatgeek", "metric_name": "listing_count", "value": 10}])

    df = pd.read_csv(csv_path)
    assert list(df.columns) == ["week_start_date", "source", "metric_name", "value"]
    assert len(df) == 1


def test_append_rows_appends_without_duplicating_header(tmp_path):
    csv_path = str(tmp_path / "weekly_data.csv")
    append_rows(csv_path, [{"week_start_date": "2026-08-03", "source": "wikipedia_pageviews", "metric_name": "pageview_count", "value": 500}])

    append_rows(csv_path, [{"week_start_date": "2026-08-10", "source": "seatgeek", "metric_name": "listing_count", "value": 10}])

    df = pd.read_csv(csv_path)
    assert len(df) == 2


def test_append_rows_creates_parent_directory_if_missing(tmp_path):
    csv_path = str(tmp_path / "processed" / "weekly_data.csv")

    append_rows(csv_path, [{"week_start_date": "2026-08-10", "source": "seatgeek", "metric_name": "listing_count", "value": 10}])

    assert os.path.exists(csv_path)
