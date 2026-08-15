import datetime
from unittest.mock import MagicMock

import pytest

from data_sources.common import current_week_start_date, normalize_metrics, retry_with_backoff


def test_current_week_start_date_returns_monday_of_that_iso_week():
    # 2026-08-12 is a Wednesday in ISO week 2026-W33; that week's Monday is 2026-08-10
    result = current_week_start_date(today=datetime.date(2026, 8, 12))
    assert result == datetime.date(2026, 8, 10)


def test_current_week_start_date_defaults_to_today(monkeypatch):
    fixed_today = datetime.date(2026, 8, 15)

    class _FixedDate(datetime.date):
        @classmethod
        def today(cls):
            return fixed_today

    monkeypatch.setattr(datetime, "date", _FixedDate)

    result = current_week_start_date()
    assert result == datetime.date(2026, 8, 10)


def test_normalize_metrics_returns_common_shape_rows():
    week_start_date = datetime.date(2026, 8, 10)

    rows = normalize_metrics(week_start_date, "seatgeek", {"avg_ticket_price": 142.5, "listing_count": 87})

    assert rows == [
        {"week_start_date": "2026-08-10", "source": "seatgeek", "metric_name": "avg_ticket_price", "value": 142.5},
        {"week_start_date": "2026-08-10", "source": "seatgeek", "metric_name": "listing_count", "value": 87},
    ]


def test_retry_with_backoff_retries_and_returns_result_on_third_attempt():
    func = MagicMock(side_effect=[Exception("boom"), Exception("boom again"), "ok"])
    sleep_fn = MagicMock()

    result = retry_with_backoff(func, max_attempts=3, base_delay_seconds=1, sleep_fn=sleep_fn)

    assert result == "ok"
    assert func.call_count == 3
    assert sleep_fn.call_args_list == [((1,),), ((2,),)]


def test_retry_with_backoff_raises_after_exhausting_max_attempts():
    func = MagicMock(side_effect=Exception("always fails"))
    sleep_fn = MagicMock()

    with pytest.raises(Exception, match="always fails"):
        retry_with_backoff(func, max_attempts=3, base_delay_seconds=1, sleep_fn=sleep_fn)

    assert func.call_count == 3
    assert sleep_fn.call_count == 2
