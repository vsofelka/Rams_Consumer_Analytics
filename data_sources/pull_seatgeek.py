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

    lowest_prices = [e["stats"]["lowest_price"] for e in events if e["stats"].get("lowest_price") is not None]
    average_prices = [e["stats"]["average_price"] for e in events if e["stats"].get("average_price") is not None]
    listing_counts = [e["stats"].get("listing_count", 0) for e in events]

    metrics = {
        "min_ticket_price": min(lowest_prices) if lowest_prices else 0,
        "avg_ticket_price": sum(average_prices) / len(average_prices) if average_prices else 0,
        "listing_count": sum(listing_counts),
    }
    return normalize_metrics(week_start_date, "seatgeek", metrics)
