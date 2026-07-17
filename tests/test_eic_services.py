import inspect
from pathlib import Path
import sys
import tempfile
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
    streamlit_mod.error = lambda *args, **kwargs: None
    streamlit_mod.stop = lambda: (_ for _ in ()).throw(RuntimeError("streamlit.stop"))
    streamlit_mod.markdown = lambda *args, **kwargs: None
    streamlit_mod.caption = lambda *args, **kwargs: None
    streamlit_mod.columns = lambda *args, **kwargs: [types.SimpleNamespace(__enter__=lambda self: self, __exit__=lambda self, exc_type, exc, tb: False) for _ in range(8)]
    streamlit_mod.button = lambda *args, **kwargs: False
    streamlit_mod.selectbox = lambda label, options, **kwargs: options[0] if options else ""
    streamlit_mod.dataframe = lambda *args, **kwargs: None
    streamlit_mod.info = lambda *args, **kwargs: None
    streamlit_mod.success = lambda *args, **kwargs: None
    streamlit_mod.warning = lambda *args, **kwargs: None
    streamlit_mod.tabs = lambda labels: [types.SimpleNamespace(__enter__=lambda self: self, __exit__=lambda self, exc_type, exc, tb: False) for _ in labels]
    streamlit_mod.expander = lambda *args, **kwargs: types.SimpleNamespace(__enter__=lambda self: self, __exit__=lambda self, exc_type, exc, tb: False)
    streamlit_mod.download_button = lambda *args, **kwargs: False
    streamlit_mod.text_input = lambda *args, **kwargs: ""
    streamlit_mod.text_area = lambda *args, **kwargs: ""
    streamlit_mod.checkbox = lambda *args, **kwargs: False
    streamlit_mod.form = lambda *args, **kwargs: types.SimpleNamespace(__enter__=lambda self: self, __exit__=lambda self, exc_type, exc, tb: False)
    streamlit_mod.form_submit_button = lambda *args, **kwargs: False
    streamlit_mod.rerun = lambda: None
    streamlit_mod.query_params = {}
else:
    streamlit_mod = sys.modules["streamlit"]
    if not hasattr(streamlit_mod, "cache_resource"):
        def _cache_data(*args, **kwargs):
            def decorator(fn):
                fn.clear = lambda: None
                return fn
            return decorator
        streamlit_mod.cache_resource = _cache_data

if "streamlit.components" not in sys.modules:
    components_v1 = types.SimpleNamespace(html=lambda *args, **kwargs: None)
    sys.modules["streamlit.components"] = types.SimpleNamespace(v1=components_v1)
    sys.modules["streamlit.components.v1"] = components_v1

if "openai" not in sys.modules:
    sys.modules["openai"] = types.SimpleNamespace(OpenAI=object)

if "supabase" not in sys.modules:
    sys.modules["supabase"] = types.SimpleNamespace(create_client=lambda *args, **kwargs: None)

if "pycountry" not in sys.modules:
    sys.modules["pycountry"] = types.SimpleNamespace(countries=[], languages=[])


from app_pages import admin
from services import eic_service
from services.eic_display_service import (
    get_model_comparison_column_display,
    get_model_comparison_value_display,
)
from translations_en import EN
from translations_es import ES
from translations_tr import TR


class _FakeResult:
    def __init__(self, data):
        self.data = data


