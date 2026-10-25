import unittest
from unittest.mock import patch

from helpers import practice_engine


class _Rows:
    def __init__(self, rows):
        self.data = rows


class _Reviews:
    def __init__(self, rows):
        self.rows = rows

    def table(self, name):
        assert name == "teacher_review_requests"
        return self

    def select(self, *args):
        return self

    def in_(self, *args):
        return self

    def eq(self, *args):
        return self

    def execute(self):
        return _Rows(self.rows)


class TeacherReviewOverrideRegradeTests(unittest.TestCase):
    def test_rpc_answer_ids_resolve_to_saved_positions_for_regrade(self):
        reviews = [{"practice_session_id": 31, "status": "reviewed", "reviewed_at": "2026-10-25T12:00:00Z",
                    "review_payload": {"answer_overrides": {"88": "correct", "89": "incorrect", "90": "keep", "999": "correct"}}}]
        answers = {31: [{"id": 88, "exercise_idx": 0, "question_idx": 1},
                        {"id": 89, "exercise_idx": 2, "question_idx": 0},
                        {"id": 90, "exercise_idx": 2, "question_idx": 1}]}
        with patch.object(practice_engine, "get_sb", return_value=_Reviews(reviews)):
            result = practice_engine._teacher_overrides_by_session([31], answers)
        self.assertEqual({31: {(0, 1): True, (2, 0): False}}, result)

    def test_legacy_positional_items_remain_supported(self):
        result = practice_engine._resolved_teacher_overrides(
            {"items": [{"question_key": "0:2", "override": "incorrect", "final_correct": False}]}, []
        )
        self.assertEqual({(0, 2): False}, result)

    def test_id_decision_wins_when_both_formats_exist(self):
        result = practice_engine._resolved_teacher_overrides(
            {"items": [{"question_key": "0:2", "override": "incorrect", "final_correct": False}],
             "answer_overrides": {"88": "correct"}},
            [{"id": 88, "exercise_idx": 0, "question_idx": 2}],
        )
        self.assertEqual({(0, 2): True}, result)

    def test_corrected_answer_key_cannot_erase_manual_credit(self):
        saved = [{"id": 88, "session_id": 31, "user_id": "student-1", "exercise_idx": 0,
                  "question_idx": 0, "exercise_type": "fill_in_blank", "student_answer": "old answer"}]
        overrides = practice_engine._resolved_teacher_overrides(
            {"answer_overrides": {"88": "correct"}}, saved
        )
        rescored, stats = practice_engine._evaluate_saved_practice_answers(
            {"exercises": [{"type": "fill_in_blank", "questions": ["Question"],
                            "answers": ["new answer"]}]},
            saved,
            teacher_overrides=overrides,
        )
        self.assertTrue(rescored[0]["is_correct"])
        self.assertEqual(1, stats["correct_count"])


if __name__ == "__main__":
    unittest.main()
