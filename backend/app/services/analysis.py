import json
import re
from dataclasses import dataclass
from typing import Literal

from openai import OpenAI

from ..config import get_settings


BehaviorType = Literal[
    "concept_understanding",
    "answer_seeking",
    "debugging_help",
    "task_clarification",
    "reflection_verification",
]

BEHAVIOR_TYPES: tuple[BehaviorType, ...] = (
    "concept_understanding",
    "answer_seeking",
    "debugging_help",
    "task_clarification",
    "reflection_verification",
)


@dataclass
class AnalysisResult:
    behavior_type: BehaviorType
    confidence: float
    explanation: str
    evidence_text: str
    method: str
    raw_result: dict
    model_name: str | None = None

    def __post_init__(self) -> None:
        if self.behavior_type not in BEHAVIOR_TYPES:
            raise ValueError(
                f"Unsupported behavior_type {self.behavior_type!r}; "
                f"expected one of {BEHAVIOR_TYPES}"
            )


RULES: list[tuple[str, tuple[str, ...], str]] = [
    (
        "answer_seeking",
        (
            "直接给",
            "完整答案",
            "完整代码",
            "不用解释",
            "能交的",
            "帮我写完",
            "do it for me",
            "full answer",
            "complete code",
        ),
        "提问包含直接获取完整答案或可提交产物的表达。",
    ),
    (
        "debugging_help",
        ("报错", "错误", "bug", "exception", "traceback", "为什么运行不了", "调试"),
        "提问聚焦错误、异常或调试过程。",
    ),
    (
        "reflection_verification",
        (
            "对不对",
            "是否正确",
            "验证",
            "检查我的",
            "我的理解",
            "为什么一定",
            "局限",
            "反例",
            "质疑",
            "是否可能错",
            "verify",
            "is this correct",
            "alternative",
            "limitation",
        ),
        "学生在验证、反思或质疑已有理解、代码、结果或结论。",
    ),
    (
        "task_clarification",
        ("题目要求", "什么意思", "需要提交", "任务要求", "assignment require"),
        "学生在澄清任务目标或提交要求。",
    ),
]


def _matches(text: str, patterns: tuple[str, ...]) -> str | None:
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE | re.DOTALL)
        if match:
            return match.group(0)[:160]
    return None


EXPLICIT_ANSWER_PATTERNS: tuple[str, ...] = (
    r"(\u544a\u8bc9|\u7ed9|give|tell).{0,12}(\u7b2c\s*[0-9\u4e00-\u5341]+\s*\u9898).{0,12}(\u7b54\u6848|\u89e3\u6cd5|answer|solution)",
    r"(\u7b2c\s*[0-9\u4e00-\u5341]+\s*\u9898).{0,12}(\u7b54\u6848|\u89e3\u6cd5|answer|solution)",
    r"(\u544a\u8bc9|\u7ed9|\u76f4\u63a5\u7ed9).{0,16}(\u7b54\u6848|\u6807\u51c6\u7b54\u6848|\u89e3\u6cd5|\u7ed3\u679c)",
    r"(\u7b54\u6848|\u89e3\u6cd5).{0,8}(\u662f\u4ec0\u4e48|\u662f\u591a\u5c11|\u600e\u4e48\u5199|\u600e\u4e48\u505a)",
)


def explicit_answer_request_match(text: str) -> str | None:
    return _matches(text.lower().strip(), EXPLICIT_ANSWER_PATTERNS)


def is_explicit_answer_request(text: str) -> bool:
    return explicit_answer_request_match(text) is not None


