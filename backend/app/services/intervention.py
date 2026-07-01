from .analysis import AnalysisResult


def build_intervention(analysis: AnalysisResult, risk_level: str) -> tuple[int, str, str]:
    if risk_level == "high":
        return (
            3,
            "guided_questions",
            "让我帮你一步步理清这个问题。我们先分解一下：问题的关键是理解输入和输出，"
            "以及选择合适的方法。你可以先试着描述你目前卡在哪一步，"
            "我会根据你的情况给具体的提示和下一步方向。",
        )
    if analysis.behavior_type == "debugging_help":
        return (
            2,
            "debugging_scaffold",
            "我先帮你分析这个错误。从你提供的信息来看，重点关注错误的类型和位置。"
            "通常这类问题的排查路径是：确认错误发生的具体行，检查相关的变量值，"
            "然后给出最小修改方案。",
        )
    if analysis.behavior_type == "reflection_verification":
        return (
            1,
            "verification_prompt",
            "可以。请先说明你判断它正确的一个理由，我再从边界条件、逻辑和结果三个方面帮你核对。",
        )
    if analysis.behavior_type == "task_clarification":
        return (
            1,
            "requirement_check",
            "好的，我来帮你理清任务要求。根据题目描述，核心要求包括输入格式、输出格式和约束条件。"
            "我先帮你梳理一下你需要注意的关键点。",
        )
    return (
        1,
        "concept_prompt",
        "这个问题涉及到几个关键概念。我先用简洁的方式解释核心要点，然后给你一个小例子帮助理解。"
        "理解之后如果有不清楚的地方可以继续追问。",
    )
