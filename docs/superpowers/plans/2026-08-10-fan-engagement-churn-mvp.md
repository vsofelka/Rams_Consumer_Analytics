# Fan Engagement Score + Churn Risk View — 48-Hour MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a working, validated, end-to-end pipeline — synthetic season simulator → rolling fan engagement score → churn risk view — that runs week-by-week and proves itself against a known "planted churn cohort," delivered as notebooks (no dashboard yet) plus a short results summary stating the actual validated numbers.

**Architecture:** A season simulator (`season_simulator/`) generates STM population and weekly behavior data one week at a time. Two pure-function scoring modules (`scoring/engagement.py`, `scoring/churn.py`) consume accumulated history and produce a score and a risk flag per fan per week. A runner script (`scripts/run_season.py`) wires these together and writes structured CSV output per week. Notebooks read only the CSV output — never the simulator or scoring code directly — keeping the modeling core fully decoupled from presentation, per the design doc.

**Tech Stack:** Python 3.10+, pandas, numpy, matplotlib, pytest, Jupyter.

## Global Constraints

- Rolling, not static: the simulator advances week-by-week and each week's score/churn computation reads only the accumulated history through that week — never the full season at once. (Design doc: "Architecture")
- Engagement score is a transparent weighted composite index, not a trained model, computed from a trailing recency-weighted window. (Design doc: "Engagement score")
- Churn risk is a rule applied to the engagement score's trajectory (consecutive-week decline + population-percentile threshold), not an independently trained classifier. (Design doc: "Churn risk view"; Decision log: "Churn view will be rule-based")
- The simulator must plant a known-ground-truth churn cohort so detection can be validated with precision/recall, not eyeballed. (Design doc: "Validation")
- 48-hour MVP scope trims: a smaller synthetic population, one coarse digital-engagement signal (not several sub-metrics), a handful of core unit tests rather than exhaustive edge-case coverage, and notebooks as the only output — no Streamlit dashboard in this pass. (Decision log: "MVP scope trimmed to fit the 48-hour window")
- Edge cases that must not error: a partial trailing window in the season's first weeks, and a brand-new STM with no score history (no flag, not an exception). (Design doc: "Engagement score", "Churn risk view")
- Task 11's results summary must state real numbers observed from the actual run, cross-checked against the notebook output — never placeholder or projected figures. (Decision log: "Timeline extended by a couple of days")

---

### Task 1: Project scaffolding and dependencies

**Files:**
- Create: `requirements.txt`
- Create: `pyproject.toml`
- Create: `season_simulator/__init__.py`
- Create: `scoring/__init__.py`
- Create: `scripts/__init__.py`
- Test: `tests/test_setup.py`

**Interfaces:**
- Produces: importable packages `season_simulator`, `scoring`, `scripts`, and a pytest config that puts the repo root on `sys.path` so every later task's tests can `import season_simulator...` / `import scoring...` / `import scripts...` without path hacks.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_setup.py
def test_can_import_season_simulator():
    import season_simulator
    assert season_simulator is not None


def test_can_import_scoring():
    import scoring
    assert scoring is not None


def test_can_import_scripts():
    import scripts
    assert scripts is not None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_setup.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'season_simulator'` (pytest itself may also not be installed yet; if so, run `pip install pytest` first just to confirm the failure mode, then continue).

- [ ] **Step 3: Create the packages and pytest config**

```text
# requirements.txt
pandas>=2.0
numpy>=1.24
matplotlib>=3.7
pytest>=7.0
jupyter>=1.0
```

```toml
# pyproject.toml
[tool.pytest.ini_options]
pythonpath = ["."]
testpaths = ["tests"]
```

Create three empty files: `season_simulator/__init__.py`, `scoring/__init__.py`, `scripts/__init__.py` (each with no content — just makes the directory an importable package).

- [ ] **Step 4: Install dependencies**

Run: `pip install -r requirements.txt`
Expected: installs successfully with no errors.

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/test_setup.py -v`
Expected: `3 passed`

- [ ] **Step 6: Commit**

