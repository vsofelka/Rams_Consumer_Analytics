# Power BI + BigQuery Dashboard — Design

## Context

The MVP (synthetic season simulator → rolling engagement score → rule-based churn view → notebooks) and Phase A (SQLite backbone + statistical validation, see `docs/superpowers/specs/2026-08-12-sql-stats-backbone-design.md`) are both complete. That earlier doc's Phase B named a Streamlit dashboard as the next step. **This design supersedes that Phase B decision.**

Two things changed the plan:

1. The job posting explicitly names Power BI twice — once for dashboards/reports/visualizations, once under reporting-software experience — which Streamlit is not mentioned anywhere in. Power BI is a stronger, JD-grounded choice.
2. Building the dashboard as flat-file-fed Power BI wouldn't put any SQL on screen, so a cloud warehouse layer (BigQuery) was added underneath it — the point being that the report queries a real warehouse with real SQL doing some of the row-level work, not just DAX over static files.

The existing Extract (`season_simulator/`) and Transform (`scoring/`) stages are untouched. This design covers the two new stages — **Load** (into BigQuery) and **Visualize** (Power BI) — plus the documentation that ties them together.

GCP setup already completed as a prerequisite: project `rams-fan-analytics` created, BigQuery API enabled, `gcloud` CLI authenticated (both user login and Application Default Credentials for client-library use — no service-account key file exists or is ever committed).

## Goals

- Get the same validated data (`fans`, `weekly_snapshots`) into BigQuery without touching the SQLite layer or notebooks Phase A already built.
- Put real, explainable SQL in the warehouse itself — not just `SELECT *` — by porting notebook 04's window-function and join/aggregation queries into BigQuery views.
- Build a Power BI report that queries BigQuery directly (native connector, real credentials, real SQL) and does live, slicer-driven computation via DAX — a stronger "I built this" story than a static dashboard.
- Keep it reproducible: one script to (re-)load the warehouse, one guide to (re-)build the report.

## Architecture & Data Flow

```
season_simulator ─┐
                   ├─→ scoring (engagement.py, churn.py) ─→ scripts/run_season.py ─→ data/fan_analytics.db (SQLite, unchanged)
                   │
                   └─→ scripts/load_to_bigquery.py (new) ─→ BigQuery: rams-fan-analytics.rams_fan_analytics
                                                                  ├─ fans (table)
                                                                  ├─ weekly_snapshots (table)
                                                                  ├─ v_engagement_trend (view)
                                                                  ├─ v_tier_by_plan (view)
                                                                  └─ v_at_risk_current (view)
                                                                        │
                                                                        └─→ Power BI Desktop (native BigQuery connector)
                                                                              → Fan_Engagement_Dashboard.pbix
```

`scripts/load_to_bigquery.py` reads from `data/fan_analytics.db` (never re-runs the simulator or scoring code directly — same decoupling principle every other stage already follows) and is the only new code artifact that talks to Google Cloud.

## Schema (BigQuery)

Identical shape to the existing SQLite tables, so the Load step is a straight copy, not a remodel:

- **`fans`** (dimension): `fan_id` (INT64), `tenure_years` (INT64), `plan_tier` (STRING), `baseline_engagement` (FLOAT64), `is_planted_churn` (BOOL), `decline_start_week` (FLOAT64)
- **`weekly_snapshots`** (fact): `fan_id` (INT64), `week` (INT64), `engagement_score` (FLOAT64), `tier` (STRING), `at_risk` (BOOL)

BigQuery has no enforced foreign keys or primary keys (they're declarative/informational only), so referential integrity is guaranteed by the load step reading from the already-validated SQLite db, not by warehouse-side constraints.

## Load step (`scripts/load_to_bigquery.py`)

- Connects via `google.cloud.bigquery.Client(project="rams-fan-analytics")` — picks up Application Default Credentials automatically, no key file.
- Creates the `rams_fan_analytics` dataset if it doesn't exist (location `US`, matching BigQuery's free-tier default region).
- Loads `fans` and `weekly_snapshots` from the SQLite db using `load_table_from_dataframe(..., write_disposition="WRITE_TRUNCATE")` — idempotent and safe to re-run, same regenerate-cleanly convention as `run_season.py`.
- Runs three `CREATE OR REPLACE VIEW` statements (below) so re-running the script also keeps the views in sync with any schema changes.
- New dependencies: `google-cloud-bigquery>=3.0`, `db-dtypes>=1.0`, `pyarrow>=14.0` (added to `requirements.txt`).
- SQLite has no native boolean type — `is_planted_churn` and `at_risk` are stored there as `INTEGER` (0/1). The loader casts both to Python `bool` before the `load_table_from_dataframe` call so they land as BigQuery `BOOL`, matching the schema above and letting DAX use them directly as logical filters.

### Views — the SQL-skill artifact

Ported directly from `notebooks/04_sql_analysis.ipynb`'s SQLite queries into BigQuery Standard SQL, same logic and same justification, so nothing here is arbitrary or newly invented:

