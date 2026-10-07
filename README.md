# Rams Consumer Analytics

After my training camp internship with the Los Angeles Rams marketing department, I built this project around a question a team's marketing staff cares about: which season ticket members are losing interest before they decide not to renew? It simulates a season of 300 members, scores each fan's engagement every week, flags fans whose engagement keeps dropping, and puts a dollar value and a behavioral segment on every fan. Because the fans are simulated, I planted a group that I knew was declining, so I could measure how well the alert actually works.

## Results

- In weeks 12 and 13, the churn alert flagged 15 fans and all 15 were fans I had planted to decline (precision 1.00, recall 0.60, F1 0.75).
- By the end of the season it was about 7 times more precise than flagging fans at random, and a statistical test showed that wasn't luck (p < 0.000001).
- The alert gets weaker late in the season. The rule looks for a score that keeps falling, and once a fan has already hit bottom their score stops falling, so the alert loses them. I explain this in [docs/RESULTS.md](docs/RESULTS.md).
- A GitHub Actions job pulls real Rams demand, search, and pageview data every Monday.

## What's real and what's simulated

The weekly SeatGeek demand scores, Google search interest, and Wikipedia pageviews for the Rams are real. The 300 season ticket members, their weekly behavior, the 25 fans I planted to decline, and the dollar values are simulated. The prices behind the dollar values are placeholders, not real Rams pricing.

I kept the engagement score and the churn alert on the simulated season so every result can be reproduced exactly with the same seed (`seed=42`). The reasoning is in [docs/DECISION_LOG.md](docs/DECISION_LOG.md).

## Dashboard

I built a three page Power BI report, [powerbi/Fan_Engagement_Dashboard.pbix](powerbi/Fan_Engagement_Dashboard.pbix), on BigQuery tables and views loaded by [scripts/load_to_bigquery.py](scripts/load_to_bigquery.py).

1. Season Trend: precision, recall, and F1 for all 18 weeks, average engagement by plan tier, and season totals.
2. Weekly Snapshot: a week slicer that updates the tier counts and the list of fans flagged at risk that week.
3. Fan Drill-Through: pick one fan and see their engagement over the season next to whether they were in the planted group.

How I built it is in [docs/powerbi/build_guide.md](docs/powerbi/build_guide.md), and the DAX measures are in [docs/powerbi/dax_measures.md](docs/powerbi/dax_measures.md).

## Tools

| Part of the project | Tools |
|---|---|
| Simulation and scoring | Python, pandas, NumPy |
| Segments | scikit-learn (k-means) |
| Statistics | SciPy (Mann-Whitney U test, Wilson intervals, hypergeometric test) |
| SQL | SQLite, with window functions and joins in notebook 04 |
| Warehouse and dashboard | Google BigQuery, Power BI, DAX |
| Automation | GitHub Actions |
| Real data | SeatGeek API, Google Trends (pytrends), Wikipedia pageviews API |
| Testing | pytest |

## How it works

Every week of the simulated season, each season ticket member gets four things:

1. An engagement score from 0 to 100, based on attendance, digital activity, and purchases over the last several weeks, with recent weeks counting more. Each fan also gets a tier: Super Fan, Engaged, Cooling, or Dormant.
2. A churn flag. A fan is flagged at risk when their score has dropped three weeks in a row and they're in the bottom 25% of fans that week. I used a simple rule instead of a trained model so it's easy to explain and test.
3. A lifetime value estimate in dollars, based on their plan tier, their engagement tier, and whether they're flagged.
4. A segment. I used k-means to group fans into five segments by engagement, plan tier, and how many years they've had tickets.

The season runs one week at a time, and each week only uses data up to that week. That's how it would work during a real season, where you don't know what happens next.

To test the churn flag, the simulator picks 25 of the 300 fans and makes their engagement drop starting in week 6. Since I know exactly which fans are declining, I can measure how many the alert catches and how many it gets wrong.

### How well the alert worked

The alert did best in the middle and late part of the season and then dropped off:

- Weeks 12 and 13 were the best: precision 1.00, recall 0.60, F1 0.75. It flagged 15 fans and all 15 were from the planted group.
- Recall was highest in week 15, at 0.64.
- By week 18: precision 0.62, recall 0.32, F1 0.42. It caught 8 of the 25 planted fans and had 5 false alarms out of 13 flags.