def classify_with_rules(text: str) -> AnalysisResult:
    normalized = text.lower().strip()
    explicit_answer = explicit_answer_request_match(normalized)
    if explicit_answer:
        return AnalysisResult(
            behavior_type="answer_seeking",
            confidence=0.94,
            explanation="Student explicitly asks for an answer or solution.",
            evidence_text=explicit_answer,
            method="rule",
            raw_result={"matched_pattern_text": explicit_answer},
        )

    explicit_scaffold = _matches(
        normalized,
        (
            r"\b(do not|don'?t|without)\b.{0,30}\b(full answer|answer|complete code)\b",
            r"(不要|别).{0,12}(完整答案|答案|完整代码)",
        ),
    )
    if explicit_scaffold and _matches(
        normalized, (r"\b(hint|tips?|guidance|help|advise)\b", r"(提示|思路|建议|引导)")
    ):
        return AnalysisResult(
            behavior_type="concept_understanding",
            confidence=0.9,
            explanation="学生通过请求提示或引导来理解问题，而非索取完整答案。",
            evidence_text=explicit_scaffold,
            method="rule",
            raw_result={"matched_pattern_text": explicit_scaffold},
        )

    explicit_error = _matches(
        normalized,
        (
            r"\b(traceback|exception|attributeerror|typeerror|syntaxerror|valueerror)\b",
            r"\b(error|bug|warning)\b",
            r"(报错|错误信息|异常)",
        ),
    )
    if explicit_error and not _matches(
        normalized, (r"(直接|完整).{0,10}(答案|代码)", r"\bcomplete code\b")
    ):
        return AnalysisResult(
            behavior_type="debugging_help",
            confidence=0.9,
            explanation="学生提供了明确的错误或异常信息并请求调试。",
            evidence_text=explicit_error,
            method="rule",
            raw_result={"matched_pattern_text": explicit_error},
        )

    rule_groups: list[tuple[str, tuple[str, ...], str, float]] = [
        (
            "answer_seeking",
            (
                r"(\u544a\u8bc9|\u7ed9|give|tell).{0,12}(\u7b2c\s*[0-9\u4e00-\u5341]+\s*\u9898).{0,12}(\u7b54\u6848|\u89e3\u6cd5|answer|solution)",
                r"(\u7b2c\s*[0-9\u4e00-\u5341]+\s*\u9898).{0,12}(\u7b54\u6848|\u89e3\u6cd5|answer|solution)",
                r"(\u544a\u8bc9|\u7ed9|\u76f4\u63a5\u7ed9).{0,16}(\u7b54\u6848|\u6807\u51c6\u7b54\u6848|\u89e3\u6cd5|\u7ed3\u679c)",
                r"(直接|只|就)?(给|告诉|写|生成|完成).{0,12}(答案|代码|结果|解法)",
                r"(不用|不要).{0,8}(解释|过程).{0,12}(答案|代码|结果)",
                r"(能交|可提交|直接提交|帮我写完|替我完成)",
                r"\b(do it for me|full answer|complete code|submission-ready)\b",
                r"\b(write|edit|change|replace|convert|implement|complete)\b.{0,35}\b(code|function|method|query|version)\b",
                r"\b(what is|give me|provide|tell me)\b.{0,20}\b(answer|output|solution|code)\b",
                r"choice\s*1\s+of\s+\d+",
                r"^\s*(please\s+)?(use|make|write|implement|change|replace|convert|describe|summarize)\b",
                r"^\s*(shorter|make this concise|dataframe to json|needs to be \d+)\s*$",
                r"(#\s*)?todo\b",
            ),
            "提问要求 AI 直接产生答案、代码、输出或可提交内容。",
            0.86,
        ),
        (
            "reflection_verification",
            (
                r"(对不对|是否正确|正确吗|验证|检查我的|我的理解)",
                r"\b(is this|is that|does this|do these).{0,24}\b(correct|right|look|work|mean)\b",
                r"\b(check|verify|review).{0,20}\b(my|this)\b",
                r"\bshould i (?:get|expect|replace)\b",
                r"\bwhat did you change\b",
                r"\b(does|do|is|are).{0,35}\b(my|this|these|that|it)\b.{0,20}\b(correct|right|expected|work|check out)\b",
                r"\bwhat about this\b",
                r"\bseem(?:s)? (?:right|correct|to work)\b",
                r"\bmeet (?:these|the) specifications\b",
                r"\b(you didn'?t|you did not|you should)\b",
                r"\b(isn'?t|shouldn'?t|couldn'?t|wouldn'?t)\b",
                r"\bi thought\b",
                r"\bwhy do you\b",
                r"\bwhy (?:is|are|must|should|would)\b",
                r"(反例|局限|质疑|是否可能错|为什么一定|另一种方案)",
            ),
            "学生提交、反思或质疑已有理解、结果、实现或结论。",
            0.79,
        ),
        (
            "debugging_help",
            (
                r"(报错|错误信息|运行不了|调试|哪里错|什么问题)",
                r"\b(traceback|exception|error|bug|warning|gibberish|wrong with)\b",
                r"\b(why|what).{0,18}\b(error|failing|not working|truncated)\b",
                r"\b(fix|debug).{0,25}\b(code|function|loop|model)\b",
                r"```[\s\S]{0,1200}```",
            ),
            "学生提供错误、代码或异常输出并请求定位实现问题。",
            0.82,
        ),
        (
            "task_clarification",
            (
                r"(题目|任务|作业|提交|要求|格式).{0,20}(什么|如何|几个|是否|需要)",
                r"\b(assignment|requirement|submit|readme|starter code|main\.py)\b",
                r"\bwhat (?:input|parameters?|files?)\b",
                r"\bwhat about for n\s*=",
                r"\buse [`'\"]?\d+[`'\"]? as (?:the |your )?random seed\b",
                r"\b(don'?t|do not) modify\b",
                r"\bwhat exactly is this saying\b",
                r"\bcould you give me an example\b",
            ),
            "学生在澄清任务约束、输入输出、提交方式或指定要求。",
            0.76,
        ),
        (
            "concept_understanding",
            (
                r"(不要|别).{0,10}(答案|完整代码).{0,30}(提示|思路|建议|引导)",
                r"(提示|思路|启发|下一步|一步一步|分步骤)",
                r"\b(hint|tips?|guidance|one step at a time)\b",
                r"\b(help|advise).{0,35}\b(how|fix|approach|start)\b",
                r"\bhow (?:can|do|should) i\b.{0,55}\b(change|reduce|improve|test|predict|fix|start)\b",
            ),
            "学生请求解释、方向、提示或分步骤帮助以理解问题。",
            0.8,
        ),
    ]

    for behavior, patterns, explanation, confidence in rule_groups:
        matched = _matches(normalized, patterns)
        if matched:
            return AnalysisResult(
                behavior_type=behavior,
                confidence=confidence,
                explanation=explanation,
                evidence_text=matched,
                method="rule",
                raw_result={"matched_pattern_text": matched},
            )
    return AnalysisResult(
        behavior_type="concept_understanding",
        confidence=0.62,
        explanation="未命中特定高风险规则，默认识别为概念理解型提问。",
        evidence_text=text[:120],
        method="rule",
        raw_result={"matched_pattern_text": None},
    )


