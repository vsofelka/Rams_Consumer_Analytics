import numpy as np
import pandas as pd


def generate_fan_population(n_fans, n_planted_churn, decline_start_week, seed=42):
    rng = np.random.default_rng(seed)

    fan_ids = np.arange(1, n_fans + 1)
    baseline_engagement = rng.beta(a=2, b=2, size=n_fans)
    tenure_years = rng.integers(1, 21, size=n_fans)
    plan_tier = rng.choice(["standard", "premium", "club"], size=n_fans, p=[0.6, 0.3, 0.1])

    planted_churn_ids = rng.choice(fan_ids, size=n_planted_churn, replace=False)
    is_planted_churn = np.isin(fan_ids, planted_churn_ids)

    fans = pd.DataFrame({
        "fan_id": fan_ids,
        "tenure_years": tenure_years,
        "plan_tier": plan_tier,
        "baseline_engagement": baseline_engagement,
        "is_planted_churn": is_planted_churn,
        "decline_start_week": np.where(is_planted_churn, decline_start_week, np.nan),
    })
    return fans