```bash
git add requirements.txt pyproject.toml season_simulator/__init__.py scoring/__init__.py scripts/__init__.py tests/test_setup.py
git commit -m "$(cat <<'EOF'
Add project scaffolding: packages, pytest config, dependencies

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 2: Fan population generator

**Files:**
- Create: `season_simulator/fans.py`
- Test: `tests/test_fans.py`

**Interfaces:**
- Produces: `generate_fan_population(n_fans: int, n_planted_churn: int, decline_start_week: int, seed: int = 42) -> pd.DataFrame` with columns `fan_id` (int), `tenure_years` (int), `plan_tier` (str, one of "standard"/"premium"/"club"), `baseline_engagement` (float, 0–1), `is_planted_churn` (bool), `decline_start_week` (float, NaN for non-planted fans, the given week number for planted fans).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_fans.py
import pandas as pd
from season_simulator.fans import generate_fan_population


def test_generate_fan_population_shape_and_columns():
    fans = generate_fan_population(n_fans=100, n_planted_churn=10, decline_start_week=6, seed=1)
    assert len(fans) == 100
    expected_columns = {
        "fan_id", "tenure_years", "plan_tier",
        "baseline_engagement", "is_planted_churn", "decline_start_week",
    }
    assert expected_columns.issubset(fans.columns)
    assert fans["is_planted_churn"].sum() == 10
    assert fans["baseline_engagement"].between(0, 1).all()


def test_generate_fan_population_is_reproducible_with_seed():
    fans_a = generate_fan_population(n_fans=50, n_planted_churn=5, decline_start_week=6, seed=7)
    fans_b = generate_fan_population(n_fans=50, n_planted_churn=5, decline_start_week=6, seed=7)
    pd.testing.assert_frame_equal(fans_a, fans_b)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_fans.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'season_simulator.fans'`

- [ ] **Step 3: Write minimal implementation**

```python
# season_simulator/fans.py
import numpy as np
import pandas as pd


def generate_fan_population(n_fans, n_planted_churn, decline_start_week, seed=42):
    rng = np.random.default_rng(seed)

    fan_ids = np.arange(1, n_fans + 1)
    baseline_engagement = rng.beta(a=2, b=2, size=n_fans)
    tenure_years = rng.integers(1, 21, size=n_fans)
    plan_tier = rng.choice(["standard", "premium", "club"], size=n_fans, p=[0.6, 0.3, 0.1])

    planted_churn_ids = rng.choice(fan_ids, size=n_planted_churn, replace=False)
    is_planted_churn = np.isin(fan_ids, planted_churn_ids)

    fans = pd.DataFrame({
        "fan_id": fan_ids,
        "tenure_years": tenure_years,
        "plan_tier": plan_tier,
        "baseline_engagement": baseline_engagement,
        "is_planted_churn": is_planted_churn,
        "decline_start_week": np.where(is_planted_churn, decline_start_week, np.nan),
    })
    return fans
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_fans.py -v`
Expected: `2 passed`

- [ ] **Step 5: Commit**

```bash
git add season_simulator/fans.py tests/test_fans.py
git commit -m "$(cat <<'EOF'
Add synthetic STM population generator with planted churn cohort

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 3: Weekly events generator

**Files:**
- Create: `season_simulator/events.py`
- Test: `tests/test_events.py`

**Interfaces:**
- Consumes: a fans DataFrame from `generate_fan_population` (Task 2) — needs `fan_id`, `baseline_engagement`, `is_planted_churn`, `decline_start_week` columns.
- Produces: `generate_week_events(fans: pd.DataFrame, week: int, seed: int = 42) -> pd.DataFrame` with columns `fan_id`, `week`, `attendance_signal`, `digital_signal`, `purchase_signal` (each float, 0–1).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_events.py
from season_simulator.fans import generate_fan_population
from season_simulator.events import generate_week_events


def test_generate_week_events_shape_and_bounds():
    fans = generate_fan_population(n_fans=50, n_planted_churn=5, decline_start_week=6, seed=1)
    events = generate_week_events(fans, week=1, seed=1)

    assert len(events) == 50
    expected_columns = {"fan_id", "week", "attendance_signal", "digital_signal", "purchase_signal"}
    assert expected_columns.issubset(events.columns)
    for col in ["attendance_signal", "digital_signal", "purchase_signal"]:
        assert events[col].between(0, 1).all()


def test_planted_churn_fans_decline_after_start_week():
    fans = generate_fan_population(n_fans=50, n_planted_churn=10, decline_start_week=3, seed=2)
    early = generate_week_events(fans, week=3, seed=2)
    late = generate_week_events(fans, week=10, seed=2)

    planted_ids = fans.loc[fans["is_planted_churn"], "fan_id"]
    early_avg = early[early["fan_id"].isin(planted_ids)]["attendance_signal"].mean()
    late_avg = late[late["fan_id"].isin(planted_ids)]["attendance_signal"].mean()

    assert late_avg < early_avg
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_events.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'season_simulator.events'`

- [ ] **Step 3: Write minimal implementation**

