# Fan Segmentation Implementation Plan

**Goal:** Add a per-fan-per-week behavioral segment (a named k-means cluster over
engagement score, plan tier, and tenure) that reuses the existing pipeline's data,
flows through SQLite and BigQuery the same way every other column already does, and
gives each week's five segments a deterministic, human-readable name.

**Architecture:** A new module, `scoring/segments.py`, clusters that week's fan
population fresh every time (matching this project's in-season, no-future-knowledge
principle) and derives a semantic name from each cluster's relative engagement rank and
dominant plan tier. The result becomes one new column, `segment`, on the existing
`weekly_snapshots` table/CSV — no new tables, no new BigQuery view.

**Tech Stack:** Python, pandas, scikit-learn (new dependency), sqlite3, pytest.

**Spec:** [`docs/design/specs/2026-08-22-segmentation-design.md`](../specs/2026-08-22-segmentation-design.md)

## Global Constraints

- Clustering: `sklearn.cluster.KMeans(n_clusters=5, random_state=42, n_init=10)`, refit
  fresh on every call — never persisted or reused across weeks.
- Features: `engagement_score` and `tenure_years` as-is, `plan_tier` one-hot encoded
  (nominal, not ordinal) into three dummy columns. All features standardized
  (`sklearn.preprocessing.StandardScaler`) before fitting.
- Naming: rank the 5 clusters by mean `engagement_score` (computed from the original,
  unstandardized fan data grouped by assigned cluster label — not from
  `kmeans.cluster_centers_`), descending. Map rank position 1–5 to the descriptor
  `["Highest", "High", "Mid", "Low", "Lowest"]`. Combine with each cluster's dominant
  `plan_tier` (mode among members): `f"{descriptor} Engagement {plan_tier.title()}-Tier"`.
- `assign_segments(fan_features: pd.DataFrame) -> pd.DataFrame` returns the input fans
  plus two new columns: `segment_cluster` (raw 0–4 label) and `segment` (semantic name).
  `segment_cluster` is an interface detail of this function — callers decide whether to
  keep it.
- `segment_cluster` must NOT be persisted into `weekly_snapshots` — only `segment`. It is
  not stable across weekly refits and downstream consumers should never treat it as an
  identity.
- No defensive error handling beyond what's needed — matches `scoring/churn.py`,
  `scoring/clv.py`, and `scripts/load_to_bigquery.py`'s existing convention.
- Test naming: `test_<function>_<expected_behavior>`, flat module-level functions, no
  `Test` classes, no pytest fixtures beyond plain literals — matching `tests/test_clv.py`.
- This plan does not touch `season_simulator/`, the engagement score formula, the churn
  rule, CLV, or any Power BI/BigQuery-view file — a BigQuery view for this feature (if
  ever wanted) is explicitly out of scope, tracked separately.

---

### Task 1: `scoring/segments.py` — clustering and naming

**Files:**
- Modify: `requirements.txt`
- Create: `scoring/segments.py`
- Test: `tests/test_segments.py`

**Interfaces:**
- Produces: `assign_segments(fan_features: pd.DataFrame) -> pd.DataFrame`.
  `fan_features` must have columns `fan_id`, `plan_tier`, `tenure_years`,
  `engagement_score`. Returns the same rows plus `segment_cluster` (int, 0–4) and
  `segment` (str).

- [ ] **Step 1: Add scikit-learn and install it**

Append to `requirements.txt`:
```
scikit-learn>=1.3
```
Run: `pip install -r requirements.txt`
Expected: installs with no errors.

- [ ] **Step 2: Write the failing tests**

