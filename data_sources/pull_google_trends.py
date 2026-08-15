import time

from data_sources.common import normalize_metrics, retry_with_backoff

SEARCH_TERM = "Los Angeles Rams"


def _fetch_interest_over_time(pytrends_client):
    pytrends_client.build_payload([SEARCH_TERM], timeframe="now 7-d")
    return pytrends_client.interest_over_time()


def pull_google_trends(week_start_date, pytrends_client=None, sleep_fn=time.sleep):
    if pytrends_client is None:
        from pytrends.request import TrendReq
        pytrends_client = TrendReq(hl="en-US", tz=360)

    # pytrends is an unofficial, unauthenticated wrapper around Google Trends and is
    # prone to transient rate-limiting (HTTP 429) — retried here specifically, unlike
    # the other two sources' official/documented REST APIs.
    df = retry_with_backoff(
        _fetch_interest_over_time,
        pytrends_client,
        max_attempts=3,
        base_delay_seconds=1,
        sleep_fn=sleep_fn,
    )

    score = int(df[SEARCH_TERM].iloc[-1])
    return normalize_metrics(week_start_date, "google_trends", {"search_interest_score": score})
