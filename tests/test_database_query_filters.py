import unittest
from unittest.mock import patch

from core import database


class _FakeQuery:
    def __init__(self):
        self.calls = []

    def eq(self, column, value):
        self.calls.append(("eq", column, value))
        return self

    def neq(self, column, value):
        self.calls.append(("neq", column, value))
        return self

    def gte(self, column, value):
        self.calls.append(("gte", column, value))
        return self

    def lte(self, column, value):
        self.calls.append(("lte", column, value))
        return self

    def gt(self, column, value):
        self.calls.append(("gt", column, value))
        return self

    def lt(self, column, value):
        self.calls.append(("lt", column, value))
        return self

    def in_(self, column, value):
        self.calls.append(("in", column, value))
        return self


class DatabaseQueryFilterTests(unittest.TestCase):
    def test_clear_specific_caches_only_clears_requested_functions(self):
        class _Cache:
            def __init__(self):
                self.cleared = 0

            def clear(self):
                self.cleared += 1

        cache_a = _Cache()
        cache_b = _Cache()

        database.clear_specific_caches(cache_a, None, cache_b)

        self.assertEqual(1, cache_a.cleared)
        self.assertEqual(1, cache_b.cleared)

    def test_apply_query_filter_dispatches_supported_operators(self):
        query = _FakeQuery()

        database._apply_query_filter(query, "eq", "user_id", "abc")
        database._apply_query_filter(query, "gte", "payment_date", "2026-01-01")
        database._apply_query_filter(query, "in", "student", ("Ana", "Luis"))

        self.assertEqual(
            [
                ("eq", "user_id", "abc"),
                ("gte", "payment_date", "2026-01-01"),
                ("in", "student", ["Ana", "Luis"]),
            ],
            query.calls,
        )

    def test_apply_query_filter_rejects_unknown_operator(self):
        with self.assertRaises(ValueError):
            database._apply_query_filter(_FakeQuery(), "between", "payment_date", ("a", "b"))

    def test_load_table_filtered_freezes_filter_values_for_cache_key(self):
        with patch("core.database.get_current_user_id", return_value="teacher-1"), patch(
            "core.database._load_table_cached", return_value="sentinel"
        ) as cached_loader:
            result = database.load_table_filtered(
                "payments",
                columns="student,payment_date",
                filters=[("in", "student", ["Ana", "Luis"]), ("gte", "payment_date", "2026-01-01")],
                order_by="payment_date",
                order_desc=True,
            )

        self.assertEqual("sentinel", result)
        cached_loader.assert_called_once_with(
            "payments",
            "teacher-1",
            "student,payment_date",
            10000,
            1000,
            (("in", "student", ("Ana", "Luis")), ("gte", "payment_date", "2026-01-01")),
            "payment_date",
            True,
        )


if __name__ == "__main__":
    unittest.main()
