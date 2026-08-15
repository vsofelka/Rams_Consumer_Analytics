# Weekly Real-World Data Scraping — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development
> (recommended) or superpowers:executing-plans to implement this plan task-by-task.
> Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build `data_sources/` — three independently testable pull modules
(SeatGeek, Google Trends, Wikipedia pageviews), shared normalize/retry/env-loading
utilities, and an orchestrator that determines "this week," skips sources already
pulled, and appends normalized rows to `data_sources/processed/weekly_data.csv` — plus
a GitHub Actions workflow that runs it weekly and commits the CSV back, and a README
"Data Refresh" section documenting all of it.

**Architecture:** A new top-level package, `data_sources/`, parallel to `scoring/` and
`storage/`. Every function that talks to the network takes an injectable client
parameter (`session=None` / `pytrends_client=None`, lazily constructed for real use),
so the automated test suite never makes a real HTTP call — same pattern as
`scripts/load_to_bigquery.py`'s `client=None`. This plan does not touch
`season_simulator/`, `scoring/`, or `storage/db.py`.

**Tech Stack:** Python, `requests`, `pytrends`, `python-dotenv`, pandas, pytest,
`unittest.mock`.

## Global Constraints

- New dependencies (`requirements.txt`, appended in this order): `requests>=2.31`,
  `pytrends>=4.9`, `python-dotenv>=1.0`
- New package: `data_sources/` with an `__init__.py`, same as every other top-level
  package (`scoring/`, `storage/`, `scripts/`)
- Normalized row shape everywhere: `{"week_start_date": <ISO date str>, "source": str,
  "metric_name": str, "value": float}`
- `week_start_date` is always the **Monday** of the relevant ISO week
  (`date.fromisocalendar(iso_year, iso_week, 1)`), stored as an ISO date string
  (`YYYY-MM-DD`)
- No task in this plan may make a real network call inside the automated test suite —
  every network-calling function accepts an injectable client/session, and tests use
  `unittest.mock.MagicMock`
- `print()` only at the orchestration boundary (`pull_all_sources()`'s summary and its
  `if __name__ == "__main__":` block) — never inside `pull_seatgeek`, `pull_google_trends`,
  `pull_wikipedia_pageviews`, or the `common.py` helpers, matching this repo's existing
  no-`logging`-module convention
