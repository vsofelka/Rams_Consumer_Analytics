# Decision Log

A chronological record of key decisions made while working through this project, and the reasoning behind each one. Meant to make it easy to trace *why* the project looks the way it does, without digging through chat history.

---

## 2026-08-07 — Repo foundation established

**Decision:** Set up repo-level scaffolding only — `README.md`, `.gitignore`, `PROJECT_CONTEXT.md`, and `docs/job_description.md`. No project code, data, or folders tied to a specific direction yet.

**Why:** The direction (which use case, what format) wasn't decided yet, and building toward an undecided target risks wasted rework. This scaffolding is genuinely shared groundwork regardless of which direction the project ultimately took.

**Reference:** commit `806c927`.

---

## 2026-08-09 to 2026-08-10 — Use case narrowed to a layered approach

**Considered:** three candidate use cases, all pulled from the job description's "customer lifetime value, churn predictions, degrees and shifts of fandom, purchase motivators, attitudinal/behavioral clusters" line:

1. Renewal/churn risk scoring
2. Rolling fan engagement score
3. Purchase/upsell propensity

Initial rough ranking: engagement score > churn > upsell propensity.

**Decision:** Build a layered combination of the top two — a rolling fan engagement score as the core pipeline, with churn risk as a second view derived from that same score's trajectory (not an independently trained model). Purchase/upsell propensity was dropped from scope entirely.

**Why:** This is the only direction that maps onto two exact phrases from the JD at once — "churn predictions" and "degrees and **shifts** of fandom" (a rolling score is literally what "shifts" describes) — plus the segmentation/clustering qualifications bullet ("fan/customer segmentation schemas," "attitudinal/behavioral clusters"). Purchase/upsell propensity's JD anchor ("purchase motivators") was comparatively weak — motivators describes *why* someone buys, not *whether* they will, so it's a looser fit than the other two.

**Reference:** [`docs/superpowers/specs/2026-08-10-fan-engagement-churn-design.md`](superpowers/specs/2026-08-10-fan-engagement-churn-design.md).

---

## 2026-08-10 — Churn view will be rule-based, not a second trained model

**Decision:** Churn risk = engagement score declining for N consecutive weeks, combined with the current score falling below a population percentile threshold. Not an independently trained classifier.

**Why:** Keeps the build to one real pipeline instead of two separate models, stays transparent and easy to explain, and is upgradeable later — the rule can be swapped for a lightweight trained classifier (using score + trend/volatility as features) without discarding anything already built.

---

## 2026-08-10 — Deliverable format deliberately deferred

**Decision:** Don't lock the presentation layer (notebook / Streamlit / Power BI / Tableau) before building the core. Architect the modeling core (simulator + scoring + churn logic) to write clean, structured output files that any presentation layer can read.

**Why:** The modeling core is the actual substance of the project; the presentation layer is comparatively low-stakes and shouldn't block starting the real build. Decoupling the two means the format decision stays cheap to make — or change — later.

**Plan so far:** notebooks first, then a Streamlit dashboard as a lightweight interactive placeholder. A Power BI (or Tableau) report may be added later as a separate, more polished artifact built directly in its own desktop app against the same output data — not a replacement for the code-based pipeline, since BI reports aren't built through this codebase.

---

## 2026-08-10 — Design doc written for the core pipeline

**Decision:** Full architecture, data flow, engagement score computation, churn rule, and validation approach documented — including a "planted churn cohort" baked into the simulator (a known subset of STMs deliberately scripted into decline) so the churn rule's precision/recall can be measured against ground truth rather than eyeballed.

**Reference:** [`docs/superpowers/specs/2026-08-10-fan-engagement-churn-design.md`](superpowers/specs/2026-08-10-fan-engagement-churn-design.md), commit `8523feb`.

---

## 2026-08-10 — 48-hour MVP timeline set

**Decision:** Build a working end-to-end pipeline (simulator → engagement score → churn view, with some form of output) within 48 hours of this decision. A hard scoping constraint, not a soft target.

**Why:** Resolves the previously open timeline question. This constraint now directly shapes the implementation plan — scope needs to fit what's achievable in 48 hours rather than the full design being built out completely.

---

## 2026-08-10 — MVP scope trimmed to fit the 48-hour window

**Decision:** For the 48-hour MVP, keep the simulator, composite engagement score, rule-based churn view, and the planted-churn-cohort validation exactly as designed. Simplify: a smaller synthetic STM population, one coarse digital-engagement signal instead of several, and a handful of core unit tests instead of exhaustive edge-case coverage. Cut entirely from this pass: the Streamlit dashboard. Notebooks are the only output for the MVP.

**Why:** The core modeling pipeline and its validation are the actual substance of the project and can't be trimmed without losing the point. The dashboard was already architected to be decoupled from the core (see the 2026-08-10 deliverable-format entry above), making it the natural thing to defer past the 48-hour mark rather than let it compete with build time the modeling logic needs.

---

## 2026-08-10 — 48-hour timeline extended by a couple of days

