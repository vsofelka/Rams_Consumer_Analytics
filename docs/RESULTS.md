# Results Summary

A plain-language summary of what the fan engagement / churn pipeline actually produced on its one real run, for quick reference without opening Jupyter. For the full build history and reasoning, see the pointers at the end.

## What the pipeline does

The pipeline simulates a season of Season Ticket Member (STM) behavior week by week (300 fans, 18 weeks) and, for each fan in each week, computes a **rolling engagement score**: a 0–100 composite of attendance, digital activity, and purchase behavior, calculated over a trailing window so recent hot or cold streaks matter more than one old data point. That score buckets each fan into a tier — Super Fan, Engaged, Cooling, or Dormant. On top of that, a **churn risk view** flags a fan as "at risk" when their engagement score has been declining for several consecutive weeks *and* has dropped below a population percentile threshold. This is not a separately trained classifier — it's a rule read directly off the trend of the same engagement score, deliberately kept transparent and simple for this MVP pass.

## Validation result

To check whether the churn rule actually works, the simulator plants a known cohort of 25 fans (out of 300) and deliberately scripts their engagement into a decline starting week 6 — a synthetic ground truth to measure the rule against, since real churn labels don't exist for a synthetic season.

By the final week (week 18):
- **Tier distribution:** Engaged 81, Dormant 76, Cooling 73, Super Fan 70 (300 total).
- **At-risk flags:** 13 fans were flagged "at risk" by the churn rule.
- The rule **caught 8 of the 25 planted-churn fans, with 5 false alarms out of the 13 total flags** (8 true positives, 5 false positives, 17 false negatives).
- **Precision: 0.62, Recall: 0.32, F1: 0.42.**

A caveat on the tier distribution: the engagement score is a *population-relative percentile rank*, recomputed from scratch every week, and the tier cuts are fixed at 25 / 50 / 75. A roughly even four-way split is therefore expected **by construction** — it says nothing about the fan base's absolute engagement level, and it would look about the same even if every fan were highly engaged. The tiers are useful for ranking fans against each other in a given week, not for measuring the population as a whole.

### Detection over the season, week by week

Week 18 is the *worst* week of the back half, not a representative one. Computing the same metrics against every weekly snapshot tells a more useful story:

| Week | Flagged | TP | FP | FN | Precision | Recall | F1 |
|-----:|--------:|---:|---:|---:|----------:|-------:|-----:|
| 9  | 9  | 4  | 5 | 21 | 0.44 | 0.16 | 0.24 |
| 10 | 13 | 9  | 4 | 16 | 0.69 | 0.36 | 0.47 |
| 11 | 15 | 12 | 3 | 13 | 0.80 | 0.48 | 0.60 |
| 12 | 15 | 15 | 0 | 10 | 1.00 | 0.60 | 0.75 |
| 13 | 15 | 15 | 0 | 10 | 1.00 | 0.60 | 0.75 |
| 14 | 19 | 15 | 4 | 10 | 0.79 | 0.60 | 0.68 |
| 15 | 18 | 16 | 2 | 9  | 0.89 | 0.64 | 0.74 |
| 16 | 14 | 13 | 1 | 12 | 0.93 | 0.52 | 0.67 |
| 17 | 16 | 14 | 2 | 11 | 0.88 | 0.56 | 0.68 |
| 18 | 13 | 8  | 5 | 17 | 0.62 | 0.32 | 0.42 |

Detection **peaks mid-to-late season and then decays**: F1 peaks at 0.75 in weeks 12–13 (with perfect precision — 15 flags, 15 of them real), recall peaks at 0.64 in week 15, and both fall away through week 18.

### Why recall is limited — and why it gets *worse* late

The churn rule has two gates: the score must be below the 25th population percentile, **and** it must have fallen strictly week-over-week across the last 4 weekly snapshots (3 consecutive drops). Decomposing week 18 shows which gate is actually binding:

- **Percentile gate: rejects nobody.** All **25 of 25** planted-churn fans sit below the week-18 threshold (a score of 24.86). By week 14 onward, the entire planted cohort clears this gate every week. It is not the limiting factor.
- **Decline-streak gate: binding.** Only **8 of 25** planted fans post a strictly lower score in each of weeks 16, 17, and 18. Those same 8 are exactly the fans flagged from the cohort — the percentile gate removes none of them.

