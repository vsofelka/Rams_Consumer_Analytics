import datetime

import requests

from data_sources.common import normalize_metrics

WIKIMEDIA_PAGEVIEWS_URL = (
    "https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article/"
    "en.wikipedia/all-access/user/Los_Angeles_Rams/daily/{start}/{end}"
)
# Wikimedia's REST API requires a descriptive User-Agent identifying the
# project/contact per their API etiquette policy — requests without one are
# more likely to be rate-limited or blocked outright.
USER_AGENT = "rams-consumer-analytics/1.0 (https://github.com/vsofelka/Rams_Consumer_Analytics)"


def pull_wikipedia_pageviews(week_start_date, session=None):
    week_end_date = week_start_date + datetime.timedelta(days=6)
    url = WIKIMEDIA_PAGEVIEWS_URL.format(
        start=week_start_date.strftime("%Y%m%d"),
        end=week_end_date.strftime("%Y%m%d"),
    )

    if session is None:
        session = requests

    response = session.get(url, headers={"User-Agent": USER_AGENT})
    response.raise_for_status()
    items = response.json().get("items", [])

    total_views = sum(item["views"] for item in items)
    return normalize_metrics(week_start_date, "wikipedia_pageviews", {"pageview_count": total_views})
