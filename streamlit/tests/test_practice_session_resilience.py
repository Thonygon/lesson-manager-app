import unittest
from unittest.mock import patch
from types import ModuleType

try:
    import streamlit  # noqa: F401
except Exception:
    fake_streamlit = ModuleType("streamlit")
    fake_streamlit.session_state = {}
    fake_streamlit.cache_data = lambda *args, **kwargs: (lambda func: func)
    sys.modules["streamlit"] = fake_streamlit

from helpers import practice_engine


class _Result:
    def __init__(self, data):
        self.data = data


class _Query:
    def __init__(self, rows):
        self.rows = rows
        self.calls = []

    def select(self, columns):
        self.calls.append(("select", columns))
        return self

    def eq(self, column, value):
        self.calls.append(("eq", column, value))
        return self

    def order(self, column, desc=False):
        self.calls.append(("order", column, desc))
        return self

    def limit(self, value):
        self.calls.append(("limit", value))
        return self

    def execute(self):
        return _Result(self.rows)


class _Supabase:
    def __init__(self, rows):
        self.query = _Query(rows)
        self.table_name = ""

    def table(self, table_name):
        self.table_name = table_name
        return self.query


class PracticeSessionResilienceTests(unittest.TestCase):
    def test_assigned_practice_uses_canonical_resource_source_id(self):
        self.assertEqual(
            "64",
            practice_engine._practice_resource_source_id(
                {
                    "source_type": "worksheet",
                    "source_id": 174,
                    "assignment_id": 174,
                    "resource_record_id": 64,
                }
            ),
        )

    def setUp(self):
        for cache in (
            practice_engine._load_practice_history_cached,
            practice_engine._load_practice_progress_cached,
        ):
            if hasattr(cache, "clear"):
                cache.clear()

    def tearDown(self):
        practice_engine._load_practice_history_cached.clear()
        practice_engine._load_practice_progress_cached.clear()

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

    def test_retry_from_review_mode_becomes_real_retry_attempt(self):
        state = {
            "_practice_review_mode": True,
            "_practice_last_session_id": 55,
            "_practice_answers_sp": {"sp_0_0": "A"},
            "_practice_submitted_sp": True,
            "_practice_saved_sp": True,
            "sp_0_0": "A",
            "_practice_resume_answers": {"sp_0_0": "A"},
        }

        with patch.object(practice_engine.st, "session_state", state):
            practice_engine._prepare_retry_attempt("sp")

            self.assertNotIn("_practice_review_mode", practice_engine.st.session_state)
            self.assertEqual(55, practice_engine.st.session_state.get("_practice_retry_session_id"))
            self.assertNotIn("_practice_answers_sp", practice_engine.st.session_state)
            self.assertNotIn("_practice_submitted_sp", practice_engine.st.session_state)
            self.assertNotIn("_practice_saved_sp", practice_engine.st.session_state)
            self.assertNotIn("sp_0_0", practice_engine.st.session_state)
            self.assertNotIn("_practice_resume_answers", practice_engine.st.session_state)

    def test_practice_history_loader_queries_completed_rows_with_explicit_columns(self):
        class FakeResult:
            def __init__(self, data):
                self.data = data

        class FakeQuery:
            def __init__(self, log):
                self.log = log
                self.ops = []
                self.log.append(self)

            def select(self, value):
                self.ops.append(("select", value))
                return self

            def eq(self, column, value):
                self.ops.append(("eq", column, value))
                return self

            def order(self, column, desc=False):
                self.ops.append(("order", column, desc))
                return self

            def limit(self, value):
                self.ops.append(("limit", value))
                return self

            def execute(self):
                return FakeResult([{"id": 1, "status": "completed", "created_at": "2026-08-01T00:00:00+00:00"}])

        class FakeSupabase:
            def __init__(self):
                self.log = []

            def table(self, _name):
                return FakeQuery(self.log)

        fake_sb = FakeSupabase()
        practice_engine._load_practice_history_cached.clear()
        with patch.object(practice_engine, "get_sb", return_value=fake_sb):
            df = practice_engine._load_practice_history_cached("student-1", limit=25)

        self.assertEqual(1, len(df))
        query = fake_sb.log[0]
        self.assertEqual(practice_engine._PRACTICE_HISTORY_COLUMNS, query.ops[0][1])
        self.assertIn(("eq", "user_id", "student-1"), query.ops)
        self.assertIn(("eq", "status", "completed"), query.ops)
        self.assertIn(("order", "created_at", True), query.ops)
        self.assertIn(("limit", 25), query.ops)

    def test_practice_progress_loader_queries_current_user_rows_with_explicit_columns(self):
        class FakeResult:
            def __init__(self, data):
                self.data = data

        class FakeQuery:
            def __init__(self, log):
                self.log = log
                self.ops = []
                self.log.append(self)

            def select(self, value):
                self.ops.append(("select", value))
                return self

            def eq(self, column, value):
                self.ops.append(("eq", column, value))
                return self

            def execute(self):
                return FakeResult([{"id": 1, "user_id": "student-1", "total_xp": 15}])

        class FakeSupabase:
            def __init__(self):
                self.log = []

            def table(self, _name):
                return FakeQuery(self.log)

        fake_sb = FakeSupabase()
        practice_engine._load_practice_progress_cached.clear()
        with patch.object(practice_engine, "get_sb", return_value=fake_sb):
            df = practice_engine._load_practice_progress_cached("student-1")

        self.assertEqual(1, len(df))
        query = fake_sb.log[0]
        self.assertEqual(practice_engine._PRACTICE_PROGRESS_COLUMNS, query.ops[0][1])
        self.assertIn(("eq", "user_id", "student-1"), query.ops)

    def test_rescore_practice_sessions_for_resource_refreshes_saved_scores(self):
        class FakeResult:
            def __init__(self, data):
                self.data = data

        class FakeQuery:
            def __init__(self, supabase, table_name):
                self.supabase = supabase
                self.table_name = table_name
                self.filters = []
                self.pending_update = None
                self.pending_insert = None
                self.pending_delete = False

            def select(self, *_args, **_kwargs):
                return self

            def eq(self, column, value):
                self.filters.append(("eq", column, value))
                return self

            def in_(self, column, values):
                self.filters.append(("in", column, list(values)))
                return self

            def update(self, payload):
                self.pending_update = payload
                return self

            def insert(self, payload):
                self.pending_insert = payload
                return self

            def delete(self):
                self.pending_delete = True
                return self

            def execute(self):
                rows = self.supabase.tables.setdefault(self.table_name, [])

                def matches(row):
                    for op, column, value in self.filters:
                        row_value = row.get(column)
                        if op == "eq":
                            if str(row_value) != str(value):
                                return False
                        elif op == "in":
                            if not any(str(row_value) == str(item) for item in value):
                                return False
                    return True

                matched = [row for row in rows if matches(row)]

                if self.pending_delete:
                    self.supabase.tables[self.table_name] = [row for row in rows if not matches(row)]
                    return FakeResult([])

                if self.pending_update is not None:
                    for row in rows:
                        if matches(row):
                            row.update(self.pending_update)
                    return FakeResult(matched)

                if self.pending_insert is not None:
                    payloads = self.pending_insert if isinstance(self.pending_insert, list) else [self.pending_insert]
                    for payload in payloads:
                        rows.append(dict(payload))
                    return FakeResult(payloads)

                return FakeResult(matched)

        class FakeSupabase:
            def __init__(self):
                self.tables = {
                    "practice_sessions": [
                        {
                            "id": 1,
                            "user_id": "student-1",
                            "source_type": "worksheet",
                            "source_id": "7",
                            "title": "Fractions",
                            "status": "completed",
                            "correct_count": 0,
                            "total_questions": 1,
                            "score_pct": 0,
                        },
                        {
                            "id": 2,
                            "user_id": "student-2",
                            "source_type": "worksheet",
                            "source_id": "101",
                            "title": "Fractions",
                            "status": "completed",
                            "correct_count": 0,
                            "total_questions": 1,
                            "score_pct": 0,
                        },
                    ],
                    "practice_answers": [
                        {
                            "session_id": 1,
                            "user_id": "student-1",
                            "exercise_idx": 0,
                            "question_idx": 0,
                            "exercise_type": "multiple_choice",
                            "student_answer": "B",
                            "correct_answer": "A",
                            "is_correct": False,
                            "answered_at": "2026-08-01T10:00:00+00:00",
                        },
                        {
                            "session_id": 2,
                            "user_id": "student-2",
                            "exercise_idx": 0,
                            "question_idx": 0,
                            "exercise_type": "multiple_choice",
                            "student_answer": "B",
                            "correct_answer": "A",
                            "is_correct": False,
                            "answered_at": "2026-08-01T10:00:00+00:00",
                        },
                    ],
                    "teacher_assignments": [
                        {"id": 101, "student_id": "student-2", "assignment_type": "worksheet", "source_record_id": 7, "score_pct": 0, "correct_count": 0, "total_questions": 1},
                    ],
                    "teacher_assignment_attempts": [
                        {
                            "id": 201,
                            "assignment_id": 101,
                            "student_id": "student-2",
                            "practice_session_id": 2,
                            "score_pct": 0,
                            "correct_count": 0,
                            "total_questions": 1,
                            "created_at": "2026-08-01T10:05:00+00:00",
                            "submission_payload": {"result": {"score_pct": 0, "correct": 0, "total": 1}},
                            "status": "graded",
                        },
                    ],
                }

            def table(self, table_name):
                return FakeQuery(self, table_name)

        fake_sb = FakeSupabase()
        rebuilt_users = []
        exercise_data = {
            "title": "Fractions",
            "source_type": "worksheet",
            "source_id": 7,
            "exercises": [
                {
                    "type": "multiple_choice",
                    "questions": [{"stem": "1 + 1", "options": ["A", "B"]}],
                    "answers": ["B"],
                }
            ],
        }
        colliding_resource = {
            "title": "Unrelated resource 101",
            "source_type": "worksheet",
            "source_id": 101,
            "exercises": [
                {
                    "type": "multiple_choice",
                    "questions": [{"stem": "Unrelated", "options": ["A", "B"]}],
                    "answers": ["A"],
                }
            ],
        }

        with (
            patch.object(practice_engine, "get_sb", return_value=fake_sb),
            patch.object(practice_engine, "rebuild_practice_progress_for_user", side_effect=rebuilt_users.append),
            patch.object(practice_engine, "_clear_practice_caches"),
        ):
            collision_rescored = practice_engine.rescore_practice_sessions_for_resource(
                "worksheet", 101, colliding_resource
            )
            self.assertEqual(0, collision_rescored)
            self.assertEqual(
                0,
                next(row for row in fake_sb.tables["practice_sessions"] if row["id"] == 2)["score_pct"],
            )
            rescored = practice_engine.rescore_practice_sessions_for_resource("worksheet", 7, exercise_data)

        self.assertEqual(2, rescored)
        session_direct = next(row for row in fake_sb.tables["practice_sessions"] if row["id"] == 1)
        session_assigned = next(row for row in fake_sb.tables["practice_sessions"] if row["id"] == 2)
        self.assertEqual(100, session_direct["score_pct"])
        self.assertEqual(100, session_assigned["score_pct"])
        self.assertEqual(1, session_direct["correct_count"])
        self.assertEqual(1, session_assigned["correct_count"])
        self.assertEqual("7", str(session_assigned["source_id"]))

        direct_answer = next(row for row in fake_sb.tables["practice_answers"] if str(row["session_id"]) == "1")
        assigned_answer = next(row for row in fake_sb.tables["practice_answers"] if str(row["session_id"]) == "2")
        self.assertTrue(direct_answer["is_correct"])
        self.assertEqual("B", direct_answer["correct_answer"])
        self.assertTrue(assigned_answer["is_correct"])
        self.assertEqual("B", assigned_answer["correct_answer"])

        attempt_row = fake_sb.tables["teacher_assignment_attempts"][0]
        assignment_row = fake_sb.tables["teacher_assignments"][0]
        self.assertEqual(100, attempt_row["score_pct"])
        self.assertEqual(1, attempt_row["correct_count"])
        self.assertEqual(100, assignment_row["score_pct"])
        self.assertEqual(1, assignment_row["correct_count"])
        self.assertCountEqual(["student-1", "student-2"], rebuilt_users)

    def test_rescore_reconciles_answers_when_questions_are_reordered(self):
        previous = {
            "exercises": [
                {
                    "type": "multiple_choice",
                    "questions": [
                        {"stem": "First question", "options": ["A", "B"]},
                        {"stem": "Second question", "options": ["A", "B"]},
                    ],
                    "answers": ["A", "B"],
                }
            ]
        }
        edited = {
            "exercises": [
                {
                    "type": "multiple_choice",
                    "questions": [
                        {"stem": "Second question", "options": ["A", "B"]},
                        {"stem": "First question", "options": ["A", "B"]},
                    ],
                    "answers": ["B", "A"],
                }
            ]
        }
        rows = [
            {"session_id": 5, "user_id": "student-1", "exercise_idx": 0, "question_idx": 0, "exercise_type": "multiple_choice", "student_answer": "A"},
            {"session_id": 5, "user_id": "student-1", "exercise_idx": 0, "question_idx": 1, "exercise_type": "multiple_choice", "student_answer": "B"},
        ]

        rescored_rows, stats = practice_engine._evaluate_saved_practice_answers(
            edited,
            rows,
            previous_exercise_data=previous,
        )

        self.assertEqual(["B", "A"], [row["student_answer"] for row in rescored_rows])
        self.assertEqual(100, stats["score_pct"])

    def test_rescore_preserves_explicit_teacher_override(self):
        exercise_data = {
            "exercises": [
                {
                    "type": "short_answer",
                    "questions": [{"text": "Name a valid synonym"}],
                    "answers": ["large"],
                }
            ]
        }
        rows = [
            {
                "session_id": 6,
                "user_id": "student-1",
                "exercise_idx": 0,
                "question_idx": 0,
                "exercise_type": "short_answer",
                "student_answer": "big",
            }
        ]

        rescored_rows, stats = practice_engine._evaluate_saved_practice_answers(
            exercise_data,
            rows,
            previous_exercise_data=exercise_data,
            teacher_overrides={(0, 0): True},
        )

        self.assertTrue(rescored_rows[0]["is_correct"])
        self.assertEqual("large", rescored_rows[0]["correct_answer"])
        self.assertEqual(100, stats["score_pct"])

    def test_review_state_maps_legacy_answer_keys_to_current_widgets(self):
        class Query:
            def __init__(self, table_name, tables):
                self.table_name = table_name
                self.tables = tables
                self.filters = []

            def select(self, *_args, **_kwargs):
                return self

            def eq(self, column, value):
                self.filters.append((column, value))
                return self

            def order(self, *_args, **_kwargs):
                return self

            def limit(self, *_args, **_kwargs):
                return self

            def execute(self):
                rows = list(self.tables.get(self.table_name, []))
                for column, value in self.filters:
                    rows = [row for row in rows if str(row.get(column) or "") == str(value)]
                return _Result(rows)

        class Supabase:
            def __init__(self):
                self.tables = {
                    "practice_sessions": [
                        {
                            "id": 11,
                            "user_id": "student-1",
                            "score_pct": 100,
                            "correct_count": 1,
                            "total_questions": 1,
                            "exercise_data": {
                                "exercises": [
                                    {
                                        "type": "multiple_choice",
                                        "questions": [{"stem": "Choose", "options": ["wash", "cook"]}],
                                        "answers": ["wash"],
                                    }
                                ]
                            },
                        }
                    ],
                    "practice_answers": [
                        {
                            "session_id": 11,
                            "user_id": "student-1",
                            "exercise_idx": 0,
                            "question_idx": 0,
                            "exercise_type": "multiple_choice",
                            "student_answer": "",
                            "correct_answer": "wash",
                            "is_correct": True,
                        }
                    ],
                    "teacher_assignment_attempts": [
                        {
                            "student_id": "student-1",
                            "practice_session_id": 11,
                            "assignment_id": 21,
                            "submission_payload": {"result": {"answers": {"practice_0_0": "wash"}}},
                        }
                    ],
                    "teacher_review_requests": [],
                }

            def table(self, table_name):
                return Query(table_name, self.tables)

        exercise_data = {
            "exercises": [
                {
                    "type": "multiple_choice",
                    "questions": [{"stem": "Choose", "options": ["wash", "cook"]}],
                    "answers": ["wash"],
                }
            ]
        }
        with (
            patch.object(practice_engine, "get_sb", return_value=Supabase()),
            patch.object(practice_engine, "get_current_user_id", return_value="student-1"),
        ):
            state = practice_engine.load_practice_review_state(
                11,
                exercise_data=exercise_data,
                session_key="sp",
                assignment_id=21,
            )

        self.assertEqual("wash", state["answers"]["sp_0_0"])
        self.assertEqual(100, state["summary"]["score_pct"])

    def test_history_loader_filters_orders_and_limits_in_supabase(self):
        sb = _Supabase([{"id": 7, "user_id": "student-1", "status": "completed"}])
        with patch.object(practice_engine, "get_sb", return_value=sb):
            result = practice_engine._load_practice_history_cached("student-1", limit=25)

        self.assertEqual("practice_sessions", sb.table_name)
        self.assertEqual(1, len(result))
        self.assertIn(("select", practice_engine._PRACTICE_HISTORY_COLUMNS), sb.query.calls)
        self.assertIn(("eq", "user_id", "student-1"), sb.query.calls)
        self.assertIn(("eq", "status", "completed"), sb.query.calls)
        self.assertIn(("order", "created_at", True), sb.query.calls)
        self.assertIn(("limit", 25), sb.query.calls)

    def test_progress_loader_selects_only_current_user_rows(self):
        sb = _Supabase([{"id": 8, "user_id": "student-1", "total_xp": 40}])
        with patch.object(practice_engine, "get_sb", return_value=sb):
            result = practice_engine._load_practice_progress_cached("student-1")

        self.assertEqual("practice_progress", sb.table_name)
        self.assertEqual(1, len(result))
        self.assertIn(("select", practice_engine._PRACTICE_PROGRESS_COLUMNS), sb.query.calls)
        self.assertIn(("eq", "user_id", "student-1"), sb.query.calls)


if __name__ == "__main__":
    unittest.main()