```python
# season_simulator/events.py
import numpy as np
import pandas as pd

DECAY_RATE = 0.85
NOISE_STD = 0.1


def _effective_engagement(fans, week):
    decline_active = fans["is_planted_churn"] & (week >= fans["decline_start_week"])
    weeks_declining = np.where(decline_active, week - fans["decline_start_week"] + 1, 0)
    decay_factor = DECAY_RATE ** weeks_declining
    return fans["baseline_engagement"] * decay_factor


def generate_week_events(fans, week, seed=42):
    rng = np.random.default_rng(seed * 1000 + week)
    effective = _effective_engagement(fans, week).to_numpy()

    def noisy_signal(base):
        return np.clip(base + rng.normal(0, NOISE_STD, size=len(base)), 0, 1)

    events = pd.DataFrame({
        "fan_id": fans["fan_id"].to_numpy(),
        "week": week,
        "attendance_signal": noisy_signal(effective),
        "digital_signal": noisy_signal(effective),
        "purchase_signal": noisy_signal(effective * 0.6),
    })
    return events
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_events.py -v`
Expected: `2 passed`

- [ ] **Step 5: Commit**

```bash
git add season_simulator/events.py tests/test_events.py
git commit -m "$(cat <<'EOF'
Add weekly behavior event generator with scripted churn decay

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 4: Engagement score computation

**Files:**
- Create: `scoring/engagement.py`
- Test: `tests/test_engagement.py`

**Interfaces:**
- Consumes: an accumulated events history DataFrame (concatenation of `generate_week_events` outputs across weeks) with columns `fan_id`, `week`, `attendance_signal`, `digital_signal`, `purchase_signal`.
- Produces: `compute_weekly_engagement_scores(events_history: pd.DataFrame, current_week: int, window: int = 6) -> pd.DataFrame` with columns `fan_id`, `week`, `engagement_score` (float, 0–100), `tier` (one of "Dormant", "At Risk", "Engaged", "Super Fan").

- [ ] **Step 1: Write the failing test**

```python
# tests/test_engagement.py
import pandas as pd
from season_simulator.fans import generate_fan_population
from season_simulator.events import generate_week_events
from scoring.engagement import compute_weekly_engagement_scores


def test_engagement_score_in_valid_range():
    fans = generate_fan_population(n_fans=30, n_planted_churn=3, decline_start_week=6, seed=5)
    events_history = pd.concat(
        [generate_week_events(fans, week=w, seed=5) for w in range(1, 4)],
        ignore_index=True,
    )
    scores = compute_weekly_engagement_scores(events_history, current_week=3, window=6)

    assert len(scores) == 30
    assert scores["engagement_score"].between(0, 100).all()
    assert set(scores["tier"].unique()).issubset({"Dormant", "At Risk", "Engaged", "Super Fan"})


def test_partial_window_does_not_error_in_first_week():
    fans = generate_fan_population(n_fans=20, n_planted_churn=2, decline_start_week=6, seed=8)
    events_history = generate_week_events(fans, week=1, seed=8)
    scores = compute_weekly_engagement_scores(events_history, current_week=1, window=6)

    assert len(scores) == 20
    assert not scores["engagement_score"].isna().any()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_engagement.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'scoring.engagement'`

- [ ] **Step 3: Write minimal implementation**

```python
# scoring/engagement.py
import numpy as np
import pandas as pd

RAW_SIGNAL_COLUMNS = ["attendance_signal", "digital_signal", "purchase_signal"]
CATEGORY_WEIGHTS = {"attendance_signal": 0.4, "digital_signal": 0.3, "purchase_signal": 0.3}


def _trailing_window_average(events_history, current_week, window):
    start_week = max(1, current_week - window + 1)
    windowed = events_history[
        (events_history["week"] >= start_week) & (events_history["week"] <= current_week)
    ].copy()
    windowed["recency_weight"] = windowed["week"] - start_week + 1

    def weighted_avg(group):
        weights = group["recency_weight"]
        return pd.Series({
            col: np.average(group[col], weights=weights) for col in RAW_SIGNAL_COLUMNS
        })

    return windowed.groupby("fan_id").apply(weighted_avg).reset_index()


