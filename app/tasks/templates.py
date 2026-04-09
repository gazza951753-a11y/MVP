from datetime import datetime


def build_utm_campaign(platform_type: str, primary_intent: str) -> str:
    return f"{platform_type}_{primary_intent}_{datetime.utcnow().strftime('%Y%m')}"


def draft_expert_reply(intents: list[str]) -> str:
    if "urgent" in intents:
        return "Понимаю, что срочно. Могу подсказать пошаговый план и помочь оформить решение под ваш дедлайн."
    return "Могу дать структурированный разбор и рекомендации по вашей задаче, без лишней рекламы."
