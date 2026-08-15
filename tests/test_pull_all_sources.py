import datetime
import os
from unittest.mock import MagicMock, patch

import pandas as pd

from data_sources.pull_all_sources import already_pulled_sources, append_rows, pull_all_sources


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


def test_pull_all_sources_pulls_all_three_on_a_fresh_csv(tmp_path):
    csv_path = str(tmp_path / "weekly_data.csv")

    with patch("data_sources.pull_all_sources.pull_seatgeek") as mock_seatgeek, \
         patch("data_sources.pull_all_sources.pull_google_trends") as mock_trends, \
         patch("data_sources.pull_all_sources.pull_wikipedia_pageviews") as mock_wiki:
        mock_seatgeek.return_value = [{"week_start_date": "2026-08-10", "source": "seatgeek", "metric_name": "listing_count", "value": 10}]
        mock_trends.return_value = [{"week_start_date": "2026-08-10", "source": "google_trends", "metric_name": "search_interest_score", "value": 42}]
        mock_wiki.return_value = [{"week_start_date": "2026-08-10", "source": "wikipedia_pageviews", "metric_name": "pageview_count", "value": 3100}]

        summary = pull_all_sources(csv_path=csv_path, week_start_date=datetime.date(2026, 8, 10), seatgeek_client_id="fake-id")

    assert sorted(summary["pulled"]) == ["google_trends", "seatgeek", "wikipedia_pageviews"]
    assert summary["skipped"] == []
    assert summary["failed"] == []
    df = pd.read_csv(csv_path)
    assert len(df) == 3


def test_pull_all_sources_skips_a_source_already_pulled_this_week(tmp_path):
    csv_path = str(tmp_path / "weekly_data.csv")
    pd.DataFrame([{"week_start_date": "2026-08-10", "source": "seatgeek", "metric_name": "listing_count", "value": 10}]).to_csv(csv_path, index=False)

    with patch("data_sources.pull_all_sources.pull_seatgeek") as mock_seatgeek, \
         patch("data_sources.pull_all_sources.pull_google_trends") as mock_trends, \
         patch("data_sources.pull_all_sources.pull_wikipedia_pageviews") as mock_wiki:
        mock_trends.return_value = [{"week_start_date": "2026-08-10", "source": "google_trends", "metric_name": "search_interest_score", "value": 42}]
        mock_wiki.return_value = [{"week_start_date": "2026-08-10", "source": "wikipedia_pageviews", "metric_name": "pageview_count", "value": 3100}]

        summary = pull_all_sources(csv_path=csv_path, week_start_date=datetime.date(2026, 8, 10), seatgeek_client_id="fake-id")

    mock_seatgeek.assert_not_called()
    assert "seatgeek" in summary["skipped"]
    assert sorted(summary["pulled"]) == ["google_trends", "wikipedia_pageviews"]


def test_pull_all_sources_one_failure_does_not_block_the_others(tmp_path):
    csv_path = str(tmp_path / "weekly_data.csv")

    with patch("data_sources.pull_all_sources.pull_seatgeek") as mock_seatgeek, \
         patch("data_sources.pull_all_sources.pull_google_trends") as mock_trends, \
         patch("data_sources.pull_all_sources.pull_wikipedia_pageviews") as mock_wiki:
        mock_seatgeek.side_effect = Exception("SeatGeek API down")
        mock_trends.return_value = [{"week_start_date": "2026-08-10", "source": "google_trends", "metric_name": "search_interest_score", "value": 42}]
        mock_wiki.return_value = [{"week_start_date": "2026-08-10", "source": "wikipedia_pageviews", "metric_name": "pageview_count", "value": 3100}]

        summary = pull_all_sources(csv_path=csv_path, week_start_date=datetime.date(2026, 8, 10), seatgeek_client_id="fake-id")

    assert "seatgeek" in summary["failed"]
    assert sorted(summary["pulled"]) == ["google_trends", "wikipedia_pageviews"]
    df = pd.read_csv(csv_path)
    assert set(df["source"]) == {"google_trends", "wikipedia_pageviews"}


def test_pull_all_sources_missing_seatgeek_credentials_is_a_skip_not_a_failure(tmp_path):
    csv_path = str(tmp_path / "weekly_data.csv")

    with patch("data_sources.pull_all_sources.pull_google_trends") as mock_trends, \
         patch("data_sources.pull_all_sources.pull_wikipedia_pageviews") as mock_wiki:
        mock_trends.return_value = [{"week_start_date": "2026-08-10", "source": "google_trends", "metric_name": "search_interest_score", "value": 42}]
        mock_wiki.return_value = [{"week_start_date": "2026-08-10", "source": "wikipedia_pageviews", "metric_name": "pageview_count", "value": 3100}]

        summary = pull_all_sources(csv_path=csv_path, week_start_date=datetime.date(2026, 8, 10), seatgeek_client_id=None)

    assert "seatgeek" in summary["skipped"]
    assert "seatgeek" not in summary["failed"]
