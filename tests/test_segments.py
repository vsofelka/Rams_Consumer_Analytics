import re

import pandas as pd

from scoring.segments import assign_segments

SEGMENT_PATTERN = re.compile(
    r"^(Highest|High|Mid|Low|Lowest) Engagement (Standard|Premium|Club)-Tier$"
)


def _mixed_fan_features_fixture():
    # 30 fans across 3 plan tiers with clearly separated engagement bands, so
    # k-means has real structure to find regardless of the exact split it picks.
    fan_id = list(range(1, 31))
    plan_tier = ["standard"] * 10 + ["premium"] * 10 + ["club"] * 10
    engagement_score = (
        [10.0 + i for i in range(10)]
        + [45.0 + i for i in range(10)]
        + [80.0 + i for i in range(10)]
    )
    tenure_years = [5] * 30
    return pd.DataFrame({
        "fan_id": fan_id,
        "plan_tier": plan_tier,
        "tenure_years": tenure_years,
        "engagement_score": engagement_score,
    })


def _five_band_fixture():
    # 25 fans, single plan tier and tenure held constant, five tightly-separated
    # engagement bands -- isolates the ranking/naming logic from the plan-tier
    # dimension. Band E (highest engagement) must be named "Highest Engagement...",
    # band A (lowest) must be named "Lowest Engagement...".
    bands = {
        "A": [5.0, 6.0, 7.0, 8.0, 9.0],
        "B": [25.0, 26.0, 27.0, 28.0, 29.0],
        "C": [45.0, 46.0, 47.0, 48.0, 49.0],
        "D": [65.0, 66.0, 67.0, 68.0, 69.0],
        "E": [85.0, 86.0, 87.0, 88.0, 89.0],
    }
    rows = []
    fan_id = 1
    for band, scores in bands.items():
        for score in scores:
            rows.append({"fan_id": fan_id, "band": band, "engagement_score": score})
            fan_id += 1
    df = pd.DataFrame(rows)
    df["plan_tier"] = "standard"
    df["tenure_years"] = 5
    return df


def test_assign_segments_produces_exactly_five_distinct_segment_names():
    fan_features = _mixed_fan_features_fixture()

    result = assign_segments(fan_features)

    assert result["segment"].nunique() == 5


def test_assign_segments_returns_exactly_one_row_per_input_fan():
    fan_features = _mixed_fan_features_fixture()

    result = assign_segments(fan_features)

    assert len(result) == len(fan_features)
    assert set(result["fan_id"]) == set(fan_features["fan_id"])
    assert result["fan_id"].duplicated().sum() == 0


def test_assign_segments_names_match_expected_pattern():
    fan_features = _mixed_fan_features_fixture()

    result = assign_segments(fan_features)

    assert all(SEGMENT_PATTERN.match(name) for name in result["segment"])


def test_assign_segments_ranks_engagement_bands_correctly():
    fan_features = _five_band_fixture()

    # assign_segments() preserves every input column (it copies fan_features and adds
    # segment_cluster/segment on top), so "band" is already on the result -- no need to
    # re-merge it back in (doing so would collide into "band_x"/"band_y" instead).
    result = assign_segments(fan_features)

    segment_by_band = result.groupby("band")["segment"].first()

    assert segment_by_band["E"].startswith("Highest Engagement")
    assert segment_by_band["A"].startswith("Lowest Engagement")


def test_assign_segments_is_deterministic_across_calls():
    fan_features = _mixed_fan_features_fixture()

    result1 = assign_segments(fan_features)
    result2 = assign_segments(fan_features)

    assert list(result1.sort_values("fan_id")["segment"]) == list(
        result2.sort_values("fan_id")["segment"]
    )
