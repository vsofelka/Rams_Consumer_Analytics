# SQL Backbone + Statistical Validation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a real SQLite database (loaded directly by the existing simulation pipeline) and a statistical-validation module (Mann-Whitney U, Wilson confidence intervals, a hypergeometric test) to the existing fan-engagement/churn MVP, demonstrated through a new SQL-analysis notebook and documented in `docs/RESULTS.md`.

**Architecture:** `scripts/run_season.py` gains an optional `db_path` parameter — when given, it writes each week's data into a SQLite database (`fans` and `weekly_snapshots` tables) alongside its existing, unchanged CSV output. A new `scoring/stats.py` module adds three pure, independently-testable statistical functions. A new notebook (`notebooks/04_sql_analysis.ipynb`) reads only from the SQLite database — never the simulator or scoring code directly — runs real SQL (joins, window functions, aggregations, a CTE), and calls the new stats functions to validate the churn rule statistically.

**Tech Stack:** Python 3.10+, pandas, numpy, scipy (new), sqlite3 (standard library), pytest, Jupyter.

## Global Constraints

- The existing CSV pipeline and its tests must remain unchanged. SQLite writing is additive: `run_season()`'s new `db_path` parameter defaults to `None`, and when it's `None` no database is written and existing behavior is byte-for-byte identical to before this plan.
- `notebooks/04_sql_analysis.ipynb` reads only from the SQLite database (`data/fan_analytics.db`) — it must never import `season_simulator` or call `run_season()` directly. This is the same decoupling principle the existing three notebooks already follow.
- SQLite is the chosen engine (see `docs/DECISION_LOG.md`, 2026-08-12 entry) — no other database engine is in scope for this plan.
- The three statistical functions (Mann-Whitney U, Wilson CI, hypergeometric test) were each chosen to match the actual data-generating process, not used interchangeably — see `docs/DECISION_LOG.md` for the reasoning behind each. Do not substitute a different test than the one specified per task.
- `docs/RESULTS.md`'s new "Statistical Validation" section must state real numbers, cross-checked against `notebooks/04_sql_analysis.ipynb`'s actual saved cell output — never placeholder or projected figures. This mirrors the same rule already in force for the rest of that document.
- `README.md` is explicitly **not** touched in this plan — it's held until the later scale-up phase so it's written once against final numbers.
- This is a solo portfolio project; work directly on the `main` branch (no feature branch/worktree needed), matching every prior task in this repo.

---

### Task 1: SQLite storage module

**Files:**
- Create: `storage/__init__.py`
- Create: `storage/db.py`
- Test: `tests/test_db.py`

**Interfaces:**
- Produces: `create_schema(conn: sqlite3.Connection) -> None`, `write_fans(conn: sqlite3.Connection, fans: pd.DataFrame) -> None`, `write_weekly_snapshot(conn: sqlite3.Connection, snapshot: pd.DataFrame) -> None`. `write_fans` expects the same columns `generate_fan_population` produces (`fan_id`, `tenure_years`, `plan_tier`, `baseline_engagement`, `is_planted_churn`, `decline_start_week`). `write_weekly_snapshot` expects the same columns a `run_season` weekly snapshot has (`fan_id`, `week`, `engagement_score`, `tier`, `at_risk`).

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_db.py
import sqlite3
import pandas as pd
from storage.db import create_schema, write_fans, write_weekly_snapshot


def test_create_schema_creates_both_tables():
    conn = sqlite3.connect(":memory:")
    create_schema(conn)
    tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert {"fans", "weekly_snapshots"}.issubset(tables)


def test_write_fans_round_trips_data():
    conn = sqlite3.connect(":memory:")
    create_schema(conn)
    fans = pd.DataFrame({
        "fan_id": [1, 2],
        "tenure_years": [3, 7],
        "plan_tier": ["standard", "premium"],
        "baseline_engagement": [0.4, 0.8],
        "is_planted_churn": [True, False],
        "decline_start_week": [6.0, None],
    })
    write_fans(conn, fans)
    result = pd.read_sql("SELECT * FROM fans ORDER BY fan_id", conn)
    assert len(result) == 2
    assert set(result["fan_id"]) == {1, 2}


