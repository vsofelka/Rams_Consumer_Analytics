# Power BI Build Guide

Prerequisite: `python scripts/load_to_bigquery.py` has been run successfully — see `docs/superpowers/plans/2026-08-15-bigquery-load-and-powerbi-docs.md` Task 5 for the verification numbers this depends on.

## 1. Connect to BigQuery

1. Open Power BI Desktop → **Home** → **Get Data** → **More…** → search "BigQuery" → select **Google BigQuery** → **Connect**.
2. Sign in with the Google account tied to the `rams-fan-analytics` project (OAuth window opens).
3. In the Navigator tree, expand `rams-fan-analytics` → `rams_fan_analytics` and check the boxes for: `fans`, `weekly_snapshots`, `v_engagement_trend`, `v_tier_by_plan`, `v_at_risk_current`.
4. Click **Load** (not "Transform Data" — the loader already wrote clean, typed data, no Power Query cleanup needed).

## 2. Build the model

1. Switch to the **Model** view (left rail, three-boxes icon).
2. Drag `fans[fan_id]` onto `weekly_snapshots[fan_id]` to create a relationship.
3. In the relationship dialog, confirm: cardinality **One to many** (fans is the "one" side), cross-filter direction **Single**, and the relationship is **active**.
4. Drag `fans[fan_id]` onto `v_engagement_trend[fan_id]` to create a second relationship. In the relationship dialog, confirm: cardinality **One to many** (fans is the "one" side), cross-filter direction **Single**, and the relationship is **active** — this is required for Page 3's drill-through to filter the trend chart by the selected fan.
5. Leave `v_tier_by_plan` and `v_at_risk_current` unrelated to anything — they're pre-shaped for specific visuals, not part of the star schema.

## 3. Add the DAX measures

1. In the **Data** view, right-click `weekly_snapshots` in the field list → **New measure**.
2. Paste in each measure from `docs/powerbi/dax_measures.md` one at a time (11 total), pressing Enter after each to commit it before starting the next.

## 4. Page 1 — Season Trend

This page ignores the week slicer (added on Page 2) entirely — every visual here should show all 18 weeks at once.

1. Add a **Line chart**. X-axis: `weekly_snapshots[week]`. Values: `[Precision]`, `[Recall]`, `[F1 Score]` (all three, as separate lines).
2. Add a **Line chart** below it. X-axis: `v_tier_by_plan[week]`. Y-axis: `v_tier_by_plan[avg_engagement_score]`. Legend: `v_tier_by_plan[plan_tier]`. (Not `n_fans` — every fan has exactly one row per week, so the per-tier counts are constant across the season and would render as flat, unchanging bands. `avg_engagement_score` is the column that actually varies week to week. A stacked area chart isn't the right fit here either, since stacking an average across categories isn't meaningful — averages don't sum — hence a line chart with `plan_tier` as the legend.)
3. Add four **Card** visuals along the top for `[At-Risk Count]`, `[Precision]`, `[Recall]`, `[F1 Score]` — these will show whatever the *total* (unfiltered by week) values resolve to, which is fine as a page-level headline. Note: these are season-wide totals across all 18 weeks (5,400 fan-weeks), not the week-18 snapshot reported in `docs/RESULTS.md` — they will not match that document's headline numbers, and that's expected; use Page 2's week slicer to see a single-week view comparable to `RESULTS.md`.

## 5. Page 2 — Weekly Snapshot

1. Add a **Slicer** visual bound to `weekly_snapshots[week]`. Set it to single-select (Format pane → Selection → Single select: On).
2. Add four **Card** visuals: `[Super Fan Count]`, `[Engaged Count]`, `[Cooling Count]`, `[Dormant Count]` — these now respond to the slicer.
3. Add a **Table** visual using `v_at_risk_current[fan_id]`, `v_at_risk_current[engagement_score]`, `v_at_risk_current[tier]`. Note: this view is defined as "the latest week only," so it will not change when you move the slicer to an earlier week — that's expected; it's meant as the current-state view. Sort by `engagement_score` ascending.

## 6. Page 3 — Fan Drill-Through

1. Create a new page named exactly `Fan Drill-Through`.
2. In the Visualizations pane, drag `fans[fan_id]` into the **Drill through** field well at the bottom — this makes the page a drill-through target.
3. Add a **Line chart** on this page: X-axis `v_engagement_trend[week]`, Values `v_engagement_trend[engagement_score]`. Add a second line for `v_engagement_trend[score_delta]` if you want the week-over-week delta visible too (put it on a second value well, not a second Y-axis — Power BI will ask if you want a secondary axis; decline it and use two separate small multiples or a tooltip instead, since a dual-axis chart makes the two series' shapes hard to compare fairly).
4. Add a **Card** for `fans[is_planted_churn]` so the ground-truth flag is visible on the drill-through page.
5. Back on Page 2, right-click a `fan_id` value in the at-risk table → **Drill through** → **Fan Drill-Through** to test it.

## 7. Save

File → Save As → save to `powerbi/Fan_Engagement_Dashboard.pbix` at the repo root (create the `powerbi/` folder if it doesn't exist — this is a hand-built artifact, not generated output, so unlike `data/`, it should be committed to git rather than gitignored).
