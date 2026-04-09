from __future__ import annotations

from app.tasks.templates import build_utm_campaign, draft_expert_reply


def decision(opportunity: float, risk: float, blocked: bool = False) -> str:
    if blocked:
        return "investigate_access"
    if risk > 70:
        return "watch_only"
    if opportunity >= 75 and risk <= 35:
        return "reply_opportunity"
    if opportunity >= 60 and risk <= 50:
        return "review_platform"
    return "watch_only"


def priority_from_scores(opportunity: float, risk: float) -> int:
    if opportunity >= 80 and risk <= 30:
        return 5
    if opportunity >= 70 and risk <= 40:
        return 4
    if opportunity >= 60 and risk <= 50:
        return 3
    if risk > 70:
        return 1
    return 2


def build_task_payload(platform_type: str, intents: list[str], opportunity: float, risk: float) -> dict:
    primary_intent = intents[0] if intents else "general"
    task_type = decision(opportunity, risk)
    return {
        "task_type": task_type,
        "status": "new",
        "priority": priority_from_scores(opportunity, risk),
        "opportunity_score": opportunity,
        "risk_score": risk,
        "recommended_action": "manual_review_rules_before_touch",
        "message_draft": draft_expert_reply(intents),
        "utm_campaign": build_utm_campaign(platform_type, primary_intent),
    }