def test_write_weekly_snapshot_round_trips_data():
    conn = sqlite3.connect(":memory:")
    create_schema(conn)
    snapshot = pd.DataFrame({
        "fan_id": [1, 2],
        "week": [1, 1],
        "engagement_score": [55.0, 80.0],
        "tier": ["Cooling", "Engaged"],
        "at_risk": [False, False],
    })
    write_weekly_snapshot(conn, snapshot)
    result = pd.read_sql("SELECT * FROM weekly_snapshots ORDER BY fan_id", conn)
    assert len(result) == 2
    assert result.loc[0, "engagement_score"] == 55.0


def test_write_weekly_snapshot_appends_across_multiple_weeks():
    conn = sqlite3.connect(":memory:")
    create_schema(conn)
    week1 = pd.DataFrame({
        "fan_id": [1], "week": [1], "engagement_score": [55.0], "tier": ["Cooling"], "at_risk": [False],
    })
    week2 = pd.DataFrame({
        "fan_id": [1], "week": [2], "engagement_score": [50.0], "tier": ["Cooling"], "at_risk": [False],
    })
    write_weekly_snapshot(conn, week1)
    write_weekly_snapshot(conn, week2)
    result = pd.read_sql("SELECT * FROM weekly_snapshots ORDER BY week", conn)
    assert len(result) == 2
    assert list(result["week"]) == [1, 2]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_db.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'storage'`

- [ ] **Step 3: Create the package and write the minimal implementation**

Create an empty `storage/__init__.py` (no content — just makes the directory an importable package).

```python
# storage/db.py
import sqlite3
import pandas as pd

FANS_SCHEMA = """
CREATE TABLE IF NOT EXISTS fans (
    fan_id INTEGER PRIMARY KEY,
    tenure_years INTEGER,
    plan_tier TEXT,
    baseline_engagement REAL,
    is_planted_churn INTEGER,
    decline_start_week REAL
)
"""

WEEKLY_SNAPSHOTS_SCHEMA = """
CREATE TABLE IF NOT EXISTS weekly_snapshots (
    fan_id INTEGER,
    week INTEGER,
    engagement_score REAL,
    tier TEXT,
    at_risk INTEGER,
    PRIMARY KEY (fan_id, week),
    FOREIGN KEY (fan_id) REFERENCES fans(fan_id)
)
"""


def create_schema(conn: sqlite3.Connection) -> None:
    conn.execute(FANS_SCHEMA)
    conn.execute(WEEKLY_SNAPSHOTS_SCHEMA)
    conn.commit()


def write_fans(conn: sqlite3.Connection, fans: pd.DataFrame) -> None:
    fans.to_sql("fans", conn, if_exists="append", index=False)
    conn.commit()


def write_weekly_snapshot(conn: sqlite3.Connection, snapshot: pd.DataFrame) -> None:
    snapshot.to_sql("weekly_snapshots", conn, if_exists="append", index=False)
    conn.commit()
```

Note: `create_schema` must always be called before `write_fans`/`write_weekly_snapshot` — the write functions use `if_exists="append"`, which requires the table (with its `PRIMARY KEY`/`FOREIGN KEY` constraints) to already exist. Calling `to_sql` with `if_exists="replace"` instead would silently drop those constraints.

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_db.py -v`
Expected: `4 passed`

- [ ] **Step 5: Commit**