Create `tests/test_segments.py`:
```python
import re

import pandas as pd

from scoring.segments import assign_segments

SEGMENT_PATTERN = re.compile(
    r"^(Highest|High|Mid|Low|Lowest) Engagement (Standard|Premium|Club)-Tier$"
)


def _mixed_fan_features_fixture():
    # 30 fans across 3 plan tiers with clearly separated engagement bands, so
    # k-means has real structure to find regardless of the exact split it picks.
    fan_id = list(range(1, 31))
    plan_tier = ["standard"] * 10 + ["premium"] * 10 + ["club"] * 10
    engagement_score = (
        [10.0 + i for i in range(10)]
        + [45.0 + i for i in range(10)]
        + [80.0 + i for i in range(10)]
    )
    tenure_years = [5] * 30
    return pd.DataFrame({
        "fan_id": fan_id,
        "plan_tier": plan_tier,
        "tenure_years": tenure_years,
        "engagement_score": engagement_score,
    })


def _five_band_fixture():
    # 25 fans, single plan tier and tenure held constant, five tightly-separated
    # engagement bands -- isolates the ranking/naming logic from the plan-tier
    # dimension. Band E (highest engagement) must be named "Highest Engagement...",
    # band A (lowest) must be named "Lowest Engagement...".
    bands = {
        "A": [5.0, 6.0, 7.0, 8.0, 9.0],
        "B": [25.0, 26.0, 27.0, 28.0, 29.0],
        "C": [45.0, 46.0, 47.0, 48.0, 49.0],
        "D": [65.0, 66.0, 67.0, 68.0, 69.0],
        "E": [85.0, 86.0, 87.0, 88.0, 89.0],
    }
    rows = []
    fan_id = 1
    for band, scores in bands.items():
        for score in scores:
            rows.append({"fan_id": fan_id, "band": band, "engagement_score": score})
            fan_id += 1
    df = pd.DataFrame(rows)
    df["plan_tier"] = "standard"
    df["tenure_years"] = 5
    return df


def test_assign_segments_produces_exactly_five_distinct_segment_names():
    fan_features = _mixed_fan_features_fixture()

    result = assign_segments(fan_features)

    assert result["segment"].nunique() == 5


def test_assign_segments_returns_exactly_one_row_per_input_fan():
    fan_features = _mixed_fan_features_fixture()

    result = assign_segments(fan_features)

    assert len(result) == len(fan_features)
    assert set(result["fan_id"]) == set(fan_features["fan_id"])
    assert result["fan_id"].duplicated().sum() == 0


def test_assign_segments_names_match_expected_pattern():
    fan_features = _mixed_fan_features_fixture()

    result = assign_segments(fan_features)

    assert all(SEGMENT_PATTERN.match(name) for name in result["segment"])


def test_assign_segments_ranks_engagement_bands_correctly():
    fan_features = _five_band_fixture()

    # assign_segments() preserves every input column (it copies fan_features and adds
    # segment_cluster/segment on top), so "band" is already on the result -- no need to
    # re-merge it back in (doing so would collide into "band_x"/"band_y" instead).
    result = assign_segments(fan_features)

    segment_by_band = result.groupby("band")["segment"].first()

    assert segment_by_band["E"].startswith("Highest Engagement")
    assert segment_by_band["A"].startswith("Lowest Engagement")


def test_assign_segments_is_deterministic_across_calls():
    fan_features = _mixed_fan_features_fixture()

    result1 = assign_segments(fan_features)
    result2 = assign_segments(fan_features)

    assert list(result1.sort_values("fan_id")["segment"]) == list(
        result2.sort_values("fan_id")["segment"]
    )
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `pytest tests/test_segments.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'scoring.segments'`.

- [ ] **Step 4: Write minimal implementation**

Create `scoring/segments.py`:
```python
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler

N_CLUSTERS = 5
RANDOM_STATE = 42
ENGAGEMENT_DESCRIPTORS = ["Highest", "High", "Mid", "Low", "Lowest"]


def assign_segments(fan_features):
    plan_dummies = pd.get_dummies(fan_features["plan_tier"], prefix="plan").astype(float)
    features = pd.concat(
        [fan_features[["engagement_score", "tenure_years"]], plan_dummies], axis=1
    )

    X = StandardScaler().fit_transform(features)
    labels = KMeans(n_clusters=N_CLUSTERS, random_state=RANDOM_STATE, n_init=10).fit_predict(X)

    result = fan_features.copy()
    result["segment_cluster"] = labels

    cluster_engagement = result.groupby("segment_cluster")["engagement_score"].mean()
    rank_order = cluster_engagement.sort_values(ascending=False).index.tolist()
    descriptor_by_cluster = {
        cluster_id: ENGAGEMENT_DESCRIPTORS[rank] for rank, cluster_id in enumerate(rank_order)
    }

    dominant_tier_by_cluster = result.groupby("segment_cluster")["plan_tier"].agg(
        lambda s: s.mode().iloc[0]
    )

    result["segment"] = result["segment_cluster"].map(
        lambda c: f"{descriptor_by_cluster[c]} Engagement {dominant_tier_by_cluster[c].title()}-Tier"
    )

    return result
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_segments.py -v`
Expected: 5 passed.

- [ ] **Step 6: Commit**

```bash
git add requirements.txt scoring/segments.py tests/test_segments.py
git commit -m "Add fan segmentation module (k-means over engagement/plan/tenure)"
```

---

### Task 2: `storage/db.py` — `segment` column on `weekly_snapshots`

**Files:**
- Modify: `storage/db.py` (`WEEKLY_SNAPSHOTS_SCHEMA`)
- Modify: `tests/test_db.py`

**Interfaces:**
- Consumes: nothing new — `write_weekly_snapshot`'s signature and behavior are
  unchanged (it already writes whatever columns the passed DataFrame has).
- Produces: `weekly_snapshots` now has a `segment TEXT` column. Existing rows/tests that
  don't provide a `segment` column continue to work unchanged.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_db.py`:
