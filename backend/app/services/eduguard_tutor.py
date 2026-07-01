from dataclasses import asdict, dataclass

from ..models import Message
from .analysis import AnalysisResult, has_personal_attempt
from .intervention import build_intervention
from .tutor import generate_tutor_reply


@dataclass
class TutorDecision:
    behavior_type: str
    risk_level: str
    risk_score: float
    intervention_level: int
    strategy_type: str
    strategy_reason: str
    response_policy: str
    allow_direct_answer: bool
    generated_response: str
    generated_by: str
    generation_model: str | None

    def metadata(self) -> dict:
        decision = asdict(self)
        decision.pop("generated_response")
        return {
            "eduguard_tutor": {
                "version": "v1",
                **decision,
            }
        }


def explain_strategy(
    analysis: AnalysisResult,
    risk_level: str,
    risk_score: float,
    student_text: str,
) -> tuple[str, bool]:
    attempted = has_personal_attempt(student_text)
    if risk_level == "high":
        return (
            f"学生当前风险分数为 {risk_score:.0f}，存在答案依赖倾向；"
            "先给出概念性引导和思考框架，再请学生尝试自己解决，保留关键推理过程。",
            False,
        )
    if analysis.behavior_type == "debugging_help":
        return (
            "学生提供了代码、错误或具体实现问题；直接帮助分析错误并给出修改建议，"
            "同时引导学生理解错误原因。",
            True,
        )
    if analysis.behavior_type == "reflection_verification":
        return (
            "学生正在验证自己的理解或结果；先检查其理由，再通过边界条件或反例完成核对。",
            True,
        )
    if analysis.behavior_type == "task_clarification":
        return (
            "学生需要澄清任务边界；直接解释输入、输出和提交要求，帮助理解任务。",
            True,
        )
    return (
        "学生主要在理解概念；先给出清晰的概念解释和例子，再用一个问题检查理解。",
        risk_level != "high",
    )


def run_eduguard_tutor(
    task_title: str,
    task_description: str,
    history: list[Message],
    analysis: AnalysisResult,
    risk_level: str,
    risk_score: float,
) -> TutorDecision:
    intervention_level, strategy_type, fallback_content = build_intervention(
        analysis, risk_level
    )
    strategy_reason, allow_direct_answer = explain_strategy(
        analysis,
        risk_level,
        risk_score,
        history[-1].content if history else "",
    )
    response_policy = (
        "优先给出概念性解释和思考框架，引导学生自己完成关键步骤；"
        "不要直接给出可提交的完整代码或答案。"
        if not allow_direct_answer
        else "直接回答问题，在解释清楚后用一个问题检查学生的理解，保持自然对话感。"
    )
    response_text, generated_by, generation_model = generate_tutor_reply(
        task_title=task_title,
        task_description=task_description,
        history=history,
        analysis=analysis,
        risk_level=risk_level,
        strategy_type=strategy_type,
        strategy_reason=strategy_reason,
        response_policy=response_policy,
        fallback_content=fallback_content,
    )
    return TutorDecision(
        behavior_type=analysis.behavior_type,
        risk_level=risk_level,
        risk_score=risk_score,
        intervention_level=intervention_level,
        strategy_type=strategy_type,
        strategy_reason=strategy_reason,
        response_policy=response_policy,
        allow_direct_answer=allow_direct_answer,
        generated_response=response_text,
        generated_by=generated_by,
        generation_model=generation_model,
    )
