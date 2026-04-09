"""Unit tests for processing layer: normalize, dedupe, classify, score."""
from __future__ import annotations

import pytest

from app.processing.classify_rules import detect_intents, invalidate_cache
from app.processing.dedupe import make_fingerprint
from app.processing.normalize import canonicalize_url, normalize_text
from app.processing.scoring import compute_confidence, compute_opportunity, compute_risk


# --------------------------------------------------------------------------- #
# normalize                                                                    #
# --------------------------------------------------------------------------- #

class TestCanonicalizeUrl:
    def test_strips_utm_params(self):
        url = "https://t.me/example/?utm_source=x&utm_medium=y"
        assert "utm_source" not in canonicalize_url(url)
        assert "utm_medium" not in canonicalize_url(url)

    def test_strips_ref_param(self):
        url = "https://t.me/example/?ref=abc&foo=1"
        result = canonicalize_url(url)
        assert "ref=" not in result
        assert "foo=1" in result

    def test_lowercases_host(self):
        assert canonicalize_url("HTTPS://T.ME/Example") == "https://t.me/Example"

    def test_removes_trailing_slash(self):
        assert canonicalize_url("https://t.me/chan/") == "https://t.me/chan"

    def test_stable_without_params(self):
        url = "https://vk.com/studyhelp"
        assert canonicalize_url(url) == url

    def test_empty_string_returns_empty(self):
        assert canonicalize_url("") == ""


class TestNormalizeText:
    def test_lowercases(self):
        assert normalize_text("КУРСОВАЯ") == "курсовая"

    def test_collapses_whitespace(self):
        assert normalize_text("hello   world") == "hello world"

    def test_strips_leading_trailing(self):
        assert normalize_text("  test  ") == "test"

    def test_empty(self):
        assert normalize_text("") == ""


# --------------------------------------------------------------------------- #
# dedupe                                                                       #
# --------------------------------------------------------------------------- #

class TestMakeFingerprint:
    def test_stable(self):
        assert make_fingerprint("Hello", "https://a") == make_fingerprint("Hello", "https://a")

    def test_different_text(self):
        assert make_fingerprint("A", "https://a") != make_fingerprint("B", "https://a")

    def test_different_url(self):
        assert make_fingerprint("A", "https://a") != make_fingerprint("A", "https://b")

    def test_prefix(self):
        fp = make_fingerprint("test", "https://x")
        assert fp.startswith("sha256:")

    def test_empty_inputs(self):
        fp = make_fingerprint("", "")
        assert fp.startswith("sha256:")


# --------------------------------------------------------------------------- #
# classify                                                                     #
# --------------------------------------------------------------------------- #

class TestDetectIntents:
    def setup_method(self):
        # Invalidate cache so tests always use baseline rules
        invalidate_cache()

    def test_urgent_detected(self):
        intents, hits = detect_intents("Срочно нужна курсовая, дедлайн завтра")
        assert "urgent" in intents
        assert hits["urgent"] > 0

    def test_need_help_detected(self):
        intents, hits = detect_intents("Посоветуйте кто сделает работу")
        assert "need_help" in intents

    def test_plagiarism_detected(self):
        intents, _ = detect_intents("Как поднять уникальность, антиплагиат не прошёл")
        assert "plagiarism" in intents

    def test_formatting_detected(self):
        intents, _ = detect_intents("Нужно оформление ВКР по ГОСТу")
        assert "formatting" in intents

    def test_revisions_detected(self):
        intents, _ = detect_intents("Есть замечания от научрука, нужны правки")
        assert "revisions" in intents

    def test_negative_filter_blocks_meme(self):
        intents, hits = detect_intents("Это мем про срочно горит")
        assert intents == []
        assert hits == {}

    def test_empty_text(self):
        intents, hits = detect_intents("")
        assert intents == []

    def test_no_match(self):
        intents, hits = detect_intents("Хороший день, солнце светит")
        assert intents == []

    def test_scores_in_range(self):
        _, hits = detect_intents("Срочно нужна помощь с курсовой, антиплагиат провалился")
        for score in hits.values():
            assert 0.0 < score <= 1.0

    def test_multiple_intents(self):
        intents, _ = detect_intents("Срочно нужна помощь, антиплагиат и замечания")
        assert len(intents) >= 2


# --------------------------------------------------------------------------- #
# scoring                                                                      #
# --------------------------------------------------------------------------- #

class TestComputeOpportunity:
    def test_result_in_range(self):
        score = compute_opportunity({"relevance": 80, "demand": 90, "freshness": 70})
        assert 0 <= score <= 100

    def test_all_zeros(self):
        score = compute_opportunity({"relevance": 0, "demand": 0, "freshness": 0})
        assert score == 0.0

    def test_all_hundreds(self):
        score = compute_opportunity(
            {
                "relevance": 100,
                "demand": 100,
                "freshness": 100,
                "audience": 100,
                "admin_reachability": 100,
                "competitor_presence": 100,
                "content_fit": 100,
            }
        )
        assert score == 100.0

    def test_partial_features(self):
        # Should not crash with partial feature dict
        score = compute_opportunity({"relevance": 60})
        assert 0 <= score <= 100


class TestComputeRisk:
    def test_result_in_range(self):
        score = compute_risk({"rule_strictness": 80, "moderation_risk": 50})
        assert 0 <= score <= 100

    def test_all_zeros(self):
        assert compute_risk({}) == 0.0

    def test_all_hundreds(self):
        score = compute_risk(
            {
                "rule_strictness": 100,
                "moderation_risk": 100,
                "spam_sensitivity": 100,
                "automation_barrier": 100,
                "reputation_risk": 100,
            }
        )
        assert score == 100.0


class TestComputeConfidence:
    def test_empty_hits_returns_baseline(self):
        assert compute_confidence({}) == pytest.approx(0.2)

    def test_single_hit(self):
        conf = compute_confidence({"urgent": 0.9})
        assert 0.0 < conf <= 1.0

    def test_multiple_hits_averages(self):
        conf = compute_confidence({"urgent": 1.0, "need_help": 0.5})
        assert conf == pytest.approx(0.75)
