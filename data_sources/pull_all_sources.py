import os

import pandas as pd

from data_sources.common import current_week_start_date
from data_sources.pull_google_trends import pull_google_trends
from data_sources.pull_seatgeek import MissingCredentialsError, pull_seatgeek
from data_sources.pull_wikipedia_pageviews import pull_wikipedia_pageviews


def already_pulled_sources(csv_path, week_start_date):
    if not os.path.exists(csv_path):
        return set()
    existing = pd.read_csv(csv_path)
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
        week_start_date = current_week_start_date()

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
