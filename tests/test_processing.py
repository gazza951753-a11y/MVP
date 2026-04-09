from app.processing.classify_rules import detect_intents
from app.processing.dedupe import make_fingerprint
from app.processing.normalize import canonicalize_url
from app.processing.scoring import compute_opportunity, compute_risk


def test_canonicalize_url_strips_tracking_params():
    url = "https://t.me/example/?utm_source=x&ref=abc&a=1"
    assert canonicalize_url(url) == "https://t.me/example?a=1"


def test_detect_intents_urgent_and_need_help():
    intents, hits = detect_intents("Срочно нужна помощь, дедлайн завтра")
    assert "urgent" in intents
    assert hits["urgent"] > 0


def test_fingerprint_stable():
    fp1 = make_fingerprint("Тест", "https://a")
    fp2 = make_fingerprint("Тест", "https://a")
    assert fp1 == fp2


def test_scoring_in_range():
    opportunity = compute_opportunity({"relevance": 80, "demand": 80})
    risk = compute_risk({"rule_strictness": 80})
    assert 0 <= opportunity <= 100
    assert 0 <= risk <= 100
