"""Run EduGuard's deterministic classifier over a reviewed StudyChat JSONL."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.services.analysis import classify_with_rules


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("path", type=Path)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/processed/studychat_rules_300.jsonl"),
    )
    args = parser.parse_args()

    rows = []
    for line in args.path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        result = classify_with_rules(row["text"])
        row["mapping_predicted_label"] = row.get("predicted_label")
        row["predicted_label"] = result.behavior_type
        row["prediction_method"] = result.method
        row["prediction_confidence"] = result.confidence
        row["prediction_explanation"] = result.explanation
        row["prediction_evidence"] = result.evidence_text
        rows.append(row)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(json.dumps({"output": str(args.output), "samples": len(rows)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
