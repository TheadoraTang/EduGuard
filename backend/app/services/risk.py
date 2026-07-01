from dataclasses import dataclass

from .analysis import has_personal_attempt, is_explicit_answer_request


@dataclass
class Evidence:
    evidence_type: str
    description: str
    weight: float
    data: dict


@dataclass
class RiskResult:
    score: float
    level: str
    evidences: list[Evidence]


def assess_risk(
    text: str,
    behavior_type: str,
    prior_answer_seeking_count: int,
    has_reflection: bool,
) -> RiskResult:
    normalized = text.lower()
    evidences: list[Evidence] = []
    effective_answer_seeking = behavior_type == "answer_seeking" or is_explicit_answer_request(text)

    def add(kind: str, description: str, weight: float, **data):
        evidences.append(Evidence(kind, description, weight, data))

    if effective_answer_seeking:
        add("explicit_answer_request", "当前提问明确索要完整答案。", 30, behavior=behavior_type)
    if prior_answer_seeking_count >= 1 and effective_answer_seeking:
        add(
            "repeated_answer_request",
            "本次对话中已连续或重复索要答案。",
            20,
            previous_count=prior_answer_seeking_count,
        )
    if not has_personal_attempt(text):
        add("missing_attempt", "当前提问没有提供个人尝试、代码或思路。", 15)
    if any(
        phrase in normalized
        for phrase in ("能交的", "直接提交", "完整代码", "帮我写完", "submission-ready")
    ):
        add("submission_ready_request", "提问要求生成可直接提交的内容。", 20)
    if has_personal_attempt(text):
        add("personal_attempt", "学生提供了代码、思路、输出或错误信息。", -10)
    if behavior_type == "reflection_verification" or has_reflection:
        add("reflection_or_verification", "学生进行了反思或主动验证。", -15)

    if effective_answer_seeking:
        add(
            "answer_request_severity",
            "Direct answer requests should not be treated as low risk.",
            15,
        )

    score = max(0.0, min(100.0, sum(item.weight for item in evidences)))
    level = "low" if score < 30 else "medium" if score < 60 else "high"
    return RiskResult(score=score, level=level, evidences=evidences)
