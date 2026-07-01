"""Generate vanilla (no pipeline) LLM replies for student messages.

This script calls the LLM with a simple teaching assistant prompt without
any EduGuard behavior analysis, risk assessment, or scaffolding strategy.
"""

from __future__ import annotations

import argparse
import json
import os
import random
import re
import time
from collections import defaultdict
from pathlib import Path

from openai import OpenAI

VANILLA_SYSTEM_PROMPT = (
    "你是一个友好的教学助手。"
)


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


def build_history(
    chat_messages: list[dict],
    current_seq: int,
    max_turns: int = 12,
) -> list[dict[str, str]]:
    prior = [
        m for m in chat_messages
        if extract_seq(m["sample_id"]) < current_seq
    ][-max_turns:]
    return [{"role": "user", "content": m["text"]} for m in prior]


def call_vanilla_llm(
    client: OpenAI,
    model: str,
    history: list[dict[str, str]],
    current_text: str,
) -> str:
    messages: list[dict[str, str]] = [
        {"role": "system", "content": VANILLA_SYSTEM_PROMPT}
    ]
    messages.extend(history)
    messages.append({"role": "user", "content": current_text})

    response = client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=0.4,
        max_tokens=900,
        extra_body={"thinking": {"type": "disabled"}},
    )
    return (response.choices[0].message.content or "").strip()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate vanilla LLM replies for student messages."
    )
    parser.add_argument(
        "--input", type=Path,
        default=Path("data/final/studychat_behavior_test.jsonl"),
    )
    parser.add_argument(
        "--output", type=Path,
        default=Path("data/processed/vanilla_replies.jsonl"),
    )
    parser.add_argument(
        "--limit", type=int, default=200,
        help="Number of messages to process (0 = all pending)",
    )
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--model", default=os.getenv("LLM_MODEL", "deepseek-v4-flash")
    )
    parser.add_argument("--api-key", default=os.getenv("LLM_API_KEY"))
    parser.add_argument(
        "--base-url",
        default=os.getenv("LLM_BASE_URL", "https://api.deepseek.com"),
    )
    parser.add_argument("--sleep", type=float, default=0.1)
    parser.add_argument("--max-retries", type=int, default=3)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    rows = read_jsonl(args.input)
    chat_groups = group_and_sort_rows(rows)

    completed = load_completed(args.output)
    sampled = sample_messages(rows, args.limit, args.seed, completed)

    if args.dry_run:
        preview = []
        for row in sampled[:3]:
            hist = build_history(
                chat_groups[row["chat_id_hash"]],
                extract_seq(row["sample_id"]),
            )
            preview.append({
                "sample_id": row["sample_id"],
                "history_turns": len(hist),
                "text_preview": row["text"][:150],
            })
        print(json.dumps({
            "script": "generate_vanilla_replies",
            "input_samples": len(rows),
            "already_completed": len(completed),
            "pending": len(sampled),
            "preview": preview,
        }, ensure_ascii=False, indent=2))
        return

    if not args.api_key:
        raise SystemExit("LLM_API_KEY is required (set in .env or pass --api-key)")

    client = OpenAI(
        api_key=args.api_key,
        base_url=args.base_url,
        timeout=90,
    )

    failures = 0
    for index, row in enumerate(sampled, start=1):
        history = build_history(
            chat_groups[row["chat_id_hash"]],
            extract_seq(row["sample_id"]),
        )

        last_error = None
        for attempt in range(1, args.max_retries + 1):
            try:
                reply = call_vanilla_llm(
                    client, args.model, history, row["text"]
                )
                append_jsonl(args.output, {
                    "sample_id": row["sample_id"],
                    "chat_id_hash": row["chat_id_hash"],
                    "vanilla_reply": reply,
                    "generation_model": args.model,
                    "history_turns": len(history),
                })
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
        "script": "generate_vanilla_replies",
        "requested": len(sampled),
        "failures": failures,
        "output": str(args.output),
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
