import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

from prepare_bench2026_single_annotator import (  # noqa: E402
    ANNOTATION_FIELDS,
    RETEST_PER_SILVER_STRATUM,
    prepare_formal,
    prepare_retest,
    select_retest_rows,
    validate_formal_rows,
)


LABELS = [
    "answer_seeking",
    "concept_understanding",
    "debugging_help",
    "reflection_verification",
    "task_clarification",
]


def make_rows() -> tuple[list[dict], list[dict]]:
    formal = []
    private = []
    for label_index, label in enumerate(LABELS):
        for index in range(110):
            annotation_id = f"BG26-{label_index:02d}-{index:03d}"
            formal.append(
                {
                    "annotation_id": annotation_id,
                    "phase": "formal",
                    "order": len(formal) + 1,
                    "semester": "f24" if index % 2 else "s25",
                    "topic": f"a{1 + index % 7}",
                    "prior_student_messages": [],
                    "student_message": f"message {label}-{index}",
                    **{field: "" for field in ANNOTATION_FIELDS},
                }
            )
            private.append(
                {
                    "annotation_id": annotation_id,
                    "phase": "formal",
                    "sample_id": f"sample-{label_index}-{index}",
                    "chat_id_hash": f"chat-{label_index}-{index // 2}",
                    "user_id_hash": f"user-{index % 20}",
                    "silver_label": label,
                }
            )
    return formal, private


def test_formal_shuffle_is_deterministic_and_clears_annotations():
    rows, _ = make_rows()
    validate_formal_rows(rows)
    rows[0]["behavior_label"] = "answer_seeking"
    rows[0]["review_notes"] = "temporary"
    rows[0]["behavior_label"] = ""
    rows[0]["review_notes"] = ""
    first = prepare_formal(rows, seed=20260909)
    second = prepare_formal(rows, seed=20260909)
    assert [row["annotation_id"] for row in first] == [
        row["annotation_id"] for row in second
    ]
    assert all(not row[field] for row in first for field in ANNOTATION_FIELDS)


def test_retest_has_twelve_rows_per_silver_stratum_and_alias_ids():
    rows, private = make_rows()
    formal = prepare_formal(rows, seed=20260909)
    selected = select_retest_rows(formal, private, seed=20260910)
    retest, mapping = prepare_retest(selected, private, seed=20260911)

    assert len(retest) == RETEST_PER_SILVER_STRATUM * len(LABELS)
    assert Counter(row["silver_label"] for row in mapping) == {
        label: RETEST_PER_SILVER_STRATUM for label in LABELS
    }
    assert {row["annotation_id"] for row in formal}.isdisjoint(
        row["annotation_id"] for row in retest
    )
    formal_by_id = {row["annotation_id"]: row for row in formal}
    mapping_by_alias = {row["retest_annotation_id"]: row for row in mapping}
    for row in retest:
        source = formal_by_id[mapping_by_alias[row["annotation_id"]]["formal_annotation_id"]]
        assert row["student_message"] == source["student_message"]
        assert row["phase"] == "delayed_retest"


def test_validate_rejects_prefilled_formal_annotations():
    rows, _ = make_rows()
    rows[0]["behavior_label"] = "answer_seeking"
    try:
        validate_formal_rows(rows)
    except ValueError as exc:
        assert "already contains annotations" in str(exc)
    else:
        raise AssertionError("Expected prefilled formal annotations to be rejected")
