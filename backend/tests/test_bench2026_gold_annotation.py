import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

from prepare_bench2026_gold_annotation import (  # noqa: E402
    BLINDED_FIELDS,
    FORBIDDEN_BLINDED_FIELDS,
    LABEL_QUOTAS,
    PILOT_PER_LABEL,
    attach_prior_student_messages,
    balanced_label_sample,
    make_annotator_payload,
    split_pilot_formal,
)


def make_rows() -> list[dict]:
    rows = []
    for label_index, (label, quota) in enumerate(LABEL_QUOTAS.items()):
        for index in range(quota + 15):
            rows.append(
                {
                    "sample_id": f"sample-{label_index}-{index}",
                    "chat_id_hash": f"chat-{label_index}-{index // 3}",
                    "user_id_hash": f"user-{index % 12}",
                    "reviewed_label": label,
                    "text": f"message {label_index}-{index}",
                    "split": "test",
                    "semester": "f24" if index % 2 else "s25",
                    "topic": f"a{1 + index % 4}",
                }
            )
    return rows


def test_sampling_is_deterministic_and_hits_declared_quotas():
    rows = attach_prior_student_messages(make_rows())
    first = balanced_label_sample(rows, LABEL_QUOTAS, seed=20260908)
    second = balanced_label_sample(rows, LABEL_QUOTAS, seed=20260908)
    assert [row["sample_id"] for row in first] == [row["sample_id"] for row in second]
    assert Counter(row["reviewed_label"] for row in first) == Counter(LABEL_QUOTAS)


def test_pilot_and_formal_are_disjoint_with_fixed_pilot_coverage():
    selected = balanced_label_sample(
        attach_prior_student_messages(make_rows()), LABEL_QUOTAS, seed=20260908
    )
    pilot, formal = split_pilot_formal(selected, PILOT_PER_LABEL, seed=20260918)
    assert len(pilot) == PILOT_PER_LABEL * len(LABEL_QUOTAS)
    assert len(formal) == sum(LABEL_QUOTAS.values()) - len(pilot)
    assert Counter(row["reviewed_label"] for row in pilot) == {
        label: PILOT_PER_LABEL for label in LABEL_QUOTAS
    }
    assert {row["sample_id"] for row in pilot}.isdisjoint(
        row["sample_id"] for row in formal
    )


def test_blinded_payloads_match_membership_without_leaking_labels_or_ids():
    selected = balanced_label_sample(
        attach_prior_student_messages(make_rows()), LABEL_QUOTAS, seed=20260908
    )
    pilot, _ = split_pilot_formal(selected, PILOT_PER_LABEL, seed=20260918)
    annotator_a = make_annotator_payload(pilot, "pilot", 20260908, 101)
    annotator_b = make_annotator_payload(pilot, "pilot", 20260908, 201)

    assert {row["annotation_id"] for row in annotator_a} == {
        row["annotation_id"] for row in annotator_b
    }
    assert [row["annotation_id"] for row in annotator_a] != [
        row["annotation_id"] for row in annotator_b
    ]
    for row in annotator_a + annotator_b:
        assert tuple(row) == BLINDED_FIELDS
        assert not (FORBIDDEN_BLINDED_FIELDS & row.keys())
        assert row["behavior_label"] == ""


def test_prior_context_contains_only_earlier_student_messages():
    rows = [
        {
            "sample_id": f"sample-{index}",
            "chat_id_hash": "one-chat",
            "user_id_hash": "one-user",
            "reviewed_label": "answer_seeking",
            "text": f"turn {index}",
            "split": "test",
        }
        for index in range(1, 7)
    ]
    enriched = attach_prior_student_messages(rows, max_prior=4)
    assert enriched[0]["prior_student_messages"] == []
    assert enriched[-1]["prior_student_messages"] == [
        "turn 2",
        "turn 3",
        "turn 4",
        "turn 5",
    ]
