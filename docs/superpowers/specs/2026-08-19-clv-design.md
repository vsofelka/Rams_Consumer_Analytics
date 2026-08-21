# Customer Lifetime Value (CLV) — Design

## Context

The engagement-score/churn pipeline and its Power BI dashboard are complete and merged to main. This adds a second layer on top of that same core — not a new, separate use case — directly addressing a gap identified in a recruiter-perspective review of the project against `docs/job_description.md`: the JD names customer lifetime value explicitly, alongside churn, and the project currently has no dollar-value story at all. Every number the churn view produces today is a count ("13 fans flagged"); this makes those counts a revenue figure a marketing team would actually act on.

This is deliberately scoped as an extension of the existing churn/engagement work — same fans, same weekly data, same at-risk list — rather than a standalone CLV model, per the project's own "build one well, not several shallowly" principle (`PROJECT_CONTEXT.md`). No new simulator, no new validation methodology, no new page in the dashboard.

No real Rams pricing or renewal-rate data exists. Every dollar figure and every retention assumption below is a clearly labeled **placeholder** — reasonable, round, order-of-magnitude numbers, not a fitted or researched model. They live in one place (`scoring/clv.py`) specifically so they're trivial to replace once real figures are available.

## Goals

- Attach a defensible, transparent dollar figure to every fan, every week, derived only from data the pipeline already has.
- Make that figure respond to the churn signal already being computed — a fan's CLV should visibly change as their engagement tier changes and as they become flagged at-risk — so the two views reinforce each other instead of sitting side by side.
- Be explicit, in code comments and in docs, about the difference between this and the churn rule: churn was validated against a known planted-churn ground truth with real statistical tests. CLV has no equivalent ground truth to validate against — it is an assumption-driven estimate, and the docs must say so plainly rather than imply a rigor it doesn't have.

## Architecture & Data Flow

```
season_simulator ─┐
                   ├─→ scoring (engagement.py, churn.py, clv.py [new]) ─→ scripts/run_season.py ─┬─→ data/weekly_snapshots/*.csv (unchanged)
                   │                                                                              └─→ data/fan_analytics.db (SQLite)
                   │
                   └─→ scripts/load_to_bigquery.py ─→ BigQuery (weekly_snapshots.clv column + v_at_risk_current.clv) ─→ Power BI
```

No new inputs and no new upstream dependency: `scripts/run_season.py`'s existing weekly loop already has each fan's `plan_tier` (static, from `fans`) and that week's freshly-computed `engagement_score`/`tier`/`at_risk`. CLV is a pure function of exactly those three already-in-hand values.

## `scoring/clv.py` (new module)

Pure function, unit-tested, same shape as `scoring/churn.py` — no classes, no state:

```python
def estimate_clv(plan_tier: str, engagement_tier: str, at_risk: bool) -> float:
    ...
```

**Formula:**
```
CLV = ANNUAL_VALUE[plan_tier] × EXPECTED_REMAINING_YEARS[engagement_tier] × (AT_RISK_DISCOUNT if at_risk else 1.0)
```

**Placeholder constants** (module-level, named, commented as placeholders pending real Rams pricing/retention data):

| `plan_tier` | `ANNUAL_VALUE` |
|---|---|
| standard | $2,000 |
| premium | $6,000 |
| club | $15,000 |

| `engagement_tier` | `EXPECTED_REMAINING_YEARS` |
|---|---|
| Super Fan | 8 |
| Engaged | 5 |
| Cooling | 2 |
| Dormant | 0.5 |

`AT_RISK_DISCOUNT = 0.5` — applied on top of the tier-based years figure when `at_risk` is `True`, so a currently-declining fan's CLV reflects that decline beyond just whatever tier they're already in.

Sanity checks: a Super Fan on a club plan → $15,000 × 8 = $120,000. A Dormant, at-risk, standard-tier fan → $2,000 × 0.5 × 0.5 = $500.

**Why tier-only (not tier + `tenure_years`):** a longer-tenured fan intuitively might have different retention odds, but there's no real data to justify a specific interaction shape — adding `tenure_years` as a second factor would be reaching for false precision the placeholder data can't support. Tier alone, plus the at-risk discount, keeps every input independently swappable and the whole formula explainable in one sentence.

## Storage

- `storage/db.py`: `weekly_snapshots` table gains one new column, `clv REAL`. `write_weekly_snapshot` passes it through like every existing column — no schema versioning/migration needed since this is a fresh-generated SQLite file each run (`WRITE_TRUNCATE`-equivalent regeneration, per existing convention).
- `scripts/run_season.py`: calls `estimate_clv(...)` inside the existing weekly loop, right alongside where `tier` and `at_risk` are already computed, and includes the result in the row written to both the CSV and SQLite outputs.

## BigQuery

- `scripts/load_to_bigquery.py`'s `read_weekly_snapshots` needs **no code change** — it's a `SELECT *` passthrough, so the new `clv` column flows through automatically once it exists in SQLite.
- `v_at_risk_current`'s view SQL (`_view_queries()`) gains one additional selected column, `w.clv`, so the at-risk list carries dollar value with it into the dashboard.

## Power BI (Day 3 work — not built as part of this spec's implementation plan)

No new page. Two additions to the existing **Weekly Snapshot** page (Page 2):
- `clv` added to the existing at-risk table's columns (alongside `fan_id`, `engagement_score`, `tier`).
- A new `[At-Risk CLV]` DAX measure — `SUM` of `clv` filtered to `at_risk = TRUE` — added as a fifth header card on that page.

This is hands-on Power BI Desktop work, done live once the data layer is built and verified, the same way the original dashboard build was. The implementation plan for this spec covers the data/code layer only; the Power BI addition is tracked separately.

## Documentation

- `docs/DECISION_LOG.md` — new entry: why CLV was added (JD alignment), why it's dynamic and tier-based, and the explicit "this is a placeholder, not a validated model" caveat.
- `docs/RESULTS.md` — new section reporting the actual CLV numbers produced by a real run (season-wide at-risk CLV total, and the same caveat repeated here since this is the doc most likely to be read in isolation).
- `README.md` — one addition to the "What this is" section noting the CLV layer exists and pointing at `docs/RESULTS.md`.

## Testing

`tests/test_clv.py`, matching `tests/test_churn.py`'s style — flat `test_<function>_<expected_behavior>` functions, no classes, no fixtures beyond plain literals:

- Each of the 4 engagement tiers returns the expected base value for a given `plan_tier`, `at_risk=False`.
- `at_risk=True` halves the result relative to the same tier/plan with `at_risk=False`.
- The full sanity-check case: Dormant + at-risk + standard → `500.0` exactly.
- The full sanity-check case: Super Fan + not-at-risk + club → `120000.0` exactly.

No defensive error handling and no corresponding tests for invalid `plan_tier`/`engagement_tier` values — inputs are always controlled by the pipeline (`plan_tier` comes from `season_simulator/fans.py`'s fixed choice list, `engagement_tier` from `scoring/engagement.py`'s fixed tier labels), matching this repo's existing convention of not handling cases that can't occur.

## Out of Scope

- Real Rams pricing, renewal-rate, or retention-curve data — placeholders only, pending Victor's own research.
- Segmentation/behavioral clusters (separate, subsequent piece of work).
- Any change to the churn rule itself, the engagement score formula, or the statistical validation already in `notebooks/04_sql_analysis.ipynb`.
- The Power BI dashboard changes themselves (tracked as Day 3 hands-on work, not part of this spec's implementation plan).
