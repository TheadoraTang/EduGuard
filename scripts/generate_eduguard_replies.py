"""Generate EduGuard pipeline replies for student messages.

Runs the full EduGuard pipeline (classify -> risk -> intervention -> tutor)
for each sampled message, producing a reply with full decision trace.
"""

from __future__ import annotations

import argparse
import json
import os
import random
import re
import sys
import time
import uuid
from collections import defaultdict
from dataclasses import asdict
from pathlib import Path

# Python path setup - must happen before importing app modules
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.models import Message, MessageSender  # noqa: E402
from app.services.analysis import (  # noqa: E402
    AnalysisResult,
    classify_with_llm,
    classify_student_message,
    classify_with_rules,
)
from app.services.eduguard_tutor import run_eduguard_tutor  # noqa: E402
from app.services.ml_behavior import classify_with_ml_model  # noqa: E402
from app.services.risk import assess_risk  # noqa: E402


def read_jsonl(path: Path) -> list[dict]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def load_completed(path: Path) -> set[str]:
    if not path.exists():
        return set()
    return {row["sample_id"] for row in read_jsonl(path)}


def append_jsonl(path: Path, row: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def extract_seq(sample_id: str) -> int:
    match = re.search(r"-(\d+)$", sample_id)
    return int(match.group(1)) if match else 0


def group_and_sort_rows(rows: list[dict]) -> dict[str, list[dict]]:
    groups: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        groups[row["chat_id_hash"]].append(row)
    for chat_id in groups:
        groups[chat_id].sort(key=lambda r: extract_seq(r["sample_id"]))
    return groups


def sample_messages(
    rows: list[dict],
    n: int,
    seed: int,
    completed: set[str],
) -> list[dict]:
    pending = [r for r in rows if r["sample_id"] not in completed]
    if n <= 0 or n >= len(pending):
        return pending
    rng = random.Random(seed)
    return rng.sample(pending, n)


def build_message_history(
    chat_messages: list[dict],
    current_seq: int,
    max_turns: int = 12,
) -> list[Message]:
    prior = [
        m for m in chat_messages
        if extract_seq(m["sample_id"]) < current_seq
    ][-max_turns:]

    dummy_conv_id = uuid.uuid4().hex
    return [
        Message(
            id=uuid.uuid4().hex,
            conversation_id=dummy_conv_id,
            sender=MessageSender.student,
            content=m["text"],
            sequence_number=i,
        )
        for i, m in enumerate(prior)
    ]


def build_chat_state(
    chat_messages: list[dict],
    current_seq: int,
) -> tuple[int, bool]:
    """Build risk state from prior messages using rules-only classification."""
    prior_answer_seeking_count = 0
    has_reflection = False
    prior = [m for m in chat_messages if extract_seq(m["sample_id"]) < current_seq]
    for m in prior:
        result = classify_with_rules(m["text"])
        if result.behavior_type == "answer_seeking":
            prior_answer_seeking_count += 1
        if result.behavior_type == "reflection_verification":
            has_reflection = True
    return prior_answer_seeking_count, has_reflection


def run_pipeline(
    student_text: str,
    history: list[Message],
    prior_answer_seeking_count: int,
    has_reflection: bool,
    task_title: str,
    task_description: str,
    classifier: str,
    classifier_model: Path,
) -> dict:
    # Step 1: classify
    recent_context = [m.content for m in history[-4:]]
    if classifier == "ml":
        analysis = classify_with_ml_model(
            student_text, recent_context, str(classifier_model)
        )
    elif classifier == "rule":
        analysis = classify_with_rules(student_text)
    elif classifier == "llm":
        analysis = classify_with_llm(student_text, recent_context)
        if analysis is None:
            analysis = classify_with_rules(student_text)
    else:
        analysis = classify_student_message(student_text, recent_context)

    # Step 2: assess risk
    risk = assess_risk(
        student_text,
        analysis.behavior_type,
        prior_answer_seeking_count=prior_answer_seeking_count,
        has_reflection=has_reflection,
    )

    # Step 3: run full tutor pipeline
    decision = run_eduguard_tutor(
        task_title=task_title,
        task_description=task_description,
        history=history,
        analysis=analysis,
        risk_level=risk.level,
        risk_score=risk.score,
    )

    return {
        "eduguard_reply": decision.generated_response,
        "behavior_type": decision.behavior_type,
        "behavior_confidence": analysis.confidence,
        "behavior_method": analysis.method,
        "behavior_model": analysis.model_name,
        "risk_level": decision.risk_level,
        "risk_score": decision.risk_score,
        "risk_evidences": [asdict(e) for e in risk.evidences],
        "intervention_level": decision.intervention_level,
        "strategy_type": decision.strategy_type,
        "strategy_reason": decision.strategy_reason,
        "response_policy": decision.response_policy,
        "allow_direct_answer": decision.allow_direct_answer,
        "generated_by": decision.generated_by,
        "generation_model": decision.generation_model,
        "history_turns": len(history),
        "prior_answer_seeking_count": prior_answer_seeking_count,
        "has_reflection": has_reflection,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate EduGuard pipeline replies for student messages."
    )
    parser.add_argument(
        "--input", type=Path,
        default=Path("data/final/studychat_behavior_test.jsonl"),
    )
    parser.add_argument(
        "--output", type=Path,
        default=Path("data/processed/eduguard_replies.jsonl"),
    )
    parser.add_argument(
        "--limit", type=int, default=200,
        help="Number of messages to process (0 = all pending)",
    )
    parser.add_argument(
        "--seed", type=int, default=42,
        help="Must match vanilla script seed for consistent sampling",
    )
    parser.add_argument("--sleep", type=float, default=0.1)
    parser.add_argument("--max-retries", type=int, default=3)
    parser.add_argument(
        "--classifier",
        choices=["auto", "llm", "ml", "rule"],
        default="auto",
        help="Classifier used for the current student message.",
    )
    parser.add_argument(
        "--classifier-model",
        type=Path,
        default=Path("data/models/studychat_behavior_tfidf_logreg.joblib"),
        help="Joblib model artifact used when --classifier ml.",
    )
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if args.classifier == "ml" and not args.classifier_model.exists():
        raise SystemExit(
            f"Missing classifier model: {args.classifier_model}. "
            "Run scripts/train_behavior_classifier.py first."
        )

    rows = read_jsonl(args.input)
    chat_groups = group_and_sort_rows(rows)

    completed = load_completed(args.output)
    sampled = sample_messages(rows, args.limit, args.seed, completed)

    # Build topic -> task context mapping
    topic_map: dict[str, tuple[str, str]] = {}
    for row in rows:
        topic = row.get("topic", "") or "未分类作业"
        if topic not in topic_map:
            topic_map[topic] = (
                topic,
                "学生正在完成课程作业，使用AI助手辅助学习。",
            )

    if args.dry_run:
        preview = []
        for row in sampled[:3]:
            chat_id = row["chat_id_hash"]
            current_seq = extract_seq(row["sample_id"])
            hist = build_message_history(chat_groups[chat_id], current_seq)
            asc, ref = build_chat_state(chat_groups[chat_id], current_seq)
            topic = row.get("topic", "") or "未分类作业"
            preview.append({
                "sample_id": row["sample_id"],
                "topic": topic,
                "history_turns": len(hist),
                "prior_answer_seeking_count": asc,
                "has_reflection": ref,
                "text_preview": row["text"][:150],
            })
        print(json.dumps({
            "script": "generate_eduguard_replies",
            "input_samples": len(rows),
            "already_completed": len(completed),
            "pending": len(sampled),
            "preview": preview,
        }, ensure_ascii=False, indent=2))
        return

    failures = 0
    for index, row in enumerate(sampled, start=1):
        chat_id = row["chat_id_hash"]
        current_seq = extract_seq(row["sample_id"])

        history = build_message_history(chat_groups[chat_id], current_seq)
        prior_asc, has_ref = build_chat_state(chat_groups[chat_id], current_seq)

        topic = row.get("topic", "") or "未分类作业"
        task_title, task_description = topic_map[topic]

        last_error = None
        for attempt in range(1, args.max_retries + 1):
            try:
                result = run_pipeline(
                    student_text=row["text"],
                    history=history,
                    prior_answer_seeking_count=prior_asc,
                    has_reflection=has_ref,
                    task_title=task_title,
                    task_description=task_description,
                    classifier=args.classifier,
                    classifier_model=args.classifier_model,
                )
                result["sample_id"] = row["sample_id"]
                result["chat_id_hash"] = row["chat_id_hash"]
                result["topic"] = topic
                append_jsonl(args.output, result)
                last_error = None
                break
            except Exception as error:
                last_error = error
                if attempt < args.max_retries:
                    time.sleep(attempt)

        if last_error is not None:
            failures += 1
            print(f"[failed] {row['sample_id']}: {last_error}")
        elif index % 50 == 0 or index == len(sampled):
            print(f"[progress] {index}/{len(sampled)}")

        time.sleep(args.sleep)

    print(json.dumps({
        "script": "generate_eduguard_replies",
        "requested": len(sampled),
        "failures": failures,
        "output": str(args.output),
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
