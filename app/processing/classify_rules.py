"""Intent detection engine.

Loads trigger rules from the database (triggers table) on first call and caches
them.  Falls back to built-in baseline rules when the DB is unavailable (e.g.
during unit tests or before the first migration).

The cache is invalidated once per ``CACHE_TTL_SECONDS`` to pick up rule changes
made by operators without requiring a restart.
"""
from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)

# --------------------------------------------------------------------------- #
# Baseline rules (used as fallback and as seed data)                          #
# --------------------------------------------------------------------------- #

BASELINE_TRIGGERS: list[dict] = [
    {
        "code": "need_help",
        "description": "Ищут помощь или исполнителя",
        "regex_patterns": [r"кто\s+сделает", r"нужна\s+помощь", r"посоветуйте", r"нужен\s+исполнитель"],
        "keywords": ["заказать", "помогите", "ищу автора"],
        "negative_keywords": ["мем", "шутк", "бесплатно"],
        "weight": 10.0,
    },
    {
        "code": "urgent",
        "description": "Срочность / дедлайн",
        "regex_patterns": [r"срочно", r"горит", r"дедлайн", r"сдать\s+завтра", r"до\s+утра"],
        "keywords": ["срочно", "успеть", "сегодня"],
        "negative_keywords": ["мем", "шутк"],
        "weight": 12.0,
    },
    {
        "code": "plagiarism",
        "description": "Антиплагиат / уникальность",
        "regex_patterns": [r"антиплагиат", r"уникальност", r"поднять\s+уникальност"],
        "keywords": ["антиплаг", "уникальность", "проверка оригинальности"],
        "negative_keywords": [],
        "weight": 9.0,
    },
    {
        "code": "formatting",
        "description": "ГОСТ / оформление",
        "regex_patterns": [r"гост", r"оформлен", r"список\s+литератур", r"оформить\s+вкр"],
        "keywords": ["ГОСТ", "оформление", "список литературы", "ВКР"],
        "negative_keywords": [],
        "weight": 6.0,
    },
    {
        "code": "revisions",
        "description": "Правки по научруку / замечания",
        "regex_patterns": [r"правк", r"замечани", r"научрук", r"исправит"],
        "keywords": ["правки", "замечания", "научный руководитель"],
        "negative_keywords": [],
        "weight": 7.0,
    },
    {
        "code": "competitor_mention",
        "description": "Упоминание конкурента",
        "regex_patterns": [r"автор24", r"studwork", r"helpstudent", r"курсач"],
        "keywords": [],
        "negative_keywords": [],
        "weight": 8.0,
    },
]

GLOBAL_NEGATIVE = [r"мем", r"шутк", r"прикол"]

CACHE_TTL_SECONDS = 300  # 5 minutes


@dataclass
class _TriggerRule:
    code: str
    regex_patterns: list[re.Pattern]
    keywords: list[str]
    negative_keywords: list[str]
    weight: float


@dataclass
class _Cache:
    rules: list[_TriggerRule] = field(default_factory=list)
    loaded_at: Optional[float] = None  # None = never loaded

    def is_stale(self) -> bool:
        if self.loaded_at is None:
            return True
        return time.monotonic() - self.loaded_at > CACHE_TTL_SECONDS


_cache = _Cache()


def _compile(trigger_dict: dict) -> _TriggerRule:
    patterns = [re.compile(p, re.IGNORECASE) for p in (trigger_dict.get("regex_patterns") or [])]
    return _TriggerRule(
        code=trigger_dict["code"],
        regex_patterns=patterns,
        keywords=[k.lower() for k in (trigger_dict.get("keywords") or [])],
        negative_keywords=[k.lower() for k in (trigger_dict.get("negative_keywords") or [])],
        weight=float(trigger_dict.get("weight", 1.0)),
    )


def _load_from_db() -> Optional[list[_TriggerRule]]:
    """Try to load enabled triggers from DB; return None on any error."""
    try:
        from sqlalchemy import select

        from app.db.base import SessionLocal
        from app.db.models import Trigger

        with SessionLocal() as session:
            rows = session.execute(select(Trigger).where(Trigger.enabled.is_(True))).scalars().all()
            if not rows:
                return None
            return [
                _compile(
                    {
                        "code": t.code,
                        "regex_patterns": t.regex_patterns or [],
                        "keywords": t.keywords or [],
                        "negative_keywords": t.negative_keywords or [],
                        "weight": t.weight,
                    }
                )
                for t in rows
            ]
    except Exception as exc:  # noqa: BLE001
        logger.debug("Cannot load triggers from DB (%s); using baseline rules", exc)
        return None


def _get_rules() -> list[_TriggerRule]:
    if _cache.is_stale():
        db_rules = _load_from_db()
        _cache.rules = db_rules if db_rules else [_compile(t) for t in BASELINE_TRIGGERS]
        _cache.loaded_at = time.monotonic()
    return _cache.rules


def invalidate_cache() -> None:
    """Force reload of trigger rules on next call (e.g. after seed insert)."""
    _cache.loaded_at = None


# --------------------------------------------------------------------------- #
# Public API                                                                   #
# --------------------------------------------------------------------------- #

_GLOBAL_NEG_PATTERNS = [re.compile(p, re.IGNORECASE) for p in GLOBAL_NEGATIVE]


def detect_intents(text: str) -> tuple[list[str], dict[str, float]]:
    """Return (intent_codes, {code: confidence_score}) for *text*.

    Confidence is ``min(1.0, 0.4 + hit_count * 0.3)`` per rule, scaled by the
    trigger weight normalised to [0, 1] relative to the maximum weight in the
    rule set (so heavier triggers contribute proportionally more).
    """
    lowered = text.lower()

    if any(p.search(lowered) for p in _GLOBAL_NEG_PATTERNS):
        return [], {}

    rules = _get_rules()
    max_weight = max((r.weight for r in rules), default=1.0)

    intents: list[str] = []
    scores: dict[str, float] = {}

    for rule in rules:
        # Rule-level negative filter
        if any(kw in lowered for kw in rule.negative_keywords):
            continue

        regex_hits = sum(1 for p in rule.regex_patterns if p.search(lowered))
        kw_hits = sum(1 for kw in rule.keywords if kw in lowered)
        total_hits = regex_hits + kw_hits

        if total_hits:
            raw_confidence = min(1.0, 0.4 + total_hits * 0.3)
            weight_factor = rule.weight / max_weight
            intents.append(rule.code)
            scores[rule.code] = round(raw_confidence * weight_factor, 4)

    return intents, scores
