import json
import sys
import tempfile
import types
import unittest
from pathlib import Path
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

if "supabase" not in sys.modules:
    sys.modules["supabase"] = types.SimpleNamespace(create_client=lambda *args, **kwargs: None)


from helpers import resource_affinity_runtime
from helpers import resource_affinity_unsupervised_eval as affinity_eval
from services import eic_report_service
from services import experiment_report_context_service as context_service
from services import ml_experiment_service


def _rows_for_table(table_name: str) -> list[dict]:
    if table_name == "resource_affinity_content_excerpts":
        return [
            {
                "resource_type": "worksheet",
                "resource_id": "1",
                "content_excerpt": "Read a short story about yesterday Choose the correct past tense verb",
                "content_excerpt_source": "sanitized_worksheet_json_view",
                "content_excerpt_char_count": 68,
            },
            {
                "resource_type": "exam",
                "resource_id": "exam1",
                "content_excerpt": "Choose the correct past tense verb",
                "content_excerpt_source": "sanitized_exam_data_view",
                "content_excerpt_char_count": 34,
            },
        ]
    if table_name == "lesson_plans":
        return [
            {
                "id": "lp1",
                "title": "Past tense story lesson",
                "subject": "English",
                "topic": "Past tense narratives",
                "learner_stage": "adult_stage",
                "level_or_band": "A2",
                "lesson_purpose": "review_topic",
                "plan_language": "en",
                "student_material_language": "en",
                "status": "active",
                "is_public": True,
                "plan_json": {
                    "learning_objectives": ["Use past tense verbs in a short story"],
                    "warm_up": ["Talk about yesterday"],
                    "assessment": {"success_criteria": "Student can retell a simple event"},
                },
            },
            {
                "id": "lp2",
                "title": "Archived lesson",
                "subject": "English",
                "topic": "Archived topic",
                "status": "archived",
                "plan_json": {"learning_objectives": ["Should not be included"]},
            },
        ]
    if table_name == "worksheets":
        return [
            {
                "id": str(idx),
                "title": title,
                "subject": subject,
                "topic": topic,
                "learner_stage": "adult_stage",
                "level_or_band": level,
                "worksheet_type": "fill_in_the_blanks",
                "student_material_language": lang,
                "status": "active",
                "is_public": True,
                "worksheet_json": {"instructions": f"Practice {topic}", "questions": [topic, title]},
            }
            for idx, title, subject, topic, level, lang in [
                (1, "Past verbs worksheet", "english", "Past tense narratives", "A2", "en"),
                (2, "Future plans worksheet", "English", "Future plans", "A2", "en"),
                (3, "Spanish subjunctive worksheet", "Spanish", "Subjunctive wishes", "B1", "es"),
                (4, "Spanish sports worksheet", "spanish", "Sports opinions", "B1", "es"),
                (5, "Math fractions worksheet", "math", "Equivalent fractions", "Grade 5", "en"),
            ]
        ]
    if table_name == "quick_exams":
        return [
            {
                "id": "exam1",
                "title": "Past tense quick exam",
                "subject": "English",
                "topic": "Past tense narratives",
                "learner_stage": "adult_stage",
                "level": "A2",
                "exam_length": "short",
                "exercise_types": ["multiple_choice", "short_answer"],
                "plan_language": "en",
                "student_material_language": "en",
                "status": "active",
                "is_public": True,
                "exam_data": {"questions": ["Choose the correct past tense verb"]},
            }
        ]
    if table_name == "videos":
        return [
            {
                "id": "video1",
                "title": "Past tense recap video",
                "subject": "English",
                "topic": "Past tense narratives",
                "description": "Short recap video for yesterday stories",
                "learner_stage": "adult_stage",
                "level_or_band": "A2",
                "student_material_language": "en",
                "status": "active",
                "is_public": True,
            }
        ]
    if table_name == "learning_programs":
        return [
            {
                "id": "program1",
                "title": "English A2 storytelling program",
                "subject": "English",
                "learner_stage": "adult_stage",
                "level_or_band": "A2",
                "program_language": "en",
                "student_material_language": "en",
                "program_overview": "Narrative speaking and grammar sequence",
                "status": "active",
                "is_public": True,
                "program_data": {"units": ["Past stories"]},
            }
        ]
    if table_name == "learning_program_topics":
        return [
            {
                "id": "topic1",
                "program_id": "program1",
                "unit_number": 1,
                "topic_number": 1,
                "title": "Past tense narratives",
                "lesson_focus": "Tell a simple story about yesterday",
                "lesson_purpose": "grammar_and_speaking",
                "learning_objectives": ["Use regular and irregular past tense verbs"],
                "success_criteria": "Student can retell a simple event",
                "status": "active",
            },
            {
                "id": "topic2",
                "program_id": "program1",
                "unit_number": 1,
                "topic_number": 2,
                "title": "Future plans",
                "lesson_focus": "Talk about planned activities",
                "lesson_purpose": "speaking",
                "learning_objectives": ["Use going to for plans"],
                "success_criteria": "Student can state a plan",
                "status": "active",
            },
        ]
    return []


