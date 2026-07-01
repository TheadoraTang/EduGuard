"""Evaluate a human-reviewed MathDial scaffold JSONL."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from sklearn.metrics import accuracy_score, classification_report, f1_score


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("path", type=Path)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/processed/mathdial_scaffold_evaluation.json"),
    )
    args = parser.parse_args()

    rows = [
        json.loads(line)
        for line in args.path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    reviewed = [row for row in rows if row.get("reviewed_strategy")]
    result: dict = {
        "samples": len(rows),
        "reviewed_samples": len(reviewed),
        "predicted_strategy_distribution": dict(
            sorted(Counter(row["predicted_strategy"] for row in rows).items())
        ),
        "answer_disclosure_candidate_rate": (
            sum(bool(row["answer_disclosure_candidate"]) for row in rows) / len(rows)
            if rows
            else 0
        ),
    }
    if reviewed:
        truth = [row["reviewed_strategy"] for row in reviewed]
        predicted = [row["predicted_strategy"] for row in reviewed]
        labels = sorted(set(truth) | set(predicted))
        disclosure_rows = [
            row
            for row in reviewed
            if row.get("reviewed_answer_disclosure") in {"yes", "no"}
        ]
        result.update(
            {
                "strategy_accuracy": accuracy_score(truth, predicted),
                "strategy_macro_f1": f1_score(truth, predicted, average="macro"),
                "strategy_report": classification_report(
                    truth, predicted, labels=labels, output_dict=True, zero_division=0
                ),
                "reviewed_strategy_distribution": dict(
                    sorted(Counter(truth).items())
                ),
                "reviewed_answer_disclosure_rate": (
                    sum(
                        row["reviewed_answer_disclosure"] == "yes"
                        for row in disclosure_rows
                    )
                    / len(disclosure_rows)
                    if disclosure_rows
                    else 0
                ),
                "reviewed_answer_disclosure_samples": len(disclosure_rows),
            }
        )

    for field in (
        "pedagogical_relevance_score",
        "promotes_thinking_score",
        "clarity_score",
    ):
        scores = [float(row[field]) for row in reviewed if str(row.get(field, "")).strip()]
        if scores:
            result[f"mean_{field}"] = sum(scores) / len(scores)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {args.output}")


if __name__ == "__main__":
    main()
