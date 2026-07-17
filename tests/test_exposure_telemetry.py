import unittest
from unittest.mock import patch
import sys
import types


if "streamlit" not in sys.modules:
    def _cache_data(*args, **kwargs):
        def decorator(fn):
            fn.clear = lambda: None
            return fn
        return decorator

    sys.modules["streamlit"] = types.SimpleNamespace(
        session_state={},
        secrets={},
        cache_data=_cache_data,
        error=lambda *args, **kwargs: None,
        stop=lambda: (_ for _ in ()).throw(RuntimeError("streamlit.stop")),
        markdown=lambda *args, **kwargs: None,
        caption=lambda *args, **kwargs: None,
        columns=lambda *args, **kwargs: [],
        button=lambda *args, **kwargs: False,
        selectbox=lambda *args, **kwargs: 30,
        dataframe=lambda *args, **kwargs: None,
        info=lambda *args, **kwargs: None,
        success=lambda *args, **kwargs: None,
    )

if "supabase" not in sys.modules:
    sys.modules["supabase"] = types.SimpleNamespace(create_client=lambda *args, **kwargs: None)

if "pycountry" not in sys.modules:
    sys.modules["pycountry"] = types.SimpleNamespace(countries=[], languages=[])

from helpers import exposure_telemetry as telemetry
from helpers import student_recommendation_ml


class _FakeResult:
    def __init__(self, data):
        self.data = data


class _FakeTableQuery:
    def __init__(self, table_name, store):
        self.table_name = table_name
        self.store = store
        self.filters = []
        self.selected = None
        self._limit = None
        self._order = None
        self._pending_update = None
        self._pending_insert = None

    def select(self, value):
        self.selected = value
        return self

    def eq(self, column, value):
        self.filters.append(("eq", column, value))
        return self

    def gte(self, column, value):
        self.filters.append(("gte", column, value))
        return self

    def lte(self, column, value):
        self.filters.append(("lte", column, value))
        return self

    def in_(self, column, value):
        self.filters.append(("in", column, tuple(value)))
        return self

    def order(self, column, desc=False):
        self._order = (column, desc)
        return self

    def limit(self, value):
        self._limit = int(value)
        return self

    def insert(self, payload):
        self._pending_insert = payload
        return self

    def update(self, payload):
        self._pending_update = payload
        return self

    def _matches(self, row):
        for op, column, value in self.filters:
            row_value = row.get(column)
            if op == "eq" and row_value != value:
                return False
            if op == "gte" and str(row_value or "") < str(value):
                return False
            if op == "lte" and str(row_value or "") > str(value):
                return False
            if op == "in" and row_value not in value:
                return False
        return True

    def execute(self):
        rows = self.store.setdefault(self.table_name, [])
        if self._pending_insert is not None:
            payloads = self._pending_insert if isinstance(self._pending_insert, list) else [self._pending_insert]
            inserted = []
            for payload in payloads:
                payload = dict(payload)
                if self.table_name == "resource_exposures":
                    duplicate = next((row for row in rows if row.get("idempotency_key") == payload.get("idempotency_key")), None)
                    if duplicate:
                        raise RuntimeError("duplicate exposure idempotency_key")
                if self.table_name == "resource_exposure_events":
                    duplicate = next((row for row in rows if row.get("idempotency_key") == payload.get("idempotency_key")), None)
                    if duplicate:
                        raise RuntimeError("duplicate event idempotency_key")
                payload.setdefault("id", len(rows) + 1)
                rows.append(payload)
                inserted.append(payload)
            return _FakeResult(inserted)
        if self._pending_update is not None:
            updated = []
            for row in rows:
                if self._matches(row):
                    row.update(dict(self._pending_update))
                    updated.append(dict(row))
            return _FakeResult(updated)
        results = [dict(row) for row in rows if self._matches(row)]
        if self._order:
            column, desc = self._order
            results.sort(key=lambda row: str(row.get(column) or ""), reverse=bool(desc))
        if self._limit is not None:
            results = results[: self._limit]
        return _FakeResult(results)


