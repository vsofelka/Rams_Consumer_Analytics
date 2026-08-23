import pandas as pd
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler

N_CLUSTERS = 5
RANDOM_STATE = 42
ENGAGEMENT_DESCRIPTORS = ["Highest", "High", "Mid", "Low", "Lowest"]


def assign_segments(fan_features):
    plan_dummies = pd.get_dummies(fan_features["plan_tier"], prefix="plan").astype(float)
    features = pd.concat(
        [fan_features[["engagement_score", "tenure_years"]], plan_dummies], axis=1
    )

    X = StandardScaler().fit_transform(features)
    labels = KMeans(n_clusters=N_CLUSTERS, random_state=RANDOM_STATE, n_init=10).fit_predict(X)

    result = fan_features.copy()
    result["segment_cluster"] = labels

    cluster_engagement = result.groupby("segment_cluster")["engagement_score"].mean()
    rank_order = cluster_engagement.sort_values(ascending=False).index.tolist()
    descriptor_by_cluster = {
        cluster_id: ENGAGEMENT_DESCRIPTORS[rank] for rank, cluster_id in enumerate(rank_order)
    }

    dominant_tier_by_cluster = result.groupby("segment_cluster")["plan_tier"].agg(
        lambda s: s.mode().iloc[0]
    )

    result["segment"] = result["segment_cluster"].map(
        lambda c: f"{descriptor_by_cluster[c]} Engagement {dominant_tier_by_cluster[c].title()}-Tier"
    )

    return result
