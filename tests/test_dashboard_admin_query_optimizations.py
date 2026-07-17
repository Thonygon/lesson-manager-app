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
        cache_resource=_cache_data,
        error=lambda *args, **kwargs: None,
        stop=lambda: (_ for _ in ()).throw(RuntimeError("streamlit.stop")),
        markdown=lambda *args, **kwargs: None,
        caption=lambda *args, **kwargs: None,
        columns=lambda *args, **kwargs: [],
        button=lambda *args, **kwargs: False,
        selectbox=lambda *args, **kwargs: "",
        dataframe=lambda *args, **kwargs: None,
        info=lambda *args, **kwargs: None,
        success=lambda *args, **kwargs: None,
        warning=lambda *args, **kwargs: None,
        toggle=lambda *args, **kwargs: False,
        checkbox=lambda *args, **kwargs: False,
        text_input=lambda *args, **kwargs: "",
        text_area=lambda *args, **kwargs: "",
        form=lambda *args, **kwargs: types.SimpleNamespace(__enter__=lambda self: self, __exit__=lambda self, exc_type, exc, tb: False),
        form_submit_button=lambda *args, **kwargs: False,
        rerun=lambda: None,
        query_params={},
    )
else:
    streamlit_mod = sys.modules["streamlit"]
    if not isinstance(streamlit_mod, types.ModuleType):
        module = types.ModuleType("streamlit")
        for name in dir(streamlit_mod):
            if name.startswith("__"):
                continue
            setattr(module, name, getattr(streamlit_mod, name))
        sys.modules["streamlit"] = module
        streamlit_mod = module
    if not hasattr(streamlit_mod, "cache_resource"):
        def _cache_data(*args, **kwargs):
            def decorator(fn):
                fn.clear = lambda: None
                return fn
            return decorator
        setattr(streamlit_mod, "cache_resource", _cache_data)

if "streamlit.components" not in sys.modules:
    components_v1 = types.SimpleNamespace(html=lambda *args, **kwargs: None)
    sys.modules["streamlit.components"] = types.SimpleNamespace(v1=components_v1)
    sys.modules["streamlit.components.v1"] = components_v1

if "openai" not in sys.modules:
    sys.modules["openai"] = types.SimpleNamespace(OpenAI=object)

from app_pages import admin
from helpers import dashboard


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

    def order(self, column, desc=False):
        self.ops.append(("order", column, desc))
        return self

    def limit(self, value):
        self.ops.append(("limit", value))
        return self

    def execute(self):
        return _FakeResult(self.data)


class _FakeSupabase:
    def __init__(self, table_data=None):
        self.table_data = table_data or {}
        self.table_log = []

    def table(self, table_name):
        return _FakeQuery(table_name, self.table_log, self.table_data.get(table_name, []))


class DashboardAdminQueryOptimizationTests(unittest.TestCase):
    def tearDown(self):
        dashboard.load_dashboard_source_frames.clear()
        admin._fetch_overrides.clear()

    def test_dashboard_source_frames_use_shared_explicit_column_queries(self):
        with patch.object(dashboard, "load_table_filtered") as load_table_filtered:
            load_table_filtered.side_effect = ["classes-frame", "payments-frame"]

            classes, payments = dashboard.load_dashboard_source_frames()

        self.assertEqual("classes-frame", classes)
        self.assertEqual("payments-frame", payments)
        self.assertEqual(2, load_table_filtered.call_count)
        self.assertEqual(
            (
                ("classes",),
                {
                    "columns": dashboard._DASHBOARD_CLASS_COLUMNS,
                    "order_by": "lesson_date",
                    "order_desc": True,
                },
            ),
            load_table_filtered.call_args_list[0],
        )
        self.assertEqual(
            (
                ("payments",),
                {
                    "columns": dashboard._DASHBOARD_PAYMENT_COLUMNS,
                    "order_by": "payment_date",
                    "order_desc": True,
                },
            ),
            load_table_filtered.call_args_list[1],
        )

    def test_admin_override_loader_uses_explicit_columns(self):
        fake_sb = _FakeSupabase(
            table_data={
                "admin_overrides": [
                    {
                        "id": 1,
                        "user_id": "user-1",
                        "override_type": "plan_assignment",
                        "old_value": "free",
                        "new_value": "teacher_pro",
                        "note": "granted",
                        "admin_user_id": "admin-1",
                        "admin_email": "admin@classio.app",
                        "created_at": "2026-07-14T00:00:00+00:00",
                    }
                ]
            }
        )

        with patch.object(admin, "get_sb", return_value=fake_sb):
            rows = admin._fetch_overrides()

        self.assertEqual(1, len(rows))
        query = fake_sb.table_log[0]
        self.assertEqual(admin._ADMIN_OVERRIDE_COLUMNS, query.ops[0][1])
        self.assertIn(("order", "created_at", True), query.ops)
        self.assertIn(("limit", 100), query.ops)


if __name__ == "__main__":
    unittest.main()