def compute_weekly_engagement_scores(events_history, current_week, window=6):
    averaged = _trailing_window_average(events_history, current_week, window)

    scored = averaged[["fan_id"]].copy()
    for col in RAW_SIGNAL_COLUMNS:
        scored[f"{col}_pct"] = averaged[col].rank(pct=True) * 100

    scored["engagement_score"] = sum(
        scored[f"{col}_pct"] * weight for col, weight in CATEGORY_WEIGHTS.items()
    )
    scored["week"] = current_week
    scored["tier"] = pd.cut(
        scored["engagement_score"],
        bins=[-0.1, 25, 50, 75, 100],
        labels=["Dormant", "At Risk", "Engaged", "Super Fan"],
    ).astype(str)

    return scored[["fan_id", "week", "engagement_score", "tier"]]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_engagement.py -v`
Expected: `2 passed`

- [ ] **Step 5: Commit**

```bash
git add scoring/engagement.py tests/test_engagement.py
git commit -m "$(cat <<'EOF'
Add rolling engagement score: recency-weighted composite index

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 5: Churn risk rule

**Files:**
- Create: `scoring/churn.py`
- Test: `tests/test_churn.py`

**Interfaces:**
- Consumes: an accumulated score history DataFrame (concatenation of `compute_weekly_engagement_scores` outputs across weeks) with columns `fan_id`, `week`, `engagement_score`, `tier`.
- Produces: `apply_churn_rule(score_history: pd.DataFrame, current_week: int, decline_weeks: int = 3, risk_percentile: float = 25.0) -> pd.DataFrame` with columns `fan_id`, `week`, `at_risk` (bool).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_churn.py
import pandas as pd
from scoring.churn import apply_churn_rule


def test_at_risk_flag_true_for_consistently_declining_fan():
    score_history = pd.DataFrame({
        "fan_id": [1, 1, 1, 1],
        "week": [1, 2, 3, 4],
        "engagement_score": [80, 60, 40, 20],
    })
    result = apply_churn_rule(score_history, current_week=4, decline_weeks=3, risk_percentile=100.0)
    assert result.loc[result["fan_id"] == 1, "at_risk"].item() == True


def test_at_risk_flag_false_for_fan_without_enough_history():
    score_history = pd.DataFrame({
        "fan_id": [2, 2],
        "week": [3, 4],
        "engagement_score": [50, 45],
    })
    result = apply_churn_rule(score_history, current_week=4, decline_weeks=3, risk_percentile=100.0)
    assert result.loc[result["fan_id"] == 2, "at_risk"].item() == False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_churn.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'scoring.churn'`

- [ ] **Step 3: Write minimal implementation**

```python
# scoring/churn.py
import pandas as pd


def _is_declining(group, decline_weeks):
    group = group.sort_values("week")
    if len(group) < decline_weeks + 1:
        return False
    scores = group["engagement_score"].to_numpy()
    return all(scores[i] < scores[i - 1] for i in range(1, len(scores)))


def apply_churn_rule(score_history, current_week, decline_weeks=3, risk_percentile=25.0):
    recent_weeks = list(range(current_week - decline_weeks, current_week + 1))
    windowed = score_history[score_history["week"].isin(recent_weeks)]

    declining_by_fan = windowed.groupby("fan_id").apply(
        lambda group: _is_declining(group, decline_weeks)
    )

    current_scores = (
        score_history[score_history["week"] == current_week]
        .set_index("fan_id")["engagement_score"]
    )
    risk_threshold = current_scores.quantile(risk_percentile / 100)

    at_risk = pd.DataFrame({
        "fan_id": current_scores.index,
        "week": current_week,
        "engagement_score": current_scores.values,
    })
    at_risk["is_declining"] = at_risk["fan_id"].map(declining_by_fan).fillna(False)
    at_risk["below_risk_threshold"] = at_risk["engagement_score"] <= risk_threshold
    at_risk["at_risk"] = at_risk["is_declining"] & at_risk["below_risk_threshold"]

    return at_risk[["fan_id", "week", "at_risk"]]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_churn.py -v`
Expected: `2 passed`

- [ ] **Step 5: Commit**

```bash
git add scoring/churn.py tests/test_churn.py
git commit -m "$(cat <<'EOF'
Add churn risk rule: decline streak plus percentile threshold

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 6: Validation metrics against the planted churn cohort

**Files:**
- Create: `scoring/validation.py`
- Test: `tests/test_validation.py`

**Interfaces:**
- Consumes: an `at_risk` DataFrame from `apply_churn_rule` (Task 5) for one week (columns `fan_id`, `week`, `at_risk`), and a `fans` DataFrame from `generate_fan_population` (Task 2) (needs `fan_id`, `is_planted_churn`, `decline_start_week`).
- Produces: `evaluate_churn_detection(at_risk: pd.DataFrame, fans: pd.DataFrame, week: int) -> dict` with keys `precision`, `recall`, `f1`, `true_positives`, `false_positives`, `false_negatives`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_validation.py
import numpy as np
import pandas as pd
from scoring.validation import evaluate_churn_detection


