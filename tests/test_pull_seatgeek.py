import datetime
from unittest.mock import MagicMock

import pytest

from data_sources.pull_seatgeek import pull_seatgeek, MissingCredentialsError


def _events_response_fixture():
    return {
        "events": [
            {"stats": {"lowest_price": 80, "average_price": 150, "listing_count": 40}},
            {"stats": {"lowest_price": 65, "average_price": 130, "listing_count": 60}},
        ]
    }


def test_pull_seatgeek_raises_missing_credentials_when_client_id_absent(monkeypatch):
    monkeypatch.delenv("SEATGEEK_CLIENT_ID", raising=False)

    with pytest.raises(MissingCredentialsError):
        pull_seatgeek(datetime.date(2026, 8, 10), client_id=None, session=MagicMock())


def test_pull_seatgeek_returns_normalized_rows_from_events():
    session = MagicMock()
    session.get.return_value.json.return_value = _events_response_fixture()
    session.get.return_value.raise_for_status.return_value = None

    rows = pull_seatgeek(datetime.date(2026, 8, 10), client_id="fake-id", session=session)

    values = {(r["metric_name"], r["value"]) for r in rows}
    assert ("min_ticket_price", 65) in values
    assert ("avg_ticket_price", 140.0) in values
    assert ("listing_count", 100) in values
    assert all(r["source"] == "seatgeek" for r in rows)
    assert all(r["week_start_date"] == "2026-08-10" for r in rows)


def test_pull_seatgeek_calls_api_with_client_id_and_performer_filter():
    session = MagicMock()
    session.get.return_value.json.return_value = {"events": []}
    session.get.return_value.raise_for_status.return_value = None

    pull_seatgeek(datetime.date(2026, 8, 10), client_id="fake-id", session=session)

    args, kwargs = session.get.call_args
    assert "client_id" in kwargs["params"]
    assert kwargs["params"]["client_id"] == "fake-id"


def test_pull_seatgeek_returns_empty_list_when_no_events_found():
    session = MagicMock()
    session.get.return_value.json.return_value = {"events": []}
    session.get.return_value.raise_for_status.return_value = None

    rows = pull_seatgeek(datetime.date(2026, 8, 10), client_id="fake-id", session=session)

    assert rows == []


def test_pull_seatgeek_excludes_zero_price_sentinel_from_min_and_avg():
    session = MagicMock()
    session.get.return_value.json.return_value = {
        "events": [
            {"stats": {"lowest_price": 80, "average_price": 150, "listing_count": 40}},
            # SeatGeek's `0` sentinel means "no pricing data", not "$0 tickets" — it
            # must not drag the computed min/avg down to 0.
            {"stats": {"lowest_price": 0, "average_price": 0, "listing_count": 5}},
        ]
    }
    session.get.return_value.raise_for_status.return_value = None

    rows = pull_seatgeek(datetime.date(2026, 8, 10), client_id="fake-id", session=session)

    values = {(r["metric_name"], r["value"]) for r in rows}
    assert ("min_ticket_price", 80) in values
    assert ("avg_ticket_price", 150.0) in values
    assert ("listing_count", 45) in values


def test_pull_seatgeek_handles_event_missing_stats_key_without_raising():
    session = MagicMock()
    session.get.return_value.json.return_value = {
        "events": [
            {"stats": {"lowest_price": 80, "average_price": 150, "listing_count": 40}},
            # No "stats" key at all — must not raise KeyError, and must not stop the
            # other event in the same response from being counted.
            {"id": "no-stats-event"},
        ]
    }
    session.get.return_value.raise_for_status.return_value = None

    rows = pull_seatgeek(datetime.date(2026, 8, 10), client_id="fake-id", session=session)

    values = {(r["metric_name"], r["value"]) for r in rows}
    assert ("min_ticket_price", 80) in values
    assert ("avg_ticket_price", 150.0) in values
    assert ("listing_count", 40) in values
