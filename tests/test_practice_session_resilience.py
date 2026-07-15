import unittest
import sys
from unittest.mock import patch
from types import ModuleType

if "streamlit" not in sys.modules:
    fake_streamlit = ModuleType("streamlit")
    fake_streamlit.session_state = {}
    sys.modules["streamlit"] = fake_streamlit

from helpers import practice_engine


class PracticeSessionResilienceTests(unittest.TestCase):
    def test_invalid_multiple_choice_answer_is_dropped_before_widget_restore(self):
        exercise_data = {
            "exercises": [
                {
                    "type": "multiple_choice",
                    "questions": [{"stem": "Pick one", "options": ["A", "B"]}],
                }
            ]
        }

        with patch.object(practice_engine.st, "session_state", {"sp_0_0": "C"}):
            practice_engine._restore_practice_widget_state_from_answers(
                exercise_data,
                {"sp_0_0": "C"},
                "sp",
            )
            self.assertNotIn("sp_0_0", practice_engine.st.session_state)

    def test_valid_multiple_choice_answer_is_preserved_on_restore(self):
        exercise_data = {
            "exercises": [
                {
                    "type": "multiple_choice",
                    "questions": [{"stem": "Pick one", "options": ["A", "B"]}],
                }
            ]
        }

        with patch.object(practice_engine.st, "session_state", {}):
            practice_engine._restore_practice_widget_state_from_answers(
                exercise_data,
                {"sp_0_0": "B"},
                "sp",
            )
            self.assertEqual(practice_engine.st.session_state.get("sp_0_0"), "B")


if __name__ == "__main__":
    unittest.main()