def test_evaluate_churn_detection_perfect_match():
    fans = pd.DataFrame({
        "fan_id": [1, 2, 3],
        "is_planted_churn": [True, False, False],
        "decline_start_week": [5, np.nan, np.nan],
    })
    at_risk = pd.DataFrame({
        "fan_id": [1, 2, 3],
        "week": [10, 10, 10],
        "at_risk": [True, False, False],
    })
    result = evaluate_churn_detection(at_risk, fans, week=10)
    assert result["precision"] == 1.0
    assert result["recall"] == 1.0
    assert result["f1"] == 1.0


def test_evaluate_churn_detection_missed_planted_fan():
    fans = pd.DataFrame({
        "fan_id": [1, 2],
        "is_planted_churn": [True, False],
        "decline_start_week": [5, np.nan],
    })
    at_risk = pd.DataFrame({
        "fan_id": [1, 2],
        "week": [10, 10],
        "at_risk": [False, False],
    })
    result = evaluate_churn_detection(at_risk, fans, week=10)
    assert result["recall"] == 0.0
    assert result["true_positives"] == 0
    assert result["false_negatives"] == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_validation.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'scoring.validation'`

- [ ] **Step 3: Write minimal implementation**

```python
# scoring/validation.py
def evaluate_churn_detection(at_risk, fans, week):
    merged = at_risk.merge(fans[["fan_id", "is_planted_churn", "decline_start_week"]], on="fan_id")
    merged["ground_truth_at_risk"] = merged["is_planted_churn"] & (week >= merged["decline_start_week"])

    true_positives = int(((merged["at_risk"]) & (merged["ground_truth_at_risk"])).sum())
    false_positives = int(((merged["at_risk"]) & (~merged["ground_truth_at_risk"])).sum())
    false_negatives = int(((~merged["at_risk"]) & (merged["ground_truth_at_risk"])).sum())

    precision = true_positives / (true_positives + false_positives) if (true_positives + false_positives) > 0 else 0.0
    recall = true_positives / (true_positives + false_negatives) if (true_positives + false_negatives) > 0 else 0.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) > 0 else 0.0

    return {
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "true_positives": true_positives,
        "false_positives": false_positives,
        "false_negatives": false_negatives,
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_validation.py -v`
Expected: `2 passed`

- [ ] **Step 5: Commit**

```bash
git add scoring/validation.py tests/test_validation.py
git commit -m "$(cat <<'EOF'
Add precision/recall validation against planted churn cohort

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 7: Season runner — wire it together and write weekly output

**Files:**
- Create: `scripts/run_season.py`
- Modify: `.gitignore` (add generated data output)
- Test: `tests/test_run_season.py`

**Interfaces:**
- Consumes: `generate_fan_population` (Task 2), `generate_week_events` (Task 3), `compute_weekly_engagement_scores` (Task 4), `apply_churn_rule` (Task 5).
- Produces: `run_season(n_fans, n_planted_churn, decline_start_week, n_weeks, output_dir, window=6, decline_weeks=3, risk_percentile=25.0, seed=42) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict[int, pd.DataFrame]]` returning `(fans, events_history, score_history, weekly_snapshots)`, and writes `fans.csv` plus one `week_NN.csv` per week (columns `fan_id`, `week`, `engagement_score`, `tier`, `at_risk`) to `output_dir`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_run_season.py
from scripts.run_season import run_season
from scoring.validation import evaluate_churn_detection


def test_run_season_produces_weekly_snapshot_files(tmp_path):
    output_dir = tmp_path / "weekly_snapshots"
    fans, events_history, score_history, snapshots = run_season(
        n_fans=40,
        n_planted_churn=5,
        decline_start_week=3,
        n_weeks=5,
        output_dir=str(output_dir),
        seed=99,
    )

    assert len(list(output_dir.glob("week_*.csv"))) == 5
    assert (output_dir / "fans.csv").exists()
    week_5 = snapshots[5]
    assert len(week_5) == 40
    expected_columns = {"fan_id", "week", "engagement_score", "tier", "at_risk"}
    assert expected_columns.issubset(week_5.columns)


def test_run_season_flags_some_planted_churn_fans_by_final_week(tmp_path):
    fans, events_history, score_history, snapshots = run_season(
        n_fans=60,
        n_planted_churn=10,
        decline_start_week=3,
        n_weeks=10,
        output_dir=str(tmp_path / "weekly_snapshots"),
        seed=100,
    )

    final_week = 10
    at_risk_final = snapshots[final_week][["fan_id", "week", "at_risk"]]
    result = evaluate_churn_detection(at_risk_final, fans, week=final_week)
    assert result["recall"] > 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_run_season.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'scripts.run_season'`

- [ ] **Step 3: Write minimal implementation**

```python
# scripts/run_season.py
import os
import pandas as pd

from season_simulator.fans import generate_fan_population
from season_simulator.events import generate_week_events
from scoring.engagement import compute_weekly_engagement_scores
from scoring.churn import apply_churn_rule


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
):
    fans = generate_fan_population(n_fans, n_planted_churn, decline_start_week, seed=seed)
    os.makedirs(output_dir, exist_ok=True)
    fans.to_csv(os.path.join(output_dir, "fans.csv"), index=False)

    events_history = pd.DataFrame(
        columns=["fan_id", "week", "attendance_signal", "digital_signal", "purchase_signal"]
    )
    score_history = pd.DataFrame(columns=["fan_id", "week", "engagement_score", "tier"])
    weekly_snapshots = {}

    for week in range(1, n_weeks + 1):
        week_events = generate_week_events(fans, week, seed=seed)
        events_history = pd.concat([events_history, week_events], ignore_index=True)

        week_scores = compute_weekly_engagement_scores(events_history, current_week=week, window=window)
        score_history = pd.concat([score_history, week_scores], ignore_index=True)

        week_at_risk = apply_churn_rule(
            score_history, current_week=week, decline_weeks=decline_weeks, risk_percentile=risk_percentile
        )

        snapshot = week_scores.merge(week_at_risk[["fan_id", "at_risk"]], on="fan_id")
        snapshot.to_csv(os.path.join(output_dir, f"week_{week:02d}.csv"), index=False)
        weekly_snapshots[week] = snapshot

    return fans, events_history, score_history, weekly_snapshots


