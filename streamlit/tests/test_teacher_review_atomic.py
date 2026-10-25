import unittest
from unittest.mock import patch

from helpers import teacher_student_integration as tsi


class _Result:
    data = {"review_id": 17, "score_pct": 100}


class _Rpc:
    def __init__(self):
        self.calls = []

    def rpc(self, name, payload):
        self.calls.append((name, payload))
        return self

    def execute(self):
        return _Result()


class TeacherReviewAtomicTests(unittest.TestCase):
    def test_question_keys_become_answer_ids_for_one_rpc(self):
        client = _Rpc()
        detail = {"practice_session_id": 31, "student_id": "student-1", "items": [{"question_key": "0:1", "exercise_idx": 0, "question_idx": 1}]}
        with (
            patch.object(tsi, "get_current_user_id", return_value="teacher-1"),
            patch.object(tsi, "load_teacher_review_request_detail", return_value=detail),
            patch.object(tsi, "_load_practice_answers_map", return_value={(0, 1): {"id": 88}}),
            patch.object(tsi, "get_sb", return_value=client),
            patch.object(tsi, "_clear_teacher_student_caches"),
        ):
            result = tsi.submit_teacher_review(17, {"0:1": "correct"}, "Good work")
        self.assertEqual((True, "teacher_review_saved"), result)
        self.assertEqual([("classio_submit_teacher_review_oidc", {"p_review_id": 17, "p_overrides": {"88": "correct"}, "p_teacher_feedback": "Good work", "p_teacher_id": "teacher-1"})], client.calls)

    def test_unknown_answer_is_rejected_before_write(self):
        client = _Rpc()
        detail = {"practice_session_id": 31, "student_id": "student-1", "items": []}
        with (
            patch.object(tsi, "get_current_user_id", return_value="teacher-1"),
            patch.object(tsi, "load_teacher_review_request_detail", return_value=detail),
            patch.object(tsi, "_load_practice_answers_map", return_value={}),
            patch.object(tsi, "get_sb", return_value=client),
        ):
            result = tsi.submit_teacher_review(17, {"0:1": "correct"})
        self.assertEqual((False, "teacher_review_save_failed"), result)
        self.assertEqual([], client.calls)

    def test_missing_legacy_answer_with_keep_is_ignored(self):
        client = _Rpc()
        detail = {"practice_session_id": 31, "student_id": "student-1", "items": [{"question_key": "0:1", "exercise_idx": 0, "question_idx": 1}]}
        with (
            patch.object(tsi, "get_current_user_id", return_value="teacher-1"),
            patch.object(tsi, "load_teacher_review_request_detail", return_value=detail),
            patch.object(tsi, "_load_practice_answers_map", return_value={}),
            patch.object(tsi, "get_sb", return_value=client),
            patch.object(tsi, "_clear_teacher_student_caches"),
        ):
            result = tsi.submit_teacher_review(17, {"0:1": "keep"})
        self.assertEqual((True, "teacher_review_saved"), result)
        self.assertEqual({}, client.calls[0][1]["p_overrides"])


if __name__ == "__main__":
    unittest.main()
