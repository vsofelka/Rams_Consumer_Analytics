# Project Context — LA Rams Marketing Analytics & Consumer Insights

This file summarizes everything discussed about this project so it can be handed to Claude Code without relying on a separate chat history. Reference it when prompting Claude Code.

For the reasoning behind each decision below, see [`docs/DECISION_LOG.md`](docs/DECISION_LOG.md). For the technical design of the current build, see [`docs/superpowers/specs/2026-08-10-fan-engagement-churn-design.md`](docs/superpowers/specs/2026-08-10-fan-engagement-churn-design.md).

## The Application

**Company:** Los Angeles Rams
**Role:** Intern, Marketing Analytics & Consumer Insights
**Applicant:** Victor Sofelkanik — recent BBA graduate (Information Systems & Business Analytics, Loyola Marymount University). Also has a past LA Rams Training Camp Internship (Marketing Department), which is a direct personal connection to this organization.

Full job description: see [`docs/job_description.md`](docs/job_description.md).

## Current Direction

**Core constraint:** the project should contribute value in-season, not just be a preseason/one-time planning exercise — so it's built as a rolling pipeline that updates on a recurring cadence as new data comes in, rather than a static one-off analysis.

**Use case:** a layered combination of a rolling fan engagement score and a churn risk view. One core pipeline computes a weekly engagement score per Season Ticket Member (STM); churn risk is a second view derived from that same score's trajectory (a sustained decline), not a separately trained model. Purchase/upsell propensity was considered and dropped from scope. See `docs/DECISION_LOG.md` for how this was narrowed down from three candidate use cases and the full reasoning.

**Deliverable format:** deliberately left open for now. The modeling core is architected to be decoupled from however it's presented, so the format choice (notebook, Streamlit dashboard, Power BI/Tableau report, or some combination) doesn't need to be locked before the real build starts.

**Timeline:** extended. The original 48-hour MVP target (starting 2026-08-10) has been pushed out by a couple of extra days — still a real constraint, just less compressed. The in-progress MVP build (see the implementation plan) continues on the same task sequence; the extra time is buffer rather than a mandate to re-scope mid-build. See `docs/DECISION_LOG.md` for the original 48-hour decision and this extension.

## Technical Environment

- Building in Cursor, connected to a GitHub repo (repo already created and cloned).
- Using Claude Code inside Cursor to do the actual implementation.
- Installed plugins: Superpowers (structured planning/TDD workflow), GitHub plugin (repo/PR/commit operations from within Claude Code).
- Victor's general technical background: SQL, Python, Tableau, Power BI, Excel (Microsoft Certified), Snowflake, HubSpot, Jira, GitHub, Jupyter Notebook. Comfortable with Claude Code / Cursor as a build workflow (used the same approach for his capstone project and a prior application project).

## What NOT to Do

- **Don't build multiple use cases at once.** The JD lists many possible models (CLV, churn, clusters, purchase motivators), and it would be easy to try to touch all of them. The plan is to build one well rather than build several shallowly.
- **Don't scaffold a specific deliverable format prematurely.** It's deliberately left open (see Current Direction above) — the modeling core stays decoupled from presentation so the format choice can be made cheaply once there's something real to wrap.
- **Build something that actually runs, not a mockup.** The point of this project is being able to speak concretely about real design decisions and real output — a static mockup or hardcoded example wouldn't hold up under follow-up questions.
- **Keep the code readable.** It may be extended live with Claude Code, so clarity matters more than cleverness.
- **Don't over-polish to the point of misrepresenting how finished it is.** If it's still a work in progress, it should look and read like one.

## Open Items

- Final deliverable format (notebook / Streamlit / Power BI / Tableau / combination) — deliberately deferred, see above.

## Where to Look for More

- **How we got here, and why:** [`docs/DECISION_LOG.md`](docs/DECISION_LOG.md) — chronological record of key decisions as the project was worked through.
- **Current technical design:** [`docs/superpowers/specs/`](docs/superpowers/specs/) — design docs for each part of the build.
- **The job posting this project is built against:** [`docs/job_description.md`](docs/job_description.md).
