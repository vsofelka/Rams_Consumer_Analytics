# Project Context — LA Rams Marketing Analytics & Consumer Insights

This file summarizes everything discussed about this project so it can be handed to Claude Code without relying on a separate chat history. Reference it when prompting Claude Code.

## The Application

**Company:** Los Angeles Rams
**Role:** Intern, Marketing Analytics & Consumer Insights
**Applicant:** Victor Sofelkanik — recent BBA graduate (Information Systems & Business Analytics, Loyola Marymount University). Also has a past LA Rams Training Camp Internship (Marketing Department), which is a direct personal connection to this organization.

Full job description: see [`docs/job_description.md`](docs/job_description.md).

## Project Direction (decided so far)

**Core constraint from Victor:** The project should contribute value in-season, not just be a preseason/one-time planning exercise. This points toward models that update on a rolling/recurring basis as new data comes in, rather than a static one-off analysis.

**Candidate use cases discussed (not yet finalized — narrow to one before building):**

1. **Renewal/churn risk scoring** — flag season ticket holders showing early disengagement signals (declining attendance, no merch purchases, drop in app activity) so the team can intervene mid-season rather than waiting until renewal time.
2. **Rolling fan engagement score** — a score per fan based on recent behavior (attendance streaks, digital activity, purchases) that updates on a regular cadence (e.g. weekly) and feeds targeting decisions.
3. **Purchase/upsell propensity** — predicting which fans are likely to buy upgrades, merch, or add-ons based on recent activity, refreshed as the season progresses.

As of the last working session, Victor's rough ranking (subject to change) was: 2 (engagement score) > 1 (churn) > 3 (upsell propensity). One idea raised but not committed to: layering these rather than building three separate models — e.g. treating the rolling engagement score as the core pipeline, with churn risk emerging as a downstream read of a sustained score decline. This is still open for discussion.

**Not yet decided:**

- Which single use case to build (check with Victor before finalizing scope, or pick the strongest fit and flag the choice clearly).
- Final deliverable format. Options discussed:
  - Interactive web app/dashboard (similar to a prior project built for a different application — Node/Express backend + plain HTML/CSS/JS frontend)
  - Python/Jupyter notebook with models + visualizations
  - Power BI or Tableau-style dashboard
  - Combination: notebook for modeling + simple dashboard for output
- Timeline: whether this needs to be fully finished before the application is submitted, or built incrementally with details to explain live in an interview (this was the approach for the prior Faraday Future project — build something real, keep refining, discuss specifics in the interview rather than over-describing an unfinished project in application materials).

## Technical Environment

- Building in Cursor, connected to a GitHub repo (repo already created and cloned).
- Using Claude Code inside Cursor to do the actual implementation.
- Installed plugins: Superpowers (structured planning/TDD workflow), GitHub plugin (repo/PR/commit operations from within Claude Code).
- Victor's general technical background: SQL, Python, Tableau, Power BI, Excel (Microsoft Certified), Snowflake, HubSpot, Jira, GitHub, Jupyter Notebook. Comfortable with Claude Code / Cursor as a build workflow (used the same approach for his capstone project and a prior application project).

## What NOT to Do

- Don't build multiple use cases at once — the JD lists many possible models (CLV, churn, clusters, purchase motivators), but the plan is to build one well rather than touch all of them.
- Don't assume the deliverable format yet if this file is out of date — confirm with Victor which format was ultimately chosen before scaffolding a full project.
- Mirror the approach from the previous project: build something that actually runs (not a mockup), keep the code readable since it may be extended live with Claude Code, and don't over-polish to the point of pretending it's more finished than it is if it's still a work in progress.

## Next Step

Before scaffolding the full project, confirm with Victor (if not already answered elsewhere):

1. Which of the three in-season use cases to build (or confirm a different direction).
2. Final format for the deliverable.
3. Whether this needs to be finished before submitting the application, or can be built incrementally.
