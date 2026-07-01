"""Evaluate StudyChat's source-label mapping on rows where it has coverage."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from sklearn.metrics import accuracy_score, classification_report, confusion_matrix, f1_score


LABELS = [
    "answer_seeking",
    "concept_understanding",
    "debugging_help",
    "reflection_verification",
    "task_clarification",
]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("path", type=Path)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/final/studychat_mapping_test_evaluation.json"),
    )
    args = parser.parse_args()

    rows = [
        json.loads(line)
        for line in args.path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    covered = [row for row in rows if row.get("predicted_label") in LABELS]
    truth = [row["reviewed_label"] for row in covered]
    predicted = [row["predicted_label"] for row in covered]
    result = {
        "test_samples": len(rows),
        "covered_samples": len(covered),
        "missing_predictions": len(rows) - len(covered),
        "coverage": len(covered) / len(rows) if rows else 0,
        "accuracy_on_covered": accuracy_score(truth, predicted),
        "macro_f1_on_covered": f1_score(truth, predicted, labels=LABELS, average="macro"),
        "weighted_f1_on_covered": f1_score(
            truth, predicted, labels=LABELS, average="weighted"
        ),
        "labels": LABELS,
        "confusion_matrix": confusion_matrix(
            truth, predicted, labels=LABELS
        ).tolist(),
        "classification_report": classification_report(
            truth,
            predicted,
            labels=LABELS,
            output_dict=True,
            zero_division=0,
        ),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
