import numpy as np
import pandas as pd

DECAY_RATE = 0.85
NOISE_STD = 0.1


def _effective_engagement(fans, week):
    decline_active = fans["is_planted_churn"] & (week >= fans["decline_start_week"])
    weeks_declining = np.where(decline_active, week - fans["decline_start_week"] + 1, 0)
    decay_factor = DECAY_RATE ** weeks_declining
    return fans["baseline_engagement"] * decay_factor


def generate_week_events(fans, week, seed=42):
    rng = np.random.default_rng(seed * 1000 + week)
    effective = _effective_engagement(fans, week).to_numpy()

    def noisy_signal(base):
        return np.clip(base + rng.normal(0, NOISE_STD, size=len(base)), 0, 1)

    events = pd.DataFrame({
        "fan_id": fans["fan_id"].to_numpy(),
        "week": week,
        "attendance_signal": noisy_signal(effective),
        "digital_signal": noisy_signal(effective),
        "purchase_signal": noisy_signal(effective * 0.6),
    })
    return events
