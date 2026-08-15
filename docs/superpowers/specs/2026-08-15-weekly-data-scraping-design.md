# Real-World Weekly Data Scraping — Design

## Context

Everything built so far (MVP, Phase A's SQLite backbone, Phase B's BigQuery/Power BI
dashboard) runs entirely on the synthetic season simulator — there is no real-world
signal anywhere in the project. This phase adds one, deliberately kept separate from
the simulator: a small weekly pipeline that pulls three genuinely external, freely
available signals about the LA Rams — SeatGeek ticket listings, Google search
interest, and Wikipedia pageviews — normalizes them into one flat table, and appends
to it automatically every week via GitHub Actions.

This is intentionally *not* wired into `season_simulator/`, `scoring/`, or
`storage/db.py`. Those model a synthetic season with a planted-churn ground truth;
mixing in real external data would blur the one property that makes that validation
honest (see the 2026-08-12 decision log entry on why real data was deferred out of
Phase A). This phase is a standalone, additive data asset — real signals, on their
own timeline, in their own files — not a replacement or an input to the existing
pipeline.

## Goals

- Three independently pull-able, independently testable real data sources, each a
  plain importable function with no network calls at test time (same
  dependency-injection pattern `load_to_bigquery.py` already established with
  `client=None`).
- One orchestrator, `data_sources/pull_all_sources.py`, that determines "this week,"
  skips sources already pulled for it, calls the three pull functions, normalizes
  everything into one shape, and appends to a single accumulating CSV.
- Fully automated on a weekly cadence via GitHub Actions, re-runnable by hand, safe to
  re-run mid-week without duplicating rows.
- Graceful degradation: a missing credential, a rate-limited pytrends call, or a
  transient network blip on any one source should not stop the other two from being
  pulled, and should not be treated as a fatal error — it's expected, ordinary
  operation for free/unofficial APIs.

## Architecture & Data Flow

```
data_sources/pull_all_sources.py  (orchestrator; GitHub Actions entry point)
  ├─ data_sources/common.py         current_week_start_date(), normalize_metrics(),
  │                                 retry_with_backoff(), .env loading
  ├─ data_sources/pull_seatgeek.py            → SeatGeek Events API (requests)
  ├─ data_sources/pull_google_trends.py       → pytrends (wrapped in retry_with_backoff)
  └─ data_sources/pull_wikipedia_pageviews.py → Wikimedia REST Pageviews API (requests)
        │
        ▼
  data_sources/processed/weekly_data.csv   (long/tidy shape, committed to git)
        │
        ▼
  .github/workflows/weekly-data-pull.yml
    Monday 09:00 UTC (cron) + workflow_dispatch
    → checkout → setup-python → pip install -r requirements.txt
    → python data_sources/pull_all_sources.py   (SEATGEEK_CLIENT_ID from repo secret)
    → git diff on the CSV → commit + push back to the branch, if changed
```

Nothing here touches `season_simulator/`, `scoring/`, `storage/db.py`, or
`scripts/run_season.py`. This is a second, parallel top-level package, same level as
`scoring/` or `storage/`.

## Data shape

`data_sources/processed/weekly_data.csv`, one row per metric per source per week —
long/tidy, not wide, so adding a fourth source or a new metric later never requires a
schema migration, just new rows:

| column           | type   | example        |
|------------------|--------|----------------|
| `week_start_date`| date   | `2026-08-10`   |
| `source`         | string | `seatgeek`     |
| `metric_name`    | string | `avg_ticket_price` |
| `value`          | float  | `142.50`       |

**Metric names per source:**
- `seatgeek`: `avg_ticket_price`, `min_ticket_price`, `listing_count` — one aggregate
  set of rows across all upcoming Rams home games, not per-game. Keeps the common row
  shape identical across all three sources with no per-game identifier column needed.
- `google_trends`: `search_interest_score` (one row/week, pytrends' 0–100 index)
- `wikipedia_pageviews`: `pageview_count` (one row/week, summed daily views Mon–Sun)

## Key decisions

**`week_start_date` (a Monday date), not the `"2026-W33"` ISO-week string, is the
value actually stored and joined on.** The orchestrator still computes the ISO week
internally (via `date.today().isocalendar()`) to log a human-readable label, but
`date.fromisocalendar(iso_year, iso_week, 1)` — the Monday of that week — is the
column that goes in the CSV and the key the idempotency check uses. A plain ISO date
sorts and compares correctly with zero string-parsing logic anywhere downstream; an
ISO-week string doesn't, and has year-boundary edge cases (`"2026-W01"` vs
`"2025-W53"`) a date doesn't.

**Idempotency check is a straightforward read-then-diff, not a lock or a hash.** On
each run: compute this week's `week_start_date`; if `weekly_data.csv` exists, read it
and collect the *set* of `source` values already present for that `week_start_date`;
for each of the three sources, skip it (log, continue) if it's in that set, otherwise
pull it. This is correct for the actual failure mode that matters — a scheduled run
plus a manual re-trigger the same week — without needing cross-run locking, because
GitHub Actions runs this pipeline serially against a freshly checked-out copy of the
already-committed CSV each time.