So the constraint is the *strict monotonic decline* requirement, and the reason it tightens over the season is the shape of the planted decline itself. Each planted fan's underlying engagement is `baseline × 0.85^(weeks declining)`, which decays geometrically toward a floor: by week 18 that multiplier is down to 0.12. Their scores have essentially **bottomed out**, and the cohort's average week-over-week change collapses accordingly — from about −4.7 points at week 8 to −0.29 points at week 18. Once a fan is scraping the floor, week-to-week movement is dominated by simulation noise rather than continued decline, so a strictly-lower score every single week stops happening: 23 of 25 planted fans posted a strictly lower score at week 12, versus only 15 of 25 at week 18. Requiring three such drops back-to-back compounds that, leaving 8.

This is a real and instructive limitation of the rule, not a bug: **a "still falling" rule stops firing once a fan has already hit bottom.** A production version would pair the decline-streak trigger with a "sustained low level" condition so that fans who already churned stay visible instead of aging out of the flag.

## Statistical validation

The results above are point estimates from a single run. `notebooks/04_sql_analysis.ipynb` runs three formal statistical tests against the same week-18 data to check whether those numbers hold up.

- **Is the planted-churn cohort's decline statistically real?** Yes — a Mann-Whitney U test comparing the 25 planted-churn fans' week-18 engagement scores (median 5.60) against everyone else's (median 54.63) gives p = 0.000000, well below 0.05. The gap visible in the charts is not sampling noise.
- **How precise are the precision/recall numbers, really?** With only 13 fans flagged, the point estimates carry real uncertainty: precision is 0.62, with a 95% Wilson confidence interval of (0.36, 0.82), and recall is 0.32, with a 95% Wilson confidence interval of (0.17, 0.52). Read these as ranges, not exact figures.
- **Does the rule beat random chance?** Yes, decisively. Flagging 13 fans at random out of 300, with 25 true churners in the population, would be expected to catch only about 1.08 true positives by luck (13 × 25 / 300). The rule actually caught 8. A hypergeometric test puts the probability of matching or beating 8 true positives by chance alone at p = 0.000001.

These three tests were each chosen to fit the shape of the actual data — a rank-based test for a non-normally-distributed score, an interval method suited to small counts, and an exact test suited to sampling without replacement — rather than one default technique applied everywhere; see `docs/DECISION_LOG.md` for the full reasoning.

## What this does and doesn't prove

This validates that the rule-based heuristic is directionally correct — it enriches meaningfully for fans on a known decline path. The base rate is 25 planted churners out of 300 fans, about 8%, so flagging 13 fans at random would be expected to land roughly 8% precision (about 1 real churner). The observed 0.62 precision is therefore around **7–8x better than random guessing**, and it reaches 1.00 at weeks 12–13. That's a genuine, real result from a real run of the pipeline.

What it does **not** prove: this is a rule validated against **synthetic, planted-pattern data** generated by the same codebase that scores it — not a trained model validated against real STM behavior. The 25 planted churners decline in a specific scripted way, and the rule was built (and could be tuned) with knowledge of that pattern, which is a much easier target than messy real-world churn. Precision and recall here describe how well a simple trend rule recovers a known synthetic signal, not how well it would perform on an actual fan base. Treat this as a proof of pipeline mechanics and validation methodology, not as a production-ready churn model.

## Where to look for more

- Design doc: [`docs/superpowers/specs/2026-08-10-fan-engagement-churn-design.md`](superpowers/specs/2026-08-10-fan-engagement-churn-design.md)
- Decision log: [`docs/DECISION_LOG.md`](DECISION_LOG.md)
- Notebooks: [`notebooks/01_generate_season.ipynb`](../notebooks/01_generate_season.ipynb) (simulator run), [`notebooks/02_engagement_model.ipynb`](../notebooks/02_engagement_model.ipynb) (engagement score), [`notebooks/03_churn_view.ipynb`](../notebooks/03_churn_view.ipynb) (churn rule + validation)

Run parameters for this pass: `n_fans=300`, `n_planted_churn=25`, `decline_start_week=6`, `n_weeks=18`, `seed=42`, `window=6`, `decline_weeks=3`, `risk_percentile=25.0` (see `scripts/run_season.py`).