```bash
git add storage/__init__.py storage/db.py tests/test_db.py
git commit -m "$(cat <<'EOF'
Add SQLite storage module: schema and write functions

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 2: Wire SQLite writing into the season runner

**Files:**
- Modify: `scripts/run_season.py`
- Modify: `tests/test_run_season.py`
- Modify: `.gitignore`

**Interfaces:**
- Consumes: `create_schema`, `write_fans`, `write_weekly_snapshot` (Task 1).
- Produces: `run_season(..., db_path: str | None = None)` — same signature as before plus one new optional keyword argument. When `db_path` is `None` (the default), behavior is identical to before this task. When given a path, a SQLite database is created there with a `fans` table and a `weekly_snapshots` table populated week-by-week as the season runs.

- [ ] **Step 1: Write the failing tests**

Add these two tests to the end of `tests/test_run_season.py` (the existing two tests in that file stay exactly as they are):

```python
def test_run_season_writes_to_sqlite_when_db_path_given(tmp_path):
    import sqlite3

    db_path = str(tmp_path / "test.db")
    fans, events_history, score_history, snapshots = run_season(
        n_fans=20,
        n_planted_churn=2,
        decline_start_week=3,
        n_weeks=4,
        output_dir=str(tmp_path / "weekly_snapshots"),
        seed=55,
        db_path=db_path,
    )

    conn = sqlite3.connect(db_path)
    fans_count = conn.execute("SELECT COUNT(*) FROM fans").fetchone()[0]
    snapshots_count = conn.execute("SELECT COUNT(*) FROM weekly_snapshots").fetchone()[0]
    conn.close()

    assert fans_count == 20
    assert snapshots_count == 20 * 4


def test_run_season_skips_sqlite_when_db_path_omitted(tmp_path):
    fans, events_history, score_history, snapshots = run_season(
        n_fans=10,
        n_planted_churn=1,
        decline_start_week=2,
        n_weeks=2,
        output_dir=str(tmp_path / "weekly_snapshots"),
        seed=56,
    )
    assert len(snapshots) == 2
```

- [ ] **Step 2: Run tests to verify the new ones fail**

Run: `pytest tests/test_run_season.py -v`
Expected: the two new tests FAIL with `TypeError: run_season() got an unexpected keyword argument 'db_path'` (for the first) — the second currently passes already since it doesn't use `db_path`, which is fine.

- [ ] **Step 3: Modify `scripts/run_season.py`**

Replace the full file with:

```python
import os
import sqlite3
import sys

import pandas as pd

# Running this file directly (`python scripts/run_season.py`) puts scripts/ on
# sys.path rather than the repo root, so the sibling packages below would not be
# importable. Importing it as a module (pytest, notebooks) is unaffected.
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from season_simulator.fans import generate_fan_population
from season_simulator.events import generate_week_events
from scoring.engagement import compute_weekly_engagement_scores
from scoring.churn import apply_churn_rule
from storage.db import create_schema, write_fans, write_weekly_snapshot


def run_season(
    n_fans,
    n_planted_churn,
    decline_start_week,
    n_weeks,
    output_dir,
    window=6,
    decline_weeks=3,
    risk_percentile=25.0,
    seed=42,
    db_path=None,
):
    fans = generate_fan_population(n_fans, n_planted_churn, decline_start_week, seed=seed)
    os.makedirs(output_dir, exist_ok=True)
    fans.to_csv(os.path.join(output_dir, "fans.csv"), index=False)

    db_conn = None
    if db_path is not None:
        db_conn = sqlite3.connect(db_path)
        create_schema(db_conn)
        write_fans(db_conn, fans)

    # Accumulate per-week frames in lists and concat them each iteration. Seeding
    # the history with an empty `columns=`-only DataFrame instead would make every
    # column object-dtype and propagate that through each concat.
    event_frames = []
    score_frames = []
    weekly_snapshots = {}

    # Both are reassigned on every iteration below; these placeholders are only
    # returned in the degenerate n_weeks < 1 case, where there is no data to type.
    events_history = pd.DataFrame(
        columns=["fan_id", "week", "attendance_signal", "digital_signal", "purchase_signal"]
    )
    score_history = pd.DataFrame(columns=["fan_id", "week", "engagement_score", "tier"])

    try:
        for week in range(1, n_weeks + 1):
            week_events = generate_week_events(fans, week, seed=seed)
            event_frames.append(week_events)
            events_history = pd.concat(event_frames, ignore_index=True)

            week_scores = compute_weekly_engagement_scores(events_history, current_week=week, window=window)
            score_frames.append(week_scores)
            score_history = pd.concat(score_frames, ignore_index=True)

            week_at_risk = apply_churn_rule(
                score_history, current_week=week, decline_weeks=decline_weeks, risk_percentile=risk_percentile
            )

            snapshot = week_scores.merge(week_at_risk[["fan_id", "at_risk"]], on="fan_id")
            snapshot.to_csv(os.path.join(output_dir, f"week_{week:02d}.csv"), index=False)
            weekly_snapshots[week] = snapshot

            if db_conn is not None:
                write_weekly_snapshot(db_conn, snapshot)
    finally:
        if db_conn is not None:
            db_conn.close()

    return fans, events_history, score_history, weekly_snapshots


