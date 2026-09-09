import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

from prepare_bench2026_student_splits import (  # noqa: E402
    SPLITS,
    allocate_group_counts,
    build_manifest,
    parse_ratios,
    split_rows_by_student,
    validate_split_integrity,
    write_jsonl,
)


def make_rows() -> list[dict]:
    labels = [
        "answer_seeking",
        "concept_understanding",
        "debugging_help",
        "task_clarification",
        "reflection_verification",
    ]
    rows = []
    for user_index in range(20):
        for row_index in range(2 + user_index % 3):
            rows.append(
                {
                    "sample_id": f"sample-{user_index}-{row_index}",
                    "chat_id_hash": f"chat-{user_index}-{row_index // 2}",
                    "user_id_hash": f"user-{user_index}",
                    "reviewed_label": labels[(user_index + row_index) % len(labels)],
                    "split": "legacy",
                    "semester": "f24" if user_index % 2 == 0 else "s25",
                    "topic": f"a{1 + user_index % 4}",
                }
            )
    return rows


def test_student_split_is_deterministic_and_has_zero_leakage():
    rows = make_rows()
    ratios = parse_ratios([0.70, 0.15, 0.15])
    first, first_assignment, first_score = split_rows_by_student(
        rows, ratios, seed=20260907, search_iterations=100
    )
    second, second_assignment, second_score = split_rows_by_student(
        rows, ratios, seed=20260907, search_iterations=100
    )

    assert first_assignment == second_assignment
    assert first_score == second_score
    assert {
        split: [row["sample_id"] for row in first[split]] for split in SPLITS
    } == {
        split: [row["sample_id"] for row in second[split]] for split in SPLITS
    }
    assert validate_split_integrity(first, expected_samples=len(rows)) == {
        "samples": {"train_dev": 0, "train_test": 0, "dev_test": 0},
        "students": {"train_dev": 0, "train_test": 0, "dev_test": 0},
        "conversations": {"train_dev": 0, "train_test": 0, "dev_test": 0},
    }
    assert all(row["legacy_split"] == "legacy" for split in SPLITS for row in first[split])


def test_student_count_uses_largest_remainder_allocation():
    ratios = parse_ratios([0.70, 0.15, 0.15])
    assert allocate_group_counts(202, ratios) == {
        "train": 142,
        "dev": 30,
        "test": 30,
    }


def test_manifest_records_hashes_and_distributions(tmp_path):
    input_path = tmp_path / "input.jsonl"
    rows = make_rows()
    write_jsonl(input_path, rows)
    ratios = parse_ratios([0.70, 0.15, 0.15])
    split_rows, _, score = split_rows_by_student(
        rows, ratios, seed=20260907, search_iterations=50
    )
    output_paths = {
        split: tmp_path / f"studychat_student_{split}.jsonl" for split in SPLITS
    }
    for split in SPLITS:
        write_jsonl(output_paths[split], split_rows[split])

    manifest = build_manifest(
        input_path,
        output_paths,
        split_rows,
        ratios,
        seed=20260907,
        search_iterations=50,
        score=score,
    )

    assert manifest["input"]["samples"] == len(rows)
    assert manifest["input"]["students"] == 20
    assert manifest["method"]["group_field"] == "user_id_hash"
    assert len(manifest["input"]["sha256"]) == 64
    assert all(len(manifest["splits"][split]["sha256"]) == 64 for split in SPLITS)
    assert json.loads(json.dumps(manifest))["overlap_checks"]["students"] == {
        "train_dev": 0,
        "train_test": 0,
        "dev_test": 0,
    }
