import datetime
from unittest.mock import MagicMock

import pandas as pd
import pytest

from data_sources.pull_google_trends import pull_google_trends


def _interest_over_time_fixture():
    return pd.DataFrame({"Los Angeles Rams": [42], "isPartial": [False]})


def test_pull_google_trends_returns_normalized_search_interest_score():
    client = MagicMock()
    client.interest_over_time.return_value = _interest_over_time_fixture()

    rows = pull_google_trends(datetime.date(2026, 8, 10), pytrends_client=client, sleep_fn=MagicMock())

    assert rows == [
        {"week_start_date": "2026-08-10", "source": "google_trends", "metric_name": "search_interest_score", "value": 42}
    ]
    client.build_payload.assert_called_once()


def test_pull_google_trends_retries_on_failure_and_eventually_succeeds():
    client = MagicMock()
    client.interest_over_time.side_effect = [Exception("rate limited"), Exception("rate limited"), _interest_over_time_fixture()]
    sleep_fn = MagicMock()

    rows = pull_google_trends(datetime.date(2026, 8, 10), pytrends_client=client, sleep_fn=sleep_fn)

    assert rows[0]["value"] == 42
    assert client.interest_over_time.call_count == 3
    assert sleep_fn.call_count == 2


def test_pull_google_trends_raises_after_exhausting_retries():
    client = MagicMock()
    client.interest_over_time.side_effect = Exception("still rate limited")

    with pytest.raises(Exception, match="still rate limited"):
        pull_google_trends(datetime.date(2026, 8, 10), pytrends_client=client, sleep_fn=MagicMock())

    assert client.interest_over_time.call_count == 3
