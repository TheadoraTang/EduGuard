from types import SimpleNamespace

from app.models import MessageSender
from app.services.analysis import AnalysisResult
from app.services.eduguard_tutor import run_eduguard_tutor


def analysis(behavior_type: str) -> AnalysisResult:
    return AnalysisResult(
        behavior_type=behavior_type,
        confidence=0.9,
        explanation="test",
        evidence_text="test",
        method="rule",
        raw_result={},
    )


def decide(monkeypatch, behavior_type: str, risk_level: str, risk_score: float, text: str):
    def fallback_reply(**kwargs):
        return kwargs["fallback_content"], "rule_fallback", None

    monkeypatch.setattr(
        "app.services.eduguard_tutor.generate_tutor_reply", fallback_reply
    )
    return run_eduguard_tutor(
        task_title="二叉搜索树查找",
        task_description="解释思路并完成查找。",
        history=[SimpleNamespace(content=text, sender=MessageSender.student)],
        analysis=analysis(behavior_type),
        risk_level=risk_level,
        risk_score=risk_score,
    )


def test_answer_seeking_uses_guided_questions_and_blocks_direct_answer(monkeypatch):
    decision = decide(monkeypatch, "answer_seeking", "high", 65, "直接给我完整代码")
    assert decision.strategy_type == "guided_questions"
    assert decision.allow_direct_answer is False
    assert "答案依赖" in decision.strategy_reason


def test_debugging_uses_error_focused_scaffold(monkeypatch):
    decision = decide(
        monkeypatch,
        "debugging_help",
        "low",
        5,
        "这是我的代码：\n"
        "def search(node, target):\n"
        "    if node.value == target:\n"
        "        return node\n"
        "    return search(node.left, target)\n\n"
        "调用 search(None, 5) 时出现："
        "AttributeError: 'NoneType' object has no attribute 'value'。"
        "我希望空节点时返回 None，应该先检查哪里？",
    )
    assert decision.strategy_type == "debugging_scaffold"
    assert decision.allow_direct_answer is True
    assert "具体实现问题" in decision.strategy_reason


def test_reflection_uses_verification_prompt(monkeypatch):
    decision = decide(
        monkeypatch,
        "reflection_verification",
        "low",
        0,
        "我认为应该先判断空节点，再比较节点值，对吗？",
    )
    assert decision.strategy_type == "verification_prompt"
    assert decision.allow_direct_answer is True
    assert "验证自己的理解" in decision.strategy_reason