def _select_columns(rows: list[dict], columns: str) -> list[dict]:
    wanted = [column.strip() for column in str(columns or "").split(",") if column.strip()]
    return [{key: row.get(key) for key in wanted if key in row} for row in rows]


class ResourceAffinityExperiment3UpgradeTests(unittest.TestCase):
    def setUp(self):
        if hasattr(resource_affinity_runtime.load_resource_affinity_index, "cache_clear"):
            resource_affinity_runtime.load_resource_affinity_index.cache_clear()

    def test_extraction_records_lesson_topics_normalization_and_exclusions(self):
        requested_columns = {}

        def fake_fetch(table, columns, page_size=500):
            requested_columns[table] = columns
            return _select_columns(_rows_for_table(table), columns)

        with patch.object(affinity_eval, "_fetch_all_rows", side_effect=fake_fetch):
            profiles, summary, exclusions, normalization = affinity_eval.extract_resource_profiles()

        self.assertNotIn("updated_at", requested_columns["worksheets"])
        self.assertNotIn("worksheet_json", requested_columns["worksheets"])
        self.assertNotIn("updated_at", requested_columns["quick_exams"])
        self.assertNotIn("exam_data", requested_columns["quick_exams"])
        self.assertIn("plan_language", requested_columns["quick_exams"])
        self.assertIn("student_material_language", requested_columns["videos"])
        self.assertIn("program_language", requested_columns["learning_programs"])
        self.assertEqual(12, summary["source_row_count"])
        self.assertEqual(11, summary["included_row_count"])
        self.assertEqual(1, summary["excluded_row_count"])
        self.assertEqual({"archived_status": 1}, summary["excluded_counts_by_reason"])
        self.assertEqual(2, summary["curricular_anchor_count"])
        self.assertEqual(9, summary["candidate_resource_count"])
        self.assertEqual(11, summary["completeness"]["language"]["known_count"])
        lesson = profiles[profiles["resource_key"] == "lesson_plan:lp1"].iloc[0].to_dict()
        self.assertIn("Use past tense verbs", lesson["topics_extracted"])
        topic = profiles[profiles["resource_key"] == "program_topic:topic1"].iloc[0].to_dict()
        self.assertEqual("curricular_anchor", topic["resource_role"])
        self.assertEqual("english", topic["subject_normalized"])
        self.assertIn("subject", set(normalization["field"]))
        self.assertEqual("english", profiles[profiles["resource_key"] == "lesson_plan:lp1"].iloc[0]["subject_normalized"])
        worksheet = profiles[profiles["resource_key"] == "worksheet:1"].iloc[0].to_dict()
        self.assertIn("short story", worksheet["content_excerpt"])
        self.assertEqual("sanitized_worksheet_json_view", worksheet["content_excerpt_source"])
        video = profiles[profiles["resource_key"] == "video:video1"].iloc[0].to_dict()
        self.assertEqual("en", video["language"])

    def test_extraction_does_not_fetch_large_json_when_excerpt_view_unavailable(self):
        calls = []

        def fake_fetch(table, columns, page_size=500):
            calls.append((table, columns, page_size))
            if table == affinity_eval.RESOURCE_CONTENT_EXCERPT_TABLE:
                raise RuntimeError("relation does not exist")
            return _select_columns(_rows_for_table(table), columns)

        with patch.object(affinity_eval, "_fetch_all_rows", side_effect=fake_fetch):
            profiles, summary, _, _ = affinity_eval.extract_resource_profiles()

        worksheet_calls = [call for call in calls if call[0] == "worksheets"]
        self.assertEqual(1, len(worksheet_calls))
        self.assertNotIn("worksheet_json", worksheet_calls[0][1])
        self.assertEqual(500, worksheet_calls[0][2])
        self.assertEqual(5, summary["included_counts_by_type"]["worksheet"])
        self.assertEqual("content_excerpt_view_unavailable_metadata_only", summary["warnings"][0]["warning"])
        self.assertTrue((profiles["resource_type"] == "worksheet").any())
        self.assertEqual("", profiles[profiles["resource_key"] == "worksheet:1"].iloc[0]["content_excerpt"])

    def test_local_json_sanitizer_excludes_answers_and_media(self):
        excerpt = affinity_eval._sanitize_content_excerpt(
            {
                "reading_passage": "Maria walked to school yesterday.",
                "questions": [
                    {
                        "stem": "What did Maria do?",
                        "options": ["walked to school", "stayed home"],
                        "answer_key": "walked to school",
                        "image_base64": "data:image/png;base64," + "x" * 1000,
                    }
                ],
                "solution": "The answer is A.",
            }
        )
        self.assertIn("Maria walked", excerpt)
        self.assertIn("What did Maria do", excerpt)
        self.assertIn("stayed home", excerpt)
        self.assertNotIn("answer is", excerpt)
        self.assertNotIn("base64", excerpt)

    def test_generation_writes_safe_local_artifacts_and_runtime_loads_fitted_representation(self):
        try:
            import sklearn  # noqa: F401
        except Exception:
            self.skipTest("scikit-learn is not available in this environment")
        with tempfile.TemporaryDirectory() as tmpdir:
            run_dir = Path(tmpdir) / "runs" / "run123"
            with patch.object(affinity_eval, "_fetch_all_rows", side_effect=lambda table, columns, page_size=500: _rows_for_table(table)):
                result = affinity_eval.generate_resource_affinity_unsupervised_evaluation(run_dir, run_id="run123")
                review = affinity_eval.review_resource_affinity_unsupervised(run_dir)

            self.assertEqual("run123", result["evaluation"]["run_id"])
            self.assertEqual("VALIDATED_EXPLORATORY_RUN", review["final_verdict"])
            for filename in [
                affinity_eval.EXCLUSION_AUDIT_FILENAME,
                affinity_eval.CATEGORY_NORMALIZATION_AUDIT_FILENAME,
                affinity_eval.ANCHOR_RESOURCE_CANDIDATES_FILENAME,
                affinity_eval.HUMAN_REVIEW_SAMPLE_FILENAME,
                affinity_eval.EXPERIMENT_CONFIG_FILENAME,
                affinity_eval.REPRESENTATION_MANIFEST_FILENAME,
            ]:
                self.assertTrue((run_dir / filename).exists(), filename)
            human_review = (run_dir / affinity_eval.HUMAN_REVIEW_SAMPLE_FILENAME).read_text(encoding="utf-8")
            self.assertIn("curricular_anchor", human_review)
            self.assertIn("candidate_resource", human_review)

            with (
                patch.object(resource_affinity_runtime, "RUNS_ROOT", Path(tmpdir) / "runs"),
                patch.object(resource_affinity_runtime, "ALLOW_NON_KMEANS_RUNTIME_FALLBACK", True),
            ):
                resource_affinity_runtime.load_resource_affinity_index.cache_clear()
                index = resource_affinity_runtime.load_resource_affinity_index()
                self.assertTrue(index["available"], index.get("reason"))
                self.assertIn(index["model_family"], {"dbscan", "kmeans", "agglomerativeclustering"})
                self.assertIn("preferred_family=kmeans", index["runtime_model_policy"])
                score, meta = resource_affinity_runtime.resource_affinity_score(
                    {"id": "1", "title": "Past verbs worksheet", "subject": "English", "topic": "Past tense narratives"},
                    "worksheet",
                    {"subject": "English", "topic": "Past tense story practice", "level": "A2"},
                )
            self.assertGreaterEqual(score, 0.0)
            self.assertTrue(meta["matched"])
            self.assertIn(meta["model_family"], {"dbscan", "kmeans", "agglomerativeclustering"})

    def test_runtime_prefers_kmeans_artifacts_over_newer_dbscan_artifacts(self):
        def write_candidate(run_dir: Path, winner: str, *, mtime: float) -> None:
            run_dir.mkdir(parents=True)
            (run_dir / "resource_affinity_run_summary.json").write_text(
                json.dumps(
                    {
                        "dataset": {
                            "feature_schema_version": "resource_affinity_unsupervised.v5",
                            "included_row_count": 10,
                        },
                        "evaluation": {
                            "winner": winner,
                            "best_model": {"model_name": winner, "selection_score": 0.12},
                        },
                    }
                ),
                encoding="utf-8",
            )
            (run_dir / "resource_affinity_model_comparison.csv").write_text(
                "model_name,selection_score\n" f"{winner},0.12\n",
                encoding="utf-8",
            )
            (run_dir / "resource_affinity_dataset_frozen.csv").write_text("resource_key\nworksheet:1\n", encoding="utf-8")
            (run_dir / "resource_affinity_cluster_assignments.csv").write_text("resource_key,cluster_id\nworksheet:1,0\n", encoding="utf-8")
            (run_dir / "resource_affinity_representation_manifest.json").write_text("{}", encoding="utf-8")
            for path in run_dir.iterdir():
                path.touch()
            (run_dir / "resource_affinity_run_summary.json").touch()
            import os

            for path in run_dir.iterdir():
                os.utime(path, (mtime, mtime))

        with tempfile.TemporaryDirectory() as tmpdir:
            runs_root = Path(tmpdir) / "runs"
            write_candidate(runs_root / "older_kmeans", "KMeans k=24", mtime=100.0)
            write_candidate(runs_root / "newer_dbscan", "DBSCAN eps=0.32 min_samples=2", mtime=200.0)

            with patch.object(resource_affinity_runtime, "RUNS_ROOT", runs_root):
                self.assertEqual("older_kmeans", resource_affinity_runtime._best_run_dir().name)

    def test_resource_affinity_artifact_labels_are_experiment_aware(self):
        path = Path("resource_affinity_pairwise_neighbors.csv")
        self.assertEqual("Pairwise Semantic Neighbors CSV", eic_report_service._artifact_display_name("holdout_predictions_csv", path))
        self.assertEqual("Holdout Predictions CSV", eic_report_service._artifact_display_name("holdout_predictions_csv", Path("assigned_predictions.csv")))

    def test_run_aware_context_uses_local_summary_without_supabase(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            run_root = Path(tmpdir) / "reports" / "ml_architecture" / "resource_affinity_unsupervised" / "runs" / "run123"
            run_root.mkdir(parents=True)
            (run_root / "resource_affinity_run_summary.json").write_text(
                json.dumps(
                    {
                        "dataset": {"included_row_count": 6, "excluded_row_count": 1},
                        "evaluation": {
                            "maturity_verdict": "EXPLORATORY_ONLY",
                            "best_model": {"model_name": "DBSCAN eps=0.32 min_samples=2", "silhouette_score": 0.75},
                        },
                    }
                ),
                encoding="utf-8",
            )
            old_cwd = Path.cwd()
            try:
                import os

                os.chdir(tmpdir)
                with (
                    patch.object(context_service, "REPORT_CONTEXT_ROOT", Path(tmpdir) / "eic_reports"),
                    patch.object(context_service, "get_sb") as get_sb,
                    patch.dict("os.environ", {"EXPERIMENT_REPORT_CONTEXT_STORAGE": "local"}, clear=False),
                ):
                    context = context_service.get_report_context("run123", "resource_affinity_unsupervised_discovery", "en")
            finally:
                os.chdir(old_cwd)

        get_sb.assert_not_called()
        self.assertIn("6 resources", context["business_problem"])
        self.assertIn("structured human review", context["decision_supported"])

    def test_resource_affinity_eligibility_is_metadata_only(self):
        with (
            patch.object(ml_experiment_service, "list_experiment_runs", return_value=[]),
            patch.object(affinity_eval, "extract_resource_profiles") as extract_profiles,
        ):
            result = ml_experiment_service.compute_resource_affinity_experiment_eligibility()

        extract_profiles.assert_not_called()
        self.assertTrue(result.eligible)
        self.assertTrue(result.data_summary["catalog_scan_deferred"])


if __name__ == "__main__":
    unittest.main()
