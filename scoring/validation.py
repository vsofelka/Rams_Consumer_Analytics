def evaluate_churn_detection(at_risk, fans, week):
    merged = at_risk.merge(fans[["fan_id", "is_planted_churn", "decline_start_week"]], on="fan_id")

    # SQLite has no native boolean type, so these columns come back from
    # pd.read_sql as int64 (0/1). Cast explicitly so `&` and `~` are logical
    # operations rather than bitwise ones on integers.
    at_risk_flag = merged["at_risk"].astype(bool)
    is_planted = merged["is_planted_churn"].astype(bool)

    ground_truth_at_risk = is_planted & (week >= merged["decline_start_week"])

    true_positives = int((at_risk_flag & ground_truth_at_risk).sum())
    false_positives = int((at_risk_flag & ~ground_truth_at_risk).sum())
    false_negatives = int((~at_risk_flag & ground_truth_at_risk).sum())

    precision = true_positives / (true_positives + false_positives) if (true_positives + false_positives) > 0 else 0.0
    recall = true_positives / (true_positives + false_negatives) if (true_positives + false_negatives) > 0 else 0.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) > 0 else 0.0

    return {
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "true_positives": true_positives,
        "false_positives": false_positives,
        "false_negatives": false_negatives,
    }
