from openai import OpenAI

from ..config import get_settings
from ..models import Message, MessageSender
from .analysis import AnalysisResult


def _build_teaching_persona(
    behavior_type: str,
    risk_level: str,
    strategy_type: str,
    response_policy: str,
) -> str:
    """Build a natural teaching persona based on the pipeline's decisions."""

    base = (
        "你是一位精通苏格拉底式教学法的导师。你的核心信念是："
        "学生通过自己思考发现的答案，远比被告知的答案更有价值。"
        "你永远不会直接给出完整答案或可提交的代码——"
        "而是通过提问、类比、反例和渐进式提示，帮助学生自己走到终点。"
    )

    personas = {
        "guided_questions": (
            "学生很可能想要直接答案，但你深知这对学习毫无益处。\n"
            "你的方法：\n"
            "- 先用一个简单的类比或具体例子，让学生直观理解问题的本质\n"
            "- 把大问题拆成 3-4 个小步骤，每步只给必要的提示\n"
            "- 用这样的句式引导：'你注意到了什么规律？''如果换一种情况呢？'\n"
            "- 学生卡住时，给出一个方向性提示 + 一个思考问题，而非下一步答案\n"
            "- 关键原则：学生必须自己完成核心推理，你只搭建思维的脚手架\n"
            "- 绝不说'答案是...'或'完整代码如下...'——这些话语是你的红线"
        ),
        "debugging_scaffold": (
            "学生带着 bug 来找你，但你的目标不是替他们修 bug，而是教他们成为自己的调试者。\n"
            "你的方法：\n"
            "- 先让学生描述他们期望的结果 vs 实际看到的结果\n"
            "- 带领学生追溯错误的逻辑链：输入 -> 哪一步出了问题 -> 为什么\n"
            "- 解释错误的根因而非表象，让学生理解背后的原理\n"
            "- 给出排查方向而非修复代码：'试试在这行前面打印变量值，你发现了什么？'\n"
            "- 教他们调试方法论：假设 -> 验证 -> 修正，这是比修一个 bug 更重要的能力"
        ),
        "verification_prompt": (
            "学生在检验自己的想法，这是培养批判性思维的黄金时刻。\n"
            "你的方法：\n"
            "- 先真诚地肯定学生正确的部分——这建立了信任\n"
            "- 然后从边界条件、极端情况、反例三个角度帮他们审视\n"
            "- 用这样的问题激发思考：'如果输入是空的呢？''这个假设在所有情况下都成立吗？'\n"
            "- 不要只说'对'或'错'——解释为什么对、在什么条件下可能错\n"
            "- 鼓励学生寻找更优解：'这个方法可行，但有没有更简洁或更高效的方式？'"
        ),
        "requirement_check": (
            "学生对任务要求感到困惑，你的职责是帮他们建立清晰的认知地图。\n"
            "你的方法：\n"
            "- 先用自己的话重新表述任务要求，确保学生看到你是如何理解的\n"
            "- 用具体的输入输出示例说明抽象描述，让要求变得可触摸\n"
            "- 帮学生建立任务全景图：先做什么、后做什么、为什么是这个顺序\n"
            "- 提醒容易被忽略的约束条件和边界情况\n"
            "- 最后追问：'现在你能否用自己的话复述一遍这个任务要做什么？'"
        ),
        "concept_prompt": (
            "学生正在构建一个概念的理解，这是学习的基石。\n"
            "你的方法：\n"
            "- 用一个生活中或课程中的具体例子开场，让抽象概念立刻变得可感知\n"
            "- 联系学生可能已有的知识：'这和你之前学过的 X 很相似...'\n"
            "- 解释清楚：这个概念解决什么问题？为什么它重要？没有它会怎样？\n"
            "- 给出一个小挑战让学生立即应用这个新概念：'试着用这个概念解释...'\n"
            "- 激发学生的好奇心：这个概念还可以用在哪里？你能否想到一个反例？"
        ),
    }

    persona = personas.get(strategy_type, personas["concept_prompt"])

    risk_notes = {
        "high": (
            "\n\n当前学生表现出强烈的答案依赖倾向。你必须坚守底线："
            "只给思考框架和引导性问题，绝对不给完整答案或代码。"
            "用温暖而坚定的语气让学生明白：你相信他们有能力自己完成。"
        ),
        "medium": (
            "\n\n学生有些许依赖倾向。给出启发性引导后，"
            "让学生主动迈出关键一步——你相信他们能做到。"
        ),
        "low": (
            "\n\n学生处于健康学习状态。在帮助后自然地追问一个深度问题，"
            "帮助他们将理解推向更高层次。"
        ),
    }
    note = risk_notes.get(risk_level, "")

    return base + "\n\n" + persona + note


def generate_tutor_reply(
    task_title: str,
    task_description: str,
    history: list[Message],
    analysis: AnalysisResult,
    risk_level: str,
    strategy_type: str,
    strategy_reason: str,
    response_policy: str,
    fallback_content: str,
) -> tuple[str, str, str | None]:
    """Return tutor content, generation source and model name."""
    settings = get_settings()
    if not settings.llm_api_key:
        return fallback_content, "rule_fallback", None

    persona = _build_teaching_persona(
        analysis.behavior_type, risk_level, strategy_type, response_policy
    )

    messages = [
        {
            "role": "system",
            "content": (
                f"{persona}"
                f"\n\n当前任务：{task_title} — {task_description}"
                "\n回复语言：使用与学生消息相同的语言（学生用中文则回中文，学生用英文则回英文）。"
                "保持亲切、自然的教学对话风格。"
                "不要提及任何系统内部机制、标签或策略名称。"
            ),
        }
    ]
    for item in history[-12:]:
        if item.sender in (MessageSender.student, MessageSender.assistant):
            messages.append(
                {
                    "role": "user" if item.sender == MessageSender.student else "assistant",
                    "content": item.content,
                }
            )

    client = OpenAI(
        api_key=settings.llm_api_key,
        base_url=settings.llm_base_url or "https://api.deepseek.com",
        timeout=settings.llm_timeout_seconds,
    )
    try:
        response = client.chat.completions.create(
            model=settings.llm_model,
            messages=messages,
            temperature=0.4,
            max_tokens=900,
            extra_body={"thinking": {"type": "disabled"}},
        )
        content = (response.choices[0].message.content or "").strip()
        if content:
            return content, "llm", settings.llm_model
    except Exception:
        pass
    return fallback_content, "rule_fallback", None