```python
def test_write_weekly_snapshot_round_trips_segment_column():
    conn = sqlite3.connect(":memory:")
    create_schema(conn)
    snapshot = pd.DataFrame({
        "fan_id": [1], "week": [1], "engagement_score": [55.0], "tier": ["Cooling"],
        "at_risk": [False], "clv": [4000.0], "segment": ["Mid Engagement Standard-Tier"],
    })
    write_weekly_snapshot(conn, snapshot)
    result = pd.read_sql("SELECT * FROM weekly_snapshots", conn)
    assert result.loc[0, "segment"] == "Mid Engagement Standard-Tier"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_db.py::test_write_weekly_snapshot_round_trips_segment_column -v`
Expected: FAIL — `sqlite3.OperationalError: table weekly_snapshots has no column named segment`.

- [ ] **Step 3: Add the column to the schema**

In `storage/db.py`, change `WEEKLY_SNAPSHOTS_SCHEMA` to:
```python
WEEKLY_SNAPSHOTS_SCHEMA = """
CREATE TABLE IF NOT EXISTS weekly_snapshots (
    fan_id INTEGER,
    week INTEGER,
    engagement_score REAL,
    tier TEXT,
    at_risk INTEGER,
    clv REAL,
    segment TEXT,
    PRIMARY KEY (fan_id, week),
    FOREIGN KEY (fan_id) REFERENCES fans(fan_id)
)
"""
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_db.py -v`
Expected: all pass (previous tests + this new one). Existing round-trip tests that don't
provide `segment` must still pass unchanged (SQLite fills it as `NULL`).

- [ ] **Step 5: Commit**

```bash
git add storage/db.py tests/test_db.py
git commit -m "Add segment column to weekly_snapshots schema"
```

---

### Task 3: Wire `assign_segments` into `scripts/run_season.py`

**Files:**
- Modify: `scripts/run_season.py`
- Modify: `tests/test_run_season.py`

**Interfaces:**
- Consumes: `scoring.segments.assign_segments` (Task 1); the now-`segment`-capable
  `storage.db.write_weekly_snapshot` (Task 2).
- Produces: every snapshot `run_season()` returns/writes now includes a `segment`
  column. `segment_cluster` is never written to any output.

- [ ] **Step 1: Write the failing test**

In `tests/test_run_season.py`, change `test_run_season_produces_weekly_snapshot_files`'s
`expected_columns` line (currently `{"fan_id", "week", "engagement_score", "tier",
"at_risk", "clv"}`) to:
```python
    expected_columns = {"fan_id", "week", "engagement_score", "tier", "at_risk", "clv", "segment"}
```

Then append a new test to the same file:
```python
def test_run_season_never_persists_raw_segment_cluster_label(tmp_path):
    fans, events_history, score_history, snapshots = run_season(
        n_fans=20,
        n_planted_churn=2,
        decline_start_week=2,
        n_weeks=3,
        output_dir=str(tmp_path / "weekly_snapshots"),
        seed=42,
    )

    final_week = 3
    assert "segment_cluster" not in snapshots[final_week].columns
    assert snapshots[final_week]["segment"].notna().all()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_run_season.py -v`
Expected: FAIL — `KeyError: 'segment'` on the modified test, `AssertionError` on the new
test (no `segment` column exists yet).

- [ ] **Step 3: Wire the calculation in**

In `scripts/run_season.py`, add the import (alongside the existing `scoring.clv` import):
```python
from scoring.segments import assign_segments
```

Then, immediately after the existing CLV block (the lines ending in
`snapshot = snapshot.drop(columns=["plan_tier"])`), add:
```python
            fan_features = week_scores[["fan_id", "engagement_score"]].merge(
                fans[["fan_id", "plan_tier", "tenure_years"]], on="fan_id"
            )
            segments = assign_segments(fan_features)
            snapshot = snapshot.merge(segments[["fan_id", "segment"]], on="fan_id")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_run_season.py -v`
Expected: all pass (existing tests + the modified one + the new one).

- [ ] **Step 5: Run the full existing test suite to check for regressions**

Run: `pytest -v`
Expected: all tests pass, 0 failures.

- [ ] **Step 6: Commit**

```bash
git add scripts/run_season.py tests/test_run_season.py
git commit -m "Compute fan segment per fan per week in the season runner"
```

---

### Task 4: Decision log and README pointer

**Files:**
- Modify: `docs/DECISION_LOG.md`
- Modify: `README.md`