if __name__ == "__main__":
    run_season(
        n_fans=300,
        n_planted_churn=25,
        decline_start_week=6,
        n_weeks=18,
        output_dir="data/weekly_snapshots",
        db_path="data/fan_analytics.db",
    )
```

- [ ] **Step 4: Add the database file to `.gitignore`**

Add this line to `.gitignore`, near the existing `data/weekly_snapshots/` entry:

```text
data/fan_analytics.db
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_run_season.py -v`
Expected: `4 passed`

- [ ] **Step 6: Run the full test suite to confirm nothing else broke**

Run: `pytest -v`
Expected: all tests pass (the full existing suite plus this task's additions).

- [ ] **Step 7: Generate the real database for the notebook**

Run: `python scripts/run_season.py`
Expected: `data/fan_analytics.db` now exists alongside the already-existing `data/weekly_snapshots/` CSVs, with a `fans` table (300 rows) and a `weekly_snapshots` table (5,400 rows — 300 fans × 18 weeks).

- [ ] **Step 8: Commit**

```bash
git add scripts/run_season.py tests/test_run_season.py .gitignore
git commit -m "$(cat <<'EOF'
Wire SQLite writing into the season runner

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 3: Statistical validation module

**Files:**
- Modify: `requirements.txt`
- Create: `scoring/stats.py`
- Test: `tests/test_stats.py`

**Interfaces:**
- Consumes: a `weekly_snapshots`-shaped DataFrame (`fan_id`, `engagement_score`) and a `fans`-shaped DataFrame (`fan_id`, `is_planted_churn`) for `compare_churn_cohort_engagement`. `wilson_confidence_interval` and `hypergeometric_test` consume plain counts, no DataFrames.
- Produces: `compare_churn_cohort_engagement(scores: pd.DataFrame, fans: pd.DataFrame) -> dict` with keys `statistic`, `p_value`, `planted_median`, `rest_median`, `n_planted`, `n_rest`. `wilson_confidence_interval(successes: int, n: int, confidence: float = 0.95) -> dict` with keys `lower`, `upper`, `point_estimate`. `hypergeometric_test(population_size: int, n_true_churners: int, n_flagged: int, n_true_positives: int) -> dict` with keys `p_value`, `expected_true_positives_by_chance`, `observed_true_positives`.

- [ ] **Step 1: Add scipy to requirements.txt**

Add this line to `requirements.txt`:

```text
scipy>=1.10
```

Run: `pip install -r requirements.txt`
Expected: installs successfully with no errors.

- [ ] **Step 2: Write the failing tests**