class _FakeQuery:
    def __init__(self, table_name, store):
        self.table_name = table_name
        self.store = store
        self.filters = []
        self._limit = None
        self._range = None
        self._order = None

    def select(self, value):
        return self

    def eq(self, column, value):
        self.filters.append(("eq", column, value))
        return self

    def in_(self, column, values):
        self.filters.append(("in", column, tuple(values)))
        return self

    def gte(self, column, value):
        self.filters.append(("gte", column, value))
        return self

    def lte(self, column, value):
        self.filters.append(("lte", column, value))
        return self

    def order(self, column, desc=False):
        self._order = (column, bool(desc))
        return self

    def limit(self, value):
        self._limit = int(value)
        return self

    def range(self, start, end):
        self._range = (int(start), int(end))
        return self

    def _matches(self, row):
        for op, column, value in self.filters:
            current = row.get(column)
            if op == "eq" and current != value:
                return False
            if op == "in" and current not in value:
                return False
            if op == "gte" and str(current or "") < str(value):
                return False
            if op == "lte" and str(current or "") > str(value):
                return False
        return True

    def execute(self):
        rows = [dict(row) for row in self.store.get(self.table_name, []) if self._matches(row)]
        if self._order:
            column, desc = self._order
            rows.sort(key=lambda row: str(row.get(column) or ""), reverse=desc)
        if self._range is not None:
            start, end = self._range
            rows = rows[start : end + 1]
        if self._limit is not None:
            rows = rows[: self._limit]
        return _FakeResult(rows)


class _FakeSupabase:
    def __init__(self, store):
        self.store = store

    def table(self, table_name):
        return _FakeQuery(table_name, self.store)


