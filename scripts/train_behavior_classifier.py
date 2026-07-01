"""Train and evaluate a supervised StudyChat behavior classifier."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import joblib
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix, f1_score
from sklearn.pipeline import FeatureUnion, Pipeline


LABELS = [
    "answer_seeking",
    "concept_understanding",
    "debugging_help",
    "reflection_verification",
    "task_clarification",
]


def read_jsonl(path: Path) -> list[dict]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def build_text(row: dict, include_context: bool) -> str:
    text = str(row.get("text", ""))
    if not include_context:
        return text
    context = row.get("recent_context") or []
    if not context:
        return text
    context_text = "\n".join(str(item).strip() for item in context if str(item).strip())
    return f"Recent context:\n{context_text}\n\nCurrent student message:\n{text}"


def load_xy(path: Path, include_context: bool) -> tuple[list[str], list[str], list[dict]]:
    rows = read_jsonl(path)
    kept = [row for row in rows if row.get("reviewed_label") in LABELS]
    return (
        [build_text(row, include_context) for row in kept],
        [row["reviewed_label"] for row in kept],
        kept,
    )


def make_pipeline(
    max_features: int,
    c: float,
    class_weight: str | None,
    word_ngram_max: int,
    char_ngram_max: int,
    min_df: int,
) -> Pipeline:
    features = FeatureUnion(
        [
            (
                "word",
                TfidfVectorizer(
                    analyzer="word",
                    ngram_range=(1, word_ngram_max),
                    min_df=min_df,
                    max_features=max_features,
                    sublinear_tf=True,
                    strip_accents="unicode",
                ),
            ),
            (
                "char",
                TfidfVectorizer(
                    analyzer="char_wb",
                    ngram_range=(3, char_ngram_max),
                    min_df=min_df,
                    max_features=max_features // 2,
                    sublinear_tf=True,
                ),
            ),
        ]
    )
    classifier = LogisticRegression(
        C=c,
        class_weight=class_weight,
        max_iter=2000,
        random_state=42,
    )
    return Pipeline([("features", features), ("classifier", classifier)])


def evaluate(name: str, model: Pipeline, x: list[str], y: list[str]) -> dict:
    predicted = model.predict(x)
    return {
        "split": name,
        "samples": len(y),
        "accuracy": accuracy_score(y, predicted),
        "macro_f1": f1_score(y, predicted, labels=LABELS, average="macro"),
        "weighted_f1": f1_score(y, predicted, labels=LABELS, average="weighted"),
        "labels": LABELS,
        "confusion_matrix": confusion_matrix(y, predicted, labels=LABELS).tolist(),
        "classification_report": classification_report(
            y,
            predicted,
            labels=LABELS,
            output_dict=True,
            zero_division=0,
        ),
    }


def add_predictions(rows: list[dict], model: Pipeline, x: list[str]) -> list[dict]:
    predicted = model.predict(x)
    probabilities = model.predict_proba(x)
    classes = list(model.classes_)
    output = []
    for row, label, proba in zip(rows, predicted, probabilities, strict=False):
        scores = {str(cls): float(score) for cls, score in zip(classes, proba, strict=False)}
        output.append(
            {
                **row,
                "predicted_label": str(label),
                "prediction_method": "ml_tfidf_logreg",
                "prediction_confidence": scores.get(str(label), 0.0),
                "prediction_probabilities": scores,
            }
        )
    return output


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--train",
        type=Path,
        default=Path("data/final/studychat_behavior_train.jsonl"),
    )
    parser.add_argument(
        "--dev",
        type=Path,
        default=Path("data/final/studychat_behavior_dev.jsonl"),
    )
    parser.add_argument("--test", type=Path)
    parser.add_argument(
        "--model-output",
        type=Path,
        default=Path("data/models/studychat_behavior_tfidf_logreg.joblib"),
    )
    parser.add_argument(
        "--metrics-output",
        type=Path,
        default=Path("data/processed/studychat_ml_classifier_metrics.json"),
    )
    parser.add_argument("--predictions-output", type=Path)
    parser.add_argument("--max-features", type=int, default=100000)
    parser.add_argument("--c", type=float, default=4.0)
    parser.add_argument("--class-weight", choices=["balanced", "none"], default="balanced")
    parser.add_argument("--word-ngram-max", type=int, default=2)
    parser.add_argument("--char-ngram-max", type=int, default=5)
    parser.add_argument("--min-df", type=int, default=2)
    parser.add_argument("--include-context", action="store_true")
    args = parser.parse_args()

    x_train, y_train, train_rows = load_xy(args.train, args.include_context)
    x_dev, y_dev, dev_rows = load_xy(args.dev, args.include_context)

    class_weight = None if args.class_weight == "none" else args.class_weight
    model = make_pipeline(
        args.max_features,
        args.c,
        class_weight,
        args.word_ngram_max,
        args.char_ngram_max,
        args.min_df,
    )
    model.fit(x_train, y_train)

    metrics = {
        "model": "tfidf_word_char_logistic_regression",
        "train_path": str(args.train),
        "dev_path": str(args.dev),
        "test_path": str(args.test) if args.test else None,
        "train_samples": len(train_rows),
        "include_context": args.include_context,
        "evaluations": {
            "dev": evaluate("dev", model, x_dev, y_dev),
        },
    }

    test_rows: list[dict] = []
    x_test: list[str] = []
    if args.test:
        x_test, y_test, test_rows = load_xy(args.test, args.include_context)
        metrics["evaluations"]["test"] = evaluate("test", model, x_test, y_test)

    artifact = {
        "pipeline": model,
        "labels": LABELS,
        "model_name": "studychat-tfidf-logreg",
        "metadata": {
            "train_path": str(args.train),
            "dev_path": str(args.dev),
            "test_path": str(args.test) if args.test else None,
            "train_samples": len(train_rows),
            "include_context": args.include_context,
            "max_features": args.max_features,
            "c": args.c,
            "class_weight": args.class_weight,
            "word_ngram_max": args.word_ngram_max,
            "char_ngram_max": args.char_ngram_max,
            "min_df": args.min_df,
        },
    }

    args.model_output.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(artifact, args.model_output)

    args.metrics_output.parent.mkdir(parents=True, exist_ok=True)
    args.metrics_output.write_text(
        json.dumps(metrics, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    if args.predictions_output:
        rows = test_rows or dev_rows
        x_values = x_test or x_dev
        write_jsonl(args.predictions_output, add_predictions(rows, model, x_values))

    print(
        json.dumps(
            {
                "model_output": str(args.model_output),
                "metrics_output": str(args.metrics_output),
                "dev_accuracy": metrics["evaluations"]["dev"]["accuracy"],
                "dev_macro_f1": metrics["evaluations"]["dev"]["macro_f1"],
                "test_accuracy": metrics["evaluations"].get("test", {}).get("accuracy"),
                "test_macro_f1": metrics["evaluations"].get("test", {}).get("macro_f1"),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