```python
# tests/test_stats.py
import pandas as pd
import pytest

from scoring.stats import (
    compare_churn_cohort_engagement,
    wilson_confidence_interval,
    hypergeometric_test,
)


def test_compare_churn_cohort_engagement_detects_clear_difference():
    # 5 vs 5 with complete separation: exact one-sided Mann-Whitney p-value is
    # 1/C(10,5) = 1/252 ~= 0.004. (2 vs 2 is NOT enough — the smallest possible
    # exact one-sided p-value with n1=n2=2 is 1/6 ~= 0.167, which can never
    # cross a 0.05 threshold no matter how separated the groups are.)
    fans = pd.DataFrame({
        "fan_id": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
        "is_planted_churn": [True, True, True, True, True, False, False, False, False, False],
    })
    scores = pd.DataFrame({
        "fan_id": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
        "engagement_score": [10.0, 12.0, 14.0, 16.0, 18.0, 70.0, 72.0, 74.0, 76.0, 78.0],
    })
    result = compare_churn_cohort_engagement(scores, fans)
    assert result["p_value"] < 0.05
    assert result["planted_median"] < result["rest_median"]
    assert result["n_planted"] == 5
    assert result["n_rest"] == 5


def test_compare_churn_cohort_engagement_no_difference_is_not_significant():
    # Fully interleaved values: planted and rest ranks alternate, so the U
    # statistic lands right at its expected value under the null (no
    # difference), which should be nowhere close to significant.
    fans = pd.DataFrame({
        "fan_id": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
        "is_planted_churn": [True, False, True, False, True, False, True, False, True, False],
    })
    scores = pd.DataFrame({
        "fan_id": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
        "engagement_score": [48.0, 48.5, 49.0, 49.5, 50.0, 50.5, 51.0, 51.5, 52.0, 52.5],
    })
    result = compare_churn_cohort_engagement(scores, fans)
    assert result["p_value"] > 0.05


def test_wilson_confidence_interval_contains_point_estimate_and_is_bounded():
    result = wilson_confidence_interval(successes=8, n=25, confidence=0.95)
    assert result["point_estimate"] == pytest.approx(0.32)
    assert result["lower"] < result["point_estimate"] < result["upper"]
    assert 0.0 <= result["lower"] < result["upper"] <= 1.0


def test_wilson_confidence_interval_narrows_with_larger_sample_same_proportion():
    small_n = wilson_confidence_interval(successes=8, n=25, confidence=0.95)
    large_n = wilson_confidence_interval(successes=80, n=250, confidence=0.95)
    small_width = small_n["upper"] - small_n["lower"]
    large_width = large_n["upper"] - large_n["lower"]
    assert large_width < small_width


def test_hypergeometric_test_extreme_case_exact_probability():
    # Population of 4 with 2 true churners. Drawing exactly 2 fans and getting
    # both churners is the only way this happens: C(2,2)*C(2,0)/C(4,2) = 1/6.
    result = hypergeometric_test(population_size=4, n_true_churners=2, n_flagged=2, n_true_positives=2)
    assert result["p_value"] == pytest.approx(1 / 6)
    assert result["expected_true_positives_by_chance"] == pytest.approx(1.0)


def test_hypergeometric_test_zero_true_positives_is_certain():
    result = hypergeometric_test(population_size=300, n_true_churners=25, n_flagged=13, n_true_positives=0)
    assert result["p_value"] == pytest.approx(1.0)
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `pytest tests/test_stats.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'scoring.stats'`

- [ ] **Step 4: Write the minimal implementation**

```python
# scoring/stats.py
import math

from scipy import stats


def compare_churn_cohort_engagement(scores: "pd.DataFrame", fans: "pd.DataFrame") -> dict:
    merged = scores.merge(fans[["fan_id", "is_planted_churn"]], on="fan_id")
    planted = merged.loc[merged["is_planted_churn"], "engagement_score"]
    rest = merged.loc[~merged["is_planted_churn"], "engagement_score"]

    statistic, p_value = stats.mannwhitneyu(planted, rest, alternative="less")

    return {
        "statistic": float(statistic),
        "p_value": float(p_value),
        "planted_median": float(planted.median()),
        "rest_median": float(rest.median()),
        "n_planted": int(len(planted)),
        "n_rest": int(len(rest)),
    }


def wilson_confidence_interval(successes: int, n: int, confidence: float = 0.95) -> dict:
    if n == 0:
        return {"lower": 0.0, "upper": 0.0, "point_estimate": 0.0}

    z_scores = {0.95: 1.959963985, 0.99: 2.575829304}
    z = z_scores[confidence]
    p_hat = successes / n

    denominator = 1 + z**2 / n
    center = (p_hat + z**2 / (2 * n)) / denominator
    margin = (z * math.sqrt((p_hat * (1 - p_hat) + z**2 / (4 * n)) / n)) / denominator

    return {
        "lower": max(0.0, center - margin),
        "upper": min(1.0, center + margin),
        "point_estimate": p_hat,
    }


def hypergeometric_test(population_size: int, n_true_churners: int, n_flagged: int, n_true_positives: int) -> dict:
    rv = stats.hypergeom(population_size, n_true_churners, n_flagged)
    p_value = float(rv.sf(n_true_positives - 1))  # P(X >= n_true_positives)

    return {
        "p_value": p_value,
        "expected_true_positives_by_chance": float(rv.mean()),
        "observed_true_positives": n_true_positives,
    }
