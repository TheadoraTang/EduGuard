"""Convert MathDial teacher turns into a leakage-safe scaffold review set."""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import re
from collections import Counter, defaultdict
from pathlib import Path


STRATEGY_MAP = {
    "focus": "error_focus",
    "probing": "probing_question",
    "generic": "generic_prompt",
    "telling": "direct_explanation",
}


def stable_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]


def stable_split(problem: str) -> str:
    bucket = int(stable_hash(problem)[:8], 16) % 100
    return "train" if bucket < 70 else "dev" if bucket < 85 else "test"


def infer_strategy(text: str, source_act: str) -> tuple[str, str]:
    act = source_act.strip().lower()
    if act in STRATEGY_MAP:
        return STRATEGY_MAP[act], "source_dialog_act"

    normalized = text.lower().strip()
    if re.search(r"\b(the answer|equals?|therefore|you need to|first .* then)\b", normalized):
        return "direct_explanation", "text_heuristic"
    if re.search(r"\b(good start|well done|you are close|nice try)\b", normalized):
        return "feedback_prompt", "text_heuristic"
    if "?" in text or re.match(
        r"^(what|why|how|where|which|can you|could you|do you|would you)", normalized
    ):
        if re.search(r"\b(where|wrong|mistake|difference|instead|know that)\b", normalized):
            return "error_focus", "text_heuristic"
        return "probing_question", "text_heuristic"
    return "generic_prompt", "fallback"


def disclosure_candidate(teacher_text: str, reference_solution: str) -> bool:
    teacher_numbers = set(re.findall(r"(?<!\w)-?\d+(?:\.\d+)?", teacher_text))
    solution_numbers = re.findall(r"(?<!\w)-?\d+(?:\.\d+)?", reference_solution)
    final_number = solution_numbers[-1] if solution_numbers else None
    direct_language = bool(
        re.search(r"\b(the answer is|equals?|therefore|so .* is)\b", teacher_text.lower())
    )
    return bool(final_number and final_number in teacher_numbers and direct_language)


def load_turns(paths: list[Path]) -> list[dict]:
    rows: list[dict] = []
    for path in paths:
        data = json.loads(path.read_text(encoding="utf-8"))
        for dialogue_index, dialogue in enumerate(data):
            history = dialogue.get("dialog_history", [])
            for turn_index, turn in enumerate(history):
                if turn.get("user") != "Teacher" or turn_index == 0:
                    continue
                previous_student = next(
                    (
                        item
                        for item in reversed(history[:turn_index])
                        if item.get("user") == "Student"
                    ),
                    None,
                )
                if not previous_student:
                    continue
                teacher_text = str(turn.get("text", "")).strip()
                student_text = str(previous_student.get("text", "")).strip()
                if not teacher_text or not student_text:
                    continue
                source_act = str(turn.get("dialog_act", "") or "")
                strategy, strategy_source = infer_strategy(teacher_text, source_act)
                problem = str(dialogue.get("problem", "")).strip()
                row_id = stable_hash(
                    f"{path.name}:{dialogue_index}:{turn_index}:{problem}:{teacher_text}"
                )
                rows.append(
                    {
                        "sample_id": f"mathdial-{row_id}",
                        "source_file": path.name,
                        "dialogue_index": dialogue_index,
                        "teacher_turn_index": turn_index,
                        "problem_id_hash": stable_hash(problem),
                        "split": stable_split(problem),
                        "topic": dialogue.get("topic"),
                        "problem": problem,
                        "student_text": student_text,
                        "teacher_text": teacher_text,
                        "source_dialog_act": source_act,
                        "predicted_strategy": strategy,
                        "strategy_source": strategy_source,
                        "answer_disclosure_candidate": disclosure_candidate(
                            teacher_text, str(dialogue.get("reference_solution", ""))
                        ),
                        "reviewed_strategy": "",
                        "reviewed_answer_disclosure": "",
                        "pedagogical_relevance_score": "",
                        "promotes_thinking_score": "",
                        "clarity_score": "",
                        "review_notes": "",
                    }
                )
    return rows


def stratified_sample(rows: list[dict], size: int, seed: int) -> list[dict]:
    rng = random.Random(seed)
    groups: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        groups[row["predicted_strategy"]].append(row)
    for group in groups.values():
        rng.shuffle(group)

    selected: list[dict] = []
    labels = sorted(groups)
    quota = max(1, size // max(1, len(labels)))
    for label in labels:
        selected.extend(groups[label][:quota])
    selected_ids = {row["sample_id"] for row in selected}
    remainder = [row for row in rows if row["sample_id"] not in selected_ids]
    rng.shuffle(remainder)
    selected.extend(remainder[: max(0, size - len(selected))])
    rng.shuffle(selected)
    return selected[:size]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("paths", nargs="+", type=Path)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/processed/mathdial_scaffold_review_300.jsonl"),
    )
    parser.add_argument("--size", type=int, default=300)
    parser.add_argument("--seed", type=int, default=20260623)
    args = parser.parse_args()

    candidates = load_turns(args.paths)
    rows = (
        candidates
        if args.size <= 0 or args.size >= len(candidates)
        else stratified_sample(candidates, args.size, args.seed)
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(
        json.dumps(
            {
                "output": str(args.output),
                "samples": len(rows),
                "strategy_distribution": dict(
                    sorted(Counter(row["predicted_strategy"] for row in rows).items())
                ),
                "split_distribution": dict(
                    sorted(Counter(row["split"] for row in rows).items())
                ),
                "seed": args.seed,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
