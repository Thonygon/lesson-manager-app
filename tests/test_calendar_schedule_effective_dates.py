import unittest
from datetime import date
from unittest.mock import patch

import pandas as pd

from helpers import calendar_helpers, schedule


class _FakeResult:
    def __init__(self, data=None):
        self.data = data or []


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
    def __init__(self):
        self.operations = []

    def table(self, table_name):
        return _MutationQuery(table_name, self.operations, "noop")


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

    def test_update_schedule_from_date_versions_existing_schedule(self):
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

        self.assertEqual(2, len(fake_sb.operations))
        update_op, insert_op = fake_sb.operations
        self.assertEqual("update", update_op["action"])
        self.assertEqual({"end_date": "2026-09-01"}, update_op["payload"])
        self.assertIn(("id", 10), update_op["filters"])
        self.assertEqual("insert", insert_op["action"])
        self.assertEqual("2026-09-02", insert_op["payload"]["start_date"])
        self.assertEqual(2, insert_op["payload"]["weekday"])
        self.assertEqual("12:30", insert_op["payload"]["time"])
        self.assertEqual(90, insert_op["payload"]["duration_minutes"])

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

        insert_op = fake_sb.operations[1]
        self.assertEqual("2026-12-20", insert_op["payload"]["end_date"])


if __name__ == "__main__":
    unittest.main()