```

Note: `compare_churn_cohort_engagement`'s type hints use a quoted `"pd.DataFrame"` because this module doesn't otherwise need a top-level `import pandas as pd` — the function only calls `.merge`/`.loc`/`.median()` on objects passed in, it never constructs a DataFrame itself. This matches the file as specified; do not add an unused top-level pandas import.

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_stats.py -v`
Expected: `6 passed`

- [ ] **Step 6: Run the full test suite to confirm nothing else broke**

Run: `pytest -v`
Expected: all tests pass.

- [ ] **Step 7: Commit**

```bash
git add requirements.txt scoring/stats.py tests/test_stats.py
git commit -m "$(cat <<'EOF'
Add statistical validation module: Mann-Whitney U, Wilson CI, hypergeometric test

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 4: Notebook 4 — SQL analysis and statistical validation

**Files:**
- Create: `notebooks/04_sql_analysis.ipynb`

**Interfaces:**
- Consumes: `data/fan_analytics.db` (Task 2), `compare_churn_cohort_engagement`, `wilson_confidence_interval`, `hypergeometric_test` (Task 3), `evaluate_churn_detection` (existing, `scoring/validation.py`).

This notebook reads only from the SQLite database — it must never import `season_simulator` or call `run_season()`.

- [ ] **Step 1: Create the notebook with these cells, in order**

Cell 1 (path setup — same boilerplate as every prior notebook):

```python
import sys, os

if os.path.basename(os.getcwd()) == "notebooks":
    os.chdir("..")
if os.getcwd() not in sys.path:
    sys.path.insert(0, os.getcwd())
```

Cell 2 (imports and connection):

```python
import sqlite3
import pandas as pd

from scoring.stats import compare_churn_cohort_engagement, wilson_confidence_interval, hypergeometric_test
from scoring.validation import evaluate_churn_detection

conn = sqlite3.connect("data/fan_analytics.db")
fans = pd.read_sql("SELECT * FROM fans", conn)
fans.head()
```

Cell 3 (markdown):

```markdown
## Week-over-week trend via SQL window function

`LAG() OVER (PARTITION BY fan_id ORDER BY week)` looks back one row within
each fan's own week-ordered history to compute how much their score moved
since the prior week — a rolling comparison expressed entirely in SQL,
without pulling the data into pandas first.
```

Cell 4 (window function query):

```python
trend_query = """
SELECT
    fan_id,
    week,
    engagement_score,
    engagement_score - LAG(engagement_score) OVER (PARTITION BY fan_id ORDER BY week) AS score_delta
FROM weekly_snapshots
ORDER BY fan_id, week
"""
trend = pd.read_sql(trend_query, conn)
trend.head(10)
```

Cell 5 (markdown):

```markdown
## Engagement by plan tier, over time

A `JOIN` between the fact table (`weekly_snapshots`) and the dimension
table (`fans`) plus a `GROUP BY` on week and plan tier — the kind of
aggregation a BI report would run directly against this database.
```

Cell 6 (join + group by query):

```python
tier_by_plan_query = """
SELECT
    w.week,
    f.plan_tier,
    AVG(w.engagement_score) AS avg_engagement_score,
    COUNT(*) AS n_fans
FROM weekly_snapshots w
JOIN fans f ON w.fan_id = f.fan_id
GROUP BY w.week, f.plan_tier
ORDER BY w.week, f.plan_tier
"""
by_plan_tier = pd.read_sql(tier_by_plan_query, conn)
by_plan_tier.tail(10)
```

Cell 7 (markdown):

```markdown
## Reconstructing the at-risk list in pure SQL

Notebook 03 produced the final week's at-risk list using pandas. Here's
the same result arrived at a different way — a CTE finds the latest week,
then filters `weekly_snapshots` down to flagged fans in that week. This is
a cross-check: if these two independently-computed lists ever disagreed,
that would mean a bug somewhere in the pipeline.
```

Cell 8 (CTE query):

```python
at_risk_query = """
WITH final_week AS (
    SELECT MAX(week) AS max_week FROM weekly_snapshots
)
SELECT
    w.fan_id,
    w.engagement_score,
    w.tier
FROM weekly_snapshots w, final_week
WHERE w.week = final_week.max_week AND w.at_risk = 1
ORDER BY w.engagement_score ASC
"""
at_risk_sql = pd.read_sql(at_risk_query, conn)
at_risk_sql
```

Cell 9 (markdown):

```markdown
## Statistical test 1 — is the planted-churn cohort's decline real?

