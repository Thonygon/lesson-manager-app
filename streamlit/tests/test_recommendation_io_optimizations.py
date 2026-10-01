import unittest
from unittest.mock import patch

from helpers import recommendation_memory
from helpers import recommendation_models


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

    def gte(self, column, value):
        self.ops.append(("gte", column, value))
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

    @property
    def not_(self):
        return self

    def is_(self, column, value):
        self.ops.append(("not.is", column, value))
        return self

    def execute(self):
        return _FakeResult(self.data)


class _FakeRpcQuery:
    def __init__(self, fn_name, params, rpc_log, data):
        self.fn_name = fn_name
        self.params = params
        self.rpc_log = rpc_log
        self.data = data
        self.rpc_log.append(self)

    def execute(self):
        return _FakeResult(self.data)


class _FakeSupabase:
    def __init__(self, table_data=None, rpc_data=None):
        self.table_data = table_data or {}
        self.rpc_data = rpc_data or {}
        self.table_log = []
        self.rpc_log = []

    def table(self, table_name):
        return _FakeQuery(table_name, self.table_log, self.table_data.get(table_name, []))

    def rpc(self, fn_name, params):
        return _FakeRpcQuery(fn_name, params, self.rpc_log, self.rpc_data.get(fn_name, []))


class RecommendationIoOptimizationTests(unittest.TestCase):
    def tearDown(self):
        recommendation_models._load_topic_resource_reference_rows.clear()
        recommendation_memory.load_recommendation_event_summary.clear()

    def test_topic_reference_rows_are_tenant_scoped_and_bounded(self):
        fake_sb = _FakeSupabase(
            table_data={
                "teacher_assignments": [{"teacher_id": "teacher-1", "student_id": "student-1"}],
                "learning_program_recommendation_events": [{"teacher_id": "teacher-1", "student_id": "student-1"}],
                "learning_program_topic_videos": [{"teacher_id": "teacher-1", "topic_id": 7, "video_id": 11}],
            }
        )
        with (
            patch.object(recommendation_models, "get_sb", return_value=fake_sb),
            patch.object(recommendation_models, "_execute_recommendation_query", side_effect=lambda query, **_: query.execute()),
        ):
            payload = recommendation_models._load_topic_resource_reference_rows(
                teacher_id="teacher-1",
                student_id="student-1",
            )

        self.assertEqual(1, len(payload["assignments"]))
        self.assertEqual(1, len(payload["events"]))
        self.assertEqual(1, len(payload["video_links"]))

        assignment_query = next(query for query in fake_sb.table_log if query.table_name == "teacher_assignments")
        self.assertIn(("eq", "teacher_id", "teacher-1"), assignment_query.ops)
        self.assertIn(("eq", "student_id", "student-1"), assignment_query.ops)
        self.assertTrue(any(op[0] == "gte" and op[1] == "updated_at" for op in assignment_query.ops))
        self.assertIn(("limit", 1200), assignment_query.ops)
        self.assertNotIn(("select", "*"), assignment_query.ops)

        video_query = next(query for query in fake_sb.table_log if query.table_name == "learning_program_topic_videos")
        self.assertIn(("eq", "teacher_id", "teacher-1"), video_query.ops)

    def test_student_scoped_reference_rows_skip_unscoped_video_query(self):
        fake_sb = _FakeSupabase(
            table_data={
                "teacher_assignments": [],
                "learning_program_recommendation_events": [],
                "learning_program_topic_videos": [{"teacher_id": "teacher-2"}],
            }
        )
        with (
            patch.object(recommendation_models, "get_sb", return_value=fake_sb),
            patch.object(recommendation_models, "_execute_recommendation_query", side_effect=lambda query, **_: query.execute()),
        ):
            payload = recommendation_models._load_topic_resource_reference_rows(student_id="student-1")

        self.assertEqual([], payload["video_links"])
        queried_tables = [query.table_name for query in fake_sb.table_log]
        self.assertNotIn("learning_program_topic_videos", queried_tables)

    def test_recommendation_event_summary_uses_deployed_table_without_missing_rpc_probe(self):
        fake_sb = _FakeSupabase(
            table_data={
                "learning_program_recommendation_events": [
                    {
                        "teacher_id": "teacher-1",
                        "student_id": "student-9",
                        "learning_program_assignment_id": 41,
                        "learning_program_topic_id": 7,
                        "recommendation_bucket": "review",
                        "event_type": "student_improved",
                        "resource_kind": "worksheet",
                        "metadata": {"score_pct": 88.0},
                        "created_at": "2026-07-01T00:00:00+00:00",
                    },
                    {
                        "teacher_id": "teacher-1",
                        "student_id": "student-9",
                        "learning_program_assignment_id": 41,
                        "learning_program_topic_id": 7,
                        "recommendation_bucket": "review",
                        "event_type": "assignment_created",
                        "resource_kind": "video",
                        "metadata": {},
                        "created_at": "2026-06-30T00:00:00+00:00",
                    },
                ]
            }
        )
        with (
            patch.object(recommendation_memory, "get_sb", return_value=fake_sb),
            patch.object(recommendation_memory, "get_current_user_id", return_value="teacher-1"),
            patch.object(recommendation_memory, "get_current_user_role", return_value="teacher"),
            patch.object(recommendation_memory, "_execute_query_with_diagnostics", side_effect=lambda query, **_: query.execute()),
        ):
            summary = recommendation_memory.load_recommendation_event_summary((41,), "student-9")

        self.assertEqual([], fake_sb.rpc_log)
        event_query = next(
            query for query in fake_sb.table_log
            if query.table_name == "learning_program_recommendation_events"
        )
        self.assertIn(("eq", "teacher_id", "teacher-1"), event_query.ops)
        self.assertIn(("eq", "student_id", "student-9"), event_query.ops)
        self.assertIn(("in", "learning_program_assignment_id", (41,)), event_query.ops)

        key = (41, 7, "review")
        self.assertIn(key, summary)
        self.assertEqual(2, summary[key]["count"])
        self.assertEqual("student_improved", summary[key]["last_event_type"])
        self.assertEqual({"worksheet", "video"}, summary[key]["resource_kinds"])


if __name__ == "__main__":
    unittest.main()
