"""Evaluate behavior predictions from a reviewed JSONL file."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from sklearn.metrics import accuracy_score, classification_report, confusion_matrix, f1_score


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("path", type=Path)
    parser.add_argument("--output", type=Path, default=Path("data/processed/evaluation.json"))
    args = parser.parse_args()

    rows = [json.loads(line) for line in args.path.read_text(encoding="utf-8").splitlines() if line]
    truth = [row["reviewed_label"] for row in rows]
    predicted = [row["predicted_label"] for row in rows]
    labels = sorted(set(truth) | set(predicted))
    result = {
        "samples": len(rows),
        "accuracy": accuracy_score(truth, predicted),
        "macro_f1": f1_score(truth, predicted, average="macro"),
        "weighted_f1": f1_score(truth, predicted, average="weighted"),
        "labels": labels,
        "confusion_matrix": confusion_matrix(truth, predicted, labels=labels).tolist(),
        "classification_report": classification_report(
            truth, predicted, labels=labels, output_dict=True, zero_division=0
        ),
        "typical_errors": [
            row for row in rows if row["reviewed_label"] != row["predicted_label"]
        ][:20],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {args.output}")


if __name__ == "__main__":
    main()
