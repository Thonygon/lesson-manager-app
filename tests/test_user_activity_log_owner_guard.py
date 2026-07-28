import sys
import types
import unittest
from unittest.mock import patch


if "streamlit" not in sys.modules:
    def _cache_data(*args, **kwargs):
        def decorator(fn):
            fn.clear = lambda: None
            return fn
        return decorator

    sys.modules["streamlit"] = types.ModuleType("streamlit")
    streamlit_mod = sys.modules["streamlit"]
    streamlit_mod.session_state = {}
    streamlit_mod.secrets = {}
    streamlit_mod.cache_data = _cache_data
    streamlit_mod.cache_resource = _cache_data
    streamlit_mod.warning = lambda *args, **kwargs: None
    streamlit_mod.error = lambda *args, **kwargs: None
    streamlit_mod.stop = lambda: (_ for _ in ()).throw(RuntimeError("streamlit.stop"))

if "supabase" not in sys.modules:
    sys.modules["supabase"] = types.SimpleNamespace(create_client=lambda *args, **kwargs: None)

if "pycountry" not in sys.modules:
    sys.modules["pycountry"] = types.SimpleNamespace(countries=[], languages=[])


import streamlit as st

from helpers import planner_storage
from helpers import recommendation_models
from helpers import student_recommendation_ml


class _FailingSupabase:
    def table(self, table_name):
        raise AssertionError(f"Unexpected Supabase write to {table_name}")


class UserActivityLogOwnerGuardTests(unittest.TestCase):
    def setUp(self):
        st.session_state.clear()

    def test_planner_activity_skips_when_user_missing(self):
        with patch.object(planner_storage, "get_sb", return_value=_FailingSupabase()):
            planner_storage.log_user_activity("test_activity", "test_feature", {"ok": True})

    def test_teacher_material_impressions_skip_activity_insert_when_user_missing(self):
        rows = [{"id": 1, "title": "Resource", "subject": "English", "topic": "Past tense"}]
        with (
            patch.object(recommendation_models, "get_sb", return_value=_FailingSupabase()),
            patch.object(recommendation_models, "attach_teacher_material_feed_exposures", return_value=rows),
        ):
            recommendation_models.log_teacher_material_impressions(
                rows,
                "worksheet",
                "library",
                surface="teacher_home",
            )

    def test_student_recommendation_impressions_skip_activity_insert_when_user_missing(self):
        rows = [
            {
                "id": 1,
                "resource_type": "worksheet",
                "learning_program_assignment_id": 2,
                "learning_program_topic_id": 3,
                "title": "Resource",
                "subject": "English",
                "topic": "Past tense",
            }
        ]
        with (
            patch.object(student_recommendation_ml, "get_sb", return_value=_FailingSupabase()),
            patch.object(student_recommendation_ml, "attach_student_recommendation_exposures", return_value=rows),
        ):
            student_recommendation_ml.log_student_recommendation_impressions(rows, surface="student_home")


if __name__ == "__main__":
    unittest.main()
