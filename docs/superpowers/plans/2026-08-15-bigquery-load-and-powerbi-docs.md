# BigQuery Load + Power BI Docs Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Load the existing validated `fans`/`weekly_snapshots` data into BigQuery (tables + three analytical SQL views), and produce the documentation (DAX reference, build guide, decision log entries) needed to build the Power BI report on top of it.

**Architecture:** A new standalone script, `scripts/load_to_bigquery.py`, reads from the existing `data/fan_analytics.db` SQLite file (untouched — same file notebook 04 already uses) and loads two tables plus three views into BigQuery project `rams-fan-analytics`, dataset `rams_fan_analytics`. Every BigQuery-calling function takes the client as a parameter, so tests inject a mock client and never touch the network. The Power BI report itself is built manually in the Power BI Desktop GUI by the user, following the build guide this plan produces — that GUI work is not part of this plan.

**Tech Stack:** Python, `google-cloud-bigquery`, pandas, sqlite3, pytest, unittest.mock.

## Global Constraints

- New dependencies (`requirements.txt`): `google-cloud-bigquery>=3.0`, `db-dtypes>=1.0`, `pyarrow>=14.0`
- BigQuery project: `rams-fan-analytics`; dataset: `rams_fan_analytics`; location: `US`
- Tables: `fans` (fan_id, tenure_years, plan_tier, baseline_engagement, is_planted_churn, decline_start_week), `weekly_snapshots` (fan_id, week, engagement_score, tier, at_risk)
- `is_planted_churn` and `at_risk` come back from SQLite as 0/1 integers and MUST be cast to Python `bool` before loading, so they land as BigQuery `BOOL`
- Loads use `WRITE_TRUNCATE` — re-running the script is always safe
- No service-account key files anywhere — auth is Application Default Credentials only (already configured on this machine)
- No task in this plan may make a real network call to Google Cloud inside the automated test suite — BigQuery-calling functions must accept an injectable client so tests use `unittest.mock.MagicMock`
- The one real (non-mocked) run against live BigQuery is a manual verification step at the end of this plan, checked against the numbers already in `docs/RESULTS.md` (week-18 tier counts: Super Fan 70, Engaged 81, Cooling 73, Dormant 76; at-risk count 13)

---

### Task 1: Add BigQuery dependencies

**Files:**
- Modify: `requirements.txt`

**Interfaces:**
- Produces: `google.cloud.bigquery`, `db_dtypes`, `pyarrow` importable in the environment for every later task.

- [ ] **Step 1: Add the three new lines to `requirements.txt`**

Append to the end of the existing file:
```
google-cloud-bigquery>=3.0
db-dtypes>=1.0
pyarrow>=14.0
```

- [ ] **Step 2: Install them**

Run: `pip install -r requirements.txt`
Expected: all three packages install with no errors.

- [ ] **Step 3: Verify the import works**

Run: `python -c "from google.cloud import bigquery; print(bigquery.__version__)"`
Expected: prints a version string (e.g. `3.x.x`), no `ImportError`.

- [ ] **Step 4: Commit**

```bash
git add requirements.txt
git commit -m "Add BigQuery client dependencies"
```

---

### Task 2: SQLite read functions with bool casting

**Files:**
- Create: `scripts/load_to_bigquery.py`
- Test: `tests/test_load_to_bigquery.py`

**Interfaces:**
- Consumes: `storage.db.create_schema`, `storage.db.write_fans`, `storage.db.write_weekly_snapshot` (existing, from `storage/db.py`) — used only in tests, to build a fixture SQLite db.
- Produces: `read_fans(db_path: str) -> pd.DataFrame` (columns: fan_id, tenure_years, plan_tier, baseline_engagement, is_planted_churn [bool], decline_start_week). `read_weekly_snapshots(db_path: str) -> pd.DataFrame` (columns: fan_id, week, engagement_score, tier, at_risk [bool]).

- [ ] **Step 1: Write the failing tests**

