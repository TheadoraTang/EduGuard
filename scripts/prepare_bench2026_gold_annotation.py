"""Prepare a blinded, deterministic Gold annotation pack for BENCH 2026.

The script samples only from the fixed student-held-out Test split. Silver
labels are used for stratification, but are written only to the private key and
never exposed to annotators. The two annotator payloads contain identical
examples in independently shuffled orders.

Example:
    python scripts/prepare_bench2026_gold_annotation.py --force
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable


DEFAULT_INPUT = Path("data/bench2026/splits/studychat_student_test.jsonl")
DEFAULT_OUTPUT_DIR = Path("data/bench2026/human_eval")
DEFAULT_MANIFEST = Path(
    "data/bench2026/manifests/studychat_gold_annotation_manifest.json"
)
DEFAULT_SEED = 20260908
ANNOTATION_VERSION = "bench2026-gold-v1"
LABEL_QUOTAS = {
    "answer_seeking": 125,
    "concept_understanding": 125,
    "debugging_help": 125,
    "reflection_verification": 100,
    "task_clarification": 125,
}
PILOT_PER_LABEL = 10
BLINDED_FIELDS = (
    "annotation_id",
    "phase",
    "order",
    "semester",
    "topic",
    "prior_student_messages",
    "student_message",
    "behavior_label",
    "attempt_evidence",
    "answer_restriction_needed",
    "appropriate_assistance_level",
    "recommended_strategy",
    "assessment_context",
    "ambiguity_flag",
    "review_notes",
)
FORBIDDEN_BLINDED_FIELDS = {
    "sample_id",
    "chat_id_hash",
    "user_id_hash",
    "reviewed_label",
    "predicted_label",
    "source_label",
    "source_justification",
    "mapping_strength",
    "mapping_version",
}


def read_jsonl(path: Path) -> list[dict]:
    rows: list[dict] = []
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            value = json.loads(line)
            if not isinstance(value, dict):
                raise ValueError(f"Line {line_number} is not a JSON object")
            rows.append(value)
    return rows


def write_jsonl(path: Path, rows: Iterable[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sequence_number(sample_id: str) -> int:
    match = re.search(r"-(\d+)$", sample_id)
    if not match:
        raise ValueError(f"sample_id does not end in a sequence number: {sample_id}")
    return int(match.group(1))


def validate_input(rows: list[dict]) -> None:
    required = {
        "sample_id",
        "chat_id_hash",
        "user_id_hash",
        "reviewed_label",
        "text",
        "split",
    }
    if not rows:
        raise ValueError("Input Test split is empty")
    seen: set[str] = set()
    for index, row in enumerate(rows, start=1):
        missing = sorted(field for field in required if not str(row.get(field, "")).strip())
        if missing:
            raise ValueError(f"Row {index} is missing required fields: {missing}")
        if row["split"] != "test":
            raise ValueError(f"Row {index} is not in the fixed Test split")
        sample_id = str(row["sample_id"])
        if sample_id in seen:
            raise ValueError(f"Duplicate sample_id: {sample_id}")
        seen.add(sample_id)


def attach_prior_student_messages(rows: list[dict], max_prior: int = 4) -> list[dict]:
    """Attach preceding student prompts from the same conversation.

    The source contains student prompts only, so this is deliberately named
    ``prior_student_messages`` rather than full dialogue context.
    """
    by_chat: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        by_chat[str(row["chat_id_hash"])].append(row)
    result: list[dict] = []
    for chat_rows in by_chat.values():
        chat_rows.sort(key=lambda item: sequence_number(str(item["sample_id"])))
        prior: list[str] = []
        for row in chat_rows:
            enriched = dict(row)
            enriched["prior_student_messages"] = prior[-max_prior:]
            result.append(enriched)
            prior.append(str(row["text"]).strip())
    return sorted(result, key=lambda item: str(item["sample_id"]))


def balanced_label_sample(
    rows: list[dict], quotas: dict[str, int], seed: int
) -> list[dict]:
    """Sample each silver label while spreading selections across students."""
    rng = random.Random(seed)
    by_label_user: dict[str, dict[str, list[dict]]] = defaultdict(
        lambda: defaultdict(list)
    )
    for row in rows:
        by_label_user[str(row["reviewed_label"])][str(row["user_id_hash"])].append(row)

    selected: list[dict] = []
    for label, quota in quotas.items():
        groups = by_label_user.get(label, {})
        available = sum(len(group_rows) for group_rows in groups.values())
        if available < quota:
            raise ValueError(f"Label {label} has {available} rows; quota requires {quota}")

        user_ids = sorted(groups)
        rng.shuffle(user_ids)
        for user_id in user_ids:
            rng.shuffle(groups[user_id])

        label_selected: list[dict] = []
        cursor = 0
        while len(label_selected) < quota:
            user_id = user_ids[cursor % len(user_ids)]
            if groups[user_id]:
                label_selected.append(groups[user_id].pop())
            cursor += 1
        selected.extend(label_selected)

    rng.shuffle(selected)
    return selected


def split_pilot_formal(
    selected: list[dict], pilot_per_label: int, seed: int
) -> tuple[list[dict], list[dict]]:
    rng = random.Random(seed)
    by_label: dict[str, list[dict]] = defaultdict(list)
    for row in selected:
        by_label[str(row["reviewed_label"])].append(row)
    pilot: list[dict] = []
    formal: list[dict] = []
    for label in LABEL_QUOTAS:
        label_rows = by_label[label]
        rng.shuffle(label_rows)
        pilot.extend(label_rows[:pilot_per_label])
        formal.extend(label_rows[pilot_per_label:])
    rng.shuffle(pilot)
    rng.shuffle(formal)
    return pilot, formal


def annotation_id(sample_id: str, seed: int) -> str:
    digest = hashlib.sha256(f"{ANNOTATION_VERSION}|{seed}|{sample_id}".encode()).hexdigest()
    return f"BG26-{digest[:12].upper()}"


def blinded_row(row: dict, phase: str, order: int, seed: int) -> dict:
    payload = {
        "annotation_id": annotation_id(str(row["sample_id"]), seed),
        "phase": phase,
        "order": order,
        "semester": row.get("semester") or "unknown",
        "topic": row.get("topic") or "unknown",
        "prior_student_messages": row.get("prior_student_messages", []),
        "student_message": str(row["text"]),
        "behavior_label": "",
        "attempt_evidence": "",
        "answer_restriction_needed": "",
        "appropriate_assistance_level": "",
        "recommended_strategy": "",
        "assessment_context": "",
        "ambiguity_flag": "",
        "review_notes": "",
    }
    if tuple(payload) != BLINDED_FIELDS:
        raise AssertionError("Blinded payload field order drifted from the declared schema")
    if FORBIDDEN_BLINDED_FIELDS & payload.keys():
        raise AssertionError("A forbidden field leaked into a blinded payload")
    return payload


def make_annotator_payload(
    rows: list[dict], phase: str, seed: int, annotator_offset: int
) -> list[dict]:
    ordered = list(rows)
    random.Random(seed + annotator_offset).shuffle(ordered)
    return [
        blinded_row(row, phase, index, seed)
        for index, row in enumerate(ordered, start=1)
    ]


def private_key_rows(selected: list[dict], phase_ids: dict[str, str], seed: int) -> list[dict]:
    population_counts = Counter()
    for row in selected:
        population_counts[str(row["reviewed_label"])] += 1
    result = []
    for row in selected:
        label = str(row["reviewed_label"])
        result.append(
            {
                "annotation_id": annotation_id(str(row["sample_id"]), seed),
                "phase": phase_ids[str(row["sample_id"])],
                "sample_id": row["sample_id"],
                "chat_id_hash": row["chat_id_hash"],
                "user_id_hash": row["user_id_hash"],
                "silver_label": label,
                "semester": row.get("semester") or "unknown",
                "topic": row.get("topic") or "unknown",
                "has_prior_student_messages": bool(row.get("prior_student_messages")),
            }
        )
    return sorted(result, key=lambda item: item["annotation_id"])


def distribution(rows: list[dict], field: str) -> dict[str, int]:
    return dict(sorted(Counter(str(row.get(field, "unknown")) for row in rows).items()))


def annotation_manifest(
    input_path: Path,
    output_paths: dict[str, Path],
    all_test_rows: list[dict],
    selected: list[dict],
    pilot: list[dict],
    formal: list[dict],
    seed: int,
) -> dict:
    population_labels = Counter(str(row["reviewed_label"]) for row in all_test_rows)
    sample_labels = Counter(str(row["reviewed_label"]) for row in selected)
    return {
        "annotation_version": ANNOTATION_VERSION,
        "status": "superseded by bench2026-single-annotator-v1; retained for provenance",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "input": {
            "path": input_path.as_posix(),
            "sha256": sha256(input_path),
            "samples": len(all_test_rows),
            "students": len({str(row["user_id_hash"]) for row in all_test_rows}),
            "conversations": len({str(row["chat_id_hash"]) for row in all_test_rows}),
            "label_distribution": dict(sorted(population_labels.items())),
        },
        "sampling": {
            "seed": seed,
            "source_split": "student-held-out test",
            "selection_uses": "silver labels for fixed quotas only",
            "label_quotas": LABEL_QUOTAS,
            "pilot_per_label": PILOT_PER_LABEL,
            "selected_samples": len(selected),
            "selected_students": len({str(row["user_id_hash"]) for row in selected}),
            "selected_conversations": len({str(row["chat_id_hash"]) for row in selected}),
            "pilot_samples": len(pilot),
            "formal_samples": len(formal),
            "label_distribution": dict(sorted(sample_labels.items())),
            "semester_distribution": distribution(selected, "semester"),
            "topic_distribution": distribution(selected, "topic"),
            "has_prior_student_messages": sum(
                bool(row.get("prior_student_messages")) for row in selected
            ),
            "sampling_weights_by_silver_label": {
                label: population_labels[label] / sample_labels[label]
                for label in LABEL_QUOTAS
            },
        },
        "blinding": {
            "exposed_fields": list(BLINDED_FIELDS),
            "excluded_fields": sorted(FORBIDDEN_BLINDED_FIELDS),
            "context_limitation": (
                "prior_student_messages contains up to four earlier student prompts; "
                "assistant replies are unavailable in the source split"
            ),
            "annotator_orders": "independently shuffled; identical sample membership",
        },
        "outputs": {
            name: {
                "path": path.as_posix(),
                "sha256": sha256(path),
                "rows": sum(1 for _ in path.open(encoding="utf-8")),
            }
            for name, path in output_paths.items()
            if name != "private_key"
        },
        "private_key": {
            "path": output_paths["private_key"].as_posix(),
            "sha256": sha256(output_paths["private_key"]),
            "tracked_in_git": False,
        },
        "analysis_note": (
            "Historical A/B pack created before the single-annotator decision. It "
            "oversamples rare silver strata and is retained only for provenance; "
            "do not describe its same-person pilot as inter-annotator agreement. "
            "Use the single-annotator manifest for the active reference-set workflow."
        ),
    }


def ensure_targets_are_safe(paths: Iterable[Path], force: bool) -> None:
    existing = [path for path in paths if path.exists()]
    if existing and not force:
        joined = ", ".join(path.as_posix() for path in existing)
        raise FileExistsError(f"Refusing to overwrite existing files without --force: {joined}")


def prepare_annotation_pack(
    input_path: Path,
    output_dir: Path,
    manifest_path: Path,
    seed: int,
    force: bool,
) -> dict:
    paths = {
        "annotator_a_pilot": output_dir / "annotator_a_pilot_50.jsonl",
        "annotator_a_formal": output_dir / "annotator_a_formal_550.jsonl",
        "annotator_b_pilot": output_dir / "annotator_b_pilot_50.jsonl",
        "annotator_b_formal": output_dir / "annotator_b_formal_550.jsonl",
        "private_key": output_dir / "gold_annotation_private_key.jsonl",
    }
    ensure_targets_are_safe([*paths.values(), manifest_path], force)

    rows = read_jsonl(input_path)
    validate_input(rows)
    enriched = attach_prior_student_messages(rows)
    selected = balanced_label_sample(enriched, LABEL_QUOTAS, seed)
    pilot, formal = split_pilot_formal(selected, PILOT_PER_LABEL, seed + 10)

    payloads = {
        "annotator_a_pilot": make_annotator_payload(pilot, "pilot", seed, 101),
        "annotator_a_formal": make_annotator_payload(formal, "formal", seed, 102),
        "annotator_b_pilot": make_annotator_payload(pilot, "pilot", seed, 201),
        "annotator_b_formal": make_annotator_payload(formal, "formal", seed, 202),
    }
    for name, payload in payloads.items():
        write_jsonl(paths[name], payload)

    phase_ids = {str(row["sample_id"]): "pilot" for row in pilot}
    phase_ids.update({str(row["sample_id"]): "formal" for row in formal})
    write_jsonl(paths["private_key"], private_key_rows(selected, phase_ids, seed))

    manifest = annotation_manifest(
        input_path, paths, rows, selected, pilot, formal, seed
    )
    write_json(manifest_path, manifest)
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    if not args.input.exists():
        raise SystemExit(f"Input Test split not found: {args.input}")
    try:
        manifest = prepare_annotation_pack(
            args.input, args.output_dir, args.manifest, args.seed, args.force
        )
    except (ValueError, FileExistsError) as exc:
        raise SystemExit(str(exc)) from exc
    print(json.dumps(manifest["sampling"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
