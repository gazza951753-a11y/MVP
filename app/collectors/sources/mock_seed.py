from datetime import datetime, timezone

from app.collectors.base import CollectResult, Collector


class MockSeedCollector(Collector):
    name = "mock_seed"

    def collect(self) -> CollectResult:
        return CollectResult(
            platforms=[
                {
                    "platform_type": "telegram_channel",
                    "title": "Помощь студентам | курсовые",
                    "url": "https://t.me/studyassist_help",
                    "handle": "@studyassist_help",
                    "description": "Обсуждение курсовых, ВКР, правок",
                    "language": "ru",
                    "geo": "RU",
                    "audience_size": 12400,
                    "activity_last_seen_at": datetime.now(timezone.utc),
                    "rules_text": "Без спама. Реклама только по согласованию.",
                    "commercial_tolerance": 3,
                    "risk_flags": {"ban_risk": False},
                    "tags": ["student", "diploma", "coursework"],
                    "discovery_source": "seed:mock",
                }
            ],
            mentions=[
                {
                    "platform_url": "https://t.me/studyassist_help",
                    "mention_type": "post",
                    "source_url": "https://t.me/studyassist_help/101",
                    "author_handle": "@anon",
                    "published_at": datetime.now(timezone.utc),
                    "text": "Срочно нужна помощь с курсовой, дедлайн завтра",
                    "raw_payload": {"source": "mock"},
                }
            ],
        )
