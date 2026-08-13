import math

from scipy import stats


def compare_churn_cohort_engagement(scores: "pd.DataFrame", fans: "pd.DataFrame") -> dict:
    merged = scores.merge(fans[["fan_id", "is_planted_churn"]], on="fan_id")
    planted = merged.loc[merged["is_planted_churn"], "engagement_score"]
    rest = merged.loc[~merged["is_planted_churn"], "engagement_score"]

    statistic, p_value = stats.mannwhitneyu(planted, rest, alternative="less")

    return {
        "statistic": float(statistic),
        "p_value": float(p_value),
        "planted_median": float(planted.median()),
        "rest_median": float(rest.median()),
        "n_planted": int(len(planted)),
        "n_rest": int(len(rest)),
    }


def wilson_confidence_interval(successes: int, n: int, confidence: float = 0.95) -> dict:
    if n == 0:
        return {"lower": 0.0, "upper": 0.0, "point_estimate": 0.0}

    z_scores = {0.95: 1.959963985, 0.99: 2.575829304}
    z = z_scores[confidence]
    p_hat = successes / n

    denominator = 1 + z**2 / n
    center = (p_hat + z**2 / (2 * n)) / denominator
    margin = (z * math.sqrt((p_hat * (1 - p_hat) + z**2 / (4 * n)) / n)) / denominator

    return {
        "lower": max(0.0, center - margin),
        "upper": min(1.0, center + margin),
        "point_estimate": p_hat,
    }


def hypergeometric_test(population_size: int, n_true_churners: int, n_flagged: int, n_true_positives: int) -> dict:
    rv = stats.hypergeom(population_size, n_true_churners, n_flagged)
    p_value = float(rv.sf(n_true_positives - 1))  # P(X >= n_true_positives)

    return {
        "p_value": p_value,
        "expected_true_positives_by_chance": float(rv.mean()),
        "observed_true_positives": n_true_positives,
    }