class EICServiceTests(unittest.TestCase):
    def setUp(self):
        for fn_name in [
            "get_business_telemetry_health",
            "get_intelligence_component_portfolio",
            "list_validated_experiment_summaries",
            "get_latest_validated_run_summary",
            "get_academic_evidence_summary",
            "get_validated_report_downloads",
            "get_intelligence_business_summary",
            "get_evidence_trend",
        ]:
            fn = getattr(eic_service, fn_name, None)
            if hasattr(fn, "clear"):
                fn.clear()

    def test_validated_experiment_registry_excludes_failed_and_superseded_runs(self):
        fake_sb = _FakeSupabase(
            {
                "ml_experiment_runs": [
                    {"run_id": "valid-2", "experiment_id": "assigned_resource_open_within_7d", "run_status": "VALIDATED_NO_ROBUST_WINNER", "created_at": "2026-07-16T11:00:00+00:00"},
                    {"run_id": "failed-1", "experiment_id": "assigned_resource_open_within_7d", "run_status": "FAILED", "created_at": "2026-07-16T10:00:00+00:00"},
                    {"run_id": "valid-1", "experiment_id": "assigned_resource_open_within_7d", "run_status": "VALIDATED_EXPLORATORY_RUN", "created_at": "2026-07-16T09:00:00+00:00"},
                    {"run_id": "old", "experiment_id": "assigned_resource_open_within_7d", "run_status": "SUPERSEDED", "created_at": "2026-07-16T08:00:00+00:00"},
                ]
            }
        )
        with patch.object(eic_service, "get_sb", return_value=fake_sb):
            rows = eic_service.list_validated_experiment_summaries(cache_bust="1")

        self.assertEqual(["valid-2", "valid-1"], [row["run_id"] for row in rows])

    def test_business_summary_without_validated_run_recommends_data_collection(self):
        fake_sb = _FakeSupabase({"ml_experiment_runs": [], "resource_exposures": [], "resource_exposure_events": []})
        with (
            patch.object(eic_service, "get_sb", return_value=fake_sb),
            patch.object(
                eic_service,
                "list_experiment_catalog",
                return_value=[
                    {
                        "experiment_id": "assigned_resource_open_within_7d",
                        "display_label": "Experiment 1: Assigned Resource Open Within 7 Days",
                        "component_type": "supervised_experiment",
                        "latest_validated_run": {},
                        "validated_run_count": 0,
                    }
                ],
            ),
        ):
            summary = eic_service.get_intelligence_business_summary(cache_bust="1")

        cards = {row["label"]: row for row in summary["cards"]}
        self.assertEqual("continue_collecting_data", cards["recommended_business_action"]["value"])
        self.assertEqual({}, summary["latest_validated_run"])

    def test_portfolio_preserves_component_classification(self):
        fake_sb = _FakeSupabase({"ml_experiment_runs": []})
        with (
            patch.object(eic_service, "get_sb", return_value=fake_sb),
            patch.object(
                eic_service,
                "list_experiment_catalog",
                return_value=[
                    {
                        "experiment_id": "assigned_resource_open_within_7d",
                        "display_label": "Experiment 1: Assigned Resource Open Within 7 Days",
                        "component_type": "supervised_experiment",
                        "latest_validated_run": {},
                        "validated_run_count": 0,
                    }
                ],
            ),
        ):
            portfolio = eic_service.get_intelligence_component_portfolio(cache_bust="1")

        component_map = {row["component_id"]: row for row in portfolio}
        self.assertEqual("deterministic_workflow", component_map["practice_mastery_aggregator"]["component_type"])
        self.assertEqual("supervised_experiment", component_map["assigned_resource_open_within_7d"]["component_type"])

    def test_academic_evidence_uses_same_run_id_and_fingerprint(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            dataset_summary = root / "dataset_summary.json"
            run_summary = root / "run_summary.json"
            model_comparison = root / "model_comparison.csv"
            academic_report = root / "findings_interpretation_report.md"
            feature_audit = root / "feature_audit.csv"
            technical_report = root / "technical_report.md"
            dataset_summary.write_text('{"data_fingerprint":"fp-1"}', encoding="utf-8")
            run_summary.write_text('{"evaluation":{"best_thresholded_classifier":"LogisticRegression","best_precision_recall_ranking":"RandomForestClassifier","calibration_leader":"DummyClassifier","overall_evidence_strength":"Exploratory evidence"}}', encoding="utf-8")
            model_comparison.write_text("model_name,roc_auc\nDummyClassifier,0.5\nLogisticRegression,0.7\n", encoding="utf-8")
            academic_report.write_text("# findings interpretation", encoding="utf-8")
            feature_audit.write_text("feature,retained\nx,True\n", encoding="utf-8")
            technical_report.write_text("# technical", encoding="utf-8")

            fake_sb = _FakeSupabase(
                {
                    "ml_experiment_runs": [
                        {
                            "run_id": "run-1",
                            "experiment_id": "assigned_resource_open_within_7d",
                            "run_status": "VALIDATED_EXPLORATORY_RUN",
                            "created_at": "2026-07-16T10:00:00+00:00",
                            "included_row_count": 125,
                            "positive_label_count": 72,
                            "negative_label_count": 53,
                            "teachers_represented": 1,
                            "students_represented": 9,
                            "resources_represented": 22,
                            "dataset_fingerprint": "fp-1",
                            "source_start_at": "2026-04-10T00:00:00+00:00",
                            "source_end_at": "2026-07-12T00:00:00+00:00",
                            "chronological_cutoff": "2026-07-01T00:00:00+00:00",
                            "primary_metric_leader": "LogisticRegression",
                        }
                    ],
                    "ml_run_artifacts": [
                        {"run_id": "run-1", "artifact_type": "dataset_summary_json", "storage_path": str(dataset_summary), "content_type": "application/json", "size_bytes": dataset_summary.stat().st_size},
                        {"run_id": "run-1", "artifact_type": "run_summary_json", "storage_path": str(run_summary), "content_type": "application/json", "size_bytes": run_summary.stat().st_size},
                        {"run_id": "run-1", "artifact_type": "model_comparison_csv", "storage_path": str(model_comparison), "content_type": "text/csv", "size_bytes": model_comparison.stat().st_size},
                        {"run_id": "run-1", "artifact_type": "findings_interpretation_report_md", "storage_path": str(academic_report), "content_type": "text/markdown", "size_bytes": academic_report.stat().st_size},
                        {"run_id": "run-1", "artifact_type": "feature_audit_csv", "storage_path": str(feature_audit), "content_type": "text/csv", "size_bytes": feature_audit.stat().st_size},
                        {"run_id": "run-1", "artifact_type": "technical_report_md", "storage_path": str(technical_report), "content_type": "text/markdown", "size_bytes": technical_report.stat().st_size},
                    ],
                }
            )
            with (
                patch.object(eic_service, "get_sb", return_value=fake_sb),
                patch.object(
                    eic_service,
                    "list_experiment_catalog",
                    return_value=[
                        {
                            "experiment_id": "assigned_resource_open_within_7d",
                            "display_label": "Experiment 1: Assigned Resource Open Within 7 Days",
                            "business_question": "Can assigned resource opens be predicted within seven days?",
                            "latest_validated_run": {},
                            "validated_run_count": 1,
                        }
                    ],
                ),
            ):
                summary = eic_service.get_academic_evidence_summary("run-1", cache_bust="1")

        self.assertTrue(summary["is_final"])
        self.assertEqual("run-1", summary["run_id"])
        self.assertEqual("fp-1", summary["dataset_fingerprint"])
        self.assertEqual("LogisticRegression", summary["selected_metric_leader"])

    def test_technical_report_download_is_capability_gated(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            report_path = root / "technical_report.md"
            report_path.write_text("# technical", encoding="utf-8")
            artifact_rows = [
                {"run_id": "run-1", "artifact_type": "technical_report_md", "storage_path": str(report_path), "content_type": "text/markdown", "size_bytes": report_path.stat().st_size}
            ]
            with patch.object(eic_service, "list_run_artifacts", return_value=artifact_rows):
                with patch.object(eic_service, "has_capability", return_value=False):
                    hidden = eic_service.get_validated_report_downloads("run-1", cache_bust="1")
                eic_service.get_validated_report_downloads.clear()
                with patch.object(eic_service, "has_capability", return_value=True):
                    visible = eic_service.get_validated_report_downloads("run-1", cache_bust="2")

        self.assertEqual([], hidden)
        self.assertEqual("technical_report", visible[0]["report_id"])

    def test_phase4_translation_keys_exist_in_all_dictionaries(self):
        required = [
            "admin_ai_intelligence",
            "admin_ai_intelligence_title",
            "admin_eic_tab_overview",
            "admin_eic_tab_systems",
            "admin_eic_tab_evidence",
            "admin_eic_tab_data_health",
            "admin_eic_tab_decisions",
            "admin_eic_tab_reports",
            "admin_eic_empty_no_validated_run",
            "admin_eic_open_developer_workspace",
            "admin_staff_access_title",
            "admin_eic_status_healthy",
            "admin_eic_action_continue_collecting_data",
            "admin_eic_report_type_executive_docx",
            "admin_eic_report_type_academic_docx",
            "admin_eic_report_type_technical_docx",
            "admin_eic_report_download_button",
            "admin_eic_component_name_student_recommendation_ranker",
            "admin_eic_run_status_validated_no_robust_winner",
            "admin_eic_model_table_model_name",
            "admin_eic_model_table_balanced_accuracy",
            "admin_eic_model_kind_supervised",
            "admin_eic_model_status_not_applicable",
            "admin_eic_model_name_logistic_regression_reduced",
        ]
        for key in required:
            self.assertIn(key, EN)
            self.assertIn(key, ES)
            self.assertIn(key, TR)

    def test_model_comparison_display_helpers_normalize_headers_and_values(self):
        self.assertEqual("Model", get_model_comparison_column_display("model_name", lang="en"))
        self.assertEqual("Balanced accuracy", get_model_comparison_column_display("balanced_accuracy", lang="en"))
        self.assertEqual("Logistic regression (reduced)", get_model_comparison_value_display("model_name", "LogisticRegressionReduced", lang="en"))
        self.assertEqual("Supervised", get_model_comparison_value_display("model_kind", "supervised", lang="en"))
        self.assertEqual("Not applicable", get_model_comparison_value_display("cv_status", "not_applicable", lang="en"))
        self.assertEqual("Yes", get_model_comparison_value_display("used_reduced_features", "True", lang="en"))

    def test_eic_render_path_avoids_old_hardcoded_business_strings(self):
        source = inspect.getsource(admin._render_admin_ai_intelligence)
        self.assertNotIn("Legacy Diagnostic Reports", source)
        self.assertNotIn("Validated Supervised Experiment Status", source)
        self.assertNotIn("AI Intelligence", source)
        self.assertIn("get_component_display_name", source)
        self.assertIn("get_experiment_display_name", source)
        self.assertIn("get_or_create_validated_report", source)


if __name__ == "__main__":
    unittest.main()