**Interfaces:** None (documentation only).

- [ ] **Step 1: Append a new decision log entry**

Add to the end of `docs/DECISION_LOG.md`, after the existing final entry:

```markdown

---

## 2026-08-22 — Added behavioral fan segmentation, after a spike ruled out the obvious feature set

**Decision:** Add `scoring/segments.py`, clustering each week's fan population (k-means,
k=5, refit fresh every week) on `engagement_score`, `plan_tier`, and `tenure_years`, with
a deterministic name derived from each cluster's relative engagement rank and dominant
plan tier (e.g. "Highest Engagement Club-Tier"). The result is one new `segment` column
on `weekly_snapshots`, flowing through the same SQLite → BigQuery pipes as every other
column.

**Why:** The job posting names "attitudinal/behavioral clusters" explicitly
(`docs/job_description.md`), and the project previously had no segmentation beyond the
four engagement tiers, which are just percentile bands of one number. A throwaway spike
first tried clustering on the three raw behavioral signals (attendance/digital/purchase)
and found them 0.94-0.97 correlated with each other in this simulator — real clustering
on them just re-derived overall engagement level, redundant with the existing tiers. A
second spike, clustering on `(engagement_score, plan_tier, tenure_years)` instead — three
genuinely independent variables by construction in `season_simulator/fans.py` — found
real, non-redundant structure (clusters split primarily by plan tier, with engagement-
level sub-splits within the dominant standard tier). This decision builds on the second,
working feature set, not the first.

Clustering refits fresh every week rather than being fit once and reused, matching this
project's existing in-season principle (every other score/tier is recomputed from
scratch each week, never using full-season knowledge). The tradeoff — raw cluster index
numbers aren't stable across weeks — is resolved by deriving a semantic name each week
instead of exposing the raw label; the raw label (`segment_cluster`) is never persisted.

One honest gap, not resolved here: `tenure_years`'s specific contribution to cluster
membership was not rigorously isolated during the spike (a correlation check against
arbitrary/unordered k-means label numbers isn't a valid test) — the segmentation is real
and non-redundant, but exactly how much tenure drives it versus plan tier is not
precisely quantified.

**Reference:** [`docs/design/specs/2026-08-22-segmentation-design.md`](design/specs/2026-08-22-segmentation-design.md).
```

- [ ] **Step 2: Add one pointer sentence to README.md**

In `README.md`'s "What this is" section, in the same paragraph where the CLV sentence
was added ("A third lens attaches an estimated dollar value to that same trajectory —
see `docs/RESULTS.md`..."), append a new sentence to that same paragraph:

```markdown
A fourth lens groups fans each week into five named behavioral segments (e.g. "Highest
Engagement Club-Tier") using k-means over engagement, plan tier, and tenure — see
`docs/RESULTS.md` for which segments actually appeared in a real run.
```

- [ ] **Step 3: Commit**

```bash
git add docs/DECISION_LOG.md README.md
git commit -m "Document the segmentation decision and point README at it"
```

---

## Task 5 (controller-executed, not a subagent dispatch): Real numbers into RESULTS.md

Not a subagent task — run directly by the controller session after Tasks 1-4 are
complete and reviewed clean, following `docs/RESULTS.md`'s existing real-numbers-only
rule:

1. Run `python scripts/run_season.py` (regenerates `data/fan_analytics.db` and
   `data/weekly_snapshots/`, now including `segment`).
2. Query the resulting `data/fan_analytics.db` for the week-18 segment breakdown:
   `SELECT segment, COUNT(*) AS n FROM weekly_snapshots WHERE week = 18 GROUP BY segment
   ORDER BY n DESC`. This is a week-18 snapshot count, not something to sum across weeks
   (same framing precedent as CLV's "Estimated fan value" section).
3. Add a new `## Fan segments` section to `docs/RESULTS.md`, after the existing
   "Estimated fan value" section, reporting the real week-18 segment breakdown in the
   document's existing plain-language style, explicitly stating these are week-18
   snapshot counts (segments are refit fresh each week, so counts from different weeks
   aren't directly comparable in the same way a fixed-category count would be), and
   repeating the `tenure_years`-contribution honesty caveat from the decision log.
4. Commit: `git add docs/RESULTS.md && git commit -m "Add real segment breakdown to RESULTS.md from a live run"`.

## What's explicitly not in this plan

- The Power BI dashboard changes — Day 3 hands-on work, not automatable/testable code.
- A BigQuery view for segment-level rollups — a later call if Day 3's Power BI work
  wants one, not part of this data-layer plan.
- Isolating `tenure_years`'s specific contribution to cluster membership — flagged as an
  honest gap in the decision log, not solved here.
