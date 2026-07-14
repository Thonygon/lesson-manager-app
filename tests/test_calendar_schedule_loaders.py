import unittest
from unittest.mock import patch

from helpers import schedule


class _FakeResult:
    def __init__(self, data):
        self.data = data


class _FakeScheduleQuery:
    def __init__(self, table_name, data_map):
        self.table_name = table_name
        self.data_map = data_map
        self.selected_columns = ""
        self.filters = []
        self.ordering = None
        self.limit_value = None

    def select(self, columns):
        self.selected_columns = str(columns or "")
        if self.table_name == "schedules" and "timezone" in self.selected_columns:
            raise Exception("column schedules.timezone does not exist")
        if self.table_name == "calendar_overrides" and "gcal_event_id" in self.selected_columns:
            raise Exception("Could not find the 'gcal_event_id' column of 'calendar_overrides' in the schema cache")
        return self

    def eq(self, column, value):
        self.filters.append(("eq", column, value))
        return self

    def order(self, column, desc=False):
        self.ordering = (column, desc)
        return self

    def limit(self, value):
        self.limit_value = value
        return self

    def execute(self):
        return _FakeResult(self.data_map.get(self.table_name, []))


class _FakeSupabase:
    def __init__(self, data_map):
        self.data_map = data_map
        self.queries = []

    def table(self, table_name):
        query = _FakeScheduleQuery(table_name, self.data_map)
        self.queries.append(query)
        return query


class CalendarScheduleLoaderTests(unittest.TestCase):
    def tearDown(self):
        schedule._load_schedules_cached.clear()
        schedule._load_overrides_cached.clear()
        schedule._load_schedule_freezes_cached.clear()

    def test_schedule_loader_falls_back_when_timezone_column_is_missing(self):
        fake_sb = _FakeSupabase(
            {
                "schedules": [
                    {
                        "id": 11,
                        "student": "Ana",
                        "weekday": 2,
                        "time": "10:00",
                        "duration_minutes": 60,
                        "active": True,
                    }
                ]
            }
        )

        with (
            patch.object(schedule, "get_sb", return_value=fake_sb),
            patch.object(schedule, "get_current_user_id", return_value="teacher-1"),
            patch.object(schedule, "_execute_query_with_diagnostics", side_effect=lambda query, **_: query.execute()),
            patch.object(schedule, "show_data_load_error") as show_error,
        ):
            df = schedule._load_schedules_cached("teacher-1")

        self.assertEqual(["Ana"], df["student"].tolist())
        self.assertEqual([schedule.DEFAULT_TZ_NAME], df["timezone"].tolist())
        self.assertEqual(2, len(fake_sb.queries))
        self.assertEqual("id,student,weekday,time,duration_minutes,active,timezone", fake_sb.queries[0].selected_columns)
        self.assertEqual("id,student,weekday,time,duration_minutes,active", fake_sb.queries[1].selected_columns)
        self.assertIn(("eq", "user_id", "teacher-1"), fake_sb.queries[1].filters)
        self.assertEqual(schedule._SCHEDULE_ROW_LIMIT, fake_sb.queries[1].limit_value)
        show_error.assert_not_called()

    def test_override_loader_falls_back_when_gcal_column_is_missing(self):
        fake_sb = _FakeSupabase(
            {
                "calendar_overrides": [
                    {
                        "id": 21,
                        "student": "Luis",
                        "original_date": "2026-07-10",
                        "new_datetime": "2026-07-10T09:00:00+00:00",
                        "duration_minutes": 45,
                        "status": "scheduled",
                        "note": "rescheduled",
                    }
                ]
            }
        )

        with (
            patch.object(schedule, "get_sb", return_value=fake_sb),
            patch.object(schedule, "get_current_user_id", return_value="teacher-1"),
            patch.object(schedule, "_execute_query_with_diagnostics", side_effect=lambda query, **_: query.execute()),
            patch.object(schedule, "show_data_load_error") as show_error,
        ):
            df = schedule._load_overrides_cached("teacher-1", "Europe/Istanbul")

        self.assertEqual(["Luis"], df["student"].tolist())
        self.assertIn("gcal_event_id", df.columns)
        self.assertTrue(df["gcal_event_id"].isna().all())
        self.assertEqual(2, len(fake_sb.queries))
        self.assertEqual("id,student,original_date,new_datetime,duration_minutes,status,note,gcal_event_id", fake_sb.queries[0].selected_columns)
        self.assertEqual("id,student,original_date,new_datetime,duration_minutes,status,note", fake_sb.queries[1].selected_columns)
        self.assertIn(("eq", "user_id", "teacher-1"), fake_sb.queries[1].filters)
        self.assertEqual(schedule._OVERRIDE_ROW_LIMIT, fake_sb.queries[1].limit_value)
        show_error.assert_not_called()


if __name__ == "__main__":
    unittest.main()
