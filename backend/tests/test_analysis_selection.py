from types import SimpleNamespace

from app.services.analysis import AnalysisResult, classify_student_message


def settings(mode: str, path: str | None = None):
    return SimpleNamespace(
        behavior_classifier_mode=mode,
        behavior_classifier_path=path,
        behavior_classifier_min_confidence=0.5,
        llm_api_key=None,
    )


def result(method: str, behavior: str) -> AnalysisResult:
    return AnalysisResult(
        behavior_type=behavior,
        confidence=0.9,
        explanation=method,
        evidence_text=method,
        method=method,
        raw_result={},
    )


def test_llm_result_is_used_in_llm_mode_without_running_rules(monkeypatch):
    monkeypatch.setattr(
        "app.services.analysis.get_settings", lambda: settings("llm")
    )
    monkeypatch.setattr(
        "app.services.analysis.classify_with_llm",
        lambda text, context: result("llm", "reflection_verification"),
    )

    def fail_if_called(text):
        raise AssertionError("rules should not run when LLM succeeds")

    monkeypatch.setattr("app.services.analysis.classify_with_rules", fail_if_called)
    selected = classify_student_message("Is my approach correct?", [])
    assert selected.method == "llm"


def test_llm_result_is_used_before_ml_in_auto_mode(monkeypatch):
    monkeypatch.setattr(
        "app.services.analysis.get_settings", lambda: settings("auto", "model.joblib")
    )
    monkeypatch.setattr(
        "app.services.analysis.classify_with_llm",
        lambda text, context: result("llm", "answer_seeking"),
    )

    def fail_if_called(text, context, path):
        raise AssertionError("ML should not run when LLM succeeds")

    monkeypatch.setattr("app.services.ml_behavior.classify_with_ml_model", fail_if_called)
    selected = classify_student_message("What should I submit?", [])
    assert selected.method == "llm"


def test_ml_is_used_when_llm_fails_in_auto_mode(monkeypatch):
    monkeypatch.setattr(
        "app.services.analysis.get_settings", lambda: settings("auto", "model.joblib")
    )
    monkeypatch.setattr(
        "app.services.analysis.classify_with_llm",
        lambda text, context: (_ for _ in ()).throw(RuntimeError("llm failed")),
    )
    monkeypatch.setattr(
        "app.services.ml_behavior.classify_with_ml_model",
        lambda text, context, path: result("ml", "concept_understanding"),
    )

    selected = classify_student_message("What should I submit?", [])
    assert selected.method == "ml"


def test_rules_are_used_when_llm_and_ml_are_unavailable(monkeypatch):
    monkeypatch.setattr(
        "app.services.analysis.get_settings", lambda: settings("auto", "missing.joblib")
    )
    monkeypatch.setattr(
        "app.services.analysis.classify_with_llm",
        lambda text, context: None,
    )
    monkeypatch.setattr(
        "app.services.ml_behavior.classify_with_ml_model",
        lambda text, context, path: (_ for _ in ()).throw(RuntimeError("no model")),
    )
    monkeypatch.setattr(
        "app.services.analysis.classify_with_rules",
        lambda text: result("rule", "concept_understanding"),
    )
    selected = classify_student_message("What is recursion?", [])
    assert selected.method == "rule"


def test_rules_are_used_when_ml_and_llm_are_unavailable(monkeypatch):
    monkeypatch.setattr(
        "app.services.analysis.get_settings", lambda: settings("ml", "missing.joblib")
    )
    monkeypatch.setattr(
        "app.services.ml_behavior.classify_with_ml_model",
        lambda text, context, path: (_ for _ in ()).throw(RuntimeError("no model")),
    )
    monkeypatch.setattr(
        "app.services.analysis.classify_with_llm",
        lambda text, context: None,
    )
    monkeypatch.setattr(
        "app.services.analysis.classify_with_rules",
        lambda text: result("rule", "concept_understanding"),
    )
    selected = classify_student_message("What is recursion?", [])
    assert selected.method == "rule"
