import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch
from zipfile import ZipFile
import xml.etree.ElementTree as ET


if "streamlit" not in sys.modules:
    def _cache_data(*args, **kwargs):
        def decorator(fn):
            fn.clear = lambda: None
            return fn
        return decorator

    sys.modules["streamlit"] = types.ModuleType("streamlit")
    streamlit_mod = sys.modules["streamlit"]
    streamlit_mod.session_state = {"ui_lang": "en"}
    streamlit_mod.secrets = {}
    streamlit_mod.cache_data = _cache_data
    streamlit_mod.cache_resource = _cache_data
    streamlit_mod.error = lambda *args, **kwargs: None
    streamlit_mod.stop = lambda: (_ for _ in ()).throw(RuntimeError("streamlit.stop"))
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

if "supabase" not in sys.modules:
    sys.modules["supabase"] = types.SimpleNamespace(create_client=lambda *args, **kwargs: None)

if "pycountry" not in sys.modules:
    sys.modules["pycountry"] = types.SimpleNamespace(countries=[], languages=[])


from services.authorization_service import CAPABILITY_VIEW_TECHNICAL_ARTIFACTS
from services import eic_report_service


class EICReportServiceTests(unittest.TestCase):
    def _base_context(self):
        return {
            "detail": {
                "run_status": "VALIDATED_EXPLORATORY_RUN",
                "integrity_status": "PASSED",
                "maturity_verdict": "EXPLORATORY_ONLY",
                "evidence_verdict": "exploratory",
                "evidence_level": "exploratory",
                "primary_metric_leader": "LogisticRegression",
                "dataset_fingerprint": "fp-1",
                "teachers_represented": 1,
                "students_represented": 9,
                "resources_represented": 22,
                "model_results": {
                    "models_compared": [
                        {"model_name": "DummyClassifier", "model_kind": "baseline", "status": "success", "roc_auc": "0.50"},
                        {"model_name": "LogisticRegression", "model_kind": "supervised", "status": "success", "roc_auc": "0.71"},
                        {"model_name": "LogisticRegressionReduced", "model_kind": "supervised", "status": "success", "roc_auc": "0.73"},
                        {"model_name": "DecisionTreeClassifier", "model_kind": "supervised", "status": "success", "roc_auc": "0.69"},
                        {"model_name": "RandomForestClassifier", "model_kind": "supervised", "status": "success", "roc_auc": "0.82"},
                        {"model_name": "HistGradientBoostingClassifier", "model_kind": "supervised", "status": "success", "roc_auc": "0.75"},
                        {"model_name": "SVC", "model_kind": "supervised", "status": "success", "roc_auc": "0.74"},
                        {"model_name": "KNeighborsClassifier", "model_kind": "supervised", "status": "success", "roc_auc": "0.70"},
                    ],
                    "overall_evidence_conclusion": "exploratory",
                    "best_thresholded_classifier": "LogisticRegression",
                    "precision_recall_leader": "LogisticRegression",
                    "calibration_leader": "DummyClassifier",
                    "robust_winner": "yes",
                },
                "limitations": ["Only one teacher is represented in the current mature label set."],
                "validation_notes": "Integrity review passed.",
                "business_question": "Can Classio predict whether a student will open an assigned resource within seven days?",
            },
            "academic": {
                "dataset_fingerprint": "fp-1",
                "dataset_size": 125,
                "class_balance": 0.576,
                "company_context": "Classio is evaluating educational intelligence systems.",
                "business_problem": "Predict whether an assigned resource will be opened within seven days.",
                "smart_objective": "Build evidence without changing live ordering.",
                "target_definition": "opened_within_7d label",
                "train_holdout_split": {"chronological_cutoff": "2026-07-01T00:00:00+00:00"},
                "evaluation_design": "Chronological holdout.",
                "baseline": "DummyClassifier",
                "selected_metric_leader": "LogisticRegression",
                "overall_evidence_conclusion": "Exploratory evidence only.",
                "limitations": ["Teacher coverage is limited."],
                "production_readiness_decision": "EXPLORATORY_ONLY",
            },
            "telemetry": {
                "summary": {
                    "total_canonical_exposures": 125,
                    "matched_open_coverage": 0.72,
                    "unmatched_opens": 3,
                    "telemetry_freshness_hours": 4.0,
                }
            },
            "portfolio": [
                {
                    "component_id": "assigned_resource_open_within_7d",
                    "component_type": "supervised_experiment",
                    "operational_status": "offline_evaluation",
                    "recommended_next_action": "expand_teacher_coverage",
                }
            ],
            "decisions": [
                {
                    "component_id": "assigned_resource_open_within_7d",
                    "issue": "Teacher coverage is narrow.",
                    "recommended_action": "expand_teacher_coverage",
                }
            ],
            "latest_summary": {"top_decision": {"recommended_action": "expand_teacher_coverage"}},
            "run_summary": {
                "evaluation": {
                    "best_thresholded_classifier": "LogisticRegression",
                    "best_precision_recall_ranking": "LogisticRegression",
                    "calibration_leader": "DummyClassifier",
                },
                "review": {"label_reconciliation": {"limitations": ["No duplicate labels were detected."]}},
            },
            "dataset_summary": {
                "target_version": "opened_within_7d_v1",
                "feature_schema_version": "phase3_6_v1",
            },
            "lang": "en",
        }

    def _document_xml(self, path: Path) -> str:
        with ZipFile(path, "r") as handle:
            return handle.read("word/document.xml").decode("utf-8")

    def _section_xml(self, path: Path) -> str:
        with ZipFile(path, "r") as handle:
            return handle.read("word/document.xml").decode("utf-8")

    def test_all_word_reports_generate_real_docx_files(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with (
                patch.object(eic_report_service, "REPORT_ROOT", Path(tmpdir)),
                patch.object(eic_report_service, "_report_base_context", return_value=self._base_context()),
                patch.object(eic_report_service, "_artifact_path_map", return_value={}),
            ):
                builders = [
                    eic_report_service.build_experiment_report_docx,
                    eic_report_service.build_executive_report_docx,
                    eic_report_service.build_academic_report_docx,
                    eic_report_service.build_technical_report_docx,
                ]
                for builder in builders:
                    result = builder("run-1", "en")
                    self.assertTrue(result["ok"])
                    self.assertTrue(Path(result["path"]).exists())
                    with ZipFile(Path(result["path"]), "r") as handle:
                        self.assertIn("word/document.xml", handle.namelist())
                    xml_text = self._document_xml(Path(result["path"]))
                    self.assertNotIn("insufficient_to_establish_clear_winner", xml_text)
                    self.assertNotIn("VALIDATED_NO_ROBUST_WINNER", xml_text)
                    self.assertIn("run-1", xml_text)
                    self.assertIn("fp-1", xml_text)

    def test_reports_include_expected_rich_sections(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with (
                patch.object(eic_report_service, "REPORT_ROOT", Path(tmpdir)),
                patch.object(eic_report_service, "_report_base_context", return_value=self._base_context()),
                patch.object(eic_report_service, "_artifact_path_map", return_value={}),
            ):
                experiment_result = eic_report_service.build_experiment_report_docx("run-1", "en")
                exec_result = eic_report_service.build_executive_report_docx("run-1", "en")
                academic_result = eic_report_service.build_academic_report_docx("run-1", "en")
                technical_result = eic_report_service.build_technical_report_docx("run-1", "en")
                experiment_xml = self._document_xml(Path(experiment_result["path"]))
                self.assertIn("Technical Data Science Report", experiment_xml)
                self.assertIn("Feature schema and feature health", experiment_xml)
                self.assertIn("Threshold analysis", experiment_xml)
                self.assertIn("Precision-recall analysis", experiment_xml)
                self.assertIn("Artifact manifest", experiment_xml)
                exec_xml = self._document_xml(Path(exec_result["path"]))
                self.assertIn("Executive Summary", exec_xml)
                self.assertIn("Intelligence portfolio summary", exec_xml)
                self.assertIn("Prioritized actions", exec_xml)

                academic_xml = self._document_xml(Path(academic_result["path"]))
                academic_lower = academic_xml.lower()
                self.assertIn("Problem statement", academic_xml)
                self.assertIn("Solution statement", academic_xml)
                self.assertIn("SMART objectives", academic_xml)
                self.assertIn("Models evaluated", academic_xml)
                for model_name in [
                    "DummyClassifier",
                    "LogisticRegression",
                    "LogisticRegressionReduced",
                    "DecisionTreeClassifier",
                    "RandomForestClassifier",
                ]:
                    self.assertIn(model_name, academic_xml)

                technical_xml = self._document_xml(Path(technical_result["path"]))
                self.assertIn("Feature schema and feature health", technical_xml)
                self.assertIn("Threshold analysis", technical_xml)
                self.assertIn("ROC analysis", technical_xml)
                self.assertIn("Precision-recall analysis", technical_xml)
                self.assertIn("Artifact manifest", technical_xml)

    def test_technical_report_deduplicates_confusion_matrix_when_roles_share_same_model(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            picture_calls = []

            def _capture_picture(_doc, _path, caption, **kwargs):
                picture_calls.append(caption)

            with (
                patch.object(eic_report_service, "REPORT_ROOT", Path(tmpdir)),
                patch.object(eic_report_service, "_report_base_context", return_value=self._base_context()),
                patch.object(eic_report_service, "_artifact_path_map", return_value={}),
                patch.object(eic_report_service, "_add_picture_with_caption", side_effect=_capture_picture),
            ):
                result = eic_report_service.build_technical_report_docx("run-1", "en")
                self.assertTrue(result["ok"])
                confusion_captions = [caption for caption in picture_calls if "Confusion matrix" in caption]
                self.assertEqual(
                    [
                        "Figure 6. Confusion matrix for the stored baseline.",
                        "Figure 7. Confusion matrix for the primary ROC leader.",
                    ],
                    confusion_captions,
                )

    def test_technical_report_limitations_fallback_is_rendered(self):
        context = self._base_context()
        context["detail"]["limitations"] = []
        context["academic"]["limitations"] = []
        context["run_summary"]["review"]["label_reconciliation"]["limitations"] = []
        with tempfile.TemporaryDirectory() as tmpdir:
            with (
                patch.object(eic_report_service, "REPORT_ROOT", Path(tmpdir)),
                patch.object(eic_report_service, "_report_base_context", return_value=context),
                patch.object(eic_report_service, "_artifact_path_map", return_value={}),
            ):
                result = eic_report_service.build_technical_report_docx("run-1", "en")
                xml_text = self._document_xml(Path(result["path"]))
                self.assertIn("No additional validated risks were recorded for this run.", xml_text)

    def test_technical_report_contains_landscape_section_and_repeating_headers(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with (
                patch.object(eic_report_service, "REPORT_ROOT", Path(tmpdir)),
                patch.object(eic_report_service, "_report_base_context", return_value=self._base_context()),
                patch.object(eic_report_service, "_artifact_path_map", return_value={}),
            ):
                result = eic_report_service.build_technical_report_docx("run-1", "en")
                with ZipFile(Path(result["path"]), "r") as handle:
                    xml_bytes = handle.read("word/document.xml")
                root = ET.fromstring(xml_bytes)
                ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
                self.assertTrue(root.findall(".//w:sectPr/w:pgSz[@w:orient='landscape']", ns))
                self.assertTrue(root.findall(".//w:trPr/w:tblHeader", ns))

    def test_report_listing_respects_validated_and_restricted_states(self):
        with patch.object(eic_report_service, "_validated_run_detail", return_value={"run_id": "run-1"}):
            restricted_rows = eic_report_service.list_available_eic_reports("run-1", set(), language="en")
            visible_rows = eic_report_service.list_available_eic_reports(
                "run-1",
                {CAPABILITY_VIEW_TECHNICAL_ARTIFACTS},
                language="en",
            )

        self.assertEqual(["experiment_docx"], [row["report_type"] for row in restricted_rows])
        self.assertEqual("available", restricted_rows[0]["status"])
        self.assertEqual(["experiment_docx"], [row["report_type"] for row in visible_rows])
        self.assertEqual("available", visible_rows[0]["status"])

        with patch.object(eic_report_service, "_validated_run_detail", return_value={}):
            unavailable_rows = eic_report_service.list_available_eic_reports("run-2", set(), language="en")
        self.assertTrue(all(row["status"] == "no_validated_run" for row in unavailable_rows))

    def test_generation_fails_cleanly_without_validated_context(self):
        with patch.object(eic_report_service, "_report_base_context", return_value={}):
            result = eic_report_service.build_executive_report_docx("run-x", "en")
        self.assertFalse(result["ok"])
        self.assertIn("validated", result["message"].lower())


if __name__ == "__main__":
    unittest.main()
