import os

import requests

from data_sources.common import normalize_metrics

SEATGEEK_EVENTS_URL = "https://api.seatgeek.com/2/events"


class MissingCredentialsError(ValueError):
    pass


def pull_seatgeek(week_start_date, client_id=None, session=None):
    if client_id is None:
        client_id = os.environ.get("SEATGEEK_CLIENT_ID")
    if not client_id:
        raise MissingCredentialsError("SEATGEEK_CLIENT_ID is not set")

    if session is None:
        session = requests

    response = session.get(
        SEATGEEK_EVENTS_URL,
        params={"performers.slug": "los-angeles-rams", "client_id": client_id},
    )
    response.raise_for_status()
    events = response.json().get("events", [])

    if not events:
        return []

    # This account's approved API tier returns an empty `stats` object on every
    # event (confirmed via a live diagnostic call, 2026-08-21) — no lowest_price,
    # average_price, or listing_count is available. `score` and `popularity` are
    # top-level fields SeatGeek does populate; they stand in as a market-interest
    # signal in place of the ticket-pricing data this plan originally assumed.
    # See docs/DECISION_LOG.md for the full pre/post comparison.
    scores = [e["score"] for e in events]
    popularities = [e["popularity"] for e in events]

    metrics = {
        "avg_event_score": sum(scores) / len(scores),
        "avg_event_popularity": sum(popularities) / len(popularities),
    }
    return normalize_metrics(week_start_date, "seatgeek", metrics)
