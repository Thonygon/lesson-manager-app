import unittest
from datetime import date
from unittest.mock import patch

import pandas as pd

from helpers import calendar_helpers, schedule


class _FakeResult:
    def __init__(self, data=None):
        self.data = data or []


class _RpcQuery:
    def __init__(self, rpc_name: str, payload: dict, operation_log: list[dict], exc: Exception | None = None):
        self.rpc_name = rpc_name
        self.payload = dict(payload or {})
        self.operation_log = operation_log
        self.exc = exc

    def execute(self):
        self.operation_log.append(
            {
                "rpc": self.rpc_name,
                "payload": dict(self.payload or {}),
            }
        )
        if self.exc is not None:
            raise self.exc
        return _FakeResult()


class _MutationQuery:
    def __init__(self, table_name: str, operation_log: list[dict], action: str):
        self.table_name = table_name
        self.operation_log = operation_log
        self.action = action
        self.payload = None
        self.filters = []

    def update(self, payload):
        self.payload = dict(payload or {})
        self.action = "update"
        return self

    def insert(self, payload):
        self.payload = dict(payload or {})
        self.action = "insert"
        return self

    def eq(self, column, value):
        self.filters.append((column, value))
        return self

    def execute(self):
        self.operation_log.append(
            {
                "table": self.table_name,
                "action": self.action,
                "payload": dict(self.payload or {}),
                "filters": list(self.filters),
            }
        )
        return _FakeResult()


class _FakeSupabase:
    def __init__(self, *, rpc_exc: Exception | None = None, insert_exc: Exception | None = None):
        self.operations = []
        self.rpc_exc = rpc_exc
        self.insert_exc = insert_exc

    def table(self, table_name):
        query = _MutationQuery(table_name, self.operations, "noop")
        if self.insert_exc is not None and table_name == "schedules":
            original_insert = query.insert

            def _insert_with_failure(payload):
                original_insert(payload)
                query.execute = self._raise_insert_exc_then_reset(query.execute)
                return query

            query.insert = _insert_with_failure
        return query

    def rpc(self, rpc_name, payload):
        return _RpcQuery(rpc_name, payload, self.operations, exc=self.rpc_exc)

    def _raise_insert_exc_then_reset(self, original_execute):
        def _wrapped():
            self.insert_exc, exc = None, self.insert_exc
            if exc is not None:
                self.operations.append(
                    {
                        "table": "schedules",
                        "action": "insert",
                        "payload": dict(getattr(original_execute.__self__, "payload", {}) or {}),
                        "filters": list(getattr(original_execute.__self__, "filters", []) or []),
                    }
                )
                raise exc
            return original_execute()

        return _wrapped


