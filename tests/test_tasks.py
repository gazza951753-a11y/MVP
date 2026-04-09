"""Unit tests for task creation logic."""
from __future__ import annotations

import pytest

from app.tasks.creator import build_task_payload, decision, priority_from_scores
from app.tasks.templates import build_utm_campaign, draft_expert_reply


# --------------------------------------------------------------------------- #
# decision()                                                                   #
# --------------------------------------------------------------------------- #

class TestDecision:
    def test_reply_opportunity_high_opp_low_risk(self):
        assert decision(opportunity=80, risk=20) == "reply_opportunity"

    def test_reply_opportunity_boundary(self):
        assert decision(opportunity=75, risk=35) == "reply_opportunity"

    def test_review_platform_medium(self):
        assert decision(opportunity=65, risk=45) == "review_platform"

    def test_watch_only_high_risk(self):
        assert decision(opportunity=90, risk=75) == "watch_only"

    def test_watch_only_low_opp(self):
        assert decision(opportunity=40, risk=40) == "watch_only"

    def test_blocked_returns_investigate_access(self):
        assert decision(opportunity=90, risk=10, blocked=True) == "investigate_access"

    def test_blocked_overrides_everything(self):
        # Even when opportunity is perfect and risk is 0, blocked wins
        assert decision(opportunity=100, risk=0, blocked=True) == "investigate_access"


# --------------------------------------------------------------------------- #
# priority_from_scores()                                                       #
# --------------------------------------------------------------------------- #

class TestPriorityFromScores:
    def test_priority_5(self):
        assert priority_from_scores(opportunity=85, risk=25) == 5

    def test_priority_4(self):
        assert priority_from_scores(opportunity=72, risk=38) == 4

    def test_priority_3(self):
        assert priority_from_scores(opportunity=62, risk=48) == 3

    def test_priority_1_high_risk(self):
        assert priority_from_scores(opportunity=50, risk=80) == 1

    def test_priority_2_default(self):
        assert priority_from_scores(opportunity=40, risk=40) == 2


# --------------------------------------------------------------------------- #
# build_task_payload()                                                         #
# --------------------------------------------------------------------------- #

class TestBuildTaskPayload:
    def test_required_keys_present(self):
        payload = build_task_payload("telegram_channel", ["urgent"], 82, 25)
        required = {"task_type", "status", "priority", "opportunity_score", "risk_score",
                    "recommended_action", "message_draft", "utm_campaign"}
        assert required.issubset(payload.keys())

    def test_status_always_new(self):
        payload = build_task_payload("vk_group", [], 50, 50)
        assert payload["status"] == "new"

    def test_opportunity_score_stored(self):
        payload = build_task_payload("forum_thread", ["plagiarism"], 70, 30)
        assert payload["opportunity_score"] == pytest.approx(70)

    def test_risk_score_stored(self):
        payload = build_task_payload("forum_thread", ["plagiarism"], 70, 30)
        assert payload["risk_score"] == pytest.approx(30)

    def test_utm_starts_with_platform_type(self):
        payload = build_task_payload("telegram_channel", ["urgent"], 82, 25)
        assert payload["utm_campaign"].startswith("telegram_channel_")

    def test_utm_contains_intent(self):
        payload = build_task_payload("vk_group", ["plagiarism"], 70, 30)
        assert "plagiarism" in payload["utm_campaign"]

    def test_no_intents_general(self):
        payload = build_task_payload("telegram_channel", [], 50, 40)
        assert "general" in payload["utm_campaign"]


# --------------------------------------------------------------------------- #
# Templates                                                                    #
# --------------------------------------------------------------------------- #

class TestDraftExpertReply:
    def test_urgent_draft_is_different(self):
        urgent = draft_expert_reply(["urgent"])
        normal = draft_expert_reply(["formatting"])
        assert urgent != normal

    def test_returns_non_empty_string(self):
        assert len(draft_expert_reply(["need_help"])) > 10
        assert len(draft_expert_reply([])) > 10

    def test_no_autopost_content(self):
        # Draft must not contain any automated-send markers
        draft = draft_expert_reply(["urgent", "plagiarism"])
        assert "http" not in draft.lower() or "utm" not in draft.lower()


class TestBuildUtmCampaign:
    def test_format(self):
        result = build_utm_campaign("telegram_channel", "urgent")
        parts = result.split("_")
        # Should have at least: platform_type + intent + YYYYMM (= 4 parts)
        assert len(parts) >= 4

    def test_contains_platform_and_intent(self):
        result = build_utm_campaign("vk_group", "plagiarism")
        assert "vk_group" in result
        assert "plagiarism" in result

    def test_date_suffix_length(self):
        result = build_utm_campaign("forum_thread", "urgent")
        # Last segment should be 6-digit YYYYMM
        suffix = result.split("_")[-1]
        assert suffix.isdigit()
        assert len(suffix) == 6
