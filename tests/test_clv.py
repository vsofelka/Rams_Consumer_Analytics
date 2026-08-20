from scoring.clv import estimate_clv


def test_estimate_clv_super_fan_club_not_at_risk_matches_sanity_check():
    assert estimate_clv("club", "Super Fan", False) == 120000.0


def test_estimate_clv_dormant_at_risk_standard_matches_sanity_check():
    assert estimate_clv("standard", "Dormant", True) == 500.0


def test_estimate_clv_scales_with_engagement_tier_years():
    assert estimate_clv("standard", "Super Fan", False) == 16000.0
    assert estimate_clv("standard", "Engaged", False) == 10000.0
    assert estimate_clv("standard", "Cooling", False) == 4000.0
    assert estimate_clv("standard", "Dormant", False) == 1000.0


def test_estimate_clv_scales_with_plan_tier_annual_value():
    assert estimate_clv("standard", "Engaged", False) == 10000.0
    assert estimate_clv("premium", "Engaged", False) == 30000.0
    assert estimate_clv("club", "Engaged", False) == 75000.0


def test_estimate_clv_at_risk_halves_the_result():
    not_at_risk = estimate_clv("premium", "Cooling", False)
    at_risk = estimate_clv("premium", "Cooling", True)
    assert at_risk == not_at_risk * 0.5
