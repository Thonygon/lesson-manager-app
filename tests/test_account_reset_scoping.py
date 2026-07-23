import unittest
from unittest.mock import patch

from services import account_reset_service as reset_service


class _Result:
    def __init__(self, data=None, count=None):
        self.data = data or []
        self.count = count


class _Query:
    def __init__(self, table_name, store, log):
        self.table_name = table_name
        self.store = store
        self.log = log
        self.filters = []
        self.columns = "*"
        self.count_requested = False
        self.log.append(self)

    def select(self, columns, count=None, head=False):
        self.columns = columns
        self.count_requested = count == "exact"
        return self

    def eq(self, column, value):
        self.filters.append(("eq", column, value))
        return self

    def in_(self, column, values):
        self.filters.append(("in", column, tuple(values)))
        return self

    def execute(self):
        rows = list(self.store.get(self.table_name, []))
        for operator, column, value in self.filters:
            if operator == "eq":
                rows = [row for row in rows if row.get(column) == value]
            else:
                rows = [row for row in rows if row.get(column) in value]
        return _Result(rows, len(rows) if self.count_requested else None)


class _Supabase:
    def __init__(self, store):
        self.store = store
        self.log = []

    def table(self, table_name):
        return _Query(table_name, self.store, self.log)


class AccountResetScopingTests(unittest.TestCase):
    def test_student_preview_follows_assignment_relationship_instead_of_user_id(self):
        student_id = "9be49e2f-1001-499b-a1bf-1beb173dff64"
        fake_sb = _Supabase(
            {
                "learning_program_assignments": [
                    {"id": 41, "student_user_id": student_id},
                    {"id": 42, "student_user_id": "another-student"},
                ],
                "learning_program_progress": [
                    {"id": 1, "assignment_id": 41},
                    {"id": 2, "assignment_id": 42},
                ],
            }
        )

        with patch.object(reset_service, "get_sb", return_value=fake_sb):
            preview = reset_service.build_user_reset_preview(
                student_id,
                reset_service.RESET_SCOPE_STUDENT,
                remove_relationships=False,
            )

        counts = {row["label_key"]: row["count"] for row in preview["rows"]}
        self.assertEqual(1, counts["admin_reset_preview_student_program_assignments"])
        self.assertEqual(1, counts["admin_reset_preview_student_program_progress"])

        assignment_queries = [
            query for query in fake_sb.log
            if query.table_name == "learning_program_assignments"
        ]
        progress_queries = [
            query for query in fake_sb.log
            if query.table_name == "learning_program_progress"
        ]
        self.assertTrue(
            any(("eq", "student_user_id", student_id) in query.filters for query in assignment_queries)
        )
        self.assertTrue(
            any(("in", "assignment_id", (41,)) in query.filters for query in progress_queries)
        )
        self.assertFalse(
            any(
                column == "user_id"
                for query in assignment_queries + progress_queries
                for _operator, column, _value in query.filters
            )
        )


if __name__ == "__main__":
    unittest.main()