- `SEATGEEK_CLIENT_ID` is read from the environment (`os.environ`, after
  `python-dotenv`'s `load_dotenv()` has run) — never hardcoded, never logged
- Missing `SEATGEEK_CLIENT_ID` raises `MissingCredentialsError` (defined in
  `data_sources/pull_seatgeek.py`), which the orchestrator catches and records as
  `skipped`, not `failed`
- SeatGeek metrics are a **weekly aggregate across all upcoming events**
  (`avg_ticket_price`, `min_ticket_price`, `listing_count`), not per-game rows
- Wikipedia requests send `User-Agent:
  "rams-consumer-analytics/1.0 (https://github.com/vsofelka/Rams_Consumer_Analytics)"`
- No task in this plan may create or modify any file under `.claude/` for any reason,
  including to bypass a permission prompt — report BLOCKED instead
- Test naming: `test_<function>_<expected_behavior>`, flat module-level functions, no
  `Test` classes, no pytest fixtures (plain `_foo_fixture()` helpers), `tmp_path` for
  all file I/O — matching `tests/test_load_to_bigquery.py` / `tests/test_run_season.py`

---

### Task 1: Package scaffolding and dependencies

**Files:**
- Create: `data_sources/__init__.py` (empty)
- Modify: `requirements.txt`
- Modify: `tests/test_setup.py`

**Interfaces:**
- Produces: `data_sources` importable as a package for every later task.

- [ ] **Step 1: Add the new dependencies**

Append to the end of `requirements.txt`:
```
requests>=2.31
pytrends>=4.9
python-dotenv>=1.0
```

- [ ] **Step 2: Install them**

Run: `pip install -r requirements.txt`
Expected: all three install with no errors.

- [ ] **Step 3: Create the package**

Create `data_sources/__init__.py` (empty file).

- [ ] **Step 4: Add an import smoke test**

Append to `tests/test_setup.py`:
```python
def test_can_import_data_sources():
    import data_sources
    assert data_sources is not None
```

- [ ] **Step 5: Run it**

Run: `pytest tests/test_setup.py -v`
Expected: all pass (existing tests + this one).

- [ ] **Step 6: Commit**

```bash
git add requirements.txt data_sources/__init__.py tests/test_setup.py
git commit -m "Scaffold data_sources package and add scraping dependencies"
```

---

### Task 2: Shared utilities — week calculation, normalization, retry/backoff

**Files:**
- Create: `data_sources/common.py`
- Create: `tests/test_common.py`

**Interfaces:**
- Produces: `current_week_start_date(today: date = None) -> date`.
  `normalize_metrics(week_start_date: date, source: str, metrics: dict[str, float]) ->
  list[dict]`. `retry_with_backoff(func, *args, max_attempts: int = 3,
  base_delay_seconds: float = 1, sleep_fn=time.sleep, **kwargs)`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_common.py`:
```python
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
```

Note: `normalize_metrics` must iterate `metrics.items()` in a deterministic (sorted
by key) order so the assertion above is stable regardless of dict insertion order.

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_common.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'data_sources.common'`.

- [ ] **Step 3: Write minimal implementation**

Create `data_sources/common.py`:
```python
import time
from datetime import date

from dotenv import load_dotenv

load_dotenv()


def current_week_start_date(today=None):
    if today is None:
        today = date.today()
    iso_year, iso_week, _ = today.isocalendar()
    return date.fromisocalendar(iso_year, iso_week, 1)


def normalize_metrics(week_start_date, source, metrics):
    return [
        {
            "week_start_date": week_start_date.isoformat(),
            "source": source,
            "metric_name": metric_name,
            "value": value,
        }
        for metric_name, value in sorted(metrics.items())
    ]


def retry_with_backoff(func, *args, max_attempts=3, base_delay_seconds=1, sleep_fn=time.sleep, **kwargs):
    for attempt in range(max_attempts):
        try:
            return func(*args, **kwargs)
        except Exception:
            if attempt == max_attempts - 1:
                raise
            sleep_fn(base_delay_seconds * (2 ** attempt))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_common.py -v`
Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add data_sources/common.py tests/test_common.py
git commit -m "Add shared week-calculation, normalization, and retry/backoff helpers"
```

---

### Task 3: SeatGeek pull module

**Files:**
- Create: `data_sources/pull_seatgeek.py`
- Create: `tests/test_pull_seatgeek.py`

**Interfaces:**
- Consumes: `data_sources.common.normalize_metrics`.
- Produces: `MissingCredentialsError(ValueError)`. `pull_seatgeek(week_start_date:
  date, client_id: str = None, session=None) -> list[dict]`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_pull_seatgeek.py`:
```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_pull_seatgeek.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'data_sources.pull_seatgeek'`.

- [ ] **Step 3: Write minimal implementation**

Create `data_sources/pull_seatgeek.py`:
```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_pull_seatgeek.py -v`
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add data_sources/pull_seatgeek.py tests/test_pull_seatgeek.py
git commit -m "Add SeatGeek ticket-price pull module"
```

---

### Task 4: Wikipedia pageviews pull module

**Files:**
- Create: `data_sources/pull_wikipedia_pageviews.py`
- Create: `tests/test_pull_wikipedia_pageviews.py`

**Interfaces:**
- Consumes: `data_sources.common.normalize_metrics`.
- Produces: `pull_wikipedia_pageviews(week_start_date: date, session=None) -> list[dict]`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_pull_wikipedia_pageviews.py`:
```python
import datetime
from unittest.mock import MagicMock

from data_sources.pull_wikipedia_pageviews import pull_wikipedia_pageviews


def test_pull_wikipedia_pageviews_sums_daily_views_across_the_week():
    session = MagicMock()
    session.get.return_value.json.return_value = {
        "items": [{"views": 1000}, {"views": 1200}, {"views": 900}]
    }
    session.get.return_value.raise_for_status.return_value = None

    rows = pull_wikipedia_pageviews(datetime.date(2026, 8, 10), session=session)

    assert rows == [
        {"week_start_date": "2026-08-10", "source": "wikipedia_pageviews", "metric_name": "pageview_count", "value": 3100}
    ]


def test_pull_wikipedia_pageviews_sends_a_user_agent_header_identifying_this_repo():
    session = MagicMock()
    session.get.return_value.json.return_value = {"items": []}
    session.get.return_value.raise_for_status.return_value = None

    pull_wikipedia_pageviews(datetime.date(2026, 8, 10), session=session)

    args, kwargs = session.get.call_args
    assert "rams-consumer-analytics" in kwargs["headers"]["User-Agent"]
    assert "github.com/vsofelka/Rams_Consumer_Analytics" in kwargs["headers"]["User-Agent"]


def test_pull_wikipedia_pageviews_uses_monday_to_sunday_date_range():
    session = MagicMock()
    session.get.return_value.json.return_value = {"items": []}
    session.get.return_value.raise_for_status.return_value = None

    pull_wikipedia_pageviews(datetime.date(2026, 8, 10), session=session)

    args, kwargs = session.get.call_args
    assert "20260810" in args[0]
    assert "20260816" in args[0]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_pull_wikipedia_pageviews.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'data_sources.pull_wikipedia_pageviews'`.

- [ ] **Step 3: Write minimal implementation**

Create `data_sources/pull_wikipedia_pageviews.py`:
```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_pull_wikipedia_pageviews.py -v`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add data_sources/pull_wikipedia_pageviews.py tests/test_pull_wikipedia_pageviews.py
git commit -m "Add Wikipedia pageviews pull module"
```

---

### Task 5: Google Trends pull module (retry/backoff applied)

**Files:**
- Create: `data_sources/pull_google_trends.py`
- Create: `tests/test_pull_google_trends.py`

**Interfaces:**
- Consumes: `data_sources.common.normalize_metrics`, `data_sources.common.retry_with_backoff`.
- Produces: `pull_google_trends(week_start_date: date, pytrends_client=None,
  sleep_fn=time.sleep) -> list[dict]`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_pull_google_trends.py`:
```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_pull_google_trends.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'data_sources.pull_google_trends'`.

- [ ] **Step 3: Write minimal implementation**

Create `data_sources/pull_google_trends.py`:
```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_pull_google_trends.py -v`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add data_sources/pull_google_trends.py tests/test_pull_google_trends.py
git commit -m "Add Google Trends pull module with retry/backoff for pytrends rate limiting"
```

---

### Task 6: CSV idempotency-check and append helpers

**Files:**
- Create: `data_sources/pull_all_sources.py` (I/O helpers only, this task)
- Create: `tests/test_pull_all_sources.py`

**Interfaces:**
- Produces: `already_pulled_sources(csv_path: str, week_start_date: date) -> set[str]`.
  `append_rows(csv_path: str, rows: list[dict]) -> None`.

Deliberately split from Task 7's orchestration logic — these two functions are pure
file I/O, testable with `tmp_path` and no mocks at all, and are easiest to get right
in isolation before wiring them into the three pull functions.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_pull_all_sources.py`:
```python
import datetime
import os

import pandas as pd

from data_sources.pull_all_sources import already_pulled_sources, append_rows


def test_already_pulled_sources_returns_empty_set_when_csv_does_not_exist(tmp_path):
    csv_path = str(tmp_path / "weekly_data.csv")

    result = already_pulled_sources(csv_path, datetime.date(2026, 8, 10))

    assert result == set()


def test_already_pulled_sources_returns_sources_present_for_that_week(tmp_path):
    csv_path = str(tmp_path / "weekly_data.csv")
    pd.DataFrame([
        {"week_start_date": "2026-08-10", "source": "seatgeek", "metric_name": "listing_count", "value": 10},
        {"week_start_date": "2026-08-03", "source": "wikipedia_pageviews", "metric_name": "pageview_count", "value": 500},
    ]).to_csv(csv_path, index=False)

    result = already_pulled_sources(csv_path, datetime.date(2026, 8, 10))

    assert result == {"seatgeek"}


def test_append_rows_creates_csv_with_header_when_missing(tmp_path):
    csv_path = str(tmp_path / "weekly_data.csv")

    append_rows(csv_path, [{"week_start_date": "2026-08-10", "source": "seatgeek", "metric_name": "listing_count", "value": 10}])

    df = pd.read_csv(csv_path)
    assert list(df.columns) == ["week_start_date", "source", "metric_name", "value"]
    assert len(df) == 1


def test_append_rows_appends_without_duplicating_header(tmp_path):
    csv_path = str(tmp_path / "weekly_data.csv")
    append_rows(csv_path, [{"week_start_date": "2026-08-03", "source": "wikipedia_pageviews", "metric_name": "pageview_count", "value": 500}])

    append_rows(csv_path, [{"week_start_date": "2026-08-10", "source": "seatgeek", "metric_name": "listing_count", "value": 10}])

    df = pd.read_csv(csv_path)
    assert len(df) == 2


def test_append_rows_creates_parent_directory_if_missing(tmp_path):
    csv_path = str(tmp_path / "processed" / "weekly_data.csv")

    append_rows(csv_path, [{"week_start_date": "2026-08-10", "source": "seatgeek", "metric_name": "listing_count", "value": 10}])

    assert os.path.exists(csv_path)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_pull_all_sources.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'data_sources.pull_all_sources'`.

- [ ] **Step 3: Write minimal implementation**

Create `data_sources/pull_all_sources.py`:
```python
import os

import pandas as pd


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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_pull_all_sources.py -v`
Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add data_sources/pull_all_sources.py tests/test_pull_all_sources.py
git commit -m "Add weekly_data.csv idempotency-check and append helpers"
```

---

### Task 7: Orchestration — pull_all_sources() and CLI entry point

**Files:**
- Modify: `data_sources/pull_all_sources.py`
- Modify: `tests/test_pull_all_sources.py`

**Interfaces:**
- Consumes: `pull_seatgeek`, `pull_google_trends`, `pull_wikipedia_pageviews`
  (Tasks 3–5); `already_pulled_sources`, `append_rows` (Task 6);
  `current_week_start_date` (Task 2).
- Produces: `pull_all_sources(csv_path: str = "data_sources/processed/weekly_data.csv",
  week_start_date: date = None, seatgeek_client_id: str = None, seatgeek_session=None,
  pytrends_client=None, wiki_session=None) -> dict` with keys `pulled`, `skipped`,
  `failed` (each a list of source names). CLI: `python data_sources/pull_all_sources.py`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_pull_all_sources.py`:
```python
from unittest.mock import MagicMock, patch

from data_sources.pull_all_sources import pull_all_sources


def test_pull_all_sources_pulls_all_three_on_a_fresh_csv(tmp_path):
    csv_path = str(tmp_path / "weekly_data.csv")

    with patch("data_sources.pull_all_sources.pull_seatgeek") as mock_seatgeek, \
         patch("data_sources.pull_all_sources.pull_google_trends") as mock_trends, \
         patch("data_sources.pull_all_sources.pull_wikipedia_pageviews") as mock_wiki:
        mock_seatgeek.return_value = [{"week_start_date": "2026-08-10", "source": "seatgeek", "metric_name": "listing_count", "value": 10}]
        mock_trends.return_value = [{"week_start_date": "2026-08-10", "source": "google_trends", "metric_name": "search_interest_score", "value": 42}]
        mock_wiki.return_value = [{"week_start_date": "2026-08-10", "source": "wikipedia_pageviews", "metric_name": "pageview_count", "value": 3100}]

        summary = pull_all_sources(csv_path=csv_path, week_start_date=datetime.date(2026, 8, 10), seatgeek_client_id="fake-id")

    assert sorted(summary["pulled"]) == ["google_trends", "seatgeek", "wikipedia_pageviews"]
    assert summary["skipped"] == []
    assert summary["failed"] == []
    df = pd.read_csv(csv_path)
    assert len(df) == 3


def test_pull_all_sources_skips_a_source_already_pulled_this_week(tmp_path):
    csv_path = str(tmp_path / "weekly_data.csv")
    pd.DataFrame([{"week_start_date": "2026-08-10", "source": "seatgeek", "metric_name": "listing_count", "value": 10}]).to_csv(csv_path, index=False)

    with patch("data_sources.pull_all_sources.pull_seatgeek") as mock_seatgeek, \
         patch("data_sources.pull_all_sources.pull_google_trends") as mock_trends, \
         patch("data_sources.pull_all_sources.pull_wikipedia_pageviews") as mock_wiki:
        mock_trends.return_value = [{"week_start_date": "2026-08-10", "source": "google_trends", "metric_name": "search_interest_score", "value": 42}]
        mock_wiki.return_value = [{"week_start_date": "2026-08-10", "source": "wikipedia_pageviews", "metric_name": "pageview_count", "value": 3100}]

        summary = pull_all_sources(csv_path=csv_path, week_start_date=datetime.date(2026, 8, 10), seatgeek_client_id="fake-id")

    mock_seatgeek.assert_not_called()
    assert "seatgeek" in summary["skipped"]
    assert sorted(summary["pulled"]) == ["google_trends", "wikipedia_pageviews"]


def test_pull_all_sources_one_failure_does_not_block_the_others(tmp_path):
    csv_path = str(tmp_path / "weekly_data.csv")

    with patch("data_sources.pull_all_sources.pull_seatgeek") as mock_seatgeek, \
         patch("data_sources.pull_all_sources.pull_google_trends") as mock_trends, \
         patch("data_sources.pull_all_sources.pull_wikipedia_pageviews") as mock_wiki:
        mock_seatgeek.side_effect = Exception("SeatGeek API down")
        mock_trends.return_value = [{"week_start_date": "2026-08-10", "source": "google_trends", "metric_name": "search_interest_score", "value": 42}]
        mock_wiki.return_value = [{"week_start_date": "2026-08-10", "source": "wikipedia_pageviews", "metric_name": "pageview_count", "value": 3100}]

        summary = pull_all_sources(csv_path=csv_path, week_start_date=datetime.date(2026, 8, 10), seatgeek_client_id="fake-id")

    assert "seatgeek" in summary["failed"]
    assert sorted(summary["pulled"]) == ["google_trends", "wikipedia_pageviews"]
    df = pd.read_csv(csv_path)
    assert set(df["source"]) == {"google_trends", "wikipedia_pageviews"}


def test_pull_all_sources_missing_seatgeek_credentials_is_a_skip_not_a_failure(tmp_path):
    csv_path = str(tmp_path / "weekly_data.csv")

    with patch("data_sources.pull_all_sources.pull_google_trends") as mock_trends, \
         patch("data_sources.pull_all_sources.pull_wikipedia_pageviews") as mock_wiki:
        mock_trends.return_value = [{"week_start_date": "2026-08-10", "source": "google_trends", "metric_name": "search_interest_score", "value": 42}]
        mock_wiki.return_value = [{"week_start_date": "2026-08-10", "source": "wikipedia_pageviews", "metric_name": "pageview_count", "value": 3100}]

        summary = pull_all_sources(csv_path=csv_path, week_start_date=datetime.date(2026, 8, 10), seatgeek_client_id=None)

    assert "seatgeek" in summary["skipped"]
    assert "seatgeek" not in summary["failed"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_pull_all_sources.py -v`
Expected: FAIL — `ImportError: cannot import name 'pull_all_sources'`.

- [ ] **Step 3: Write minimal implementation**

Add to `data_sources/pull_all_sources.py` (imports at top, function + `__main__` block
at bottom):
```python
from data_sources.common import current_week_start_date
from data_sources.pull_google_trends import pull_google_trends
from data_sources.pull_seatgeek import MissingCredentialsError, pull_seatgeek
from data_sources.pull_wikipedia_pageviews import pull_wikipedia_pageviews

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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_pull_all_sources.py -v`
Expected: 9 passed (5 from Task 6 + 4 new).

- [ ] **Step 5: Run the full existing test suite to check for regressions**

Run: `pytest -v`
Expected: all tests pass, 0 failures.

- [ ] **Step 6: Commit**

```bash
git add data_sources/pull_all_sources.py tests/test_pull_all_sources.py
git commit -m "Add pull_all_sources orchestrator with idempotency check and CLI entry point"
```

---

### Task 8: GitHub Actions weekly workflow

**Files:**
- Create: `.github/workflows/weekly-data-pull.yml`

**Interfaces:**
- Consumes: `data_sources/pull_all_sources.py` (Task 7), `requirements.txt` (Task 1),
  the `SEATGEEK_CLIENT_ID` repo secret (set up manually by the user, not part of this
  plan).

- [ ] **Step 1: Write the workflow file**

Create `.github/workflows/weekly-data-pull.yml`:
```yaml
# Pulls this week's real-world Rams signals (SeatGeek ticket prices, Google Trends
# search interest, Wikipedia pageviews) and commits the updated
# data_sources/processed/weekly_data.csv back to the repo. Runs automatically every
# Monday morning, or on demand via the Actions tab ("Run workflow"). Safe to re-run
# mid-week — pull_all_sources.py skips any source already pulled for the current
# week, so this never duplicates a row.
name: Weekly Data Pull

on:
  schedule:
    - cron: "0 9 * * 1"  # Every Monday at 09:00 UTC
  workflow_dispatch: {}

# Prevent two concurrent runs (e.g. a manual trigger overlapping the schedule) from
# racing to commit and push at the same time.
concurrency:
  group: weekly-data-pull
  cancel-in-progress: false

permissions:
  contents: write

jobs:
  pull-and-commit:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout repo
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: Install dependencies
        run: pip install -r requirements.txt

      - name: Run weekly data pull
        env:
          SEATGEEK_CLIENT_ID: ${{ secrets.SEATGEEK_CLIENT_ID }}
        run: python data_sources/pull_all_sources.py

      - name: Commit and push updated data, if changed
        run: |
          git config user.name "github-actions[bot]"
          git config user.email "github-actions[bot]@users.noreply.github.com"
          if git diff --quiet -- data_sources/processed/weekly_data.csv; then
            echo "No changes to weekly_data.csv — nothing to commit."
          else
            git add data_sources/processed/weekly_data.csv
            git commit -m "Automated weekly data pull: $(date -u +'%Y-%m-%d')"
            git push
          fi
```

- [ ] **Step 2: Verify the YAML is well-formed**

Run: `python -c "import yaml, sys; yaml.safe_load(open('.github/workflows/weekly-data-pull.yml')); print('valid YAML')"`
(If `pyyaml` isn't installed, `pip install pyyaml` first — it's a one-off check, not
added to `requirements.txt`.)
Expected: `valid YAML`, no exception.

This is a syntax check only — the schedule trigger, secret injection, and commit/push
behavior can't be exercised locally. After pushing, verify no red "workflow file is
invalid" banner appears under the repo's **Actions** tab.

- [ ] **Step 3: Commit**

```bash
git add .github/workflows/weekly-data-pull.yml
git commit -m "Add weekly GitHub Actions workflow to pull and commit real-world data"
```

---

### Task 9: README "Data Refresh" section

**Files:**
- Modify: `README.md`

**Interfaces:** None (documentation only).

- [ ] **Step 1: Add a new `## Data Refresh` section**

Insert after `## How to run it` and before `## Repo layout`, matching the existing
first-person narrative prose style with bold key terms:

```markdown
## Data Refresh

Alongside the synthetic simulator, this repo also pulls three **real-world weekly
signals** about the LA Rams — SeatGeek home-game ticket prices, Google search
interest, and Wikipedia pageviews — and appends them to
[`data_sources/processed/weekly_data.csv`](data_sources/processed/weekly_data.csv).
This is a separate, standalone dataset; it isn't wired into the engagement score or
churn view, which stay fully synthetic and reproducible on purpose (see
[`docs/DECISION_LOG.md`](docs/DECISION_LOG.md)).

A [GitHub Actions workflow](.github/workflows/weekly-data-pull.yml) runs this
automatically every **Monday at 9am UTC**, and commits the updated CSV straight back
to the repo. The pipeline is **idempotent**: it checks which sources already have a
row for the current week before pulling anything, so triggering it again mid-week
never creates duplicate rows — it just skips whatever's already there.

To trigger a pull manually: open the **Actions** tab → **Weekly Data Pull** →
**Run workflow**.

One note on reliability: Google Trends is pulled via `pytrends`, an unofficial,
unauthenticated wrapper around Google's own interest data — there's no supported API
for it. It's retried a few times with backoff if it gets rate-limited, but it can
still occasionally fail or skip a week. That's expected behavior for a free,
unofficial data source, not a bug — the other two sources (SeatGeek, Wikipedia) are
unaffected when it happens, and the pull simply resumes the following week.
```

- [ ] **Step 2: Add `data_sources/` to the `## Repo layout` bullet list**

Insert a new bullet in `## Repo layout`, after the `scripts/run_season.py` bullet:
```markdown
- `data_sources/` — weekly real-world data pipeline: `pull_seatgeek.py`,
  `pull_google_trends.py`, `pull_wikipedia_pageviews.py`, `common.py` (shared
  normalization/retry helpers), `pull_all_sources.py` (the orchestrator run weekly by
  [`.github/workflows/weekly-data-pull.yml`](.github/workflows/weekly-data-pull.yml)) —
  see the "Data Refresh" section above
```

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "Document the weekly real-world data pull in README"
```

---

### Task 10: Decision log entries

**Files:**
- Modify: `docs/DECISION_LOG.md`

- [ ] **Step 1: Append new entries**

Add to the end of `docs/DECISION_LOG.md`, after the existing final entry, following
the established `## YYYY-MM-DD — Title` / `**Decision:**` / `**Why:**` /
`**Reference:**` format:

```markdown

---

## 2026-08-15 — Real-world weekly data pipeline added, kept separate from the simulator

**Decision:** Add a standalone weekly pipeline (`data_sources/`) that pulls three real
signals — SeatGeek ticket prices, Google Trends search interest, and Wikipedia
pageviews, all for the LA Rams — into `data_sources/processed/weekly_data.csv`, on an
automated weekly cadence via GitHub Actions. This data is not wired into
`season_simulator/`, `scoring/`, or `storage/db.py`.

**Why:** The engagement-score/churn pipeline's validation depends entirely on the
planted-churn cohort's known ground truth (see the 2026-08-12 entry) — mixing in real
external data there would blur that. This is instead a second, independent real-data
asset: a chance to demonstrate an actual data-collection pipeline (scheduled jobs,
external API integration, idempotent re-runs) without touching the part of the project
whose validity depends on staying synthetic.

**Reference:** [`docs/superpowers/specs/2026-08-15-weekly-data-scraping-design.md`](superpowers/specs/2026-08-15-weekly-data-scraping-design.md).

---

## 2026-08-15 — weekly_data.csv is committed to git, not gitignored

**Decision:** Unlike `data/weekly_snapshots/` and `data/fan_analytics.db`,
`data_sources/processed/weekly_data.csv` is tracked in git and pushed back to the repo
by the GitHub Actions workflow that generates it.

**Why:** GitHub Actions runners are ephemeral — each scheduled run starts from a fresh
checkout with no memory of prior runs. The idempotency check ("has this source already
been pulled this week?") reads the committed CSV to know what's already there; if the
file weren't committed, that check would be unanswerable and every run would start
from zero. Committing the CSV back *is* the pipeline's state store — there's no
database or artifact cache doing that job instead. It's also a genuinely accumulating
real-world dataset, unlike the fully-reproducible synthetic simulator output.
```

- [ ] **Step 2: Commit**

```bash
git add docs/DECISION_LOG.md
git commit -m "Record decisions for the real-world weekly data pipeline"
```

---

## Task 11 (controller-executed, not a subagent dispatch): Live verification

Not a subagent task — run directly by the controller session after Task 7 is
complete and reviewed clean, using the user's real `SEATGEEK_CLIENT_ID`:

1. Create a local `.env` file (already gitignored) with `SEATGEEK_CLIENT_ID=<real value>`.
2. Run `python data_sources/pull_all_sources.py`.
3. Inspect the printed summary and the resulting `data_sources/processed/weekly_data.csv`.
4. If SeatGeek's real response shape doesn't match what `pull_seatgeek.py`'s tests
   assumed (field names, structure), fix `pull_seatgeek.py` and its tests, following
   the same fix-round process used for task reviews, then re-run this verification.
5. Once correct, this run's output becomes the first committed rows of
   `weekly_data.csv` (commit separately, noting it's a live-verified seed, not part
   of a task's TDD commit).

## What's explicitly not in this plan

- Setting up the `SEATGEEK_CLIENT_ID` GitHub Actions secret — manual admin step the
  user does themselves (`gh secret set SEATGEEK_CLIENT_ID` or the Actions UI), not
  automatable, and the user has already confirmed they have credentials.
- Wiring `weekly_data.csv` into BigQuery, Power BI, or any notebook — out of scope per
  the design doc; a natural candidate for a future phase.
