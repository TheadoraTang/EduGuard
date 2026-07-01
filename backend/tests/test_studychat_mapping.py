import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

from import_studychat import map_label


def test_studychat_direct_mappings():
    assert map_label("Conceptual Questions>Definition")[0] == "concept_understanding"
    assert (
        map_label("Contextual Questions>Assignment Clarification")[0]
        == "task_clarification"
    )
    assert map_label("Verification>Check Answer")[0] == "reflection_verification"


def test_write_code_is_only_a_candidate_and_context_is_evidence():
    assert map_label("Writing>Write Code") == ("answer_seeking", "candidate_only")
    assert map_label("writing_request>Write English") == (
        "answer_seeking",
        "candidate_only",
    )
    assert map_label("Context>Error Message") == (None, "personal_attempt_evidence")
    assert map_label("provide_context>Code") == (None, "personal_attempt_evidence")
    assert map_label("editing_request>Edit Code") == ("debugging_help", "weak")
    assert map_label("Off Topic>Other") == (None, "excluded")
