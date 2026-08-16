import os
import sys
from datetime import timedelta

import pandas as pd

# Running this file directly (`python data_sources/pull_all_sources.py`, as the
# weekly-data-pull workflow does) puts data_sources/ on sys.path rather than the
# repo root, so the `data_sources.*` imports below would not be importable.
# Importing it as a module (pytest) is unaffected.
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from data_sources.common import current_week_start_date
from data_sources.pull_google_trends import pull_google_trends
from data_sources.pull_seatgeek import MissingCredentialsError, pull_seatgeek
from data_sources.pull_wikipedia_pageviews import pull_wikipedia_pageviews


def already_pulled_sources(csv_path, week_start_date):
    if not os.path.exists(csv_path):
        return set()
    try:
        existing = pd.read_csv(csv_path)
    except Exception:
        # A malformed CSV (e.g. from a prior run that crashed mid-write) shouldn't
        # block any source from being pulled — treat it as "nothing pulled yet".
        return set()
    week_str = week_start_date.isoformat()
    return set(existing.loc[existing["week_start_date"] == week_str, "source"].unique())


def append_rows(csv_path, rows):
    if not rows:
        return
    os.makedirs(os.path.dirname(csv_path), exist_ok=True)
    df = pd.DataFrame(rows)
    write_header = not os.path.exists(csv_path)
    df.to_csv(csv_path, mode="a", header=write_header, index=False)


DEFAULT_CSV_PATH = "data_sources/processed/weekly_data.csv"


def pull_all_sources(
    csv_path=DEFAULT_CSV_PATH,
    week_start_date=None,
    seatgeek_client_id=None,
    seatgeek_session=None,
    pytrends_client=None,
    wiki_session=None,
):
    if week_start_date is None:
        # Default to the most recently completed week, not the in-progress current
        # week: pull_wikipedia_pageviews requests [week_start, week_start + 6 days],
        # and Wikimedia's REST API 404s on future/incomplete days when the current
        # ISO week's Monday is used. current_week_start_date() itself is unchanged
        # and still returns the Monday of a given date's ISO week.
        week_start_date = current_week_start_date() - timedelta(weeks=1)

    already_pulled = already_pulled_sources(csv_path, week_start_date)
    summary = {"pulled": [], "skipped": [], "failed": []}

    sources = [
        ("seatgeek", lambda: pull_seatgeek(week_start_date, client_id=seatgeek_client_id, session=seatgeek_session)),
        ("google_trends", lambda: pull_google_trends(week_start_date, pytrends_client=pytrends_client)),
        ("wikipedia_pageviews", lambda: pull_wikipedia_pageviews(week_start_date, session=wiki_session)),
    ]

    for name, pull_fn in sources:
        if name in already_pulled:
            summary["skipped"].append(name)
            continue
        try:
            rows = pull_fn()
        except MissingCredentialsError:
            summary["skipped"].append(name)
            continue
        except Exception:
            summary["failed"].append(name)
            continue
        append_rows(csv_path, rows)
        summary["pulled"].append(name)

    return summary


if __name__ == "__main__":
    result = pull_all_sources()
    print(f"Weekly data pull summary — pulled: {result['pulled']}, "
          f"skipped: {result['skipped']}, failed: {result['failed']}")
    if result["failed"]:
        sys.exit(1)
