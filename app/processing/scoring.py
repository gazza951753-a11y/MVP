from __future__ import annotations


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def compute_opportunity(features: dict[str, float]) -> float:
    score = (
        0.30 * features.get("relevance", 0)
        + 0.20 * features.get("demand", 0)
        + 0.15 * features.get("freshness", 0)
        + 0.10 * features.get("audience", 0)
        + 0.10 * features.get("admin_reachability", 0)
        + 0.10 * features.get("competitor_presence", 0)
        + 0.05 * features.get("content_fit", 0)
    )
    return round(_clamp(score, 0, 100), 2)


def compute_risk(features: dict[str, float]) -> float:
    score = (
        0.35 * features.get("rule_strictness", 0)
        + 0.20 * features.get("moderation_risk", 0)
        + 0.20 * features.get("spam_sensitivity", 0)
        + 0.10 * features.get("automation_barrier", 0)
        + 0.15 * features.get("reputation_risk", 0)
    )
    return round(_clamp(score, 0, 100), 2)


def compute_confidence(trigger_hits: dict[str, float]) -> float:
    if not trigger_hits:
        return 0.2
    return round(_clamp(sum(trigger_hits.values()) / max(len(trigger_hits), 1), 0.0, 1.0), 2)