class _FakeSupabase:
    def __init__(self, tables=None):
        self.tables = tables or {}

    def table(self, table_name):
        return _FakeTableQuery(table_name, self.tables)


class ExposureTelemetryTests(unittest.TestCase):
    def setUp(self):
        telemetry.load_telemetry_health_snapshot.clear()

    def tearDown(self):
        telemetry.load_telemetry_health_snapshot.clear()

    def test_exposure_creation_is_stable_and_idempotent(self):
        fake_sb = _FakeSupabase({"resource_exposures": []})
        rows = [
            {"id": 11, "resource_type": "worksheet", "assignment_id": 0, "score": 0.91},
        ]
        with (
            patch.object(telemetry.st, "session_state", {}),
            patch.object(telemetry, "get_sb", return_value=fake_sb),
            patch.object(telemetry, "get_current_user_id", return_value="student-1"),
        ):
            first = telemetry.attach_student_recommendation_exposures(rows, surface="student_home")
            second = telemetry.attach_student_recommendation_exposures(rows, surface="student_home")

        self.assertEqual(first[0]["_telemetry_exposure_id"], second[0]["_telemetry_exposure_id"])
        self.assertEqual(1, len(fake_sb.tables["resource_exposures"]))
        self.assertIn("cycle_id", fake_sb.tables["resource_exposures"][0])
        self.assertIsNone(fake_sb.tables["resource_exposures"][0]["teacher_id"])

    def test_repeated_legitimate_exposures_are_preserved_across_sessions(self):
        fake_sb = _FakeSupabase({"resource_exposures": []})
        row = {"id": 22, "resource_type": "video", "assignment_id": 0, "score": 0.55}
        with (
            patch.object(telemetry, "get_sb", return_value=fake_sb),
            patch.object(telemetry, "get_current_user_id", return_value="student-1"),
        ):
            with patch.object(telemetry.st, "session_state", {}):
                first = telemetry.attach_student_recommendation_exposures([row], surface="student_practice")
            with patch.object(telemetry.st, "session_state", {}):
                second = telemetry.attach_student_recommendation_exposures([row], surface="student_practice")

        self.assertNotEqual(first[0]["_telemetry_exposure_id"], second[0]["_telemetry_exposure_id"])
        self.assertEqual(2, len(fake_sb.tables["resource_exposures"]))

    def test_open_event_matches_existing_exposure(self):
        fake_sb = _FakeSupabase(
            {
                "resource_exposures": [],
                "resource_exposure_events": [],
                "user_activity_log": [],
            }
        )
        item = {"id": 31, "resource_type": "worksheet", "score": 0.71}
        with (
            patch.object(telemetry.st, "session_state", {}),
            patch.object(student_recommendation_ml.st, "session_state", {}),
            patch.object(telemetry, "get_sb", return_value=fake_sb),
            patch.object(student_recommendation_ml, "get_sb", return_value=fake_sb),
            patch.object(telemetry, "get_current_user_id", return_value="student-7"),
            patch.object(student_recommendation_ml, "get_current_user_id", return_value="student-7"),
        ):
            enriched = telemetry.attach_student_recommendation_exposures([item], surface="student_home")
            student_recommendation_ml.log_student_recommendation_open(enriched[0], surface="student_home")

        self.assertEqual(1, len(fake_sb.tables["resource_exposure_events"]))
        self.assertEqual(enriched[0]["_telemetry_exposure_id"], fake_sb.tables["resource_exposure_events"][0]["exposure_id"])
        self.assertIsNone(fake_sb.tables["resource_exposure_events"][0]["teacher_id"])

    def test_assignment_exposure_creation_and_backfill_do_not_fabricate_optional_impressions(self):
        fake_sb = _FakeSupabase(
            {
                "teacher_assignments": [
                    {
                        "id": 1,
                        "teacher_id": "teacher-1",
                        "student_id": "student-1",
                        "assignment_type": "worksheet",
                        "source_type": "worksheet_builder",
                        "source_record_id": 44,
                        "status": "assigned",
                        "assigned_at": "2026-07-01T00:00:00+00:00",
                        "created_at": "2026-07-01T00:00:00+00:00",
                        "recommendation_bucket": "",
                        "recommendation_focus_kind": "",
                        "learning_program_assignment_id": None,
                        "learning_program_topic_id": None,
                        "resource_exposure_id": "",
                    }
                ],
                "resource_exposures": [],
                "resource_exposure_events": [],
            }
        )
        with (
            patch.object(telemetry.st, "session_state", {}),
            patch.object(telemetry, "get_sb", return_value=fake_sb),
            patch.object(telemetry, "_execute_query_with_diagnostics", side_effect=lambda query, **_: query.execute()),
            patch.object(telemetry, "get_current_user_id", return_value="teacher-1"),
        ):
            result = telemetry.backfill_assignment_exposures(teacher_id="teacher-1", limit=10)

        self.assertEqual({"scanned": 1, "created": 1, "skipped": 0}, result)
        self.assertEqual("assigned_resource", fake_sb.tables["resource_exposures"][0]["exposure_type"])
        self.assertTrue(fake_sb.tables["resource_exposures"][0]["is_backfilled"])
        self.assertEqual("assigned", fake_sb.tables["resource_exposure_events"][0]["event_type"])
        self.assertNotIn("optional_student_recommendation", [row["exposure_type"] for row in fake_sb.tables["resource_exposures"]])

    def test_teacher_material_feed_exposure_creation_is_idempotent(self):
        fake_sb = _FakeSupabase({"resource_exposures": []})
        rows = [{"id": 7, "title": "Exam", "subject": "english", "topic": "Grammar", "level": "A2"}]
        with (
            patch.object(telemetry.st, "session_state", {}),
            patch.object(telemetry, "get_sb", return_value=fake_sb),
            patch.object(telemetry, "get_current_user_id", return_value="teacher-1"),
        ):
            telemetry.attach_teacher_material_feed_exposures(rows, kind="exam", source="community", surface="home_preview")
            telemetry.attach_teacher_material_feed_exposures(rows, kind="exam", source="community", surface="home_preview")

        self.assertEqual(1, len(fake_sb.tables["resource_exposures"]))
        self.assertEqual("teacher_material_feed", fake_sb.tables["resource_exposures"][0]["exposure_type"])

    def test_teacher_recommendation_exposure_creation(self):
        fake_sb = _FakeSupabase({"resource_exposures": []})
        objective_rows = [
            {
                "title": "Review fractions",
                "student_id": "student-1",
                "learning_program_assignment_id": 12,
                "learning_program_topic_id": 4,
                "recommendation_bucket": "review",
                "focus_kind": "needs_practice",
                "score": 0.83,
            }
        ]
        with (
            patch.object(telemetry.st, "session_state", {}),
            patch.object(telemetry, "get_sb", return_value=fake_sb),
            patch.object(telemetry, "get_current_user_id", return_value="teacher-1"),
        ):
            telemetry.attach_teacher_objective_exposures(objective_rows, surface="teacher_recommendations:math")

        self.assertEqual(1, len(fake_sb.tables["resource_exposures"]))
        self.assertEqual("teacher_objective_recommendation", fake_sb.tables["resource_exposures"][0]["exposure_type"])

    def test_health_snapshot_detects_orphan_events_and_filters_teacher_scope(self):
        fake_sb = _FakeSupabase(
            {
                "resource_exposures": [
                    {
                        "exposure_id": "exp-1",
                        "teacher_id": "teacher-1",
                        "student_id": "student-1",
                        "viewer_user_id": "teacher-1",
                        "resource_id": "44",
                        "resource_type": "worksheet",
                        "exposure_type": "assigned_resource",
                        "surface": "assignment_creation",
                        "shown_at": "2026-07-01T00:00:00+00:00",
                    },
                    {
                        "exposure_id": "exp-2",
                        "teacher_id": "teacher-2",
                        "student_id": "student-2",
                        "viewer_user_id": "teacher-2",
                        "resource_id": "88",
                        "resource_type": "video",
                        "exposure_type": "assigned_resource",
                        "surface": "assignment_creation",
                        "shown_at": "2026-07-01T00:00:00+00:00",
                    },
                ],
                "resource_exposure_events": [
                    {
                        "exposure_id": "exp-1",
                        "event_type": "opened",
                        "event_at": "2026-07-02T00:00:00+00:00",
                        "teacher_id": "teacher-1",
                        "student_id": "student-1",
                        "viewer_user_id": "student-1",
                    },
                    {
                        "exposure_id": "missing-exp",
                        "event_type": "opened",
                        "event_at": "2026-07-03T00:00:00+00:00",
                        "teacher_id": "teacher-1",
                        "student_id": "student-1",
                        "viewer_user_id": "student-1",
                    },
                ],
                "user_activity_log": [],
            }
        )
        with (
            patch.object(telemetry.st, "session_state", {}),
            patch.object(telemetry, "get_sb", return_value=fake_sb),
            patch.object(telemetry, "get_current_user_role", return_value="teacher"),
        ):
            snapshot = telemetry.load_telemetry_health_snapshot(teacher_id="teacher-1", days=30)

        self.assertEqual(1, snapshot["summary"]["total_exposures"])
        self.assertEqual(1, snapshot["summary"]["events_without_exposures"])
        self.assertEqual(1, snapshot["summary"]["represented_students"])

    def test_no_ranking_change_from_exposure_annotation(self):
        fake_sb = _FakeSupabase({"resource_exposures": []})
        rows = [
            {"id": 1, "resource_type": "worksheet", "score": 0.95},
            {"id": 2, "resource_type": "worksheet", "score": 0.87},
            {"id": 3, "resource_type": "worksheet", "score": 0.41},
        ]
        before = [row["id"] for row in rows]
        with (
            patch.object(telemetry.st, "session_state", {}),
            patch.object(telemetry, "get_sb", return_value=fake_sb),
            patch.object(telemetry, "get_current_user_id", return_value="student-1"),
        ):
            after_rows = telemetry.attach_student_recommendation_exposures(rows, surface="student_practice")
        after = [row["id"] for row in after_rows]
        scores = [row["score"] for row in after_rows]

        self.assertEqual(before, after)
        self.assertEqual([0.95, 0.87, 0.41], scores)

    def test_cycle_id_fallback_keeps_inserts_working_on_older_schema(self):
        class _LegacyCycleQuery(_FakeTableQuery):
            def execute(self):
                if self._pending_insert is not None and self.table_name == "resource_exposures":
                    payloads = self._pending_insert if isinstance(self._pending_insert, list) else [self._pending_insert]
                    for payload in payloads:
                        if "cycle_id" in payload:
                            raise RuntimeError("Could not find the 'cycle_id' column of 'resource_exposures' in the schema cache")
                return super().execute()

        class _LegacyCycleSupabase(_FakeSupabase):
            def table(self, table_name):
                return _LegacyCycleQuery(table_name, self.tables)

        fake_sb = _LegacyCycleSupabase({"resource_exposures": []})
        rows = [{"id": 11, "resource_type": "worksheet", "assignment_id": 0, "score": 0.91}]
        with (
            patch.object(telemetry.st, "session_state", {}),
            patch.object(telemetry, "get_sb", return_value=fake_sb),
            patch.object(telemetry, "get_current_user_id", return_value="student-1"),
        ):
            enriched = telemetry.attach_student_recommendation_exposures(rows, surface="student_home")

        self.assertTrue(enriched[0]["_telemetry_exposure_id"])
        self.assertEqual(1, len(fake_sb.tables["resource_exposures"]))
        self.assertNotIn("cycle_id", fake_sb.tables["resource_exposures"][0])


if __name__ == "__main__":
    unittest.main()
