import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

from prepare_mathdial_review import disclosure_candidate, infer_strategy, stable_split


def test_dialog_acts_map_to_scaffold_strategies():
    assert infer_strategy("Where did that number come from?", "focus")[0] == "error_focus"
    assert infer_strategy("What should you do next?", "probing")[0] == "probing_question"
    assert infer_strategy("Let me explain the calculation.", "telling")[0] == "direct_explanation"


def test_missing_dialog_act_uses_text_heuristics():
    assert infer_strategy("Good start. What is the total ratio?", "")[0] == "feedback_prompt"
    assert infer_strategy("How did you get 12?", "")[0] == "probing_question"


def test_split_and_disclosure_checks_are_deterministic():
    assert stable_split("same problem") == stable_split("same problem")
    assert disclosure_candidate("Therefore the answer is 10.", "Work\n10")
    assert not disclosure_candidate("What should you calculate next?", "Work\n10")