def _load_fewshot_prompt() -> str:
    """Load few-shot prompt if available, otherwise return default prompt."""
    from pathlib import Path

    # Try to find the few-shot prompt relative to the project root
    candidates = [
        Path("prompts/behavior_fewshot_v1.json"),
        Path(__file__).resolve().parents[3] / "prompts" / "behavior_fewshot_v1.json",
    ]
    for path in candidates:
        if path.exists():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                return data["system_prompt"]
            except (json.JSONDecodeError, KeyError):
                pass

    # Fallback: default prompt
    return (
        "你是学生-AI学习行为分类器。只判断学生如何使用AI，不判断学生品格。"
        "behavior_type 只能从以下五个标签中选择："
        "concept_understanding、answer_seeking、debugging_help、"
        "task_clarification、reflection_verification。"
        "concept_understanding 表示请求概念解释、原理说明、提示、思路或分步引导；"
        "answer_seeking 表示索要完整答案、完整代码或可直接提交内容；"
        "debugging_help 表示携带代码、错误、异常输出或具体实现问题寻求调试；"
        "task_clarification 表示澄清题目要求、输入输出、约束或提交格式；"
        "reflection_verification 表示检查、反思、质疑或比较已有理解、结果或结论。"
        "若消息同时包含多个意图，选择学生希望AI执行的主要行动。"
        "请仅输出 JSON，不得输出五类以外的标签，格式为："
        '{"behavior_type":"五类标签之一","confidence":0到1,'
        '"explanation":"简短解释","evidence_text":"原文证据"}。'
    )


def classify_with_llm(text: str, recent_context: list[str]) -> AnalysisResult | None:
    settings = get_settings()
    if not settings.llm_api_key:
        return None

    client = OpenAI(
        api_key=settings.llm_api_key,
        base_url=settings.llm_base_url,
        timeout=settings.llm_timeout_seconds,
    )
    system_prompt = _load_fewshot_prompt()

    response = client.chat.completions.create(
        model=settings.llm_model,
        messages=[
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": f"最近上下文：{recent_context[-4:]}\n当前学生消息：{text}",
            },
        ],
        response_format={"type": "json_object"},
        temperature=0,
        extra_body={"thinking": {"type": "disabled"}},
    )
    raw = json.loads(response.choices[0].message.content or "{}")
    behavior_type = raw.get("behavior_type")
    if behavior_type not in BEHAVIOR_TYPES:
        raise ValueError(f"LLM returned unsupported behavior_type: {behavior_type!r}")
    return AnalysisResult(
        behavior_type=behavior_type,
        confidence=float(raw["confidence"]),
        explanation=raw["explanation"],
        evidence_text=raw["evidence_text"],
        method="llm",
        raw_result=raw,
        model_name=settings.llm_model,
    )


def classify_student_message(text: str, recent_context: list[str]) -> AnalysisResult:
    """Classify the student message using LLM first, then ML, then rules."""
    settings = get_settings()
    mode = settings.behavior_classifier_mode.lower().strip()
    if mode == "rule":
        return classify_with_rules(text)
    if mode in {"llm", "auto"}:
        try:
            llm_result = classify_with_llm(text, recent_context)
            if llm_result is not None:
                return llm_result
        except Exception:
            pass
    if mode in {"ml", "auto"} and settings.behavior_classifier_path:
        try:
            from .ml_behavior import classify_with_ml_model

            ml_result = classify_with_ml_model(
                text, recent_context, settings.behavior_classifier_path
            )
            if ml_result.confidence >= settings.behavior_classifier_min_confidence:
                return ml_result
        except Exception:
            pass
    return classify_with_rules(text)


def has_personal_attempt(text: str) -> bool:
    patterns = (
        r"```",
        r"traceback",
        r"(我的(代码|思路|输出|结果)|我写(了|的)?|我试(了|过)?|我尝试|我的理解|报错(信息|如下|是))",
        r"\b(def|class|for|while|if|import)\b",
        r"(attributeerror|typeerror|syntaxerror|exception)",
    )
    return any(re.search(pattern, text, flags=re.IGNORECASE) for pattern in patterns)
