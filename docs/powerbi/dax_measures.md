# DAX Measures Reference

All measures live on the `weekly_snapshots` table. They rely on the `fans` 1—* `weekly_snapshots` relationship (on `fan_id`) set up in the build guide's model step — referencing `fans[is_planted_churn]` inside `CALCULATE` on `weekly_snapshots` works because that relationship auto-propagates the filter.

Every measure below is filter-context-aware: it recomputes correctly whether the current context is a week slicer, a single point on a line chart, or a matrix cell.

## Confusion-matrix building blocks

**True Positives** — flagged at-risk, and really one of the 25 planted churners:
```
True Positives = 
CALCULATE(
    COUNTROWS(weekly_snapshots),
    fans[is_planted_churn] = TRUE,
    weekly_snapshots[at_risk] = TRUE
)
```

**False Positives** — flagged at-risk, but not actually a planted churner:
```
False Positives = 
CALCULATE(
    COUNTROWS(weekly_snapshots),
    fans[is_planted_churn] = FALSE,
    weekly_snapshots[at_risk] = TRUE
)
```

**False Negatives** — a planted churner the rule missed that week:
```
False Negatives = 
CALCULATE(
    COUNTROWS(weekly_snapshots),
    fans[is_planted_churn] = TRUE,
    weekly_snapshots[at_risk] = FALSE
)
```

## Detection metrics

```
Precision = 
VAR TP = [True Positives]
VAR FP = [False Positives]
RETURN
DIVIDE(TP, TP + FP)
```

```
Recall = 
VAR TP = [True Positives]
VAR FalseNeg = [False Negatives]
RETURN
DIVIDE(TP, TP + FalseNeg)
```
Note: name this variable something other than `FN` — in testing, Power BI Desktop's
DAX editor threw a persistent "The syntax for 'FN' is incorrect" error on that exact
two-letter name (while `TP`/`FP` in the other measures were unaffected), even after
retyping the formula from scratch. Renaming the variable resolved it immediately.

```
F1 Score = 
VAR P = [Precision]
VAR R = [Recall]
RETURN
DIVIDE(2 * P * R, P + R)
```

`DIVIDE` returns blank instead of erroring on a divide-by-zero week (e.g. before any fan has been flagged), which reads cleanly as "no data" on a chart rather than crashing the visual.

## At-risk and tier counts

```
At-Risk Count = 
CALCULATE(
    COUNTROWS(weekly_snapshots),
    weekly_snapshots[at_risk] = TRUE
)
```

```
Super Fan Count = 
CALCULATE(
    COUNTROWS(weekly_snapshots),
    weekly_snapshots[tier] = "Super Fan"
)
```

```
Engaged Count = 
CALCULATE(
    COUNTROWS(weekly_snapshots),
    weekly_snapshots[tier] = "Engaged"
)
```

```
Cooling Count = 
CALCULATE(
    COUNTROWS(weekly_snapshots),
    weekly_snapshots[tier] = "Cooling"
)
```

```
Dormant Count = 
CALCULATE(
    COUNTROWS(weekly_snapshots),
    weekly_snapshots[tier] = "Dormant"
)
```

These four automatically sum to the total fan count in whatever week context is active, since `tier` is mutually exclusive per fan per week.
