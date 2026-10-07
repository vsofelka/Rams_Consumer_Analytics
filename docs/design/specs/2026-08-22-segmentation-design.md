# Fan Segmentation (Behavioral/Attitudinal Clusters) — Design

## Context

The engagement-score/churn pipeline, its Power BI dashboard, and the CLV layer (Day 1)
are complete. This adds a third lens on top of the same core — not a new, separate use
case — addressing another gap identified in the recruiter-perspective review against
`docs/job_description.md`: the JD names "attitudinal/behavioral clusters" and "purchase
motivators" explicitly, and the project currently has no segmentation beyond the four
engagement tiers (Super Fan/Engaged/Cooling/Dormant), which are really just percentile
bands of one number.

Two throwaway spikes (not part of this spec's implementation, findings only) determined
the actual feature basis:

1. **Rejected:** clustering on the three raw behavioral signals (attendance/digital/
   purchase percentile ranks). These are 0.94–0.97 correlated with each other in the
   simulator (all three are noisy observations of one shared latent engagement value,
   not independent traits) — k-means on them just re-derives overall engagement level
   (Spearman(cluster, mean_pct) = 0.76, near-zero centroid spread across axes),
   redundant with the tiers that already exist.
2. **Confirmed:** clustering on `(engagement_score, plan_tier, tenure_years)`. These
   three are genuinely near-zero correlated with each other (independent random draws
   in `season_simulator/fans.py`). k-means finds real, non-redundant structure: clusters
   split primarily by `plan_tier` with engagement-level sub-splits within the dominant
   standard tier. Spearman(cluster, engagement_score) ≈ 0 confirms clusters aren't just
   re-deriving the existing tiers.

This spec builds on finding 2. Like CLV, this is deliberately scoped as an extension of
the existing core — same fans, same weekly data — rather than a standalone model, per
the project's "build one well, not several shallowly" principle (see `docs/DECISION_LOG.md`).

## Goals

- Produce a genuinely non-redundant segmentation — verified during the spike, not
  assumed — that adds real information beyond the existing engagement tiers.
- Keep the same in-season architectural discipline as every other score/tier in this
  project: recomputed fresh each week from that week's data, never using full-season
  knowledge.
- Give each week's clusters a human-readable, semantically stable name despite being
  refit from scratch every week (raw cluster index numbers are not stable across weeks).
- Be honest in the docs, matching the CLV precedent, about what this segmentation does
  and doesn't show — in particular, that `tenure_years`'s specific contribution was not
  rigorously isolated in the spike (a Spearman check against arbitrary/unordered k-means
  labels is not a valid test) and shouldn't be overclaimed in the final write-up.

## Architecture & Data Flow

```
season_simulator ─┐
                   ├─→ scoring (engagement.py, churn.py, clv.py, segments.py [new]) ─→ scripts/run_season.py ─┬─→ data/weekly_snapshots/*.csv
                   │                                                                                          └─→ data/fan_analytics.db (SQLite)
                   │
                   └─→ scripts/load_to_bigquery.py ─→ BigQuery (weekly_snapshots.segment column) ─→ Power BI
```

Same no-new-inputs shape as CLV: `scripts/run_season.py`'s weekly loop already has each
fan's `plan_tier` (static), `tenure_years` (static), and that week's `engagement_score`.
Segmentation is a function of exactly those three already-in-hand values, refit fresh
each week — never using data from other weeks.

## `scoring/segments.py` (new module)

```python
def assign_segments(fan_features: pd.DataFrame) -> pd.DataFrame:
    ...
```

Input: a DataFrame with one row per fan for the current week — `fan_id`, `plan_tier`,
`tenure_years`, `engagement_score`. Output: the same fans with two new columns,
`segment_cluster` (0–4, the raw k-means label, not stable across weeks) and `segment`
(the semantic name, described below).

**Clustering:** `sklearn.cluster.KMeans`, `n_clusters=5`, `random_state=42` (matching
this project's existing seed convention), fit fresh on that week's fan population every
time this function is called — never persisted or reused across weeks. Features:
`engagement_score` (as-is, already 0–100), `tenure_years` (as-is, 1–20), and `plan_tier`
one-hot encoded into three dummy columns (`standard`/`premium`/`club` — nominal, not
ordinal, since the tiers aren't equally spaced in any meaningful sense). All features
are standardized (`sklearn.preprocessing.StandardScaler`) before fitting, so the
continuous features don't dominate distance purely due to scale.

**Naming (fully deterministic, collision-free by construction):**
1. After fitting, assign each fan its raw cluster label (0–4), then group the *original,
   unstandardized* fan data by that label and compute each cluster's mean
   `engagement_score` directly from member fans (not from `kmeans.cluster_centers_`,
   which is in standardized space — simpler to reason about and test against real
   engagement-score values directly).
2. Rank the 5 clusters by that mean, descending (1st = highest, 5th = lowest — always a
   strict ranking since means of continuous floats, no tie-breaking needed).
3. Map rank position to a descriptor: `{1: "Highest", 2: "High", 3: "Mid", 4: "Low",
   5: "Lowest"}` + `" Engagement"`.
4. For each cluster, compute its dominant `plan_tier` — the mode of `plan_tier` among
   its member fans that week.
5. `segment = f"{descriptor} {dominant_plan_tier.title()}-Tier"`, e.g.
   `"Highest Engagement Club-Tier"`, `"Low Engagement Standard-Tier"`.

Because the descriptor comes from a strict 1–5 rank position (not a coarse bucket), two
clusters can never produce the same name in the same week, even when they share a
dominant plan tier — exactly the case the spike showed (multiple standard-tier clusters
split by engagement level get distinct ranks, hence distinct names).

`tenure_years` remains a clustering *feature* (it still influences which fans group
together) but does not appear in the generated name — baking three dimensions into a
label gets unwieldy, and its specific contribution wasn't rigorously isolated in the
spike (see Goals).

## Wiring into `scripts/run_season.py`

Same pattern as CLV: inside the existing weekly loop, after `tier`/`at_risk`/`clv` are
computed, build the small per-week features DataFrame (`fan_id`, `plan_tier`,
`tenure_years` merged from `fans`; `engagement_score` from that week's `week_scores`),
call `assign_segments(...)`, and merge the resulting `segment` column onto `snapshot`
before it's written out. `segment_cluster` (the raw 0–4 label) is *not* persisted to
`weekly_snapshots` — it's an internal detail of the naming algorithm, not something
downstream consumers need, and persisting an unstable-across-weeks raw index would
invite someone to misuse it as if it were a stable identity.

## Storage

`storage/db.py`: `weekly_snapshots` gains one new column, `segment TEXT`. Same
no-migration-needed situation as CLV — this is a fresh-generated SQLite file each run.

## BigQuery

`scripts/load_to_bigquery.py`'s `read_weekly_snapshots` needs no code change (`SELECT *`
passthrough). No new view and no changes to `v_at_risk_current` in this spec — a
segment-level rollup view (e.g. counts/avg engagement by segment per week), if the Day 3
Power BI work wants one, is that day's call, not part of this data-layer plan.

## Dependencies

`requirements.txt` gains `scikit-learn>=1.3` (a real dependency now, not an ad hoc
worktree install for the spikes).

## Documentation

- `docs/DECISION_LOG.md` — new entry: why segmentation was added (JD alignment), the two
  spike findings (rejected basis, confirmed basis) and why, why clustering refits weekly
  instead of being fit once, and the honesty caveat about `tenure_years`'s unverified
  specific contribution.
- `docs/RESULTS.md` — new section reporting the actual week-18 segment breakdown from a
  real run (which 5 segments appeared, how many fans in each), with the same
  "week-18 snapshot, not summed across weeks" framing precedent CLV established, since
  segment counts are also inherently a per-week snapshot, not something to accumulate.
- `README.md` — one sentence in "What this is" noting the segmentation layer exists.

## Testing

`tests/test_segments.py`, matching `tests/test_clv.py`'s style — flat
`test_<function>_<expected_behavior>` functions. Structural assertions (not exact
centroid values, since those depend on floating-point k-means internals):

- Exactly 5 distinct `segment` names appear across a populated fan-features DataFrame.
- Every input fan appears exactly once in the output, each with exactly one `segment`.
- Every generated `segment` string matches the expected pattern (one of the 5 descriptor
  words, followed by `" Engagement "`, followed by a `.title()`-cased plan tier name and
  `"-Tier"`) — a regex or simple parse check, not a hardcoded exact-string list, since
  which specific descriptor lands on which plan tier will vary depending on the input.
- With a small, hand-constructed fixture where one plan tier's fans are given
  deliberately much higher engagement scores than another's, confirm the resulting
  segment names' relative engagement ranking matches the constructed expectation (e.g.
  the group with the highest scores gets "Highest Engagement..." or "High Engagement...",
  not "Lowest Engagement...") — this is the one test with looser tolerance, calibrated to
  the plan+test-writer's judgment at implementation time, not exact-match, since k-means
  cluster boundaries with a small fixture can be sensitive to exact input values.
- `random_state=42` is fixed in the implementation (not test-overridable) so results are
  reproducible run to run — verified by running one test twice in the same process and
  asserting identical output for identical input.

No defensive error handling beyond what's needed, matching this repo's existing
convention (`scoring/churn.py`, `scoring/clv.py`, `scripts/load_to_bigquery.py`).

## Out of Scope

- Real Rams data — this is still entirely built on the synthetic simulator, no
  behavioral-clustering-specific real data exists or is claimed.
- A Power BI page or view for this feature — Day 3 hands-on work, not part of this
  spec's implementation plan.
- Persisting the raw `segment_cluster` index — deliberately not stored (see "Wiring"
  above).
- Any change to CLV, the churn rule, the engagement score formula, or the statistical
  validation already in `notebooks/04_sql_analysis.ipynb`.
- A rigorous isolation of `tenure_years`'s specific contribution to cluster membership
  (e.g. an ablation comparing 2-feature vs. 3-feature clustering) — flagged as an honest
  gap, not solved here.