**Decision:** The original 48-hour MVP deadline has been pushed out by a couple of extra days. The task sequence and scope already in progress (per the implementation plan) continue unchanged — the extension is treated as buffer, not an automatic trigger to re-scope back in what was trimmed (Streamlit dashboard, fuller test coverage, larger population).

**Why:** External timeline change, not a change in project requirements. Re-opening scope mid-build (e.g. resurrecting the dashboard) is a separate decision to make deliberately once the MVP task sequence is done, not something to fold in reactively while tasks are mid-review.

---

## 2026-08-10 — Results summary added as Task 11

**Decision:** Add a short standalone `docs/RESULTS.md` as a final task after the notebooks, stating the actual observed precision/recall/F1 and at-risk count from the real run — not projected numbers. Everything else about the 10-task MVP plan stays unchanged; this is additive, not a re-scope.

**Why:** With the timeline extended, a plain-language summary of what the validated results actually show is useful for interview reference without needing to open Jupyter, and forces one more honest cross-check that the numbers being discussed match what the notebooks actually produced.

---

## 2026-08-12 — Post-MVP scope: SQL, statistical validation, and a dashboard

**Decision:** With the MVP complete and the timeline extended further, take on three more pieces of work: a real SQL layer, statistical validation, and a Streamlit dashboard — then scale the population back up. Split into three phased sub-projects in dependency order: (A) SQL backbone + statistical validation, (B) Streamlit dashboard (built against A's SQL layer), (C) scale-up to ~2,000+ fans (deferred to last since it's just parameters once A and B exist, and doing it last avoids re-running an expensive regeneration cycle mid-build).

**Why:** SQL, statistical rigor, and the ability to communicate findings clearly are widely recognized as core skills for data science and analytics roles generally, and the MVP as built has none of the first two, and only notebooks (not a live dashboard) for the third. This is the same kind of direct-JD-language mapping that drove the original engagement-score/churn-view use-case decision (see 2026-08-09 to 2026-08-10 entry above) — building toward specific, well-grounded priorities rather than generic "add more features."

**Also considered and deferred:** real historical data, to replace the synthetic simulator. Rejected for now — the planted-churn cohort is what makes the current validation honest (known ground truth to measure precision/recall against); real data wouldn't have that, and no concrete real dataset is in hand yet. Revisit if a specific dataset becomes available. Also considered: a lightweight trained classifier as a second, genuinely different model type (would strengthen the "different types of models" angle further) — deferred out of this round to keep Phase A scoped; noted as future work.

**Reference:** [`docs/superpowers/specs/2026-08-12-sql-stats-backbone-design.md`](superpowers/specs/2026-08-12-sql-stats-backbone-design.md).

---

## 2026-08-12 — SQLite chosen as the SQL engine

**Decision:** Use SQLite for the new database layer, not DuckDB, PostgreSQL, or a cloud warehouse (Snowflake/BigQuery).

**Why:** The project's whole ethos is "clone it, `pip install`, run one command" — no server to stand up, no account to create. SQLite is built into Python's standard library (zero extra dependency) and is the most universally recognized engine. DuckDB was the closest alternative (also embedded/serverless, purpose-built for analytical queries) but was passed over for maximum simplicity; PostgreSQL/MySQL require a running server and Snowflake/BigQuery require a cloud account, both of which would break the zero-setup requirement for anyone reviewing the repo. The SQL written is standard regardless of engine, so this choice doesn't change what skill is being demonstrated — only how much friction there is to run it.

---

## 2026-08-12 — Three statistical tests chosen to fit what's actually being tested

**Decision:** Add `scoring/stats.py` with three specific techniques rather than one default test reused everywhere: a Mann-Whitney U test (planted-churn cohort vs. everyone else's engagement score), a Wilson score confidence interval (around the churn rule's precision/recall), and a hypergeometric test (probability of the observed true-positive count arising by chance).

**Why:** Each was picked to match the actual data-generating process rather than reached for by default — Mann-Whitney over a t-test because `engagement_score` is a percentile rank, not normally distributed; Wilson over a naive normal-approximation CI because the counts involved (13 flagged, 25 planted) are small and close to the boundary; hypergeometric over binomial because fans are drawn without replacement from a finite population of 300. Using three distinct techniques, each justified on its own terms, is the concrete demonstration of interpreting different types of statistical models/testing, not just running one by default.

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

---

## 2026-08-19 — README and RESULTS.md reframed around "degree of fandom" / "shifts in fandom"

**Decision:** Describe the engagement score explicitly as a fan's "degree of fandom" and the churn view explicitly as detecting "shifts" in that fandom, in `README.md` and `docs/RESULTS.md`. No underlying model, rule, or number changed — this is a language pass only.

**Why:** The job posting names "degrees and shifts of fandom" as a specific deliverable the team wants (`docs/job_description.md`). The existing tier system (Super Fan/Engaged/Cooling/Dormant, computed weekly on a rolling basis) and the trend-based churn rule already *are* exactly that — the project just wasn't describing itself in those terms. Same direct-JD-language mapping as the Power BI and BigQuery decisions above, applied to prose instead of tooling.
