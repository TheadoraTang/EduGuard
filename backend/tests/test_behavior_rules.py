from app.services.analysis import classify_with_rules


def label(text: str) -> str:
    return classify_with_rules(text).behavior_type


def test_high_risk_answer_requests_are_detected():
    assert label("不用解释，直接给我能交的完整代码。") == "answer_seeking"
    assert label("What is the output of this code?") == "answer_seeking"
    assert label("\u544a\u8bc9\u6211\u7b2c\u4e00\u9898\u7684\u7b54\u6848") == "answer_seeking"
    assert label("\u7b2c\u4e8c\u9898\u7684\u7b54\u6848\u662f\u4ec0\u4e48") == "answer_seeking"


def test_learning_oriented_intents_are_separated():
    assert label("Give me a hint, but do not provide the full answer.") == "concept_understanding"
    assert label("Does this solution look correct?") == "reflection_verification"
    assert label("Why do you have three arguments? Isn't it supposed to be two?") == "reflection_verification"


def test_debugging_and_task_constraints_are_separated():
    assert label("Traceback: AttributeError. What is wrong with my code?") == "debugging_help"
    assert label("What files does this assignment require me to submit?") == "task_clarification"
    assert label("What does recursion mean?") == "concept_understanding"