class CalendarScheduleEffectiveDateTests(unittest.TestCase):
    def tearDown(self):
        calendar_helpers.build_calendar_events.clear()
        schedule._load_schedules_cached.clear()

    def test_build_calendar_events_respects_schedule_start_and_end_dates(self):
        schedules_df = pd.DataFrame(
            [
                {
                    "id": 1,
                    "student": "Ana",
                    "weekday": 0,
                    "time": "10:00",
                    "duration_minutes": 60,
                    "active": True,
                    "timezone": "Europe/Istanbul",
                    "start_date": date(2026, 8, 10),
                    "end_date": date(2026, 8, 24),
                }
            ]
        )

        with (
            patch.object(calendar_helpers, "load_schedules", return_value=schedules_df),
            patch.object(calendar_helpers, "load_overrides", return_value=pd.DataFrame()),
            patch.object(calendar_helpers, "load_schedule_freezes", return_value=pd.DataFrame()),
            patch.object(calendar_helpers, "student_meta_maps", return_value=({}, {}, {}, {}, {})),
        ):
            events = calendar_helpers.build_calendar_events(date(2026, 8, 1), date(2026, 8, 31), "Europe/Istanbul")

        self.assertEqual(["2026-08-10", "2026-08-17", "2026-08-24"], events["Date"].tolist())

    def test_update_schedule_from_date_versions_existing_schedule_via_rpc(self):
        fake_sb = _FakeSupabase()
        schedules_df = pd.DataFrame(
            [
                {
                    "id": 10,
                    "student": "Ana",
                    "weekday": 0,
                    "time": "10:00",
                    "duration_minutes": 60,
                    "active": True,
                    "timezone": "Europe/Istanbul",
                    "start_date": date(2026, 8, 1),
                    "end_date": None,
                }
            ]
        )

        with (
            patch.object(schedule, "get_current_user_id", return_value="teacher-1"),
            patch.object(schedule, "load_schedules", return_value=schedules_df),
            patch.object(schedule, "get_sb", return_value=fake_sb),
            patch.object(schedule, "clear_app_caches"),
            patch.object(schedule, "with_owner", side_effect=lambda payload: {**payload, "user_id": "teacher-1"}),
            patch.object(schedule, "now_local", return_value=pd.Timestamp("2026-08-31T09:00:00")),
        ):
            schedule.update_schedule_from_date(
                10,
                student="Ana",
                weekday=2,
                time_str="12:30",
                duration_minutes=90,
                active=True,
                effective_start_date=date(2026, 9, 2),
            )

        self.assertEqual(1, len(fake_sb.operations))
        rpc_op = fake_sb.operations[0]
        self.assertEqual("classio_edit_schedule", rpc_op["rpc"])
        self.assertEqual("2026-09-02", rpc_op["payload"]["p_effective_start_date"])
        self.assertEqual("future", rpc_op["payload"]["p_scope"])
        self.assertEqual(2, rpc_op["payload"]["p_weekday"])
        self.assertEqual("12:30", rpc_op["payload"]["p_time"])
        self.assertEqual(90, rpc_op["payload"]["p_duration_minutes"])

    def test_update_schedule_from_date_accepts_optional_new_end_date(self):
        fake_sb = _FakeSupabase()
        schedules_df = pd.DataFrame(
            [
                {
                    "id": 11,
                    "student": "Ana",
                    "weekday": 1,
                    "time": "09:00",
                    "duration_minutes": 60,
                    "active": True,
                    "timezone": "Europe/Istanbul",
                    "start_date": date(2026, 8, 1),
                    "end_date": None,
                }
            ]
        )

        with (
            patch.object(schedule, "get_current_user_id", return_value="teacher-1"),
            patch.object(schedule, "load_schedules", return_value=schedules_df),
            patch.object(schedule, "get_sb", return_value=fake_sb),
            patch.object(schedule, "clear_app_caches"),
            patch.object(schedule, "with_owner", side_effect=lambda payload: {**payload, "user_id": "teacher-1"}),
            patch.object(schedule, "now_local", return_value=pd.Timestamp("2026-08-31T09:00:00")),
        ):
            schedule.update_schedule_from_date(
                11,
                student="Ana",
                weekday=1,
                time_str="09:00",
                duration_minutes=60,
                active=True,
                effective_start_date=date(2026, 9, 5),
                end_date=date(2026, 12, 20),
            )

        rpc_op = fake_sb.operations[0]
        self.assertEqual("2026-12-20", rpc_op["payload"]["p_end_date"])

    def test_update_schedule_from_date_can_clear_existing_end_date(self):
        fake_sb = _FakeSupabase()
        schedules_df = pd.DataFrame(
            [
                {
                    "id": 13,
                    "student": "Ana",
                    "weekday": 1,
                    "time": "09:00",
                    "duration_minutes": 60,
                    "active": True,
                    "timezone": "Europe/Istanbul",
                    "start_date": date(2026, 8, 1),
                    "end_date": date(2026, 12, 20),
                }
            ]
        )

        with (
            patch.object(schedule, "get_current_user_id", return_value="teacher-1"),
            patch.object(schedule, "load_schedules", return_value=schedules_df),
            patch.object(schedule, "get_sb", return_value=fake_sb),
            patch.object(schedule, "clear_app_caches"),
            patch.object(schedule, "with_owner", side_effect=lambda payload: {**payload, "user_id": "teacher-1"}),
            patch.object(schedule, "now_local", return_value=pd.Timestamp("2026-08-31T09:00:00")),
        ):
            schedule.update_schedule_from_date(
                13,
                student="Ana",
                weekday=1,
                time_str="09:00",
                duration_minutes=60,
                active=True,
                effective_start_date=date(2026, 9, 5),
                end_date=None,
            )

        rpc_op = fake_sb.operations[0]
        self.assertIsNone(rpc_op["payload"]["p_end_date"])

    def test_update_schedule_from_date_preserves_existing_end_date_when_omitted(self):
        fake_sb = _FakeSupabase()
        schedules_df = pd.DataFrame(
            [
                {
                    "id": 14,
                    "student": "Ana",
                    "weekday": 1,
                    "time": "09:00",
                    "duration_minutes": 60,
                    "active": True,
                    "timezone": "Europe/Istanbul",
                    "start_date": date(2026, 8, 1),
                    "end_date": date(2026, 12, 20),
                }
            ]
        )

        with (
            patch.object(schedule, "get_current_user_id", return_value="teacher-1"),
            patch.object(schedule, "load_schedules", return_value=schedules_df),
            patch.object(schedule, "get_sb", return_value=fake_sb),
            patch.object(schedule, "clear_app_caches"),
            patch.object(schedule, "with_owner", side_effect=lambda payload: {**payload, "user_id": "teacher-1"}),
            patch.object(schedule, "now_local", return_value=pd.Timestamp("2026-08-31T09:00:00")),
        ):
            schedule.update_schedule_from_date(
                14,
                student="Ana",
                weekday=1,
                time_str="09:00",
                duration_minutes=60,
                active=True,
                effective_start_date=date(2026, 9, 5),
            )

        rpc_op = fake_sb.operations[0]
        self.assertEqual("2026-12-20", rpc_op["payload"]["p_end_date"])

    def test_update_schedule_from_date_restores_original_end_date_when_legacy_insert_fails(self):
        fake_sb = _FakeSupabase(
            rpc_exc=Exception("Could not find the function public.classio_edit_schedule"),
            insert_exc=Exception("temporary insert failure"),
        )
        schedules_df = pd.DataFrame(
            [
                {
                    "id": 12,
                    "student": "Ana",
                    "weekday": 3,
                    "time": "11:00",
                    "duration_minutes": 60,
                    "active": True,
                    "timezone": "Europe/Istanbul",
                    "start_date": date(2026, 8, 1),
                    "end_date": date(2026, 12, 31),
                }
            ]
        )

        with (
            patch.object(schedule, "get_current_user_id", return_value="teacher-1"),
            patch.object(schedule, "load_schedules", return_value=schedules_df),
            patch.object(schedule, "get_sb", return_value=fake_sb),
            patch.object(schedule, "clear_app_caches"),
            patch.object(schedule, "with_owner", side_effect=lambda payload: {**payload, "user_id": "teacher-1"}),
            patch.object(schedule, "now_local", return_value=pd.Timestamp("2026-08-31T09:00:00")),
        ):
            with self.assertRaisesRegex(Exception, "temporary insert failure"):
                schedule.update_schedule_from_date(
                    12,
                    student="Ana",
                    weekday=4,
                    time_str="14:00",
                    duration_minutes=75,
                    active=True,
                    effective_start_date=date(2026, 9, 4),
                )

        self.assertEqual(4, len(fake_sb.operations))
        self.assertEqual("classio_edit_schedule", fake_sb.operations[0]["rpc"])
        self.assertEqual("update", fake_sb.operations[1]["action"])
        self.assertEqual({"end_date": "2026-09-03"}, fake_sb.operations[1]["payload"])
        self.assertEqual("insert", fake_sb.operations[2]["action"])
        self.assertEqual("update", fake_sb.operations[3]["action"])
        self.assertEqual({"end_date": "2026-12-31"}, fake_sb.operations[3]["payload"])


if __name__ == "__main__":
    unittest.main()