if __name__ == "__main__":
    run_season(
        n_fans=300,
        n_planted_churn=25,
        decline_start_week=6,
        n_weeks=18,
        output_dir="data/weekly_snapshots",
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_run_season.py -v`
Expected: `2 passed`

- [ ] **Step 5: Update .gitignore for generated data**

Add this line to `.gitignore`:

```text
data/weekly_snapshots/
```

- [ ] **Step 6: Run the full test suite to confirm nothing else broke**

Run: `pytest -v`
Expected: all tests across every task pass.

- [ ] **Step 7: Generate the real season data for the notebooks**

Run: `python scripts/run_season.py`
Expected: `data/weekly_snapshots/` now contains `fans.csv` and `week_01.csv` through `week_18.csv`.

- [ ] **Step 8: Commit**

```bash
git add scripts/run_season.py tests/test_run_season.py .gitignore
git commit -m "$(cat <<'EOF'
Add season runner: wire simulator and scoring into weekly output

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 8: Notebook 1 — generate and sanity-check the season

**Files:**
- Create: `notebooks/01_generate_season.ipynb`

**Interfaces:**
- Consumes: `run_season` (Task 7), reading nothing from disk — this notebook is what *creates* the output data other notebooks will read.

Notebooks aren't unit-testable the way the modules in Tasks 2–7 are (which already have full test coverage) — verification here means running every cell top to bottom and checking the output matches what's described, not writing assertions.

- [ ] **Step 1: Create the notebook with these cells, in order**

Cell 1 (path setup — makes imports work whether Jupyter's working directory is the repo root or `notebooks/`):

```python
import sys, os

if os.path.basename(os.getcwd()) == "notebooks":
    os.chdir("..")
if os.getcwd() not in sys.path:
    sys.path.insert(0, os.getcwd())
```

Cell 2 (imports and run):

```python
import pandas as pd
import matplotlib.pyplot as plt
from scripts.run_season import run_season

fans, events_history, score_history, snapshots = run_season(
    n_fans=300,
    n_planted_churn=25,
    decline_start_week=6,
    n_weeks=18,
    output_dir="data/weekly_snapshots",
    seed=42,
)
```

Cell 3 (sanity checks):

```python
print(fans.shape)
print(fans["is_planted_churn"].sum())
print(events_history.shape)
fans.head()
```

Cell 4 (visual sanity check — planted cohort should visibly diverge):

```python
planted_ids = fans.loc[fans["is_planted_churn"], "fan_id"]
tagged = events_history.copy()
tagged["cohort"] = tagged["fan_id"].isin(planted_ids).map({True: "Planted Churn", False: "Everyone Else"})
trend = tagged.groupby(["week", "cohort"])["attendance_signal"].mean().unstack()

trend.plot(marker="o")
plt.title("Average Attendance Signal by Week")
plt.xlabel("Week")
plt.ylabel("Attendance Signal")
plt.show()
```

- [ ] **Step 2: Run all cells top to bottom**

Expected:
- Cell 3 prints `(300, 6)`, then `25`, then `(300, 3)` for week 1 alone growing to `(5400, 5)` by the time all weeks have run (only the final state is visible after Cell 2 completes all 18 weeks, so `events_history.shape` should read `(5400, 5)`).
- Cell 4 renders a line chart with two lines: "Planted Churn" trending downward starting around week 6, "Everyone Else" staying roughly flat with minor noise.

- [ ] **Step 3: Save the notebook**

Save via Jupyter (File → Save, or Ctrl/Cmd+S) so cell outputs are persisted in the `.ipynb` file.

- [ ] **Step 4: Commit**

```bash
git add notebooks/01_generate_season.ipynb
git commit -m "$(cat <<'EOF'
Add notebook: generate season and sanity-check simulator output

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 9: Notebook 2 — explore the engagement score

**Files:**
- Create: `notebooks/02_engagement_model.ipynb`

**Interfaces:**
- Consumes: the CSV files written to `data/weekly_snapshots/` by Task 7/8 (`week_*.csv`) — reads from disk only, does not re-run the simulator, demonstrating the decoupling the design doc calls for.

- [ ] **Step 1: Create the notebook with these cells, in order**

Cell 1 (same path-setup boilerplate as Task 8, Cell 1):

```python
import sys, os

if os.path.basename(os.getcwd()) == "notebooks":
    os.chdir("..")
if os.getcwd() not in sys.path:
    sys.path.insert(0, os.getcwd())
```

Cell 2 (load from disk):

```python
import glob
import pandas as pd
import matplotlib.pyplot as plt

snapshot_files = sorted(glob.glob("data/weekly_snapshots/week_*.csv"))
all_weeks = pd.concat([pd.read_csv(f) for f in snapshot_files], ignore_index=True)
all_weeks.head()
```

Cell 3 (score distribution in the final week):

```python
final_week = all_weeks["week"].max()
final = all_weeks[all_weeks["week"] == final_week]

final["engagement_score"].plot(kind="hist", bins=20, title=f"Engagement Score Distribution — Week {final_week}")
plt.xlabel("Engagement Score")
plt.show()

final["tier"].value_counts()
```

Cell 4 (trend lines for a handful of sample fans):

```python
sample_fan_ids = all_weeks["fan_id"].drop_duplicates().sample(5, random_state=1)
sample = all_weeks[all_weeks["fan_id"].isin(sample_fan_ids)]

for fan_id, group in sample.groupby("fan_id"):
    plt.plot(group["week"], group["engagement_score"], marker="o", label=f"Fan {fan_id}")
plt.legend()
plt.title("Engagement Score Trend — Sample Fans")
plt.xlabel("Week")
plt.ylabel("Engagement Score")
plt.show()
```

- [ ] **Step 2: Run all cells top to bottom**

Expected:
- Cell 3's histogram shows scores spread across roughly the full 0–100 range (percentile-based scoring should avoid clumping), and `tier.value_counts()` sums to 300.
- Cell 4 renders 5 distinct lines with visible week-to-week movement, not flat lines.

- [ ] **Step 3: Save the notebook**

- [ ] **Step 4: Commit**

```bash
git add notebooks/02_engagement_model.ipynb
git commit -m "$(cat <<'EOF'
Add notebook: explore engagement score distribution and trends

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 10: Notebook 3 — churn view and validation

**Files:**
- Create: `notebooks/03_churn_view.ipynb`

**Interfaces:**
- Consumes: `data/weekly_snapshots/week_*.csv` and `data/weekly_snapshots/fans.csv` from disk, and `evaluate_churn_detection` (Task 6).

- [ ] **Step 1: Create the notebook with these cells, in order**

Cell 1 (same path-setup boilerplate):

```python
import sys, os

if os.path.basename(os.getcwd()) == "notebooks":
    os.chdir("..")
if os.getcwd() not in sys.path:
    sys.path.insert(0, os.getcwd())
```

Cell 2 (load from disk):

```python
import glob
import pandas as pd
from scoring.validation import evaluate_churn_detection

snapshot_files = sorted(glob.glob("data/weekly_snapshots/week_*.csv"))
all_weeks = pd.concat([pd.read_csv(f) for f in snapshot_files], ignore_index=True)
fans = pd.read_csv("data/weekly_snapshots/fans.csv")
```

Cell 3 (the at-risk list — the actual actionable output):

```python
final_week = all_weeks["week"].max()
final = all_weeks[all_weeks["week"] == final_week]

at_risk_list = final[final["at_risk"]].sort_values("engagement_score")
at_risk_list[["fan_id", "engagement_score", "tier"]]
```

Cell 4 (validation against the planted cohort):

```python
at_risk_final = final[["fan_id", "week", "at_risk"]]
result = evaluate_churn_detection(at_risk_final, fans, week=final_week)

print(f"Precision: {result['precision']:.2f}")
print(f"Recall: {result['recall']:.2f}")
print(f"F1: {result['f1']:.2f}")
print(
    f"True positives: {result['true_positives']}, "
    f"False positives: {result['false_positives']}, "
    f"False negatives: {result['false_negatives']}"
)
```

- [ ] **Step 2: Run all cells top to bottom**

Expected:
- Cell 3 shows a non-empty table of at-risk fans.
- Cell 4 prints precision/recall/F1 with **recall > 0** — meaning the rule is catching at least some of the planted-churn fans by the final week. Precision and recall won't be perfect (this is a rule-based heuristic, not a trained model); recall of exactly 0 or precision of exactly 0 means the rule isn't working and the `decline_weeks` / `risk_percentile` knobs in `scripts/run_season.py`'s call to `run_season` need tuning before moving on.

- [ ] **Step 3: Save the notebook**

- [ ] **Step 4: Commit**

```bash
git add notebooks/03_churn_view.ipynb
git commit -m "$(cat <<'EOF'
Add notebook: at-risk list and validation against planted cohort

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 11: Results summary for interview reference

**Files:**
- Create: `docs/RESULTS.md`

**Interfaces:**
- Consumes: the actual output produced by running Notebooks 1–3 (Tasks 8–10) against the real season generated in Task 7 — the precision/recall/F1 numbers, the at-risk list, and the tier distribution. This task cannot be done until Tasks 7–10 have actually been run, since it reports real numbers, not projected ones.

Added per a scope decision made after the original 10-task plan: with the timeline extended, a short standalone writeup of what the validated results actually show is useful for interview reference — readable without opening Jupyter, and a sanity check on the results before discussing them live.

- [ ] **Step 1: Re-open Notebook 3 (or read its saved cell outputs) and record the actual numbers**

From the saved outputs of `notebooks/03_churn_view.ipynb` (Task 10), note:
- The final week's precision, recall, and F1 from the `evaluate_churn_detection` call.
- The count of fans flagged `at_risk` in the final week.
- From Notebook 2 (Task 9), the tier distribution (`tier.value_counts()`) for the final week.

- [ ] **Step 2: Write `docs/RESULTS.md`**

Structure it around what was actually observed, using the real numbers from Step 1 — not placeholders. Cover, in plain language a non-technical reader (or a technical interviewer skimming quickly) can follow:
- What the pipeline does in one paragraph (rolling engagement score, churn view as a derived trend read).
- The validation result: how many of the planted-churn fans the rule caught by the final week (recall), how many flags were false alarms (precision), stated plainly (e.g. "caught N of M fans who were declining, with P false alarms").
- One honest paragraph on what the numbers do and don't prove — this is a rule-based heuristic validated against synthetic, planted-pattern data, not a trained model validated against real fan behavior. State that directly; don't oversell it.
- A pointer to where to look for more: the design doc, decision log, and the three notebooks themselves.

- [ ] **Step 3: Cross-check the numbers against the notebook outputs one more time**

Re-read the saved notebook cell outputs and confirm every number quoted in `docs/RESULTS.md` matches exactly. A mismatch here is worse than not writing the doc at all — it would misrepresent what the project shows in front of an interviewer.

- [ ] **Step 4: Commit**

```bash
git add docs/RESULTS.md
git commit -m "$(cat <<'EOF'
Add results summary with actual validation numbers from the MVP run

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
EOF
)"
```

---

## Definition of Done for the MVP

- `pytest -v` passes across all of Tasks 1–7.
- `python scripts/run_season.py` runs without error and produces `fans.csv` plus 18 weekly CSVs in `data/weekly_snapshots/`.
- All three notebooks run top-to-bottom without error and produce the expected output described in their tasks.
- Notebook 3's validation cell shows recall > 0 against the planted churn cohort.
- `docs/RESULTS.md` states the actual observed precision/recall/F1 and at-risk count, matching the notebook output exactly.
- No Streamlit dashboard, no trained classifier, no Power BI/Tableau work — those are explicitly out of scope for this MVP pass (see Decision Log). What to do with the extra timeline room is a decision to make after this list is complete, not mid-build.
