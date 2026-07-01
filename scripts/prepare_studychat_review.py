"""Build a leakage-safe, stratified StudyChat review set.

The input format matches ``import_studychat.py``: one JSON object per turn.
The output is JSONL and keeps reviewed_label empty for human annotation.

Example:
    python scripts/prepare_studychat_review.py \
        data/raw/studychat/dialogues.jsonl \
        --output data/processed/studychat_review_300.jsonl \
        --size 300
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
from collections import defaultdict
from pathlib import Path

from import_studychat import MAPPING_VERSION, anonymize, label_value, map_label


def stable_bucket(value: str) -> str:
    """Assign a conversation to train/dev/test without cross-split leakage."""
    number = int(hashlib.sha256(value.encode()).hexdigest()[:8], 16) % 100
    if number < 70:
        return "train"
    if number < 85:
        return "dev"
    return "test"


def load_candidates(path: Path, include_unmapped: bool = False) -> list[dict]:
    candidates = []
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            record = json.loads(line)
            prompt = str(record.get("prompt", "")).strip()
            if not prompt:
                continue
            raw_label, justification = label_value(record)
            mapped_label, mapping_strength = map_label(raw_label)
            if not mapped_label and not include_unmapped:
                continue
            chat_id = str(record["chatId"])
            user_id = str(record.get("userId", "unknown"))
            candidates.append(
                {
                    "sample_id": f"studychat-{anonymize(chat_id)}-{line_number}",
                    "chat_id_hash": anonymize(chat_id),
                    "user_id_hash": anonymize(user_id),
                    "split": stable_bucket(chat_id),
                    "text": prompt,
                    "topic": record.get("topic"),
                    "semester": record.get("semester"),
                    "source_label": raw_label,
                    "source_justification": justification,
                    "predicted_label": mapped_label or "",
                    "mapping_strength": mapping_strength or "unmapped",
                    "mapping_version": MAPPING_VERSION,
                    "reviewed_label": "",
                    "review_notes": "",
                }
            )
    return candidates


def stratified_sample(candidates: list[dict], size: int, seed: int) -> list[dict]:
    rng = random.Random(seed)
    by_label: dict[str, list[dict]] = defaultdict(list)
    for item in candidates:
        by_label[item["predicted_label"]].append(item)
    for rows in by_label.values():
        rng.shuffle(rows)

    selected: list[dict] = []
    labels = sorted(by_label)
    if not labels:
        return selected

    base_quota = max(1, size // len(labels))
    for label in labels:
        selected.extend(by_label[label][:base_quota])

    selected_ids = {item["sample_id"] for item in selected}
    remainder = [
        item for item in candidates if item["sample_id"] not in selected_ids
    ]
    rng.shuffle(remainder)
    selected.extend(remainder[: max(0, size - len(selected))])
    rng.shuffle(selected)
    return selected[:size]


def validate_no_leakage(rows: list[dict]) -> None:
    chat_splits: dict[str, set[str]] = defaultdict(set)
    for row in rows:
        chat_splits[row["chat_id_hash"]].add(row["split"])
    leaking = [chat_id for chat_id, splits in chat_splits.items() if len(splits) > 1]
    if leaking:
        raise ValueError(f"Conversation leakage detected: {leaking[:5]}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("path", type=Path)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/processed/studychat_review_300.jsonl"),
    )
    parser.add_argument("--size", type=int, default=300)
    parser.add_argument("--seed", type=int, default=20260712)
    parser.add_argument(
        "--include-unmapped",
        action="store_true",
        help="Keep valid prompts whose source labels cannot be mapped automatically.",
    )
    args = parser.parse_args()

    candidates = load_candidates(args.path, include_unmapped=args.include_unmapped)
    rows = (
        candidates
        if args.size <= 0 or args.size >= len(candidates)
        else stratified_sample(candidates, args.size, args.seed)
    )
    validate_no_leakage(rows)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")

    distribution: dict[str, int] = defaultdict(int)
    for row in rows:
        distribution[row["predicted_label"]] += 1
    print(
        json.dumps(
            {
                "output": str(args.output),
                "samples": len(rows),
                "distribution": dict(sorted(distribution.items())),
                "seed": args.seed,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
