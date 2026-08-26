# Project Context — Fan Engagement Analytics

This file summarizes everything discussed about this project so it can be handed to Claude Code without relying on a separate chat history. Reference it when prompting Claude Code.

For the reasoning behind each decision below, see [`docs/DECISION_LOG.md`](docs/DECISION_LOG.md). For the technical design of the current build, see [`docs/superpowers/specs/2026-08-10-fan-engagement-churn-design.md`](docs/superpowers/specs/2026-08-10-fan-engagement-churn-design.md).

## Origin

**Author:** Victor Sofelkanik — BBA graduate (Information Systems & Business Analytics, Loyola Marymount University). Has a past LA Rams Training Camp Internship (Marketing Department), which is the personal connection that inspired this project's domain.

This project originally started as a build for a specific LA Rams internship application. It has since become a standalone personal portfolio project — not tied to that or any other specific job application — kept in the Rams domain because of that genuine personal connection, not because it's targeting that employer specifically.

## Current Direction

**Core constraint:** the project should contribute value in-season, not just be a preseason/one-time planning exercise — so it's built as a rolling pipeline that updates on a recurring cadence as new data comes in, rather than a static one-off analysis.

**Use case:** a layered combination of a rolling fan engagement score and a churn risk view. One core pipeline computes a weekly engagement score per Season Ticket Member (STM); churn risk is a second view derived from that same score's trajectory (a sustained decline), not a separately trained model. Purchase/upsell propensity was considered and dropped from scope. See `docs/DECISION_LOG.md` for how this was narrowed down from three candidate use cases and the full reasoning.

**Deliverable format:** the MVP ships as Jupyter notebooks plus a written results summary ([`docs/RESULTS.md`](docs/RESULTS.md)). Whether to wrap it in anything further — a Streamlit dashboard, a Power BI/Tableau report, or some combination — remains a genuinely open, deliberately deferred decision. The modeling core is architected to be decoupled from however it's presented, so that choice can still be made cheaply now that there's something real to wrap.

**Timeline:** extended. The original 48-hour MVP target (starting 2026-08-10) was pushed out by a couple of extra days — still a real constraint, just less compressed. The MVP build (see the implementation plan) ran through its full task sequence and is now complete: simulator, scoring modules, season runner, three notebooks, and `docs/RESULTS.md`. The extra time was buffer rather than a mandate to re-scope mid-build. See `docs/DECISION_LOG.md` for the original 48-hour decision and this extension.

## Technical Environment

- Building in Cursor, connected to a GitHub repo (repo already created and cloned).
- Using Claude Code inside Cursor to do the actual implementation.
- Installed plugins: Superpowers (structured planning/TDD workflow), GitHub plugin (repo/PR/commit operations from within Claude Code).
- Victor's general technical background: SQL, Python, Tableau, Power BI, Excel (Microsoft Certified), Snowflake, HubSpot, Jira, GitHub, Jupyter Notebook. Comfortable with Claude Code / Cursor as a build workflow (used the same approach for his capstone project and a prior application project).

## What NOT to Do

- **Prefer depth and layered connection over scattered breadth.** Multiple analytical angles (churn, CLV, segmentation, etc.) are fine and encouraged — the practice that's worked well is building each new one as a layer on the same core data/pipeline (same fans, same weekly snapshots) rather than a disconnected side project, so the whole thing still reads as one coherent system, not a pile of unrelated demos.
- **Don't scaffold a specific deliverable format prematurely.** It's deliberately left open (see Current Direction above) — the modeling core stays decoupled from presentation so the format choice can be made cheaply once there's something real to wrap.
- **Build something that actually runs, not a mockup.** The point of this project is being able to speak concretely about real design decisions and real output — a static mockup or hardcoded example wouldn't hold up under follow-up questions.
- **Keep the code readable.** It may be extended live with Claude Code, so clarity matters more than cleverness.
- **Don't over-polish to the point of misrepresenting how finished it is.** If it's still a work in progress, it should look and read like one.

## Open Items

- Final deliverable format (notebook / Streamlit / Power BI / Tableau / combination) — deliberately deferred, see above.

## Where to Look for More

- **How we got here, and why:** [`docs/DECISION_LOG.md`](docs/DECISION_LOG.md) — chronological record of key decisions as the project was worked through.
- **Current technical design:** [`docs/superpowers/specs/`](docs/superpowers/specs/) — design docs for each part of the build.
