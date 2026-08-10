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
