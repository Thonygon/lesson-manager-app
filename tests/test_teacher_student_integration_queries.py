import unittest
from unittest.mock import patch
from streamlit.testing.v1 import AppTest

from helpers import teacher_student_integration as tsi
from helpers import quick_exam_storage, worksheet_storage
from helpers import video_library


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
        tsi._load_student_assignments_by_ids_cached.clear()
        tsi._load_teacher_assignment_progress_cached.clear()
        tsi._load_teacher_review_requests_cached.clear()
        video_library._load_public_videos_cached.clear()

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

    def test_student_assignment_by_id_uses_direct_scoped_lookup(self):
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
                        "teacher_note": "Great effort",
                    }
                ]
            }
        )

        with (
            patch.object(tsi, "get_sb", return_value=fake_sb),
            patch.object(tsi, "get_current_user_id", return_value="student-1"),
            patch.object(tsi, "_load_profiles_map", return_value={"teacher-1": {"display_name": "Teacher One"}}),
        ):
            row = tsi.load_student_assignment_by_id(41)

        self.assertEqual(41, row["id"])
        query = fake_sb.table_log[0]
        self.assertEqual(tsi._ASSIGNMENT_LIST_COLUMNS, query.ops[0][1])
        self.assertIn(("eq", "student_id", "student-1"), query.ops)
        self.assertIn(("in", "id", (41,)), query.ops)

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
        self.assertIn("source_type", tsi._PRACTICE_SESSION_COLUMNS)
        self.assertIn("source_id", tsi._PRACTICE_SESSION_COLUMNS)
        self.assertIn("subject", tsi._PRACTICE_SESSION_COLUMNS)
        self.assertIn("title", tsi._PRACTICE_SESSION_COLUMNS)
        self.assertNotIn("updated_at", tsi._PRACTICE_SESSION_COLUMNS)
        self.assertIn("answered_at", tsi._PRACTICE_ANSWER_COLUMNS)
        self.assertNotIn("created_at", tsi._PRACTICE_ANSWER_COLUMNS)

    def test_student_review_request_accepts_text_source_id_and_blank_assignment(self):
        inserted_payloads = []

        class InsertQuery:
            def __init__(self, table_name):
                self.table_name = table_name

            def select(self, *_args, **_kwargs):
                return self

            def eq(self, *_args, **_kwargs):
                return self

            def limit(self, *_args, **_kwargs):
                return self

            def insert(self, payload):
                inserted_payloads.append(payload)
                return self

            def execute(self):
                if self.table_name == "teacher_review_requests" and not inserted_payloads:
                    return _FakeResult([])
                return _FakeResult(inserted_payloads)

        class InsertSupabase:
            def table(self, table_name):
                return InsertQuery(table_name)

        session_row = {
            "id": 55,
            "user_id": "student-1",
            "source_type": "exam",
            "source_id": "0cf8ce5d-9b55-4705-a48f-4d74f11f6d9b",
            "subject": "english",
            "title": "Unit exam",
        }
        link_rows = [{"teacher_id": "teacher-1", "active_subjects": [{"subject_key": "english", "subject_label": "English"}]}]

        with (
            patch.object(tsi, "get_current_user_id", return_value="student-1"),
            patch.object(tsi, "_practice_session_row", return_value=session_row),
            patch.object(tsi, "get_reviewable_teacher_links_for_subject", return_value=link_rows),
            patch.object(tsi, "get_sb", return_value=InsertSupabase()),
            patch.object(tsi, "clear_app_caches", return_value=None),
        ):
            ok, msg = tsi.create_teacher_review_request(
                practice_session_id=55,
                teacher_id="teacher-1",
                assignment_id="",
                request_note="Please check question 2",
            )

        self.assertTrue(ok)
        self.assertEqual("teacher_review_requested", msg)
        self.assertEqual(1, len(inserted_payloads))
        payload = inserted_payloads[0]
        self.assertIsNone(payload["assignment_id"])
        self.assertEqual("0cf8ce5d-9b55-4705-a48f-4d74f11f6d9b", payload["source_id"])

    def test_load_exam_record_normalizes_float_identifier(self):
        captured = {}

        class Query:
            def select(self, *_args, **_kwargs):
                return self

            def eq(self, column, value):
                captured[column] = value
                return self

            def limit(self, *_args, **_kwargs):
                return self

            def execute(self):
                return _FakeResult([{"id": 99}])

        class Supabase:
            def table(self, _table_name):
                return Query()

        quick_exam_storage.load_exam_record.clear()
        try:
            with patch.object(quick_exam_storage, "get_sb", return_value=Supabase()):
                row = quick_exam_storage.load_exam_record(99.0)
        finally:
            quick_exam_storage.load_exam_record.clear()

        self.assertEqual(99, captured["id"])

    def test_public_video_loader_uses_lightweight_columns_and_preserves_image_fields(self):
        fake_sb = _FakeSupabase(
            table_data={
                "videos": [
                    {
                        "id": 9,
                        "user_id": "teacher-1",
                        "title": "Travel verbs",
                        "subject": "english",
                        "topic": "Travel",
                        "description": "Useful verbs",
                        "video_id": "abcdefghijk",
                        "youtube_url": "https://www.youtube.com/watch?v=abcdefghijk",
                        "watch_url": "https://www.youtube.com/watch?v=abcdefghijk",
                        "thumbnail_url": "https://img.youtube.com/vi/abcdefghijk/hqdefault.jpg",
                        "image_url": "https://example.com/image.png",
                        "cover_image_url": "https://example.com/cover.png",
                        "hero_image_url": "https://example.com/hero.png",
                        "learner_stage": "lower_secondary",
                        "level_or_band": "A2",
                        "level": "A2",
                        "student_material_language": "en",
                        "author_name": "",
                        "is_public": True,
                        "status": "active",
                        "created_at": "2026-08-01T00:00:00+00:00",
                        "updated_at": "2026-08-02T00:00:00+00:00",
                    }
                ]
            }
        )

        video_library._load_public_videos_cached.clear()
        try:
            with (
                patch.object(video_library, "get_sb", return_value=fake_sb),
                patch.object(video_library, "_profile_name_map", return_value={"teacher-1": {"display_name": "Teacher One"}}),
            ):
                df = video_library._load_public_videos_cached(limit=5)
        finally:
            video_library._load_public_videos_cached.clear()

        self.assertEqual(1, len(df))
        self.assertEqual("https://img.youtube.com/vi/abcdefghijk/hqdefault.jpg", df.iloc[0]["thumbnail_url"])
        query = fake_sb.table_log[0]
        self.assertEqual(video_library._VIDEO_LIST_COLUMNS, query.ops[0][1])
        self.assertIn(("eq", "is_public", True), query.ops)
        self.assertIn(("order", "updated_at", True), query.ops)
        self.assertIn(("limit", 5), query.ops)

    def test_load_worksheet_record_normalizes_float_identifier(self):
        captured = {}

        class Query:
            def select(self, *_args, **_kwargs):
                return self

            def eq(self, column, value):
                captured[column] = value
                return self

            def limit(self, *_args, **_kwargs):
                return self

            def execute(self):
                return _FakeResult([{"id": 42}])

        class Supabase:
            def table(self, _table_name):
                return Query()

        worksheet_storage.load_worksheet_record.clear()
        try:
            with patch.object(worksheet_storage, "get_sb", return_value=Supabase()):
                row = worksheet_storage.load_worksheet_record(42.0)
        finally:
            worksheet_storage.load_worksheet_record.clear()

        self.assertEqual(42, captured["id"])
        self.assertEqual(42, row["id"])

    def test_teacher_review_detail_prefers_latest_exam_source_over_stale_session_exercise_data(self):
        class Query:
            def __init__(self, table_name, rows_by_table):
                self.table_name = table_name
                self.rows_by_table = rows_by_table
                self.filters = []

            def select(self, *_args, **_kwargs):
                return self

            def eq(self, column, value):
                self.filters.append(("eq", column, value))
                return self

            def order(self, *_args, **_kwargs):
                return self

            def limit(self, *_args, **_kwargs):
                return self

            def execute(self):
                rows = list(self.rows_by_table.get(self.table_name, []))
                for _op, column, value in self.filters:
                    rows = [row for row in rows if str(row.get(column) or "") == str(value)]
                return _FakeResult(rows)

        class Supabase:
            def __init__(self):
                self.rows_by_table = {
                    "teacher_review_requests": [
                        {
                            "id": 7,
                            "teacher_id": "teacher-1",
                            "student_id": "student-1",
                            "assignment_id": 41,
                            "practice_session_id": 55,
                            "request_note": "Please review",
                            "teacher_feedback": "",
                        }
                    ],
                    "practice_sessions": [
                        {
                            "id": 55,
                            "user_id": "student-1",
                            "exercise_data": {"exercises": [{"questions": [{"text": "Old"}], "answers": [""]}]},
                            "completed_at": None,
                            "correct_count": 0,
                            "score_pct": 0,
                        }
                    ],
                    "teacher_assignments": [
                        {
                            "id": 41,
                            "student_id": "student-1",
                            "assignment_type": "exam",
                            "source_record_id": 88,
                            "content_snapshot": {
                                "exam_data": {"sections": [{"type": "multiple_choice"}]},
                                "answer_key": {"sections": [{"answers": [""]}]},
                            },
                        }
                    ],
                    "practice_answers": [
                        {
                            "id": 901,
                            "session_id": 55,
                            "user_id": "student-1",
                            "exercise_idx": 0,
                            "question_idx": 0,
                            "exercise_type": "multiple_choice",
                            "student_answer": "B",
                            "correct_answer": "",
                            "is_correct": False,
                            "answered_at": "2026-08-08T09:00:00+00:00",
                        }
                    ],
                }

            def table(self, table_name):
                return Query(table_name, self.rows_by_table)

        with (
            patch.object(tsi, "get_sb", return_value=Supabase()),
            patch.object(tsi, "get_current_user_id", return_value="teacher-1"),
            patch.object(tsi, "_load_profiles_map", return_value={"student-1": {"display_name": "Student One"}}),
            patch("helpers.quick_exam_storage.load_exam_record", return_value={"exam_data": {"sections": [{"type": "multiple_choice"}]}, "answer_key": {"sections": [{"answers": ["B"]}]}}),
            patch("helpers.practice_engine.exam_to_exercises", return_value={"exercises": [{"questions": [{"text": "Current"}], "answers": ["B"]}]}),
        ):
            detail = tsi.load_teacher_review_request_detail(7)

        self.assertEqual("B", detail["items"][0]["correct_answer"])
        self.assertEqual("Current", detail["items"][0]["prompt"])
        self.assertEqual(55, detail["session_row"]["id"])

    def test_teacher_review_detail_rebuilds_independent_exam_from_latest_source(self):
        class Query:
            def __init__(self, table_name, rows_by_table):
                self.table_name = table_name
                self.rows_by_table = rows_by_table
                self.filters = []

            def select(self, *_args, **_kwargs):
                return self

            def eq(self, column, value):
                self.filters.append(("eq", column, value))
                return self

            def order(self, *_args, **_kwargs):
                return self

            def limit(self, *_args, **_kwargs):
                return self

            def execute(self):
                rows = list(self.rows_by_table.get(self.table_name, []))
                for _op, column, value in self.filters:
                    rows = [row for row in rows if str(row.get(column) or "") == str(value)]
                return _FakeResult(rows)

        class Supabase:
            def __init__(self):
                self.rows_by_table = {
                    "teacher_review_requests": [
                        {
                            "id": 9,
                            "teacher_id": "teacher-1",
                            "student_id": "student-1",
                            "assignment_id": None,
                            "practice_session_id": 77,
                            "request_note": "Please review",
                            "teacher_feedback": "",
                        }
                    ],
                    "practice_sessions": [
                        {
                            "id": 77,
                            "user_id": "student-1",
                            "source_type": "exam",
                            "source_id": 88,
                            "exercise_data": {"exercises": [{"questions": [{"text": "Old"}], "answers": [""]}]},
                            "completed_at": None,
                            "correct_count": 0,
                            "score_pct": 0,
                        }
                    ],
                    "practice_answers": [
                        {
                            "id": 902,
                            "session_id": 77,
                            "user_id": "student-1",
                            "exercise_idx": 0,
                            "question_idx": 0,
                            "exercise_type": "multiple_choice",
                            "student_answer": "B",
                            "correct_answer": "",
                            "is_correct": False,
                            "answered_at": "2026-08-08T09:00:00+00:00",
                        }
                    ],
                }

            def table(self, table_name):
                return Query(table_name, self.rows_by_table)

        with (
            patch.object(tsi, "get_sb", return_value=Supabase()),
            patch.object(tsi, "get_current_user_id", return_value="teacher-1"),
            patch.object(tsi, "_load_profiles_map", return_value={"student-1": {"display_name": "Student One"}}),
            patch(
                "helpers.quick_exam_storage.load_exam_record",
                return_value={
                    "exam_data": {"sections": [{"type": "multiple_choice"}]},
                    "answer_key": {"sections": [{"answers": ["B"]}]},
                },
            ),
            patch(
                "helpers.practice_engine.exam_to_exercises",
                return_value={"exercises": [{"questions": [{"text": "Current"}], "answers": ["B"]}]},
            ),
        ):
            detail = tsi.load_teacher_review_request_detail(9)

        self.assertEqual("B", detail["items"][0]["correct_answer"])
        self.assertEqual("Current", detail["items"][0]["prompt"])

    def test_proactive_completion_lookup_excludes_assignment_attempts(self):
        class FilteringQuery:
            def __init__(self, table_name, rows):
                self.table_name = table_name
                self.rows = list(rows)
                self.filters = []

            def select(self, *_args, **_kwargs):
                return self

            def eq(self, column, value):
                self.filters.append(("eq", column, value))
                return self

            def in_(self, column, values):
                self.filters.append(("in", column, set(values)))
                return self

            def order(self, *_args, **_kwargs):
                return self

            def limit(self, value):
                self.limit_value = value
                return self

            def execute(self):
                rows = self.rows
                for op, column, value in self.filters:
                    if op == "eq":
                        rows = [row for row in rows if str(row.get(column) or "") == str(value)]
                    elif op == "in":
                        rows = [row for row in rows if row.get(column) in value]
                return _FakeResult(rows[: getattr(self, "limit_value", len(rows))])

        class FilteringSupabase:
            def __init__(self):
                self.tables = {
                    "practice_sessions": [
                        {"id": 1, "user_id": "student-1", "source_type": "worksheet", "source_id": "42", "status": "completed"},
                        {"id": 2, "user_id": "student-1", "source_type": "worksheet", "source_id": "42", "status": "completed"},
                    ],
                    "teacher_assignment_attempts": [
                        {"practice_session_id": 2, "student_id": "student-1"},
                    ],
                }

            def table(self, table_name):
                return FilteringQuery(table_name, self.tables.get(table_name, []))

        with patch.object(tsi, "get_sb", return_value=FilteringSupabase()):
            rows = tsi._completed_proactive_resource_sessions(
                student_id="student-1",
                assignment_type="worksheet",
                source_record_id=42,
            )

        self.assertEqual([1], [row["id"] for row in rows])

    def test_proactive_completion_confirmation_warns_teacher(self):
        app = AppTest.from_string(
            """
from types import SimpleNamespace
from helpers import teacher_student_integration as tsi

class Query:
    def __init__(self, rows):
        self.rows = rows
    def select(self, *_args, **_kwargs):
        return self
    def eq(self, *_args, **_kwargs):
        return self
    def in_(self, *_args, **_kwargs):
        return self
    def order(self, *_args, **_kwargs):
        return self
    def limit(self, *_args, **_kwargs):
        return self
    def execute(self):
        return SimpleNamespace(data=self.rows)

class Supabase:
    def table(self, table_name):
        if table_name == "practice_sessions":
            return Query([{"id": 1, "user_id": "student-1", "source_type": "worksheet", "source_id": "42", "status": "completed"}])
        return Query([])

tsi.get_sb = lambda: Supabase()
confirmed, names = tsi._render_multi_proactive_completion_confirmation(
    prefix="assignment_test",
    selected_targets=[{"label": "Ana · English", "link": {"student_id": "student-1", "student_name": "Ana"}}],
    assignment_type="worksheet",
    source_record_id=42,
)
"""
        ).run(timeout=10)

        self.assertEqual([], list(app.exception))
        rendered_warning = "\n".join(str(item.value) for item in app.warning)
        self.assertIn("already completed this activity independently", rendered_warning)
        self.assertIn("Ana", rendered_warning)

    def test_stale_resource_assign_dialog_state_is_cleared(self):
        app = AppTest.from_string(
            """
import streamlit as st
from helpers import teacher_student_integration as tsi

st.session_state["_resource_bulk_assign_dialog"] = {
    "kind": "worksheet",
    "row": {"id": 42, "title": "Old state"},
}
tsi.render_resource_bulk_assign_dialog(kind_filter="worksheet")
st.write("_resource_bulk_assign_dialog" in st.session_state)
"""
        ).run(timeout=10)

        self.assertEqual([], list(app.exception))
        self.assertIn("False", str(app.markdown[-1].value))


if __name__ == "__main__":
    unittest.main()
