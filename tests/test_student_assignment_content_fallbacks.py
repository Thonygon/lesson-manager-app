import unittest
from unittest.mock import patch

from app_pages import student_assignments


class StudentAssignmentContentFallbackTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
