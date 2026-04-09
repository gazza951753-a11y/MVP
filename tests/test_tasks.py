from app.tasks.creator import build_task_payload, decision


def test_decision_reply_opportunity():
    assert decision(opportunity=80, risk=20) == "reply_opportunity"


def test_build_task_payload_contains_required_fields():
    payload = build_task_payload("telegram_channel", ["urgent"], 82, 25)
    assert payload["task_type"] == "reply_opportunity"
    assert payload["status"] == "new"
    assert payload["utm_campaign"].startswith("telegram_channel_urgent_")
