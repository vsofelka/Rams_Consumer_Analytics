import datetime
from unittest.mock import MagicMock

from data_sources.pull_wikipedia_pageviews import pull_wikipedia_pageviews


def test_pull_wikipedia_pageviews_sums_daily_views_across_the_week():
    session = MagicMock()
    session.get.return_value.json.return_value = {
        "items": [{"views": 1000}, {"views": 1200}, {"views": 900}]
    }
    session.get.return_value.raise_for_status.return_value = None

    rows = pull_wikipedia_pageviews(datetime.date(2026, 8, 10), session=session)

    assert rows == [
        {"week_start_date": "2026-08-10", "source": "wikipedia_pageviews", "metric_name": "pageview_count", "value": 3100}
    ]


def test_pull_wikipedia_pageviews_sends_a_user_agent_header_identifying_this_repo():
    session = MagicMock()
    session.get.return_value.json.return_value = {"items": []}
    session.get.return_value.raise_for_status.return_value = None

    pull_wikipedia_pageviews(datetime.date(2026, 8, 10), session=session)

    args, kwargs = session.get.call_args
    assert "rams-consumer-analytics" in kwargs["headers"]["User-Agent"]
    assert "github.com/vsofelka/Rams_Consumer_Analytics" in kwargs["headers"]["User-Agent"]


def test_pull_wikipedia_pageviews_uses_monday_to_sunday_date_range():
    session = MagicMock()
    session.get.return_value.json.return_value = {"items": []}
    session.get.return_value.raise_for_status.return_value = None

    pull_wikipedia_pageviews(datetime.date(2026, 8, 10), session=session)

    args, kwargs = session.get.call_args
    assert "20260810" in args[0]
    assert "20260816" in args[0]
