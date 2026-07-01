from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import joblib

from .analysis import AnalysisResult, BEHAVIOR_TYPES


def _build_input(text: str, recent_context: list[str]) -> str:
    context = "\n".join(item.strip() for item in recent_context[-4:] if item.strip())
    if not context:
        return text
    return f"Recent context:\n{context}\n\nCurrent student message:\n{text}"


@lru_cache(maxsize=4)
def load_behavior_classifier(model_path: str) -> dict[str, Any]:
    path = Path(model_path)
    if not path.is_absolute() and not path.exists():
        path = Path(__file__).resolve().parents[3] / path
    artifact = joblib.load(path)
    if not isinstance(artifact, dict) or "pipeline" not in artifact:
        raise ValueError(f"Invalid behavior classifier artifact: {model_path}")
    return artifact


def classify_with_ml_model(
    text: str,
    recent_context: list[str],
    model_path: str,
) -> AnalysisResult:
    artifact = load_behavior_classifier(model_path)
    pipeline = artifact["pipeline"]
    model_name = str(artifact.get("model_name", Path(model_path).name))
    labels = list(getattr(pipeline, "classes_", artifact.get("labels", BEHAVIOR_TYPES)))
    features = [_build_input(text, recent_context)]

    predicted = str(pipeline.predict(features)[0])
    if predicted not in BEHAVIOR_TYPES:
        raise ValueError(f"ML classifier returned unsupported behavior_type: {predicted!r}")

    confidence = 0.0
    probabilities: dict[str, float] = {}
    if hasattr(pipeline, "predict_proba"):
        proba = pipeline.predict_proba(features)[0]
        probabilities = {
            str(label): float(score) for label, score in zip(labels, proba, strict=False)
        }
        confidence = probabilities.get(predicted, 0.0)

    return AnalysisResult(
        behavior_type=predicted,
        confidence=confidence,
        explanation="Predicted by a supervised StudyChat behavior classifier.",
        evidence_text=text[:240],
        method="ml",
        raw_result={
            "model_path": model_path,
            "probabilities": probabilities,
            "metadata": artifact.get("metadata", {}),
        },
        model_name=model_name,
    )
