# Design: Rolling Fan Engagement Score + Churn Risk View

**Date:** 2026-08-10
**Status:** Approved by Victor, ready for implementation planning

## Purpose

Built as a project for Victor Sofelkanik's application to the LA Rams' Intern, Marketing Analytics & Consumer Insights role. See [`PROJECT_CONTEXT.md`](../../../PROJECT_CONTEXT.md) and [`docs/job_description.md`](../job_description.md) for full background.

Core constraint: the project must contribute value **in-season**, not just as a preseason planning exercise — so it's built as a rolling pipeline that updates on a recurring cadence as new data comes in, not a static one-off analysis.

## Direction

Of the three candidate use cases (renewal/churn risk scoring, rolling fan engagement score, purchase/upsell propensity), we're building a **layered combination of the first two**: one core pipeline producing a rolling fan engagement score for Season Ticket Members (STMs), with churn risk as a second view derived from that same score's trajectory — not a separately trained model. Purchase/upsell propensity is out of scope for this build.

This maps directly onto specific language in the job description's "Leverage experience to create data-driven models..." bullet: "churn predictions" and "degrees and **shifts** of fandom" are both named explicitly, and an engagement score with tiered segmentation matches the qualifications bullet on "fan/customer segmentation schemas" and "attitudinal/behavioral clusters."

Purchase/upsell propensity was considered and deprioritized — of the three candidate use cases, its anchor in the JD text ("purchase motivators") is the weakest, since "motivators" describes *why* someone buys rather than *whether* they will.

## Architecture

```
season_simulator/          # generates a synthetic season week-by-week
    fans.py                 # STM population (tenure, plan tier, baseline engagement propensity)
    events.py                # weekly attendance, digital activity, purchases
scoring/
    engagement.py           # computes weekly engagement score per STM
    churn.py                  # applies trend rule to engagement history -> risk flag
data/
    weekly_snapshots/        # output: one file per week, per-STM scores + risk flags
notebooks/
    01_generate_season.ipynb   # run the simulator, sanity-check the data
    02_engagement_model.ipynb  # build/validate the scoring logic
    03_churn_view.ipynb        # apply and validate the churn rule
app/                        # Streamlit dashboard reading from data/weekly_snapshots
tests/                      # pytest unit tests for scoring/churn functions
```

The simulator advances week-by-week and appends to history rather than generating one static table. Engagement score and churn rule are pure functions of that accumulating history, so re-running one week forward is structurally how this would operate against a real data lake in production.

## Data flow

1. `season_simulator` generates/extends a synthetic season of STM behavior, one week at a time.
2. `scoring/engagement.py` reads the trailing window of history and computes each STM's current engagement score.
3. `scoring/churn.py` reads each STM's engagement score history and applies the trend rule to produce a risk flag.
4. Both outputs are written to `data/weekly_snapshots/` as the per-week, per-STM record.
5. Notebooks and the Streamlit app both read from `data/weekly_snapshots/` — neither touches the simulator or scoring logic directly, which keeps the modeling core decoupled from however it's ultimately presented.

## Engagement score

- Computed per STM per week, using a **trailing 4–8 week recency-weighted window** so a recent hot or cold streak matters more than one old data point.
- Input categories: attendance rate, digital activity (app/site logins, email/push engagement), purchase activity (tickets beyond plan, merch, F&B), tenure as a mild modifier.
- Each category is normalized to 0–100 **within that week's population** (percentile-based, not fixed cutoffs), so the score stays meaningful even as the underlying data or season stage shifts.
- Categories are combined into a single 0–100 score via a weighted sum, then bucketed into tiers: Super Fan / Engaged / Cooling / Dormant.
- **Method:** starts as a transparent weighted composite index, not a trained model. The output shape (one score per STM per week) is designed so a learned regression (predicting a real forward-looking outcome like next-30-day spend) could later replace the composite as a drop-in, without changing anything downstream.
- First few weeks of a season won't have a full trailing window; the score computation averages over whatever weeks exist so far rather than erroring. A brand-new STM with zero history gets no score-based churn flag (no streak exists yet) rather than an error.

## Churn risk view

- Applied to the engagement score's **history**, not raw behavior directly.
- Rule: an STM is flagged "At Risk" when their engagement score has declined for **N consecutive weeks** AND their current score is below a **population percentile threshold** (not a fixed number, so it self-calibrates as the population or season stage changes).
- N (streak length) and the percentile cutoff are tunable knobs, to be set once real simulated output exists to tune against.
- This is a rule applied on top of the engagement pipeline's output, not an independently trained model — deliberately reuses the same underlying pipeline rather than building a second model. Upgrading to a lightweight trained classifier (using score + trend/volatility as features) was considered and explicitly deferred; the rule-based approach ships first, and can be upgraded later without discarding the existing pipeline.

## Validation

The simulator deliberately scripts a known subset of STMs into a declining trajectory mid-season (a "planted churn cohort"), separate from the random noise applied to everyone else. This gives ground truth to validate against: precision/recall of the churn rule can be measured directly (does it catch the fans we know are declining?) rather than relying on eyeballing the output.

Unit tests (`pytest`) cover the scoring and churn functions directly, since both are pure functions (fixed input -> deterministic output) that are cheap to test with hand-crafted cases — including the edge cases above (partial trailing window, zero-history STM, degenerate weeks with no games or no fans).

## Tech stack

- Python: pandas, numpy for the simulator and scoring logic.
- matplotlib/plotly for notebook visualizations.
- Streamlit for the placeholder interactive dashboard.
- pytest for unit tests.

## Deliverable format

Deliberately deferred, and out of scope for this design. The modeling core (simulator + scoring + churn logic) is decoupled from presentation by design — it writes structured output files that any presentation layer can read. Current plan: notebooks first, then a Streamlit dashboard as a lightweight interactive placeholder. A more polished Power BI (or Tableau) report may be added later as an additional artifact pointed at the same output data — not a replacement, since BI tool reports are built directly in their desktop apps rather than through this codebase.

## Explicitly out of scope for this build

- Purchase/upsell propensity modeling.
- A trained churn classifier (deferred upgrade path, not part of this build).
- Real Rams/NFL data — this project uses a synthetic data simulator throughout, since no real data access exists.
- Finalizing the deliverable format (notebook vs. Streamlit vs. Power BI/Tableau vs. combination).
- Timeline/submission planning (whether this must be complete before the application is submitted, or can be built incrementally with details discussed live in an interview).