A Mann-Whitney U test compares the final week's engagement scores for the
planted-churn cohort against everyone else. Mann-Whitney is used instead
of a t-test because `engagement_score` is a population-relative percentile
rank by construction, not a normally-distributed measurement — the test
should not assume a distribution shape the data doesn't have. The
alternative hypothesis is one-sided (`"less"`): planted-churn fans are
expected to score lower, not just "different."
```

Cell 10 (Mann-Whitney):

```python
final_week_num = int(pd.read_sql("SELECT MAX(week) AS w FROM weekly_snapshots", conn)["w"].iloc[0])
final_scores = pd.read_sql(
    f"SELECT fan_id, engagement_score FROM weekly_snapshots WHERE week = {final_week_num}", conn
)

mw_result = compare_churn_cohort_engagement(final_scores, fans)
print(f"Mann-Whitney U p-value: {mw_result['p_value']:.6f}")
print(f"Planted-churn median score: {mw_result['planted_median']:.2f}")
print(f"Everyone-else median score: {mw_result['rest_median']:.2f}")
```

Cell 11 (markdown):

```markdown
## Statistical test 2 — how confident are we in precision and recall?

Precision and recall are point estimates from a small sample (a handful
of flagged fans out of 300). A Wilson score confidence interval gives a
plausible range for each, rather than reporting a single number as if it
were exact. Wilson is used instead of a naive normal-approximation
interval because it stays well-behaved for small counts close to 0 or 1.
```

Cell 12 (Wilson CI):

```python
at_risk_final = pd.read_sql(
    f"SELECT fan_id, {final_week_num} AS week, at_risk FROM weekly_snapshots WHERE week = {final_week_num}", conn
)
validation = evaluate_churn_detection(at_risk_final, fans, week=final_week_num)

precision_ci = wilson_confidence_interval(
    validation["true_positives"], validation["true_positives"] + validation["false_positives"]
)
recall_ci = wilson_confidence_interval(
    validation["true_positives"], validation["true_positives"] + validation["false_negatives"]
)

print(f"Precision: {validation['precision']:.2f}  95% CI: ({precision_ci['lower']:.2f}, {precision_ci['upper']:.2f})")
print(f"Recall: {validation['recall']:.2f}  95% CI: ({recall_ci['lower']:.2f}, {recall_ci['upper']:.2f})")
```

Cell 13 (markdown):

```markdown
## Statistical test 3 — could this many true positives happen by chance?

