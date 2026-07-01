"""Run a resumable OpenAI-compatible behavior classification experiment."""

from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path

from openai import OpenAI


def read_jsonl(path: Path) -> list[dict]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def load_completed(path: Path) -> dict[str, dict]:
    if not path.exists():
        return {}
    return {row["sample_id"]: row for row in read_jsonl(path)}


def append_jsonl(path: Path, row: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    parser.add_argument("--prompt", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--model", default=os.getenv("LLM_MODEL", "deepseek-chat"))
    parser.add_argument("--api-key", default=os.getenv("LLM_API_KEY"))
    parser.add_argument(
        "--base-url", default=os.getenv("LLM_BASE_URL", "https://api.deepseek.com")
    )
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--sleep", type=float, default=0.1)
    parser.add_argument("--max-retries", type=int, default=3)
    parser.add_argument("--allow-test", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    rows = read_jsonl(args.input)
    if rows and any(row.get("split") == "test" for row in rows) and not args.allow_test:
        raise SystemExit(
            "Refusing to run on Test data without --allow-test. "
            "Freeze the prompt on Train/Dev first."
        )
    if args.limit > 0:
        rows = rows[: args.limit]

    prompt = json.loads(args.prompt.read_text(encoding="utf-8"))
    labels = set(prompt["labels"])
    completed = load_completed(args.output)
    pending = [row for row in rows if row["sample_id"] not in completed]

    if args.dry_run:
        preview = []
        for row in pending[:3]:
            preview.append(
                {
                    "sample_id": row["sample_id"],
                    "system_prompt": prompt["system_prompt"],
                    "user_prompt": prompt["user_template"].format(
                        recent_context=json.dumps(
                            row.get("recent_context", []), ensure_ascii=False
                        ),
                        text=row["text"],
                    ),
                }
            )
        print(
            json.dumps(
                {
                    "prompt": prompt["name"],
                    "input_samples": len(rows),
                    "already_completed": len(completed),
                    "pending": len(pending),
                    "preview": preview,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return

    if not args.api_key:
        raise SystemExit("LLM_API_KEY is required unless --dry-run is used.")
    client = OpenAI(api_key=args.api_key, base_url=args.base_url, timeout=90)

    failures = 0
    for index, row in enumerate(pending, start=1):
        user_prompt = prompt["user_template"].format(
            recent_context=json.dumps(
                row.get("recent_context", []), ensure_ascii=False
            ),
            text=row["text"],
        )
        last_error = None
        for attempt in range(1, args.max_retries + 1):
            try:
                response = client.chat.completions.create(
                    model=args.model,
                    messages=[
                        {"role": "system", "content": prompt["system_prompt"]},
                        {"role": "user", "content": user_prompt},
                    ],
                    response_format={"type": "json_object"},
                    temperature=0,
                    extra_body={"thinking": {"type": "disabled"}},
                )
                raw = json.loads(response.choices[0].message.content or "{}")
                predicted = raw.get("behavior_type")
                if predicted not in labels:
                    raise ValueError(f"unsupported behavior_type: {predicted!r}")
                append_jsonl(
                    args.output,
                    {
                        **row,
                        "mapping_predicted_label": row.get("predicted_label", ""),
                        "predicted_label": predicted,
                        "prediction_confidence": float(raw.get("confidence", 0)),
                        "prediction_explanation": str(raw.get("explanation", "")),
                        "prediction_evidence": str(raw.get("evidence_text", "")),
                        "prediction_method": "llm",
                        "prediction_prompt": prompt["name"],
                        "prediction_prompt_version": prompt["version"],
                        "prediction_model": args.model,
                    },
                )
                last_error = None
                break
            except Exception as error:  # keep batch resumable across transient failures
                last_error = error
                if attempt < args.max_retries:
                    time.sleep(attempt)
        if last_error is not None:
            failures += 1
            print(f"[failed] {row['sample_id']}: {last_error}")
        elif index % 50 == 0 or index == len(pending):
            print(f"[progress] {index}/{len(pending)}")
        time.sleep(args.sleep)

    print(
        json.dumps(
            {
                "prompt": prompt["name"],
                "requested": len(pending),
                "failures": failures,
                "output": str(args.output),
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