The drop at the end comes from how the rule works. By week 18 all 25 planted fans are in the bottom 25%, but the rule also needs the score to keep falling every week, and fans who have already hit bottom stop falling. Adding a second condition for fans who stay low would help with this. The full week by week table, the statistical tests, and what these results do and don't show are in [docs/RESULTS.md](docs/RESULTS.md).

## How to run it

```bash
pip install -r requirements.txt
python scripts/run_season.py
```

`scripts/run_season.py` creates the season and saves it to `data/weekly_snapshots/` (`fans.csv` plus one file for each of the 18 weeks) and to a SQLite database (`data/fan_analytics.db`) for the SQL notebook. These files aren't saved in the repo, so you need to run this first. The seed is fixed, so you get the same results every time.

Then open the notebooks in order:

1. [notebooks/01_generate_season.ipynb](notebooks/01_generate_season.ipynb) runs the simulator and checks the output. The planted group should clearly separate from everyone else around week 6.
2. [notebooks/02_engagement_model.ipynb](notebooks/02_engagement_model.ipynb) shows how the engagement scores are spread out, the tier counts, and trend lines for individual fans.
3. [notebooks/03_churn_view.ipynb](notebooks/03_churn_view.ipynb) shows the at risk list and checks it against the planted group.
4. [notebooks/04_sql_analysis.ipynb](notebooks/04_sql_analysis.ipynb) has the SQL analysis (window functions, joins, and aggregations) and the statistical tests.

Notebooks 02 through 04 only read the saved output. They never call the simulator or the scoring code directly.

To run the tests: `pytest -v`

## Weekly data pull

Besides the simulated season, the repo pulls three kinds of real weekly data about the Rams: SeatGeek demand and popularity scores for home games, Google search interest, and Wikipedia pageviews. Each week's numbers are added to [data_sources/processed/weekly_data.csv](data_sources/processed/weekly_data.csv). This data is kept separate from the engagement score and the churn flag so those stay reproducible.

A [GitHub Actions workflow](.github/workflows/weekly-data-pull.yml) runs every Monday at 9am UTC and saves the updated file back to the repo. Before it pulls anything, it checks which sources already have data for that week, so running it twice in the same week won't add duplicate rows.

To run it yourself, go to the Actions tab, open Weekly Data Pull, and click Run workflow.

Google Trends comes from pytrends, which isn't an official Google API. The script retries a few times if Google limits the requests, but once in a while it can still miss a week. When that happens the other two sources still get pulled, and Google Trends picks back up the next week.

## Repo layout

- `season_simulator/`: the simulated fans (`fans.py`) and their weekly behavior (`events.py`), including the decline for the planted group
- `scoring/`: the engagement score (`engagement.py`), churn rule (`churn.py`), lifetime value (`clv.py`), k-means segments (`segments.py`), statistical tests (`stats.py`), and precision and recall checks (`validation.py`)
- `storage/`: the SQLite tables the season run writes to (`db.py`)
- `scripts/run_season.py`: runs the simulator and scoring and saves the weekly output
- `scripts/load_to_bigquery.py`: loads the output into BigQuery and creates the views the dashboard uses
- `data_sources/`: the weekly data pull (`pull_seatgeek.py`, `pull_google_trends.py`, `pull_wikipedia_pageviews.py`, `common.py` for shared helpers, and `pull_all_sources.py`, which the workflow runs)
- `notebooks/`: the four notebooks above
- `powerbi/Fan_Engagement_Dashboard.pbix`: the Power BI report
- `tests/`: pytest tests for the simulator, scoring, storage, data pull, BigQuery load, and season run
- `data/`: the generated output, not saved in the repo
- `docs/`
  - [docs/RESULTS.md](docs/RESULTS.md): full results, the week by week table, statistical tests, and limits
  - [docs/DECISION_LOG.md](docs/DECISION_LOG.md): the main decisions I made and why
  - [docs/powerbi/](docs/powerbi/): the Power BI build guide and DAX measures
  - [docs/design/specs/](docs/design/specs/): design docs for each part of the build

## Limits

This is a first version. The churn flag is a rule, not a trained model, and the season is simulated, not real member data. Since I designed the decline pattern myself, the alert would likely do worse on real fans. The dollar values use placeholder prices. [docs/DECISION_LOG.md](docs/DECISION_LOG.md) explains why I made these choices, and [docs/RESULTS.md](docs/RESULTS.md) goes into what the results do and don't show.
