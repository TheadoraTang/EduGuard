"""Validate and summarize EduGuard's final human-labeled datasets."""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path


BEHAVIOR_LABELS = (
    "concept_understanding",
    "answer_seeking",
    "debugging_help",
    "task_clarification",
    "reflection_verification",
)
SCAFFOLD_LABELS = (
    "probing_question",
    "error_focus",
    "feedback_prompt",
    "generic_prompt",
    "direct_explanation",
)


def read_jsonl(path: Path) -> list[dict]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def validate_unique(rows: list[dict], name: str) -> None:
    ids = [row["sample_id"] for row in rows]
    if len(ids) != len(set(ids)):
        raise ValueError(f"{name} contains duplicate sample_id values")


def validate_group_splits(rows: list[dict], group_field: str, name: str) -> None:
    group_splits: dict[str, set[str]] = defaultdict(set)
    for row in rows:
        group_splits[str(row[group_field])].add(row["split"])
    leaking = [group for group, splits in group_splits.items() if len(splits) > 1]
    if leaking:
        raise ValueError(f"{name} split leakage for {group_field}: {leaking[:5]}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", type=Path, default=Path("data/final"))
    parser.add_argument(
        "--output", type=Path, default=Path("data/final/dataset_statistics.json")
    )
    args = parser.parse_args()

    study = read_jsonl(args.data_dir / "studychat_behavior_labeled.jsonl")
    study_excluded = read_jsonl(args.data_dir / "studychat_behavior_excluded.jsonl")
    math = read_jsonl(args.data_dir / "mathdial_scaffold_labeled.jsonl")
    math_excluded = read_jsonl(args.data_dir / "mathdial_scaffold_excluded.jsonl")

    validate_unique(study, "StudyChat labeled")
    validate_unique(study_excluded, "StudyChat excluded")
    validate_unique(math, "MathDial labeled")
    validate_unique(math_excluded, "MathDial excluded")
    study_overlap = {row["sample_id"] for row in study} & {
        row["sample_id"] for row in study_excluded
    }
    math_overlap = {row["sample_id"] for row in math} & {
        row["sample_id"] for row in math_excluded
    }
    if study_overlap:
        raise ValueError(f"StudyChat labeled/excluded overlap: {list(study_overlap)[:5]}")
    if math_overlap:
        raise ValueError(f"MathDial labeled/excluded overlap: {list(math_overlap)[:5]}")
    validate_group_splits(study, "chat_id_hash", "StudyChat")
    validate_group_splits(math, "problem_id_hash", "MathDial")

    invalid_behaviors = sorted(
        {row["reviewed_label"] for row in study} - set(BEHAVIOR_LABELS)
    )
    invalid_strategies = sorted(
        {row["reviewed_strategy"] for row in math} - set(SCAFFOLD_LABELS)
    )
    if invalid_behaviors:
        raise ValueError(f"Invalid StudyChat labels: {invalid_behaviors}")
    if invalid_strategies:
        raise ValueError(f"Invalid MathDial strategies: {invalid_strategies}")

    study_initial_blank = [row for row in study if not row.get("predicted_label")]
    disclosure = Counter(row["reviewed_answer_disclosure"] for row in math)
    score_fields = (
        "pedagogical_relevance_score",
        "promotes_thinking_score",
        "clarity_score",
    )
    result = {
        "studychat": {
            "source_samples": len(study) + len(study_excluded),
            "labeled_samples": len(study),
            "excluded_samples": len(study_excluded),
            "retention_rate": len(study) / (len(study) + len(study_excluded)),
            "label_distribution": dict(
                sorted(Counter(row["reviewed_label"] for row in study).items())
            ),
            "split_distribution": dict(
                sorted(Counter(row["split"] for row in study).items())
            ),
            "retained_samples_with_blank_initial_prediction": len(study_initial_blank),
            "excluded_with_review_notes": sum(
                bool(str(row.get("review_notes", "")).strip())
                for row in study_excluded
            ),
            "unique_conversations": len({row["chat_id_hash"] for row in study}),
            "unique_students": len({row["user_id_hash"] for row in study}),
            "split_leakage_by_conversation": 0,
        },
        "mathdial": {
            "source_samples": len(math) + len(math_excluded),
            "labeled_samples": len(math),
            "excluded_samples": len(math_excluded),
            "strategy_distribution": dict(
                sorted(Counter(row["reviewed_strategy"] for row in math).items())
            ),
            "split_distribution": dict(
                sorted(Counter(row["split"] for row in math).items())
            ),
            "answer_disclosure_distribution": dict(sorted(disclosure.items())),
            "answer_disclosure_rate": disclosure["yes"] / len(math) if math else 0,
            "mean_scores": {
                field: sum(float(row[field]) for row in math) / len(math)
                for field in score_fields
            },
            "unique_problems": len({row["problem_id_hash"] for row in math}),
            "split_leakage_by_problem": 0,
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
