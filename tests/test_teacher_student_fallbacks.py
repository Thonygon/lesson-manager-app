import unittest
from unittest.mock import patch

from helpers import student_meta
from helpers import teacher_student_integration as tsi


class _FakeResult:
    def __init__(self, data):
        self.data = data


class _FakeStudentQuery:
    def __init__(self, table_name, data_map, selected_columns_log):
        self.table_name = table_name
        self.data_map = data_map
        self.selected_columns_log = selected_columns_log
        self.selected_columns = ""
        self.filters = []

    def select(self, columns):
        self.selected_columns = str(columns or "")
        self.selected_columns_log.append((self.table_name, self.selected_columns))
        if self.table_name == "students" and "linked_student_user_id" in self.selected_columns:
            raise Exception("column students.linked_student_user_id does not exist")
        return self

    def eq(self, column, value):
        self.filters.append(("eq", column, value))
        return self

    def order(self, column, desc=False):
        self.filters.append(("order", column, desc))
        return self

    def limit(self, value):
        self.filters.append(("limit", value))
        return self

    def execute(self):
        return _FakeResult(self.data_map.get(self.table_name, []))


class _FakeSupabase:
    def __init__(self, data_map):
        self.data_map = data_map
        self.selected_columns_log = []
        self.queries = []

    def table(self, table_name):
        query = _FakeStudentQuery(table_name, self.data_map, self.selected_columns_log)
        self.queries.append(query)
        return query


class TeacherStudentFallbackTests(unittest.TestCase):
    def tearDown(self):
        student_meta.load_students_df.clear()

    def test_student_meta_falls_back_when_link_columns_are_missing(self):
        fake_sb = _FakeSupabase(
            {
                "students": [
                    {
                        "student": "Ana",
                        "email": "ana@example.com",
                        "zoom_link": "",
                        "notes": "",
                        "color": "#3B82F6",
                        "phone": "",
                        "address": "",
                        "native_language": "es",
                    }
                ]
            }
        )

        with (
            patch.object(student_meta, "get_sb", return_value=fake_sb),
            patch.object(student_meta, "_execute_query_with_diagnostics", side_effect=lambda query, **_: query.execute()),
            patch.object(student_meta.st, "session_state", {"user_id": "teacher-1"}, create=True),
        ):
            df = student_meta.load_students_df()

        self.assertEqual(["Ana"], df["student"].tolist())
        self.assertIn(("students", student_meta._STUDENT_META_COLUMNS), fake_sb.selected_columns_log)
        self.assertIn(
            (
                "students",
                "student,email,zoom_link,notes,color,phone,address,native_language,teacher_student_link_id,student_source,linked_at",
            ),
            fake_sb.selected_columns_log,
        )
        self.assertIn(("eq", "user_id", "teacher-1"), fake_sb.queries[1].filters)
        self.assertEqual([""], df["linked_student_user_id"].tolist())
        self.assertEqual(["manual"], df["student_source"].tolist())

    def test_teacher_student_rows_fall_back_when_link_columns_are_missing(self):
        fake_sb = _FakeSupabase(
            {
                "students": [
                    {
                        "id": 1,
                        "user_id": "teacher-1",
                        "student": "Ana",
                        "email": "ana@example.com",
                        "zoom_link": "",
                        "notes": "",
                        "color": "#3B82F6",
                        "phone": "",
                        "address": "",
                    }
                ]
            }
        )

        with patch.object(tsi, "get_sb", return_value=fake_sb):
            rows = tsi._load_teacher_student_rows("teacher-1")

        self.assertEqual(["Ana"], [row["student"] for row in rows])
        self.assertIn(("students", tsi._STUDENT_RECORD_COLUMNS), fake_sb.selected_columns_log)
        self.assertIn(
            (
                "students",
                "id,user_id,student,email,zoom_link,notes,color,phone,address,teacher_student_link_id,student_source,linked_at",
            ),
            fake_sb.selected_columns_log,
        )
        self.assertEqual("", rows[0]["linked_student_user_id"])
        self.assertEqual("manual", rows[0]["student_source"])


if __name__ == "__main__":
    unittest.main()
