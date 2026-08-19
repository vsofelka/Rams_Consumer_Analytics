# Rams Consumer Analytics

A project built for an application to the Los Angeles Rams' **Intern, Marketing Analytics & Consumer Insights** role. See [`docs/job_description.md`](docs/job_description.md) for the full posting.

## What this is

A working, end-to-end pipeline that models a Season Ticket Member's (STM's) **degree of fandom** on a rolling basis — a 0–100 engagement score blending attendance, digital activity, and purchase behavior over a trailing, recency-weighted window — and classifies each fan into one of four fandom tiers: **Super Fan, Engaged, Cooling, Dormant**. A second view derives **churn risk** directly from *shifts* in that score's trajectory, rather than from a separately trained model: a fan is flagged "at risk" when their score has fallen for several consecutive weeks *and* sits below a population percentile threshold — a sustained shift away from their prior degree of fandom, not one bad week.

The whole thing is deliberately built to run **in-season**: the simulator advances one week at a time, and each week's score and churn flag are computed only from the history available up to that week — never from the full season at once. That mirrors how it would actually be used against live data.

Because real STM churn labels don't exist for a synthetic season, the simulator plants a known cohort of 25 fans (out of 300) whose engagement is scripted into a decline starting week 6. That gives a ground truth to measure detection against with real precision/recall, rather than eyeballing a chart.

### Validated result

Against that planted cohort, detection **peaks mid-to-late season and then decays**:

- **Weeks 12–13 (best):** precision **1.00**, recall **0.60**, F1 **0.75** — 15 fans flagged, all 15 genuinely from the planted cohort.
- **Week 15:** recall peaks at **0.64**.
- **Week 18 (final):** precision **0.62**, recall **0.32**, F1 **0.42** — 8 of the 25 planted churners caught, 5 false alarms out of 13 total flags.

The late-season decay is the interesting part, and it's a real property of the rule rather than a bug: the percentile gate passes all 25 planted churners by week 18, but the *strict week-over-week decline* requirement stops being satisfied once a declining fan's score bottoms out near the decay floor. A "still falling" rule goes quiet once a fan has already hit bottom. [`docs/RESULTS.md`](docs/RESULTS.md) has the full week-by-week table, the diagnosis, and an honest discussion of what this does and does not prove.

## How to run it

```bash
pip install -r requirements.txt
python scripts/run_season.py
```

`scripts/run_season.py` generates the season and writes `data/weekly_snapshots/` (`fans.csv` plus `week_01.csv` … `week_18.csv`). **That directory is gitignored, so a fresh clone has no data until you run this.** The run is seeded (`seed=42`) and deterministic.

Then open the notebooks in order:

1. [`notebooks/01_generate_season.ipynb`](notebooks/01_generate_season.ipynb) — runs the simulator and sanity-checks its output (the planted cohort should visibly diverge from everyone else around week 6).
2. [`notebooks/02_engagement_model.ipynb`](notebooks/02_engagement_model.ipynb) — engagement score distribution, tier breakdown, and per-fan trend lines.
3. [`notebooks/03_churn_view.ipynb`](notebooks/03_churn_view.ipynb) — the actionable at-risk list plus validation against the planted cohort.

Notebooks 02 and 03 read only the generated CSVs — never the simulator or scoring code — which keeps the modeling core fully decoupled from how it's presented.

Tests: `pytest -v`.

## Repo layout

- `season_simulator/` — synthetic STM population (`fans.py`) and weekly behavior events (`events.py`), including the scripted decline for the planted churn cohort
- `scoring/` — pure-function modeling core: `engagement.py` (rolling score + tier), `churn.py` (the at-risk rule), `validation.py` (precision/recall against ground truth)
- `scripts/run_season.py` — wires the simulator and scoring together and writes the weekly CSV output
- `notebooks/` — the three analysis notebooks described above
- `tests/` — pytest suite covering the simulator, scoring, and runner
- `data/weekly_snapshots/` — generated weekly output (**gitignored**; created by `scripts/run_season.py`)
- `scripts/load_to_bigquery.py` — loads the validated fans/weekly_snapshots data into BigQuery, plus the analytical views the dashboard reads from
- `powerbi/Fan_Engagement_Dashboard.pbix` — the Power BI report described above
- `docs/`
  - [`docs/RESULTS.md`](docs/RESULTS.md) — full validated results, week-by-week metrics, and limitations
  - [`docs/DECISION_LOG.md`](docs/DECISION_LOG.md) — chronological record of key decisions and why they were made
  - [`docs/powerbi/`](docs/powerbi/) — Power BI build guide and DAX measures reference
  - [`docs/superpowers/specs/`](docs/superpowers/specs/) — technical design docs
  - [`docs/job_description.md`](docs/job_description.md) — the job posting this project is built against
- [`PROJECT_CONTEXT.md`](PROJECT_CONTEXT.md) — full project background and open questions

## Scope

This is an MVP pass, and it's scoped honestly: a rule-based churn view rather than a trained classifier, and a synthetic season rather than real data. See [`docs/DECISION_LOG.md`](docs/DECISION_LOG.md) for the reasoning behind each of those trade-offs, and [`docs/RESULTS.md`](docs/RESULTS.md) for what the numbers do and don't support.

## Dashboard

The same validated data also drives a three-page **Power BI** report — [`powerbi/Fan_Engagement_Dashboard.pbix`](powerbi/Fan_Engagement_Dashboard.pbix) — built on top of the BigQuery tables and views loaded by [`scripts/load_to_bigquery.py`](scripts/load_to_bigquery.py):

1. **Season Trend** — precision/recall/F1 across all 18 weeks, average engagement score by plan tier, and season-wide headline metrics.
2. **Weekly Snapshot** — a week slicer driving live tier counts and the current at-risk fan list.
3. **Fan Drill-Through** — pick an individual fan and see their engagement trend alongside their ground-truth planted-churn flag.

See [`docs/powerbi/build_guide.md`](docs/powerbi/build_guide.md) for how it was built (including the DAX measures reference and a couple of real Power BI Desktop quirks worth knowing about) and [`docs/powerbi/dax_measures.md`](docs/powerbi/dax_measures.md) for the measures themselves.
