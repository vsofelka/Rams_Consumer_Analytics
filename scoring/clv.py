# Placeholder dollar/retention assumptions, pending real Rams pricing and
# renewal-rate data — see docs/superpowers/specs/2026-08-19-clv-design.md.
# Every value here is independently swappable once real figures exist.

ANNUAL_VALUE = {
    "standard": 2000,
    "premium": 6000,
    "club": 15000,
}

EXPECTED_REMAINING_YEARS = {
    "Super Fan": 8,
    "Engaged": 5,
    "Cooling": 2,
    "Dormant": 0.5,
}

AT_RISK_DISCOUNT = 0.5


def estimate_clv(plan_tier, engagement_tier, at_risk):
    base = ANNUAL_VALUE[plan_tier] * EXPECTED_REMAINING_YEARS[engagement_tier]
    if at_risk:
        return base * AT_RISK_DISCOUNT
    return base