Create `tests/test_load_to_bigquery.py`:
```python
import sqlite3

import pandas as pd

from storage.db import create_schema, write_fans, write_weekly_snapshot
from scripts.load_to_bigquery import read_fans, read_weekly_snapshots


def _fans_fixture():
    return pd.DataFrame({
        "fan_id": [1, 2],
        "tenure_years": [3, 7],
        "plan_tier": ["standard", "premium"],
        "baseline_engagement": [0.4, 0.8],
        "is_planted_churn": [True, False],
        "decline_start_week": [6.0, None],
    })


def _weekly_snapshots_fixture():
    return pd.DataFrame({
        "fan_id": [1, 2],
        "week": [1, 1],
        "engagement_score": [55.0, 80.0],
        "tier": ["Cooling", "Engaged"],
        "at_risk": [True, False],
    })


def test_read_fans_casts_is_planted_churn_to_bool(tmp_path):
    db_path = str(tmp_path / "test.db")
    conn = sqlite3.connect(db_path)
    create_schema(conn)
    write_fans(conn, _fans_fixture())
    conn.close()

    fans = read_fans(db_path)

    assert fans["is_planted_churn"].dtype == bool
    assert list(fans["is_planted_churn"]) == [True, False]
    assert len(fans) == 2


def test_read_weekly_snapshots_casts_at_risk_to_bool(tmp_path):
    db_path = str(tmp_path / "test.db")
    conn = sqlite3.connect(db_path)
    create_schema(conn)
    write_weekly_snapshot(conn, _weekly_snapshots_fixture())
    conn.close()

    snapshots = read_weekly_snapshots(db_path)

    assert snapshots["at_risk"].dtype == bool
    assert list(snapshots["at_risk"]) == [True, False]
    assert len(snapshots) == 2
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_load_to_bigquery.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'scripts.load_to_bigquery'` (file doesn't exist yet).

- [ ] **Step 3: Write minimal implementation**

Create `scripts/load_to_bigquery.py`:
```python
import sqlite3

import pandas as pd
from google.cloud import bigquery


def read_fans(db_path):
    conn = sqlite3.connect(db_path)
    try:
        fans = pd.read_sql("SELECT * FROM fans", conn)
    finally:
        conn.close()
    fans["is_planted_churn"] = fans["is_planted_churn"].astype(bool)
    return fans


def read_weekly_snapshots(db_path):
    conn = sqlite3.connect(db_path)
    try:
        snapshots = pd.read_sql("SELECT * FROM weekly_snapshots", conn)
    finally:
        conn.close()
    snapshots["at_risk"] = snapshots["at_risk"].astype(bool)
    return snapshots
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_load_to_bigquery.py -v`
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add scripts/load_to_bigquery.py tests/test_load_to_bigquery.py
git commit -m "Add SQLite read functions for BigQuery load, with bool casting"
```

---

### Task 3: Dataset creation and table load functions

**Files:**
- Modify: `scripts/load_to_bigquery.py`
- Test: `tests/test_load_to_bigquery.py`

**Interfaces:**
- Consumes: `google.cloud.bigquery` (already imported in Task 2).
- Produces: `ensure_dataset(client, project_id: str, dataset_id: str, location: str = "US") -> None`. `load_dataframe(client, project_id: str, dataset_id: str, table_id: str, dataframe: pd.DataFrame) -> None`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_load_to_bigquery.py`:
```python
from unittest.mock import MagicMock

from scripts.load_to_bigquery import ensure_dataset, load_dataframe


def test_ensure_dataset_creates_dataset_with_exists_ok():
    client = MagicMock()

    ensure_dataset(client, "rams-fan-analytics", "rams_fan_analytics", location="US")

    client.create_dataset.assert_called_once()
    args, kwargs = client.create_dataset.call_args
    dataset_arg = args[0]
    assert isinstance(dataset_arg, bigquery.Dataset)
    assert dataset_arg.dataset_id == "rams_fan_analytics"
    assert dataset_arg.location == "US"
    assert kwargs["exists_ok"] is True


def test_load_dataframe_truncates_and_waits_for_job():
    client = MagicMock()
    job = MagicMock()
    client.load_table_from_dataframe.return_value = job
    df = pd.DataFrame({"fan_id": [1, 2]})

    load_dataframe(client, "rams-fan-analytics", "rams_fan_analytics", "fans", df)

    args, kwargs = client.load_table_from_dataframe.call_args
    assert args[0] is df
    assert args[1] == "rams-fan-analytics.rams_fan_analytics.fans"
    assert kwargs["job_config"].write_disposition == bigquery.WriteDisposition.WRITE_TRUNCATE
    job.result.assert_called_once()
```

This test file needs `bigquery` imported directly too — add `from google.cloud import bigquery` to the top of `tests/test_load_to_bigquery.py` alongside the existing imports.

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_load_to_bigquery.py -v`
Expected: FAIL — `ImportError: cannot import name 'ensure_dataset'`.

- [ ] **Step 3: Write minimal implementation**

Add to `scripts/load_to_bigquery.py`:
```python
def ensure_dataset(client, project_id, dataset_id, location="US"):
    dataset_ref = bigquery.DatasetReference(project_id, dataset_id)
    dataset = bigquery.Dataset(dataset_ref)
    dataset.location = location
    client.create_dataset(dataset, exists_ok=True)


def load_dataframe(client, project_id, dataset_id, table_id, dataframe):
    table_ref = f"{project_id}.{dataset_id}.{table_id}"
    job_config = bigquery.LoadJobConfig(write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE)
    job = client.load_table_from_dataframe(dataframe, table_ref, job_config=job_config)
    job.result()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_load_to_bigquery.py -v`
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add scripts/load_to_bigquery.py tests/test_load_to_bigquery.py
git commit -m "Add BigQuery dataset creation and dataframe load functions"
```

---

### Task 4: Analytical SQL views

**Files:**
- Modify: `scripts/load_to_bigquery.py`
- Test: `tests/test_load_to_bigquery.py`

**Interfaces:**
- Produces: `create_views(client, project_id: str, dataset_id: str) -> None` — runs three `CREATE OR REPLACE VIEW` statements (`v_engagement_trend`, `v_tier_by_plan`, `v_at_risk_current`) via `client.query(sql).result()`.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_load_to_bigquery.py`:
```python
from scripts.load_to_bigquery import create_views


def test_create_views_runs_three_create_or_replace_statements():
    client = MagicMock()
    query_job = MagicMock()
    client.query.return_value = query_job

    create_views(client, "rams-fan-analytics", "rams_fan_analytics")

    assert client.query.call_count == 3
    executed_sql = [call.args[0] for call in client.query.call_args_list]
    assert all("CREATE OR REPLACE VIEW" in sql for sql in executed_sql)
    assert any("v_engagement_trend" in sql and "LAG(" in sql for sql in executed_sql)
    assert any("v_tier_by_plan" in sql and "JOIN" in sql for sql in executed_sql)
    assert any("v_at_risk_current" in sql and "WITH final_week" in sql for sql in executed_sql)
    assert query_job.result.call_count == 3
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_load_to_bigquery.py -v`
Expected: FAIL — `ImportError: cannot import name 'create_views'`.

- [ ] **Step 3: Write minimal implementation**

Add to `scripts/load_to_bigquery.py`:
```python
def _view_queries(project_id, dataset_id):
    fq = f"{project_id}.{dataset_id}"
    return {
        "v_engagement_trend": f"""
CREATE OR REPLACE VIEW `{fq}.v_engagement_trend` AS
SELECT
  fan_id,
  week,
  engagement_score,
  engagement_score - LAG(engagement_score) OVER (PARTITION BY fan_id ORDER BY week) AS score_delta
FROM `{fq}.weekly_snapshots`
""",
        "v_tier_by_plan": f"""
CREATE OR REPLACE VIEW `{fq}.v_tier_by_plan` AS
SELECT
  w.week,
  f.plan_tier,
  AVG(w.engagement_score) AS avg_engagement_score,
  COUNT(*) AS n_fans
FROM `{fq}.weekly_snapshots` w
JOIN `{fq}.fans` f ON w.fan_id = f.fan_id
GROUP BY w.week, f.plan_tier
""",
        "v_at_risk_current": f"""
CREATE OR REPLACE VIEW `{fq}.v_at_risk_current` AS
WITH final_week AS (
  SELECT MAX(week) AS max_week FROM `{fq}.weekly_snapshots`
)
SELECT w.fan_id, w.engagement_score, w.tier
FROM `{fq}.weekly_snapshots` w, final_week
WHERE w.week = final_week.max_week AND w.at_risk = TRUE
ORDER BY w.engagement_score ASC
""",
    }


def create_views(client, project_id, dataset_id):
    for sql in _view_queries(project_id, dataset_id).values():
        client.query(sql).result()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_load_to_bigquery.py -v`
Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add scripts/load_to_bigquery.py tests/test_load_to_bigquery.py
git commit -m "Add BigQuery view creation for the notebook-04 analytical queries"
```

---

### Task 5: Orchestration, CLI entry point, and live verification

**Files:**
- Modify: `scripts/load_to_bigquery.py`
- Test: `tests/test_load_to_bigquery.py`

**Interfaces:**
- Consumes: `read_fans`, `read_weekly_snapshots`, `ensure_dataset`, `load_dataframe`, `create_views` (all from Tasks 2–4).
- Produces: `load_to_bigquery(db_path: str, project_id: str, dataset_id: str, client=None) -> dict` with keys `fans_rows`, `weekly_snapshots_rows`. CLI: `python scripts/load_to_bigquery.py`.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_load_to_bigquery.py`:
```python
from scripts.load_to_bigquery import load_to_bigquery


def test_load_to_bigquery_orchestrates_full_load(tmp_path):
    db_path = str(tmp_path / "test.db")
    conn = sqlite3.connect(db_path)
    create_schema(conn)
    write_fans(conn, _fans_fixture())
    write_weekly_snapshot(conn, _weekly_snapshots_fixture())
    conn.close()

    client = MagicMock()
    client.load_table_from_dataframe.return_value = MagicMock()
    client.query.return_value = MagicMock()

    result = load_to_bigquery(db_path, "rams-fan-analytics", "rams_fan_analytics", client=client)

    assert result == {"fans_rows": 2, "weekly_snapshots_rows": 2}
    client.create_dataset.assert_called_once()
    assert client.load_table_from_dataframe.call_count == 2
    assert client.query.call_count == 3
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_load_to_bigquery.py -v`
Expected: FAIL — `ImportError: cannot import name 'load_to_bigquery'`.

- [ ] **Step 3: Write minimal implementation**

Add to `scripts/load_to_bigquery.py`:
```python
def load_to_bigquery(db_path, project_id, dataset_id, client=None):
    if client is None:
        client = bigquery.Client(project=project_id)

    ensure_dataset(client, project_id, dataset_id)

    fans = read_fans(db_path)
    load_dataframe(client, project_id, dataset_id, "fans", fans)

    weekly_snapshots = read_weekly_snapshots(db_path)
    load_dataframe(client, project_id, dataset_id, "weekly_snapshots", weekly_snapshots)

    create_views(client, project_id, dataset_id)

    return {"fans_rows": len(fans), "weekly_snapshots_rows": len(weekly_snapshots)}


if __name__ == "__main__":
    summary = load_to_bigquery(
        db_path="data/fan_analytics.db",
        project_id="rams-fan-analytics",
        dataset_id="rams_fan_analytics",
    )
    print(
        f"Loaded {summary['fans_rows']} fans and "
        f"{summary['weekly_snapshots_rows']} weekly snapshot rows into BigQuery."
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_load_to_bigquery.py -v`
Expected: 6 passed.

- [ ] **Step 5: Run the full existing test suite to check for regressions**

Run: `pytest -v`
Expected: all tests pass (previous suite + the 6 new tests), 0 failures.

- [ ] **Step 6: Commit**

```bash
git add scripts/load_to_bigquery.py tests/test_load_to_bigquery.py
git commit -m "Add load_to_bigquery orchestration and CLI entry point"
```

- [ ] **Step 7: Manual verification against real BigQuery**

This is the one step in this plan that touches live infrastructure — not part of the automated suite.

Run:
```bash
python scripts/run_season.py
python scripts/load_to_bigquery.py
```
Expected console output: `Loaded 300 fans and 5400 weekly snapshot rows into BigQuery.` (300 fans × 18 weeks).

Then verify against the numbers already validated in `docs/RESULTS.md`:
```bash
"/c/Users/vsofe/AppData/Local/Google/Cloud SDK/google-cloud-sdk/bin/bq" query --use_legacy_sql=false \
  "SELECT tier, COUNT(*) AS n FROM \`rams-fan-analytics.rams_fan_analytics.weekly_snapshots\` WHERE week = 18 GROUP BY tier ORDER BY tier"
```
Expected: Cooling 73, Dormant 76, Engaged 81, Super Fan 70 (matches `RESULTS.md`'s "Tier distribution" line).

```bash
"/c/Users/vsofe/AppData/Local/Google/Cloud SDK/google-cloud-sdk/bin/bq" query --use_legacy_sql=false \
  "SELECT COUNT(*) AS n FROM \`rams-fan-analytics.rams_fan_analytics.weekly_snapshots\` WHERE week = 18 AND at_risk = TRUE"
```
Expected: 13 (matches `RESULTS.md`'s "At-risk flags" line).

If either number doesn't match, stop and diagnose before proceeding to Task 6 — the views and later Power BI work all depend on this data being correct.

---

### Task 6: DAX measures reference

**Files:**
- Create: `docs/powerbi/dax_measures.md`

**Interfaces:**
- Produces: a markdown file the build guide (Task 7) links to and the user copy-pastes measures from into Power BI Desktop.

- [ ] **Step 1: Write the file**

Create `docs/powerbi/dax_measures.md`:
```markdown
# DAX Measures Reference

All measures live on the `weekly_snapshots` table. They rely on the `fans` 1—* `weekly_snapshots` relationship (on `fan_id`) set up in the build guide's model step — referencing `fans[is_planted_churn]` inside `CALCULATE` on `weekly_snapshots` works because that relationship auto-propagates the filter.

Every measure below is filter-context-aware: it recomputes correctly whether the current context is a week slicer, a single point on a line chart, or a matrix cell.

## Confusion-matrix building blocks

**True Positives** — flagged at-risk, and really one of the 25 planted churners:
```
True Positives = 
CALCULATE(
    COUNTROWS(weekly_snapshots),
    fans[is_planted_churn] = TRUE,
    weekly_snapshots[at_risk] = TRUE
)
```

**False Positives** — flagged at-risk, but not actually a planted churner:
```
False Positives = 
CALCULATE(
    COUNTROWS(weekly_snapshots),
    fans[is_planted_churn] = FALSE,
    weekly_snapshots[at_risk] = TRUE
)
```

**False Negatives** — a planted churner the rule missed that week:
```
False Negatives = 
CALCULATE(
    COUNTROWS(weekly_snapshots),
    fans[is_planted_churn] = TRUE,
    weekly_snapshots[at_risk] = FALSE
)
```

## Detection metrics

```
Precision = 
VAR TP = [True Positives]
VAR FP = [False Positives]
RETURN
DIVIDE(TP, TP + FP)
```

```
Recall = 
VAR TP = [True Positives]
VAR FN = [False Negatives]
RETURN
DIVIDE(TP, TP + FN)
```

```
F1 Score = 
VAR P = [Precision]
VAR R = [Recall]
RETURN
DIVIDE(2 * P * R, P + R)
```

`DIVIDE` returns blank instead of erroring on a divide-by-zero week (e.g. before any fan has been flagged), which reads cleanly as "no data" on a chart rather than crashing the visual.

## At-risk and tier counts

```
At-Risk Count = 
CALCULATE(
    COUNTROWS(weekly_snapshots),
    weekly_snapshots[at_risk] = TRUE
)
```

```
Super Fan Count = 
CALCULATE(
    COUNTROWS(weekly_snapshots),
    weekly_snapshots[tier] = "Super Fan"
)
```

```
Engaged Count = 
CALCULATE(
    COUNTROWS(weekly_snapshots),
    weekly_snapshots[tier] = "Engaged"
)
```

```
Cooling Count = 
CALCULATE(
    COUNTROWS(weekly_snapshots),
    weekly_snapshots[tier] = "Cooling"
)
```

```
Dormant Count = 
CALCULATE(
    COUNTROWS(weekly_snapshots),
    weekly_snapshots[tier] = "Dormant"
)
```

These four automatically sum to the total fan count in whatever week context is active, since `tier` is mutually exclusive per fan per week.
```

- [ ] **Step 2: Commit**

```bash
git add docs/powerbi/dax_measures.md
git commit -m "Add DAX measures reference for the Power BI report"
```

---

### Task 7: Power BI build guide

**Files:**
- Create: `docs/powerbi/build_guide.md`

**Interfaces:**
- Consumes: the BigQuery tables/views populated in Task 5, and the measures documented in Task 6.

- [ ] **Step 1: Write the file**

Create `docs/powerbi/build_guide.md`:
```markdown
# Power BI Build Guide

Prerequisite: `python scripts/load_to_bigquery.py` has been run successfully — see `docs/superpowers/plans/2026-08-15-bigquery-load-and-powerbi-docs.md` Task 5 for the verification numbers this depends on.

## 1. Connect to BigQuery

1. Open Power BI Desktop → **Home** → **Get Data** → **More…** → search "BigQuery" → select **Google BigQuery** → **Connect**.
2. Sign in with the Google account tied to the `rams-fan-analytics` project (OAuth window opens).
3. In the Navigator tree, expand `rams-fan-analytics` → `rams_fan_analytics` and check the boxes for: `fans`, `weekly_snapshots`, `v_engagement_trend`, `v_tier_by_plan`, `v_at_risk_current`.
4. Click **Load** (not "Transform Data" — the loader already wrote clean, typed data, no Power Query cleanup needed).

## 2. Build the model

1. Switch to the **Model** view (left rail, three-boxes icon).
2. Drag `fans[fan_id]` onto `weekly_snapshots[fan_id]` to create a relationship.
3. In the relationship dialog, confirm: cardinality **One to many** (fans is the "one" side), cross-filter direction **Single**, and the relationship is **active**.
4. Leave `v_engagement_trend`, `v_tier_by_plan`, and `v_at_risk_current` unrelated to anything — they're pre-shaped for specific visuals, not part of the star schema.

## 3. Add the DAX measures

1. In the **Data** view, right-click `weekly_snapshots` in the field list → **New measure**.
2. Paste in each measure from `docs/powerbi/dax_measures.md` one at a time (9 total), pressing Enter after each to commit it before starting the next.

## 4. Page 1 — Season Trend

This page ignores the week slicer (added on Page 2) entirely — every visual here should show all 18 weeks at once.

1. Add a **Line chart**. X-axis: `weekly_snapshots[week]`. Values: `[Precision]`, `[Recall]`, `[F1 Score]` (all three, as separate lines).
2. Add a **Stacked area chart** below it. X-axis: `v_tier_by_plan[week]`. Y-axis: `v_tier_by_plan[n_fans]`. Legend: `v_tier_by_plan[plan_tier]`.
3. Add four **Card** visuals along the top for `[At-Risk Count]`, `[Precision]`, `[Recall]`, `[F1 Score]` — these will show whatever the *total* (unfiltered by week) values resolve to, which is fine as a page-level headline.

## 5. Page 2 — Weekly Snapshot

1. Add a **Slicer** visual bound to `weekly_snapshots[week]`. Set it to single-select (Format pane → Selection → Single select: On).
2. Add four **Card** visuals: `[Super Fan Count]`, `[Engaged Count]`, `[Cooling Count]`, `[Dormant Count]` — these now respond to the slicer.
3. Add a **Table** visual using `v_at_risk_current[fan_id]`, `v_at_risk_current[engagement_score]`, `v_at_risk_current[tier]`. Note: this view is defined as "the latest week only," so it will not change when you move the slicer to an earlier week — that's expected; it's meant as the current-state view. Sort by `engagement_score` ascending.

## 6. Page 3 — Fan Drill-Through

1. Create a new page named exactly `Fan Drill-Through`.
2. In the Visualizations pane, drag `fans[fan_id]` into the **Drill through** field well at the bottom — this makes the page a drill-through target.
3. Add a **Line chart** on this page: X-axis `v_engagement_trend[week]`, Values `v_engagement_trend[engagement_score]`. Add a second line for `v_engagement_trend[score_delta]` if you want the week-over-week delta visible too (put it on a second value well, not a second Y-axis — Power BI will ask if you want a secondary axis; decline it and use two separate small multiples or a tooltip instead, since a dual-axis chart makes the two series' shapes hard to compare fairly).
4. Add a **Card** for `fans[is_planted_churn]` so the ground-truth flag is visible on the drill-through page.
5. Back on Page 2, right-click a `fan_id` value in the at-risk table → **Drill through** → **Fan Drill-Through** to test it.

## 7. Save

File → Save As → save to `powerbi/Fan_Engagement_Dashboard.pbix` at the repo root (create the `powerbi/` folder if it doesn't exist — this is a hand-built artifact, not generated output, so unlike `data/`, it should be committed to git rather than gitignored).
```

- [ ] **Step 2: Create the powerbi/ directory placeholder**

Run: `mkdir -p powerbi` (Bash) or the PowerShell equivalent, then create an empty `powerbi/.gitkeep` file so the empty directory is tracked until the user saves the `.pbix` into it.

- [ ] **Step 3: Commit**

```bash
git add docs/powerbi/build_guide.md powerbi/.gitkeep
git commit -m "Add Power BI build guide"
```

---

### Task 8: Decision log entries

**Files:**
- Modify: `docs/DECISION_LOG.md`

- [ ] **Step 1: Append three new entries**

Add to the end of `docs/DECISION_LOG.md`, after the existing final entry:
```markdown

---

## 2026-08-15 — Power BI replaces the planned Streamlit dashboard

**Decision:** The Phase B dashboard (see the 2026-08-12 entry above) will be built in Power BI instead of Streamlit.

**Why:** The job posting names Power BI explicitly, twice — once for building dashboards/reports/visualizations, once under reporting-software experience. Streamlit is not mentioned anywhere in the posting. This is the same direct-JD-language mapping that drove the original engagement-score/churn-view use-case decision.

**Reference:** [`docs/superpowers/specs/2026-08-15-powerbi-bigquery-design.md`](superpowers/specs/2026-08-15-powerbi-bigquery-design.md).

---

## 2026-08-15 — BigQuery chosen as the warehouse layer under Power BI

**Decision:** Add a BigQuery warehouse layer beneath the Power BI report, loaded from the existing SQLite data — BigQuery over Snowflake.

**Why:** A flat-file-fed Power BI report wouldn't put any SQL on screen. BigQuery's sandbox tier is free indefinitely with no credit card and no billing account, versus Snowflake's 30-day trial credit, which would eventually expire or require billing — a real risk for a portfolio project meant to still work months later. BigQuery also has a native Power BI connector (no ODBC driver to install) and pairs naturally with the job posting's mention of Looker Studio, a Google product.

---

## 2026-08-15 — Views carry the SQL story, DAX carries the interactive story

**Decision:** Row-level shaping (a window-function trend query, a join+aggregation query, a CTE-based at-risk reconstruction) lives as BigQuery views, ported directly from `notebooks/04_sql_analysis.ipynb`. Live, filter-context-sensitive metrics (precision/recall/F1 recomputed under whatever week is selected) live as DAX measures in Power BI.

**Why:** SQL views are static once created — they can't respond to a Power BI slicer selection. DAX measures can, via `CALCULATE`'s automatic filter-context propagation. Splitting the work this way means each tool does the job it's actually suited for, and both are demonstrable on their own terms — real SQL sitting in the warehouse and real DAX sitting in the model.
```

- [ ] **Step 2: Commit**

```bash
git add docs/DECISION_LOG.md
git commit -m "Record Power BI, BigQuery, and SQL/DAX split decisions"
```

---

## What's explicitly not in this plan

- Building the actual Power BI report (`.pbix`) — that's manual GUI work the user does following `docs/powerbi/build_guide.md`, not automatable/testable code.
- Updating `README.md` to remove the "no dashboard yet" scope note — held until the `.pbix` actually exists (per the design spec), which happens after this plan.
- Phase C (scaling the population to ~2,000+ fans) — unaffected, still deferred.