**`v_engagement_trend`** — week-over-week score delta via a window function:
```sql
CREATE OR REPLACE VIEW `rams_fan_analytics.v_engagement_trend` AS
SELECT
  fan_id,
  week,
  engagement_score,
  engagement_score - LAG(engagement_score) OVER (PARTITION BY fan_id ORDER BY week) AS score_delta
FROM `rams_fan_analytics.weekly_snapshots`
```

**`v_tier_by_plan`** — average engagement by plan tier over time, a join + aggregation:
```sql
CREATE OR REPLACE VIEW `rams_fan_analytics.v_tier_by_plan` AS
SELECT
  w.week,
  f.plan_tier,
  AVG(w.engagement_score) AS avg_engagement_score,
  COUNT(*) AS n_fans
FROM `rams_fan_analytics.weekly_snapshots` w
JOIN `rams_fan_analytics.fans` f ON w.fan_id = f.fan_id
GROUP BY w.week, f.plan_tier
```

**`v_at_risk_current`** — the latest week's at-risk list, reconstructed with a CTE:
```sql
CREATE OR REPLACE VIEW `rams_fan_analytics.v_at_risk_current` AS
WITH final_week AS (
  SELECT MAX(week) AS max_week FROM `rams_fan_analytics.weekly_snapshots`
)
SELECT w.fan_id, w.engagement_score, w.tier
FROM `rams_fan_analytics.weekly_snapshots` w, final_week
WHERE w.week = final_week.max_week AND w.at_risk = TRUE
ORDER BY w.engagement_score ASC
```

## Visualize step (Power BI)

- **Connection:** Power BI Desktop's native "Get Data → Google BigQuery" connector, OAuth sign-in with the same Google account, Import mode (chosen over DirectQuery for reliability — the report should open and work without a live BigQuery round-trip on every interaction, and this dataset is tiny enough that Import has no real downside).
- **Model:** star schema, `fans` (1) — (\*) `weekly_snapshots` on `fan_id`. The three views load in as additional tables available to visuals directly (not related into the star schema — they're pre-shaped for specific charts, not dimensional data).
- **DAX measures** (the interactive layer — things that must respond live to whatever week a slicer is on, which is exactly the job SQL views can't do since they're not filter-context-aware):
  - `True Positives`, `False Positives`, `False Negatives` — `CALCULATE`/`FILTER` over `weekly_snapshots`, joined to `fans[is_planted_churn]` via `RELATED`
  - `Precision`, `Recall`, `F1` — derived from the above
  - `At-Risk Count`, tier counts — simple filtered counts
- **Pages:**
  1. **Season Trend** (ignores the week slicer) — precision/recall/F1 line chart across all 18 weeks (sourced from the DAX measures evaluated per-week via a matrix/line visual), tier mix over time from `v_tier_by_plan`.
  2. **Weekly Snapshot** (driven by a week slicer) — tier tiles, at-risk table, KPI cards, all responsive to the selected week.
  3. **Fan Drill-Through** — right-click a flagged fan → their individual engagement trend across the season (from `v_engagement_trend`), with the planted-churn ground-truth flag shown.
- Explicitly **not attempted**: hand-authoring the `.pbix`/`.pbip` project file directly. I can't run Power BI Desktop to verify a hand-written project file would load correctly, and a broken file wastes more time than it saves. Instead: the data/views above, an exact DAX reference, and a step-by-step build guide — assembly happens in the GUI.

## Documentation

- `docs/powerbi/build_guide.md` (new) — exact steps: connect, model, paste-in DAX, pages/visuals per page.
- `docs/powerbi/dax_measures.md` (new) — the full DAX reference, one measure per section with a one-line rationale.
- `docs/DECISION_LOG.md` — new entries: the Power BI-over-Streamlit pivot (JD-grounded), the BigQuery-over-Snowflake choice (free tier persists indefinitely vs. a 30-day trial credit), and the ODBC-vs-native-connector non-issue (BigQuery has a native Power BI connector, so this question that blocked the SQLite-based approach doesn't apply).
- `README.md` — updated once the dashboard exists to remove the "no dashboard yet" scope note.

## Testing

- `tests/test_load_to_bigquery.py` — unit tests for any pure logic in the loader (e.g., dataframe-shape validation before load) that doesn't require live network/credentials — consistent with `pytest -v` running with zero external dependencies.
- The load script's actual end-to-end run against real BigQuery is **manual verification, not part of the automated suite** (same reasoning as not unit-testing `run_season.py`'s full pipeline execution) — I'll run it once after implementation and sanity-check row counts and the week-18 at-risk count against `docs/RESULTS.md`'s already-validated numbers before handing off the build guide.

## Out of scope (this pass)

- Swapping in a real (non-synthetic) data source — no concrete dataset available yet, unchanged from the Phase A decision.
- DirectQuery mode — Import chosen for reliability; revisit only if a "live query" demo moment becomes worth the added complexity.
- Generating a `.pbip`/TMDL project file programmatically — see rationale above.
- Phase C from the Phase A design (scaling the population to ~2,000+ fans) — unaffected, still deferred.
