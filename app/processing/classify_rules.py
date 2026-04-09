from __future__ import annotations

import re

PATTERNS = {
    "need_help": [r"кто\s+сделает", r"нужна\s+помощь", r"посоветуйте"],
    "urgent": [r"срочно", r"горит", r"дедлайн"],
    "plagiarism": [r"антиплагиат", r"уникальност"],
    "formatting": [r"гост", r"оформлен"],
    "revisions": [r"правк", r"замечани"],
}
NEGATIVE = [r"мем", r"шутк"]


def detect_intents(text: str) -> tuple[list[str], dict[str, float]]:
    lowered = text.lower()
    if any(re.search(p, lowered) for p in NEGATIVE):
        return [], {}

    intents: list[str] = []
    scores: dict[str, float] = {}
    for intent, patterns in PATTERNS.items():
        hits = sum(1 for p in patterns if re.search(p, lowered))
        if hits:
            intents.append(intent)
            scores[intent] = min(1.0, 0.4 + hits * 0.3)
    return intents, scores
