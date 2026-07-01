from app.services.risk import assess_risk


def test_direct_answer_request_without_attempt_is_high_risk():
    result = assess_risk(
        "\u544a\u8bc9\u6211\u7b2c\u4e00\u9898\u7684\u7b54\u6848",
        "answer_seeking",
        prior_answer_seeking_count=0,
        has_reflection=False,
    )

    assert result.level == "high"


def test_explicit_answer_text_stays_high_risk_even_if_behavior_is_misclassified():
    result = assess_risk(
        "\u7b2c\u4e8c\u9898\u7684\u7b54\u6848\u662f\u4ec0\u4e48",
        "debugging_help",
        prior_answer_seeking_count=0,
        has_reflection=False,
    )

    assert result.level == "high"
