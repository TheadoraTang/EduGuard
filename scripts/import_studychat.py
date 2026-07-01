"""Import StudyChat JSONL into EduGuard with stable anonymization and idempotency.

Usage:
    python scripts/import_studychat.py data/raw/studychat/dialogues.jsonl
    python scripts/import_studychat.py data/raw/studychat/dialogues.jsonl --limit 300
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from sqlalchemy import select

from app.db import Base, SessionLocal, engine
from app.models import (
    AnalysisMethod,
    BehaviorAnalysis,
    Conversation,
    ImportBatch,
    LearningTask,
    Message,
    MessageSender,
    User,
    UserRole,
)
from app.services.seed import DEMO_TEACHER_ID, seed_demo_data


MAPPING_VERSION = "studychat-v1.1-to-eduguard-v1"


def anonymize(value: str) -> str:
    salt = os.getenv("STUDYCHAT_HASH_SALT", "eduguard-local-demo")
    return hashlib.sha256(f"{salt}:{value}".encode()).hexdigest()[:24]


def map_label(raw_label: str) -> tuple[str | None, str]:
    normalized = raw_label.lower().replace(" ", "_")
    broad, _, specific = normalized.partition(">")
    if broad in {"off_topic", "misc"}:
        return None, "excluded"
    if broad in {"writing", "writing_request"}:
        return "answer_seeking", "candidate_only"
    if broad == "editing_request" and "code" in specific:
        return "debugging_help", "weak"
    if broad == "editing_request":
        return "answer_seeking", "candidate_only"
    if broad == "conceptual_questions":
        return "concept_understanding", "direct"
    if "assignment_clarification" in specific:
        return "task_clarification", "direct"
    if any(value in specific for value in ("code_explanation", "interpret_output")):
        return "debugging_help", "direct"
    if broad == "verification":
        return "reflection_verification", "direct"
    if broad in {"context", "provide_context"}:
        return None, "personal_attempt_evidence"
    if broad == "contextual_questions":
        return "debugging_help", "weak"
    return "concept_understanding", "fallback"


def read_records(path: Path, limit: int | None) -> list[dict]:
    records = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            records.append(json.loads(line))
            if limit and len(records) >= limit:
                break
    return records


def label_value(record: dict) -> tuple[str, str]:
    label = record.get("llm_label") or {}
    if isinstance(label, str):
        return label, ""
    return str(label.get("label", "Misc>Other")), str(label.get("justification", ""))


def ensure_student(db, external_user_id: str) -> User:
    username = f"studychat_{anonymize(external_user_id)}"
    student = db.scalar(select(User).where(User.username == username))
    if student:
        return student
    student = User(
        username=username,
        real_name=f"StudyChat 学生 {username[-6:]}",
        role=UserRole.student,
        password_hash="dataset-import",
    )
    db.add(student)
    db.flush()
    return student


def ensure_task(db, topic: str) -> LearningTask:
    title = f"StudyChat 作业 {topic}"
    task = db.scalar(select(LearningTask).where(LearningTask.title == title))
    if task:
        return task
    task = LearningTask(
        created_by=DEMO_TEACHER_ID,
        title=title,
        description="从 StudyChat 导入的匿名化人工智能课程编程任务。",
        task_type="programming",
        knowledge_points=[topic],
        difficulty=3,
        is_published=False,
    )
    db.add(task)
    db.flush()
    return task


def run(path: Path, limit: int | None, source_version: str) -> dict:
    records = read_records(path, limit)
    grouped: dict[str, list[dict]] = defaultdict(list)
    for record in records:
        grouped[str(record["chatId"])].append(record)

    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        seed_demo_data(db)
        batch = ImportBatch(
            source="studychat",
            source_version=source_version,
            file_name=path.name,
            records_seen=len(records),
            metadata_json={"mapping_version": MAPPING_VERSION},
        )
        db.add(batch)
        db.flush()
        created = 0
        skipped = 0

        for chat_id, turns in grouped.items():
            external_chat_id = anonymize(chat_id)
            exists = db.scalar(
                select(Conversation.id).where(
                    Conversation.source == "studychat",
                    Conversation.external_record_id == external_chat_id,
                )
            )
            if exists:
                skipped += 1
                continue

            turns.sort(key=lambda item: (item.get("interactionCount", 0), item.get("timestamp", 0)))
            first = turns[0]
            student = ensure_student(db, str(first.get("userId", "unknown")))
            task = ensure_task(db, str(first.get("topic", "unknown")))
            conversation = Conversation(
                student_id=student.id,
                task_id=task.id,
                source="studychat",
                external_record_id=external_chat_id,
                import_batch_id=batch.id,
                metadata_json={
                    "semester": first.get("semester"),
                    "mapping_version": MAPPING_VERSION,
                    "original_turn_count": len(turns),
                },
            )
            db.add(conversation)
            db.flush()
            sequence = 1

            for index, turn in enumerate(turns):
                prompt = str(turn.get("prompt", "")).strip()
                response = str(turn.get("response", "")).strip()
                if not prompt:
                    continue
                raw_label, justification = label_value(turn)
                mapped_label, mapping_strength = map_label(raw_label)
                student_message = Message(
                    conversation_id=conversation.id,
                    sender=MessageSender.student,
                    content=prompt,
                    sequence_number=sequence,
                    source="studychat",
                    external_record_id=f"{external_chat_id}:{index}:student",
                    metadata_json={
                        "raw_label": raw_label,
                        "mapping_strength": mapping_strength,
                        "topic": turn.get("topic"),
                    },
                )
                db.add(student_message)
                db.flush()
                if mapped_label:
                    db.add(
                        BehaviorAnalysis(
                            message_id=student_message.id,
                            behavior_type=mapped_label,
                            confidence=0.65 if mapping_strength != "direct" else 0.9,
                            method=AnalysisMethod.manual,
                            explanation=justification or f"Mapped from StudyChat label {raw_label}",
                            evidence_text=prompt[:200],
                            is_selected=True,
                            needs_review=mapping_strength != "direct",
                            raw_result={
                                "source_label": raw_label,
                                "mapping_version": MAPPING_VERSION,
                                "mapping_strength": mapping_strength,
                            },
                        )
                    )
                sequence += 1
                if response:
                    db.add(
                        Message(
                            conversation_id=conversation.id,
                            sender=MessageSender.assistant,
                            content=response,
                            sequence_number=sequence,
                            source="studychat",
                            external_record_id=f"{external_chat_id}:{index}:assistant",
                        )
                    )
                    sequence += 1
            created += 1

        batch.records_created = created
        batch.status = "completed"
        batch.completed_at = datetime.now().astimezone()
        batch.metadata_json = {
            **batch.metadata_json,
            "conversations_skipped_as_duplicates": skipped,
        }
        db.commit()
        return {
            "records_seen": len(records),
            "conversations_created": created,
            "conversations_skipped": skipped,
            "batch_id": batch.id,
        }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("path", type=Path)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--source-version", default="v1.1")
    args = parser.parse_args()
    if not args.path.exists():
        raise SystemExit(f"File not found: {args.path}")
    print(json.dumps(run(args.path, args.limit, args.source_version), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
