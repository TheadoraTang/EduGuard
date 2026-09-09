"""Prepare the BENCH 2026 single-annotator formal and delayed-retest packs.

The 550-item formal set is preserved intact. Sixty formal items are selected
for a delayed, blinded retest (12 from each silver stratum) and receive new
alias IDs. The alias mapping stays in the ignored private data directory.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable


DEFAULT_FORMAL_INPUT = Path(
    "data/bench2026/human_eval/annotator_a_formal_550.jsonl"
)
DEFAULT_PRIVATE_KEY = Path(
    "data/bench2026/human_eval/gold_annotation_private_key.jsonl"
)
DEFAULT_OUTPUT_DIR = Path("data/bench2026/human_eval")
DEFAULT_MANIFEST = Path(
    "data/bench2026/manifests/studychat_single_annotator_manifest.json"
)
DEFAULT_SEED = 20260909
VERSION = "bench2026-single-annotator-v1"
RETEST_PER_SILVER_STRATUM = 12
MINIMUM_DELAY_DAYS = 7
ANNOTATION_FIELDS = (
    "behavior_label",
    "attempt_evidence",
    "answer_restriction_needed",
    "appropriate_assistance_level",
    "recommended_strategy",
    "assessment_context",
    "ambiguity_flag",
    "review_notes",
)


def read_jsonl(path: Path) -> list[dict]:
    rows: list[dict] = []
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            row = json.loads(line)
            if not isinstance(row, dict):
                raise ValueError(f"Line {line_number} is not a JSON object")
            rows.append(row)
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


def validate_formal_rows(rows: list[dict]) -> None:
    if len(rows) != 550:
        raise ValueError(f"Formal input contains {len(rows)} rows; expected 550")
    ids = [str(row.get("annotation_id", "")) for row in rows]
    if any(not value for value in ids) or len(set(ids)) != len(ids):
        raise ValueError("Formal input has blank or duplicate annotation IDs")
    for index, row in enumerate(rows, start=1):
        if row.get("phase") != "formal":
            raise ValueError(f"Formal row {index} has phase={row.get('phase')!r}")
        filled = [field for field in ANNOTATION_FIELDS if str(row.get(field, "")).strip()]
        if filled:
            raise ValueError(
                f"Formal row {index} already contains annotations in {filled}; "
                "refusing to create a fresh single-annotator pack"
            )


def prepare_formal(rows: list[dict], seed: int) -> list[dict]:
    output = [dict(row) for row in rows]
    random.Random(seed).shuffle(output)
    for order, row in enumerate(output, start=1):
        row["phase"] = "formal"
        row["order"] = order
        for field in ANNOTATION_FIELDS:
            row[field] = ""
    return output


def select_retest_rows(
    formal_rows: list[dict], private_rows: list[dict], seed: int
) -> list[dict]:
    key_by_id = {str(row["annotation_id"]): row for row in private_rows}
    missing = [
        str(row["annotation_id"])
        for row in formal_rows
        if str(row["annotation_id"]) not in key_by_id
    ]
    if missing:
        raise ValueError(f"Private key is missing {len(missing)} formal IDs")

    by_label_user: dict[str, dict[str, list[dict]]] = defaultdict(
        lambda: defaultdict(list)
    )
    for row in formal_rows:
        key = key_by_id[str(row["annotation_id"])]
        label = str(key["silver_label"])
        user_id = str(key["user_id_hash"])
        by_label_user[label][user_id].append(row)

    rng = random.Random(seed)
    selected: list[dict] = []
    for label in sorted(by_label_user):
        groups = by_label_user[label]
        available = sum(len(items) for items in groups.values())
        if available < RETEST_PER_SILVER_STRATUM:
            raise ValueError(
                f"Silver stratum {label} has {available} formal rows; "
                f"requires {RETEST_PER_SILVER_STRATUM}"
            )
        users = sorted(groups)
        rng.shuffle(users)
        for user_id in users:
            rng.shuffle(groups[user_id])
        label_rows: list[dict] = []
        cursor = 0
        while len(label_rows) < RETEST_PER_SILVER_STRATUM:
            user_id = users[cursor % len(users)]
            if groups[user_id]:
                label_rows.append(groups[user_id].pop())
            cursor += 1
        selected.extend(label_rows)
    rng.shuffle(selected)
    return selected


def retest_alias(annotation_id: str, seed: int) -> str:
    digest = hashlib.sha256(
        f"{VERSION}|retest|{seed}|{annotation_id}".encode()
    ).hexdigest()
    return f"RT26-{digest[:12].upper()}"


def prepare_retest(
    selected: list[dict], private_rows: list[dict], seed: int
) -> tuple[list[dict], list[dict]]:
    key_by_id = {str(row["annotation_id"]): row for row in private_rows}
    payload: list[dict] = []
    mapping: list[dict] = []
    for order, source in enumerate(selected, start=1):
        original_id = str(source["annotation_id"])
        alias = retest_alias(original_id, seed)
        row = dict(source)
        row["annotation_id"] = alias
        row["phase"] = "delayed_retest"
        row["order"] = order
        for field in ANNOTATION_FIELDS:
            row[field] = ""
        payload.append(row)
        key = key_by_id[original_id]
        mapping.append(
            {
                "retest_annotation_id": alias,
                "formal_annotation_id": original_id,
                "sample_id": key["sample_id"],
                "user_id_hash": key["user_id_hash"],
                "chat_id_hash": key["chat_id_hash"],
                "silver_label": key["silver_label"],
            }
        )
    return payload, sorted(mapping, key=lambda row: row["retest_annotation_id"])


def build_manifest(
    formal_input: Path,
    private_key: Path,
    formal_output: Path,
    retest_output: Path,
    retest_mapping: Path,
    formal_rows: list[dict],
    retest_rows: list[dict],
    mapping_rows: list[dict],
    seed: int,
) -> dict:
    return {
        "version": VERSION,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "design": {
            "annotators": 1,
            "formal_unique_samples": len(formal_rows),
            "delayed_retest_samples": len(retest_rows),
            "minimum_delay_days": MINIMUM_DELAY_DAYS,
            "retest_blinding": (
                "Retest rows use alias IDs and a new order; the mapping is private"
            ),
            "paper_term": "single-annotator reference set",
            "prohibited_claim": "inter-annotator agreement",
        },
        "randomization": {
            "seed": seed,
            "retest_per_silver_stratum": RETEST_PER_SILVER_STRATUM,
        },
        "inputs": {
            "formal": {
                "path": formal_input.as_posix(),
                "sha256": sha256(formal_input),
            },
            "private_key": {
                "path": private_key.as_posix(),
                "sha256": sha256(private_key),
                "tracked_in_git": False,
            },
        },
        "outputs": {
            "formal": {
                "path": formal_output.as_posix(),
                "sha256": sha256(formal_output),
                "rows": len(formal_rows),
            },
            "retest": {
                "path": retest_output.as_posix(),
                "sha256": sha256(retest_output),
                "rows": len(retest_rows),
            },
            "retest_private_mapping": {
                "path": retest_mapping.as_posix(),
                "sha256": sha256(retest_mapping),
                "rows": len(mapping_rows),
                "tracked_in_git": False,
            },
        },
        "retest_silver_strata": dict(
            sorted(Counter(row["silver_label"] for row in mapping_rows).items())
        ),
        "integrity": {
            "formal_visible_ids_unique": len(
                {str(row["annotation_id"]) for row in formal_rows}
            )
            == len(formal_rows),
            "retest_visible_ids_unique": len(
                {str(row["annotation_id"]) for row in retest_rows}
            )
            == len(retest_rows),
            "visible_id_overlap": len(
                {str(row["annotation_id"]) for row in formal_rows}
                & {str(row["annotation_id"]) for row in retest_rows}
            ),
            "retest_maps_to_formal": all(
                row["formal_annotation_id"]
                in {str(item["annotation_id"]) for item in formal_rows}
                for row in mapping_rows
            ),
        },
    }


def ensure_safe(paths: Iterable[Path], force: bool) -> None:
    existing = [path for path in paths if path.exists()]
    if existing and not force:
        raise FileExistsError(
            "Refusing to overwrite without --force: "
            + ", ".join(path.as_posix() for path in existing)
        )


def prepare_single_annotator_pack(
    formal_input: Path,
    private_key: Path,
    output_dir: Path,
    manifest_path: Path,
    seed: int,
    force: bool,
) -> dict:
    formal_output = output_dir / "single_annotator_formal_550.jsonl"
    retest_output = output_dir / "single_annotator_retest_60.jsonl"
    retest_mapping = output_dir / "single_annotator_retest_private_key.jsonl"
    ensure_safe(
        [formal_output, retest_output, retest_mapping, manifest_path], force
    )
    source_rows = read_jsonl(formal_input)
    private_rows = read_jsonl(private_key)
    validate_formal_rows(source_rows)
    formal_rows = prepare_formal(source_rows, seed)
    selected = select_retest_rows(formal_rows, private_rows, seed + 1)
    retest_rows, mapping_rows = prepare_retest(selected, private_rows, seed + 2)
    write_jsonl(formal_output, formal_rows)
    write_jsonl(retest_output, retest_rows)
    write_jsonl(retest_mapping, mapping_rows)
    manifest = build_manifest(
        formal_input,
        private_key,
        formal_output,
        retest_output,
        retest_mapping,
        formal_rows,
        retest_rows,
        mapping_rows,
        seed,
    )
    write_json(manifest_path, manifest)
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--formal-input", type=Path, default=DEFAULT_FORMAL_INPUT)
    parser.add_argument("--private-key", type=Path, default=DEFAULT_PRIVATE_KEY)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    for path in (args.formal_input, args.private_key):
        if not path.exists():
            raise SystemExit(f"Required input not found: {path}")
    try:
        manifest = prepare_single_annotator_pack(
            args.formal_input,
            args.private_key,
            args.output_dir,
            args.manifest,
            args.seed,
            args.force,
        )
    except (ValueError, FileExistsError) as exc:
        raise SystemExit(str(exc)) from exc
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
