"""Create deterministic, student-held-out StudyChat splits for BENCH 2026.

The splitter treats every ``user_id_hash`` as an indivisible group. It searches
deterministically, using one pre-declared seed, for a 70/15/15 user assignment
whose sample and label distributions are close to the requested ratios. The
existing conversation-level ``split`` value is retained as ``legacy_split``.

Example:
    python scripts/prepare_bench2026_student_splits.py \
        data/final/studychat_behavior_labeled.jsonl
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable


SPLITS = ("train", "dev", "test")
DEFAULT_RATIOS = (0.70, 0.15, 0.15)
DEFAULT_SEED = 20260907
DEFAULT_SEARCH_ITERATIONS = 5000
SPLIT_VERSION = "bench2026-student-v1"
REQUIRED_FIELDS = (
    "sample_id",
    "chat_id_hash",
    "user_id_hash",
    "reviewed_label",
)


def read_jsonl(path: Path) -> list[dict]:
    rows: list[dict] = []
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSON on line {line_number}: {exc}") from exc
            if not isinstance(row, dict):
                raise ValueError(f"Line {line_number} is not a JSON object")
            rows.append(row)
    return rows


def write_jsonl(path: Path, rows: Iterable[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_rows(rows: list[dict]) -> None:
    if not rows:
        raise ValueError("Input dataset is empty")

    sample_ids: set[str] = set()
    chat_owners: dict[str, str] = {}
    for index, row in enumerate(rows, start=1):
        missing = [field for field in REQUIRED_FIELDS if not str(row.get(field, "")).strip()]
        if missing:
            raise ValueError(f"Row {index} is missing required fields: {missing}")

        sample_id = str(row["sample_id"])
        if sample_id in sample_ids:
            raise ValueError(f"Duplicate sample_id: {sample_id}")
        sample_ids.add(sample_id)

        chat_id = str(row["chat_id_hash"])
        user_id = str(row["user_id_hash"])
        previous_owner = chat_owners.setdefault(chat_id, user_id)
        if previous_owner != user_id:
            raise ValueError(
                f"Conversation {chat_id} belongs to multiple users: "
                f"{previous_owner}, {user_id}"
            )


def allocate_group_counts(total: int, ratios: dict[str, float]) -> dict[str, int]:
    """Allocate an integer number of users with the largest-remainder method."""
    raw = {split: total * ratios[split] for split in SPLITS}
    counts = {split: math.floor(raw[split]) for split in SPLITS}
    remaining = total - sum(counts.values())
    ranked = sorted(
        SPLITS,
        key=lambda split: (-(raw[split] - counts[split]), SPLITS.index(split)),
    )
    for split in ranked[:remaining]:
        counts[split] += 1
    return counts


def assignment_score(
    user_to_split: dict[str, str],
    rows_by_user: dict[str, list[dict]],
    ratios: dict[str, float],
) -> float:
    """Measure deviation from requested sample and per-label split ratios."""
    sample_counts = Counter()
    label_counts: dict[str, Counter] = defaultdict(Counter)
    total_labels = Counter()
    for user_id, user_rows in rows_by_user.items():
        split = user_to_split[user_id]
        sample_counts[split] += len(user_rows)
        for row in user_rows:
            label = str(row["reviewed_label"])
            label_counts[label][split] += 1
            total_labels[label] += 1

    total_samples = sum(sample_counts.values())
    sample_error = sum(
        abs(sample_counts[split] / total_samples - ratios[split])
        for split in SPLITS
    )

    label_error = 0.0
    for label, total in total_labels.items():
        label_error += sum(
            abs(label_counts[label][split] / total - ratios[split])
            for split in SPLITS
        )
    label_error /= max(len(total_labels), 1)
    return sample_error + label_error


def split_rows_by_student(
    rows: list[dict],
    ratios: dict[str, float],
    seed: int,
    search_iterations: int,
) -> tuple[dict[str, list[dict]], dict[str, str], float]:
    """Return split rows, user assignments, and the selected balance score."""
    validate_rows(rows)
    if search_iterations < 1:
        raise ValueError("search_iterations must be at least 1")

    rows_by_user: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        rows_by_user[str(row["user_id_hash"])].append(row)

    users = sorted(rows_by_user)
    user_targets = allocate_group_counts(len(users), ratios)
    rng = random.Random(seed)
    best_assignment: dict[str, str] | None = None
    best_score = math.inf

    for _ in range(search_iterations):
        candidate_users = users.copy()
        rng.shuffle(candidate_users)
        assignment: dict[str, str] = {}
        cursor = 0
        for split in SPLITS:
            next_cursor = cursor + user_targets[split]
            for user_id in candidate_users[cursor:next_cursor]:
                assignment[user_id] = split
            cursor = next_cursor

        score = assignment_score(assignment, rows_by_user, ratios)
        if score < best_score:
            best_assignment = assignment
            best_score = score

    if best_assignment is None:
        raise RuntimeError("Unable to create a student split assignment")

    split_rows: dict[str, list[dict]] = {split: [] for split in SPLITS}
    for row in rows:
        split = best_assignment[str(row["user_id_hash"])]
        output_row = dict(row)
        if "split" in output_row:
            output_row["legacy_split"] = output_row["split"]
        output_row["split"] = split
        output_row["split_version"] = SPLIT_VERSION
        split_rows[split].append(output_row)

    for split in SPLITS:
        split_rows[split].sort(key=lambda row: str(row["sample_id"]))

    validate_split_integrity(split_rows, expected_samples=len(rows))
    return split_rows, best_assignment, best_score


def pairwise_overlap(values: dict[str, set[str]]) -> dict[str, int]:
    result: dict[str, int] = {}
    for left_index, left in enumerate(SPLITS):
        for right in SPLITS[left_index + 1 :]:
            result[f"{left}_{right}"] = len(values[left] & values[right])
    return result


def validate_split_integrity(
    split_rows: dict[str, list[dict]], expected_samples: int | None = None
) -> dict[str, dict[str, int]]:
    sample_sets = {
        split: {str(row["sample_id"]) for row in split_rows[split]} for split in SPLITS
    }
    user_sets = {
        split: {str(row["user_id_hash"]) for row in split_rows[split]} for split in SPLITS
    }
    chat_sets = {
        split: {str(row["chat_id_hash"]) for row in split_rows[split]} for split in SPLITS
    }

    overlaps = {
        "samples": pairwise_overlap(sample_sets),
        "students": pairwise_overlap(user_sets),
        "conversations": pairwise_overlap(chat_sets),
    }
    leaking = {
        kind: pairs for kind, pairs in overlaps.items() if any(pairs.values())
    }
    if leaking:
        raise ValueError(f"Cross-split leakage detected: {leaking}")

    sample_count = sum(len(rows) for rows in split_rows.values())
    unique_sample_count = len(set().union(*sample_sets.values()))
    if sample_count != unique_sample_count:
        raise ValueError("Duplicate sample IDs found across or within split outputs")
    if expected_samples is not None and sample_count != expected_samples:
        raise ValueError(
            f"Split outputs contain {sample_count} samples; expected {expected_samples}"
        )
    return overlaps


def distribution(rows: list[dict], field: str) -> dict[str, int]:
    return dict(sorted(Counter(str(row.get(field, "unknown")) for row in rows).items()))


def split_summary(rows: list[dict]) -> dict:
    return {
        "samples": len(rows),
        "students": len({str(row["user_id_hash"]) for row in rows}),
        "conversations": len({str(row["chat_id_hash"]) for row in rows}),
        "labels": distribution(rows, "reviewed_label"),
        "semesters": distribution(rows, "semester"),
        "topics": distribution(rows, "topic"),
    }


def build_manifest(
    input_path: Path,
    output_paths: dict[str, Path],
    split_rows: dict[str, list[dict]],
    ratios: dict[str, float],
    seed: int,
    search_iterations: int,
    score: float,
) -> dict:
    overlaps = validate_split_integrity(
        split_rows, expected_samples=sum(len(rows) for rows in split_rows.values())
    )
    all_rows = [row for split in SPLITS for row in split_rows[split]]
    return {
        "schema_version": "1.0.0",
        "split_version": SPLIT_VERSION,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "input": {
            "path": input_path.as_posix(),
            "sha256": sha256(input_path),
            "samples": len(all_rows),
            "students": len({str(row["user_id_hash"]) for row in all_rows}),
            "conversations": len({str(row["chat_id_hash"]) for row in all_rows}),
            "labels": distribution(all_rows, "reviewed_label"),
        },
        "method": {
            "group_field": "user_id_hash",
            "ratios": ratios,
            "seed": seed,
            "search_iterations": search_iterations,
            "selection_objective": (
                "minimize absolute deviation from requested sample and per-label "
                "split ratios while keeping exact student-count quotas"
            ),
            "balance_score": score,
            "stratification_labels": "silver reviewed_label",
        },
        "splits": {
            split: {
                **split_summary(split_rows[split]),
                "path": output_paths[split].as_posix(),
                "sha256": sha256(output_paths[split]),
            }
            for split in SPLITS
        },
        "overlap_checks": overlaps,
        "test_use_policy": (
            "Do not use the test split for prompt design, threshold tuning, model "
            "selection, example selection, or exploratory error analysis."
        ),
    }


def ensure_writable_targets(paths: Iterable[Path], force: bool) -> None:
    existing = [path for path in paths if path.exists()]
    if existing and not force:
        joined = ", ".join(str(path) for path in existing)
        raise FileExistsError(
            f"Refusing to overwrite existing frozen artifacts: {joined}. "
            "Use --force only before the split has been frozen."
        )


def parse_ratios(values: list[float]) -> dict[str, float]:
    if len(values) != len(SPLITS):
        raise ValueError(f"Expected {len(SPLITS)} ratios")
    if any(value <= 0 for value in values):
        raise ValueError("All split ratios must be positive")
    if not math.isclose(sum(values), 1.0, rel_tol=0.0, abs_tol=1e-9):
        raise ValueError("Split ratios must sum to 1.0")
    return dict(zip(SPLITS, values, strict=True))


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Create deterministic student-held-out StudyChat splits."
    )
    parser.add_argument(
        "input",
        type=Path,
        nargs="?",
        default=Path("data/final/studychat_behavior_labeled.jsonl"),
    )
    parser.add_argument(
        "--output-dir", type=Path, default=Path("data/bench2026/splits")
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path(
            "data/bench2026/manifests/studychat_student_split_manifest.json"
        ),
    )
    parser.add_argument(
        "--ratios",
        type=float,
        nargs=3,
        metavar=("TRAIN", "DEV", "TEST"),
        default=list(DEFAULT_RATIOS),
    )
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument(
        "--search-iterations", type=int, default=DEFAULT_SEARCH_ITERATIONS
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite outputs only if the split has not yet been frozen.",
    )
    args = parser.parse_args()

    if not args.input.exists():
        raise SystemExit(f"Input dataset not found: {args.input}")

    try:
        ratios = parse_ratios(args.ratios)
        rows = read_jsonl(args.input)
        output_paths = {
            split: args.output_dir / f"studychat_student_{split}.jsonl"
            for split in SPLITS
        }
        ensure_writable_targets([*output_paths.values(), args.manifest], args.force)
        split_rows, _, score = split_rows_by_student(
            rows, ratios, args.seed, args.search_iterations
        )
        for split in SPLITS:
            write_jsonl(output_paths[split], split_rows[split])

        manifest = build_manifest(
            args.input,
            output_paths,
            split_rows,
            ratios,
            args.seed,
            args.search_iterations,
            score,
        )
        args.manifest.parent.mkdir(parents=True, exist_ok=True)
        args.manifest.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    except (FileExistsError, ValueError) as exc:
        raise SystemExit(str(exc)) from exc

    print(
        json.dumps(
            {
                "manifest": str(args.manifest),
                "split_version": SPLIT_VERSION,
                "seed": args.seed,
                "balance_score": score,
                "splits": {
                    split: split_summary(split_rows[split]) for split in SPLITS
                },
                "overlap_checks": manifest["overlap_checks"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
