import datetime
from unittest.mock import MagicMock

import pytest

from data_sources.pull_seatgeek import pull_seatgeek, MissingCredentialsError


def _events_response_fixture():
    return {
        "events": [
            {"score": 0.6, "popularity": 0.8},
            {"score": 0.8, "popularity": 0.9},
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

    values = {r["metric_name"]: r["value"] for r in rows}
    assert values["avg_event_score"] == pytest.approx(0.7)
    assert values["avg_event_popularity"] == pytest.approx(0.85)
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


def test_pull_seatgeek_averages_across_more_than_two_events():
    session = MagicMock()
    session.get.return_value.json.return_value = {
        "events": [
            {"score": 0.5, "popularity": 0.5},
            {"score": 0.6, "popularity": 0.7},
            {"score": 1.0, "popularity": 0.9},
        ]
    }
    session.get.return_value.raise_for_status.return_value = None

    rows = pull_seatgeek(datetime.date(2026, 8, 10), client_id="fake-id", session=session)

    values = {r["metric_name"]: r["value"] for r in rows}
    assert values["avg_event_score"] == pytest.approx(0.7)
    assert values["avg_event_popularity"] == pytest.approx(0.7)
