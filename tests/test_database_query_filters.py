import unittest
from unittest.mock import MagicMock, patch

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
    def test_supabase_client_uses_explicit_http_transport(self):
        sentinel_options = object()
        sentinel_client = object()
        with (
            patch("httpx.Client") as http_client,
            patch("supabase.ClientOptions", return_value=sentinel_options) as options_factory,
            patch.object(database, "create_client", return_value=sentinel_client) as create_client,
        ):
            result = database._create_supabase_client("https://example.supabase.co", "key")

        self.assertIs(sentinel_client, result)
        http_client.assert_called_once_with(timeout=120.0)
        options_factory.assert_called_once_with(httpx_client=http_client.return_value)
        create_client.assert_called_once_with(
            "https://example.supabase.co",
            "key",
            options=sentinel_options,
        )

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

    def test_clear_cache_domains_only_clears_matching_and_table_caches(self):
        class _Cache:
            def __init__(self):
                self.cleared = 0

            def clear(self):
                self.cleared += 1

        practice_cache = _Cache()
        resource_cache = _Cache()
        table_cache = _Cache()
        original_registry = list(database._CACHE_REGISTRY)
        original_domains = dict(database._CACHE_DOMAINS)
        try:
            database._CACHE_REGISTRY[:] = []
            database._CACHE_DOMAINS.clear()
            database.register_cache(practice_cache, "practice")
            database.register_cache(resource_cache, "resources")
            database.register_cache(table_cache, "database")

            database.clear_cache_domains("practice")

            self.assertEqual(1, practice_cache.cleared)
            self.assertEqual(0, resource_cache.cleared)
            self.assertEqual(1, table_cache.cleared)
        finally:
            database._CACHE_REGISTRY[:] = original_registry
            database._CACHE_DOMAINS.clear()
            database._CACHE_DOMAINS.update(original_domains)

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

    def test_activity_touch_only_updates_columns_present_in_deployed_profile_schema(self):
        fake_sb = MagicMock()
        update_query = fake_sb.table.return_value.update.return_value
        update_query.eq.return_value.execute.return_value.data = []

        with (
            patch.object(database, "get_current_user_id", return_value="demo_user"),
            patch.object(database, "load_profile_row", return_value={"user_id": "demo_user", "last_page": ""}),
            patch.object(database, "get_sb", return_value=fake_sb),
            patch.object(database.st, "session_state", {}, create=True),
        ):
            database.touch_current_user_activity("students")

        fake_sb.table.assert_called_once_with("profiles")
        fake_sb.table.return_value.update.assert_called_once_with({"last_page": "students"})

    def test_activity_touch_does_not_query_missing_optional_activity_columns(self):
        fake_sb = MagicMock()

        with (
            patch.object(database, "get_current_user_id", return_value="demo_user"),
            patch.object(database, "load_profile_row", return_value={"user_id": "demo_user"}),
            patch.object(database, "get_sb", return_value=fake_sb),
            patch.object(database.st, "session_state", {}, create=True),
        ):
            database.touch_current_user_activity("home")

        fake_sb.table.assert_not_called()

    def test_student_update_omits_native_language_when_live_row_lacks_column(self):
        fake_sb = MagicMock()
        shape_query = fake_sb.table.return_value.select.return_value
        shape_query.eq.return_value = shape_query
        shape_query.limit.return_value.execute.return_value.data = [{"student": "Ana", "email": "old@example.com"}]
        update_query = fake_sb.table.return_value.update.return_value
        update_query.eq.return_value = update_query

        with (
            patch.object(database, "get_current_user_id", return_value="teacher-1"),
            patch.object(database, "get_sb", return_value=fake_sb),
            patch.object(database, "clear_app_caches"),
        ):
            database.update_student_profile(
                "Ana",
                "ana@example.com",
                "",
                "",
                "#3B82F6",
                "",
                native_language="es",
            )

        payload = fake_sb.table.return_value.update.call_args.args[0]
        self.assertNotIn("native_language", payload)


if __name__ == "__main__":
    unittest.main()