**`weekly_data.csv` is committed to git, not gitignored** — unlike
`data/weekly_snapshots/` and `data/fan_analytics.db`. Two reasons: (1) it's a
genuinely valuable, accumulating real-world dataset, unlike the simulator's fully
reproducible synthetic output; (2) GitHub Actions runners are ephemeral — every
scheduled run starts from a fresh checkout with no memory of prior runs. If the CSV
weren't committed and pushed back, "already pulled this week" would be unanswerable
and every Monday would silently re-pull from scratch (and worse, a same-week manual
re-trigger would duplicate rows). Committing the CSV back to the repo *is* the
pipeline's only state store — there's no database, cache, or artifact storage doing
that job instead.

**No raw/intermediate scrape files are written to disk anywhere.** Each `pull_*.py`
function returns already-normalized rows in memory; the orchestrator appends them
straight to `weekly_data.csv`. No new `.gitignore` entries are needed — `.env`/
`.env.local` are already covered.

**Retry-with-backoff is scoped to the pytrends call only**, per the explicit
requirement and pytrends' status as an unofficial, unauthenticated API prone to rate
limiting, living as a small reusable `retry_with_backoff(func, *args,
max_attempts=3, base_delay_seconds=1, sleep_fn=time.sleep, **kwargs)` helper in
`data_sources/common.py` rather than hand-rolled inside `pull_google_trends.py`.
`sleep_fn` is injectable so tests never actually sleep. Delay is
`base_delay_seconds * 2 ** attempt_index` between attempts (not after the final
failed attempt). SeatGeek and Wikipedia are official-enough REST APIs with generous
limits that they're called once per run, uncaught at that layer — a transient failure
there surfaces as an ordinary "failed" entry in the run summary rather than being
retried.

**Error-handling philosophy: one source's failure never blocks the others.** Each
`pull_*.py` function raises on failure — it never prints or swallows errors itself,
consistent with this repo's existing convention that `print()` only happens at the
orchestration boundary, never inside library functions. `pull_all_sources()` wraps
each of the three calls in its own `try/except`, so a SeatGeek outage still lets
Google Trends and Wikipedia run, and the run summary distinguishes three outcomes per
source: `pulled`, `skipped` (already pulled this week, or missing credentials for
seatgeek specifically), and `failed` (raised, after any retries).

**Missing `SEATGEEK_CLIENT_ID` is treated as a graceful skip, not a crash.**
`pull_seatgeek()` raises a specific `MissingCredentialsError` (a small subclass of
`ValueError`) when the credential isn't set; the orchestrator catches that type
separately from a generic `Exception` and records it under `skipped` with a reason,
not `failed`. This means the pipeline runs cleanly for local development or CI dry
runs before `SEATGEEK_CLIENT_ID` is configured, without any separate "mock mode" flag
— the same code path degrades gracefully whether the credential is genuinely absent or
just not yet set up.

**Wikipedia's `User-Agent` header identifies this repo**, per Wikimedia's API
etiquette policy which asks for a real, contact-identifying value rather than a
generic default:
`"rams-consumer-analytics/1.0 (https://github.com/vsofelka/Rams_Consumer_Analytics)"`.

**GitHub Actions commit-back cannot retrigger itself**, because the workflow's only
triggers are `schedule` and `workflow_dispatch` — no `push` trigger exists to loop on.
The workflow still sets `concurrency: { group: weekly-data-pull, cancel-in-progress:
false }` so two overlapping manual triggers serialize instead of racing to push, and
commits only as `github-actions[bot]` — no personal identity.

**One live verification pass before merge.** All automated tests use mocked HTTP
clients — none of them confirm SeatGeek's real API response shape (field names like
`lowest_price`/`average_price`) matches what the tests assume. After the orchestration
task is built, the implementing session runs `python data_sources/pull_all_sources.py`
once locally with a real `SEATGEEK_CLIENT_ID`, fixes any field-name mismatches, and
lets that run seed the first real rows of `weekly_data.csv` — the same pattern used to
verify the BigQuery load against live infrastructure in the prior phase.

## Explicitly out of scope (this pass)

- Wiring this data into `scoring/`, `storage/db.py`, BigQuery, or Power BI — this is a
  standalone real-data asset, not an input to the existing synthetic pipeline. A
  future phase could join on `week_start_date`; not this one.
- Historical backfill — the pipeline starts accumulating from whenever it's first
  run; no attempt to reconstruct past weeks' ticket prices/trends/pageviews.
- Any source beyond SeatGeek, Google Trends, and Wikipedia pageviews.
- A retry/backoff wrapper around SeatGeek or Wikipedia calls (only pytrends, per the
  explicit requirement and its unofficial-API rate-limiting risk).
- Alerting/notification on repeated pipeline failures (e.g. Slack/email) — the run
  summary printed to the Actions log is the only visibility for now.
- Setting up the `SEATGEEK_CLIENT_ID` GitHub Actions repo secret — manual admin step
  the user does themselves, not automatable.
