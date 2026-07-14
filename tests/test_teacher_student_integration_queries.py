import unittest
from unittest.mock import patch

from helpers import teacher_student_integration as tsi


class _FakeResult:
    def __init__(self, data):
        self.data = data


class _FakeQuery:
    def __init__(self, table_name, log, data):
        self.table_name = table_name
        self.log = log
        self.data = data
        self.ops = []
        self.log.append(self)

    def select(self, value):
        self.ops.append(("select", value))
        return self

    def eq(self, column, value):
        self.ops.append(("eq", column, value))
        return self

    def neq(self, column, value):
        self.ops.append(("neq", column, value))
        return self

    def in_(self, column, value):
        self.ops.append(("in", column, tuple(value)))
        return self

    def order(self, column, desc=False):
        self.ops.append(("order", column, desc))
        return self

    def limit(self, value):
        self.ops.append(("limit", value))
        return self

    def execute(self):
        return _FakeResult(self.data)


class _FakeSupabase:
    def __init__(self, table_data=None):
        self.table_data = table_data or {}
        self.table_log = []

    def table(self, table_name):
        return _FakeQuery(table_name, self.table_log, self.table_data.get(table_name, []))


class TeacherStudentIntegrationQueryTests(unittest.TestCase):
    def tearDown(self):
        tsi._load_active_linked_students_for_teacher_cached.clear()
        tsi._load_student_teacher_links_cached.clear()
        tsi._load_student_assignments_cached.clear()
        tsi._load_teacher_assignment_progress_cached.clear()
        tsi._load_teacher_review_requests_cached.clear()

    def test_teacher_student_rows_use_explicit_student_columns(self):
        fake_sb = _FakeSupabase(
            table_data={
                "students": [
                    {
                        "id": 1,
                        "user_id": "teacher-1",
                        "student": "Ana",
                        "email": "ana@example.com",
                        "linked_student_user_id": "",
                        "teacher_student_link_id": None,
                        "student_source": "manual",
                    }
                ]
            }
        )

        with patch.object(tsi, "get_sb", return_value=fake_sb):
            rows = tsi._load_teacher_student_rows("teacher-1")

        self.assertEqual(["Ana"], [row["student"] for row in rows])
        query = fake_sb.table_log[0]
        self.assertEqual(tsi._STUDENT_RECORD_COLUMNS, query.ops[0][1])
        self.assertIn(("eq", "user_id", "teacher-1"), query.ops)

    def test_student_assignments_loader_is_scoped_and_uses_summary_columns(self):
        fake_sb = _FakeSupabase(
            table_data={
                "teacher_assignments": [
                    {
                        "id": 41,
                        "teacher_id": "teacher-1",
                        "student_id": "student-1",
                        "title": "Review worksheet",
                        "status": "assigned",
                        "subject_key": "english",
                        "subject_label": "English",
                        "teacher_note": "<div>Great effort</div>",
                    }
                ]
            }
        )

        with (
            patch.object(tsi, "get_sb", return_value=fake_sb),
            patch.object(tsi, "_load_profiles_map", return_value={"teacher-1": {"display_name": "Teacher One"}}),
        ):
            rows = tsi._load_student_assignments_cached("student-1", ())

        self.assertEqual(1, len(rows))
        self.assertEqual("Teacher One", rows[0]["teacher_name"])
        query = fake_sb.table_log[0]
        self.assertEqual(tsi._ASSIGNMENT_LIST_COLUMNS, query.ops[0][1])
        self.assertIn(("eq", "student_id", "student-1"), query.ops)
        self.assertIn(("neq", "status", "archived"), query.ops)

    def test_review_detail_uses_explicit_review_session_and_answer_columns(self):
        fake_sb = _FakeSupabase(
            table_data={
                "teacher_review_requests": [
                    {
                        "id": 7,
                        "teacher_id": "teacher-1",
                        "student_id": "student-1",
                        "practice_session_id": 55,
                        "request_note": "Please review",
                        "teacher_feedback": "",
                    }
                ],
                "practice_sessions": [
                    {
                        "id": 55,
                        "user_id": "student-1",
                        "exercise_data": {"exercises": []},
                        "completed_at": None,
                        "correct_count": 0,
                        "score_pct": 0,
                    }
                ],
                "practice_answers": [],
            }
        )

        with (
            patch.object(tsi, "get_sb", return_value=fake_sb),
            patch.object(tsi, "get_current_user_id", return_value="teacher-1"),
            patch.object(tsi, "_load_profiles_map", return_value={"student-1": {"display_name": "Student One"}}),
        ):
            detail = tsi.load_teacher_review_request_detail(7)

        self.assertIsInstance(detail, dict)
        review_query = next(query for query in fake_sb.table_log if query.table_name == "teacher_review_requests")
        session_query = next(query for query in fake_sb.table_log if query.table_name == "practice_sessions")
        answer_query = next(query for query in fake_sb.table_log if query.table_name == "practice_answers")
        self.assertEqual(tsi._REVIEW_REQUEST_COLUMNS, review_query.ops[0][1])
        self.assertEqual(tsi._PRACTICE_SESSION_COLUMNS, session_query.ops[0][1])
        self.assertEqual(tsi._PRACTICE_ANSWER_COLUMNS, answer_query.ops[0][1])


if __name__ == "__main__":
    unittest.main()
