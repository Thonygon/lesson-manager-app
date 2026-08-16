import unittest
from unittest.mock import patch

from app_pages import student_assignments
from app_pages import student_practice


class StudentAssignmentContentFallbackTests(unittest.TestCase):
    def test_assignment_session_match_rejects_a_different_resource(self):
        self.assertTrue(
            student_assignments._practice_session_matches_assignment(
                {"source_type": "worksheet", "source_id": "228"},
                assignment_id=228,
                source_record_id=175,
                assignment_type="worksheet",
            )
        )
        self.assertFalse(
            student_assignments._practice_session_matches_assignment(
                {"source_type": "worksheet", "source_id": "178"},
                assignment_id=228,
                source_record_id=175,
                assignment_type="worksheet",
            )
        )

    def test_proactive_practice_clears_stale_assignment_context(self):
        session_state = {
            "_practice_assignment_id": 228,
            "_practice_assignment_type": "worksheet",
        }
        exercise_data = {
            "source_type": "worksheet",
            "source_id": 178,
            "exercises": [{"type": "short_answer", "questions": ["Question"], "answers": ["Answer"]}],
        }
        with (
            patch.object(student_practice, "normalize_exercise_data_for_web", side_effect=lambda value: value),
            patch.object(student_practice, "load_in_progress_practice_session", return_value={}),
            patch.object(student_practice.st, "session_state", session_state),
        ):
            opened = student_practice._open_practice_item(exercise_data)

        self.assertTrue(opened)
        self.assertNotIn("_practice_assignment_id", session_state)
        self.assertNotIn("_practice_assignment_type", session_state)

    def test_assignment_practice_falls_back_to_full_worksheet_record(self):
        assignment_row = {
            "id": 11,
            "assignment_type": "worksheet",
            "source_record_id": 77,
            "content_snapshot": {
                "worksheet": {},
                "meta": {"learner_stage": "A1", "level_or_band": "A1"},
            },
            "subject_key": "english",
            "topic": "Pronouns",
        }

        with (
            patch.object(student_assignments, "normalize_worksheet_output", side_effect=lambda value: value),
            patch.object(student_assignments, "worksheet_has_ready_visuals", return_value=False),
            patch.object(student_assignments, "_load_source_worksheet", return_value={}),
            patch.object(student_assignments, "load_worksheet_record", return_value={"worksheet_json": {"questions": ["Q1"]}}),
            patch.object(
                student_assignments,
                "worksheet_to_exercises",
                side_effect=lambda worksheet, **_: {"exercises": [1]} if worksheet.get("questions") else {"exercises": []},
            ),
            patch.object(student_assignments, "persist_assignment_content_snapshot") as persist_snapshot,
            patch.object(student_assignments, "load_in_progress_practice_session", return_value=None),
            patch.object(student_assignments, "mark_assignment_started"),
            patch.object(student_assignments, "go_to"),
            patch.object(student_assignments.st, "rerun", create=True),
            patch.object(student_assignments.st, "warning", create=True) as warning_mock,
        ):
            student_assignments._open_assignment_practice(assignment_row)

        warning_mock.assert_not_called()
        persist_snapshot.assert_called_once()

    def test_assignment_practice_falls_back_to_full_exam_record_with_answer_key(self):
        assignment_row = {
            "id": 21,
            "assignment_type": "exam",
            "source_record_id": 88,
            "content_snapshot": {
                "exam_data": {"sections": [{"type": "multiple_choice"}]},
                "answer_key": {},
                "meta": {"learner_stage": "A2", "level_or_band": "A2"},
            },
            "subject_key": "english",
            "topic": "Pronouns",
        }

        with (
            patch.object(student_assignments, "exam_has_ready_visuals", return_value=True),
            patch.object(
                student_assignments,
                "exam_to_exercises",
                side_effect=lambda exam_data, answer_key, **_: {"exercises": [1]} if answer_key else {"exercises": []},
            ),
            patch.object(
                student_assignments,
                "_load_source_exam_bundle",
                return_value=(
                    {"sections": [{"type": "multiple_choice"}]},
                    {"sections": [{"answers": ["A"]}]},
                ),
            ),
            patch.object(student_assignments, "persist_assignment_content_snapshot") as persist_snapshot,
            patch.object(student_assignments, "load_in_progress_practice_session", return_value=None),
            patch.object(student_assignments, "mark_assignment_started"),
            patch.object(student_assignments, "go_to"),
            patch.object(student_assignments.st, "rerun", create=True),
            patch.object(student_assignments.st, "warning", create=True) as warning_mock,
        ):
            student_assignments._open_assignment_practice(assignment_row)

        warning_mock.assert_not_called()
        persist_snapshot.assert_called_once()

    def test_review_completed_assignment_uses_latest_exam_answer_key_not_stale_session_payload(self):
        assignment_row = {
            "id": 21,
            "assignment_type": "exam",
            "source_record_id": 88,
            "content_snapshot": {
                "exam_data": {"sections": [{"type": "multiple_choice"}]},
                "answer_key": {"sections": [{"answers": ["A"]}]},
                "meta": {"learner_stage": "A2", "level_or_band": "A2"},
            },
            "subject_key": "english",
            "topic": "Pronouns",
        }
        completed_session = {
            "id": 501,
            "exercise_data": {
                "source_type": "exam",
                "source_id": 21,
                "exercises": [{"answers": [""]}],
            },
        }
        rebuilt_exercise_data = {
            "source_type": "exam",
            "source_id": 21,
            "exercises": [{"answers": ["A"]}],
        }
        session_state = {}

        with (
            patch.object(student_assignments, "exam_has_ready_visuals", return_value=True),
            patch.object(student_assignments, "exam_to_exercises", return_value=rebuilt_exercise_data),
            patch.object(student_assignments, "_latest_completed_assignment_session", return_value=completed_session),
            patch.object(
                student_assignments,
                "load_practice_review_state",
                return_value={
                    "answers": {"sp_0_0": "A"},
                    "questions": {"sp_0_0": {"is_correct": True, "expected": "A"}},
                    "summary": {"score_pct": 100, "correct_count": 1, "total_questions": 1},
                },
            ),
            patch.object(student_assignments, "normalize_exercise_data_for_web", side_effect=lambda value: value),
            patch.object(student_assignments, "go_to"),
            patch.object(student_assignments.st, "rerun", create=True),
            patch.object(student_assignments.st, "session_state", session_state),
        ):
            student_assignments._open_assignment_practice(assignment_row, review_completed=True)

        self.assertEqual(
            {
                **rebuilt_exercise_data,
                "assignment_id": 21,
                "resource_record_id": 88,
            },
            session_state["practice_exercise_data"],
        )
        self.assertEqual(
            {"sp_0_0": "A"},
            session_state["_practice_resume_answers"],
        )
        self.assertTrue(session_state["_practice_review_mode"])

    def test_assignment_practice_prefers_latest_exam_source_over_stale_snapshot(self):
        assignment_row = {
            "id": 31,
            "assignment_type": "exam",
            "source_record_id": 99,
            "content_snapshot": {
                "exam_data": {"sections": [{"type": "multiple_choice"}]},
                "answer_key": {"sections": [{"answers": [""]}]},
                "meta": {"learner_stage": "A2", "level_or_band": "A2"},
            },
            "subject_key": "english",
            "topic": "Family",
        }
        latest_exam_data = {"sections": [{"type": "multiple_choice"}]}
        latest_answer_key = {"sections": [{"answers": ["B"]}]}

        with (
            patch.object(student_assignments, "exam_has_ready_visuals", return_value=True),
            patch.object(
                student_assignments,
                "_load_source_exam_bundle",
                return_value=(latest_exam_data, latest_answer_key),
            ),
            patch.object(
                student_assignments,
                "exam_to_exercises",
                side_effect=lambda exam_data, answer_key, **_: {"exercises": [answer_key["sections"][0]["answers"][0]]},
            ),
            patch.object(student_assignments, "persist_assignment_content_snapshot") as persist_snapshot,
            patch.object(student_assignments, "load_in_progress_practice_session", return_value=None),
            patch.object(student_assignments, "mark_assignment_started"),
            patch.object(student_assignments, "go_to"),
            patch.object(student_assignments.st, "rerun", create=True),
            patch.object(student_assignments.st, "warning", create=True) as warning_mock,
        ):
            student_assignments._open_assignment_practice(assignment_row)

        warning_mock.assert_not_called()
        persist_snapshot.assert_called()
        self.assertEqual(
            ["B"],
            student_assignments.st.session_state["practice_exercise_data"]["exercises"],
        )

    def test_assignment_practice_resume_uses_current_exam_data_not_stale_draft_payload(self):
        assignment_row = {
            "id": 41,
            "assignment_type": "exam",
            "source_record_id": 99,
            "content_snapshot": {
                "exam_data": {"sections": [{"type": "multiple_choice"}]},
                "answer_key": {"sections": [{"answers": [""]}]},
                "meta": {"learner_stage": "A2", "level_or_band": "A2"},
            },
            "subject_key": "english",
            "topic": "Family",
        }
        latest_exercise_data = {
            "source_type": "exam",
            "source_id": 41,
            "exercises": [{"answers": ["B"]}],
        }
        draft = {
            "id": 801,
            "exercise_data": {
                "source_type": "exam",
                "source_id": 41,
                "exercises": [{"answers": [""]}],
            },
        }
        session_state = {}

        with (
            patch.object(student_assignments, "exam_has_ready_visuals", return_value=True),
            patch.object(
                student_assignments,
                "_load_source_exam_bundle",
                return_value=(
                    {"sections": [{"type": "multiple_choice"}]},
                    {"sections": [{"answers": ["B"]}]},
                ),
            ),
            patch.object(student_assignments, "exam_to_exercises", return_value=latest_exercise_data),
            patch.object(student_assignments, "load_in_progress_practice_session", return_value=draft),
            patch.object(student_assignments, "load_practice_draft_answers", return_value={"sp_0_0": "A"}),
            patch.object(student_assignments, "normalize_exercise_data_for_web", side_effect=lambda value: value),
            patch.object(student_assignments, "mark_assignment_started"),
            patch.object(student_assignments, "go_to"),
            patch.object(student_assignments.st, "rerun", create=True),
            patch.object(student_assignments.st, "warning", create=True) as warning_mock,
            patch.object(student_assignments.st, "session_state", session_state),
        ):
            student_assignments._open_assignment_practice(assignment_row)

        warning_mock.assert_not_called()
        self.assertEqual(
            {
                **latest_exercise_data,
                "assignment_id": 41,
                "resource_record_id": 99,
            },
            session_state["practice_exercise_data"],
        )
        self.assertEqual({"sp_0_0": "A"}, session_state["_practice_resume_answers"])


if __name__ == "__main__":
    unittest.main()