If you flagged fans at random instead of using the churn rule, how many
true positives would you expect to get lucky into? A hypergeometric test
answers this exactly: it models drawing a fixed number of fans without
replacement from a finite population with a known number of true
churners in it — which is exactly what's happening here — rather than
approximating with a binomial distribution, which assumes draws don't
change the population (they do, since a fan can't be flagged twice).
```

Cell 14 (hypergeometric test):

```python
n_planted = int(fans["is_planted_churn"].sum())
n_flagged = validation["true_positives"] + validation["false_positives"]

hg_result = hypergeometric_test(
    population_size=len(fans),
    n_true_churners=n_planted,
    n_flagged=n_flagged,
    n_true_positives=validation["true_positives"],
)
print(f"P(>= {validation['true_positives']} true positives by chance): {hg_result['p_value']:.6f}")
print(f"Expected true positives by chance: {hg_result['expected_true_positives_by_chance']:.2f}")
```

- [ ] **Step 2: Run all cells top to bottom**

Expected:
- Cell 4's trend table shows a `NaN` `score_delta` for every fan's first week (no prior week to compare against) and real values afterward.
- Cell 6's aggregation has one row per (week, plan_tier) combination.
- Cell 8's at-risk table should have the same fan count and fan IDs as Notebook 03's at-risk list for the same underlying data (both are reading/deriving from the same `weekly_snapshots` data, just via SQL here instead of pandas).
- Cell 10's Mann-Whitney p-value should be well below 0.05 (the planted cohort visibly diverges by the final week, per `docs/RESULTS.md`), and `planted_median` should be noticeably lower than `rest_median`.
- Cell 12's precision/recall should match the values already in `docs/RESULTS.md`, each with a CI that contains that point estimate.
- Cell 14's p-value should be well below 0.05 (the rule's true-positive count should be higher than what chance alone would produce), and "expected by chance" should be well below the actual observed true-positive count.

If any of the last three cells' results contradict these expectations (e.g., a p-value above 0.05, or a CI that doesn't contain the point estimate), stop and investigate — do not proceed to Task 5 with results that contradict the statistical claims they're supposed to support.

- [ ] **Step 3: Save the notebook**

Save via Jupyter (or `jupyter nbconvert --to notebook --execute --inplace notebooks/04_sql_analysis.ipynb`) so cell outputs are persisted in the `.ipynb` file.

- [ ] **Step 4: Commit**

```bash
git add notebooks/04_sql_analysis.ipynb
git commit -m "$(cat <<'EOF'
Add notebook: SQL analysis and statistical validation

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 5: Document the statistical validation results

**Files:**
- Modify: `docs/RESULTS.md`

**Interfaces:**
- Consumes: the actual saved cell outputs of `notebooks/04_sql_analysis.ipynb` (Task 4) — this task cannot be done until Task 4 has actually been run, since it reports real numbers, not projected ones.

- [ ] **Step 1: Read the saved outputs of Notebook 4 and record the actual numbers**

From the saved cell outputs, note: the Mann-Whitney U p-value and both medians (Cell 10); the precision/recall point estimates and both Wilson confidence intervals (Cell 12); the hypergeometric p-value and expected-by-chance value (Cell 14).

- [ ] **Step 2: Add a "Statistical Validation" section to `docs/RESULTS.md`**

Add a new section (after the existing validation-result section, before the limitations paragraph) covering, in plain language:

- Whether the planted-churn cohort's decline is statistically real, not noise (the Mann-Whitney result), stated plainly — e.g. "the planted-churn cohort's engagement scores are significantly lower than everyone else's (p < 0.05, Mann-Whitney U test), confirming the divergence visible in the charts is real and not sampling noise."
- The precision/recall confidence intervals, stated as a range rather than treating the point estimates as exact — e.g. "precision is 0.62, with a 95% confidence interval of (X, Y) given the small sample of flagged fans."
- Whether the rule's true-positive count is better than chance (the hypergeometric result) — e.g. "a random flag of the same size would be expected to catch only N fans by chance; the rule caught M, which a hypergeometric test says has probability p of happening by chance alone."
- One sentence noting these three tests were each chosen to fit the actual data (rank-based test for a non-normal score, an interval method suited to small counts, an exact test suited to sampling without replacement) rather than applied as a single default technique everywhere — with a pointer to `docs/DECISION_LOG.md` for the full reasoning.

Use the real numbers from Step 1 throughout — no placeholders.

- [ ] **Step 3: Cross-check the numbers against the notebook outputs one more time**

Re-read the saved cell outputs in `notebooks/04_sql_analysis.ipynb` and confirm every number quoted in `docs/RESULTS.md`'s new section matches exactly.

- [ ] **Step 4: Commit**

```bash
git add docs/RESULTS.md
git commit -m "$(cat <<'EOF'
Add statistical validation results to RESULTS.md

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
EOF
)"
```

---

## Definition of Done for Phase A

- `pytest -v` passes across all tasks in this plan, plus every pre-existing test.
- `python scripts/run_season.py` still runs without error and now also produces `data/fan_analytics.db` alongside the existing CSVs.
- `notebooks/04_sql_analysis.ipynb` runs top-to-bottom without error, reads only from the SQLite database, and its statistical results are consistent with the expectations in Task 4 Step 2 (significant Mann-Whitney result, CIs containing the known point estimates, a small hypergeometric p-value).
- `docs/RESULTS.md`'s new "Statistical Validation" section states real numbers matching the notebook's saved output exactly.
- `README.md` is untouched in this plan (deferred to the scale-up phase).
- Phase B (Streamlit dashboard) and Phase C (scale-up) are separate plans, not started here.
