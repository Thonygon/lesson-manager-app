import sys
import types
import unittest
from unittest.mock import patch
from pathlib import Path
import tempfile


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
        rerun=lambda: None,
        tabs=lambda labels: [types.SimpleNamespace(__enter__=lambda self: self, __exit__=lambda self, exc_type, exc, tb: False) for _ in labels],
        page_link=lambda *args, **kwargs: None,
    )

if "supabase" not in sys.modules:
    sys.modules["supabase"] = types.SimpleNamespace(create_client=lambda *args, **kwargs: None)

if "pycountry" not in sys.modules:
    sys.modules["pycountry"] = types.SimpleNamespace(countries=[], languages=[])

from services import authorization_service as authz
from services import controlled_jobs_service as jobs
from services import ml_experiment_service as ml
from services import privileged_action_service as audit
from services import staff_roles_service as staff
from app_pages import developer_workspace as dev_workspace


class _FakeResult:
    def __init__(self, data):
        self.data = data


class _FakeQuery:
    def __init__(self, table_name, store):
        self.table_name = table_name
        self.store = store
        self.filters = []
        self.selected = None
        self._limit = None
        self._order = None
        self._pending_insert = None
        self._pending_update = None
        self._pending_delete = False
        self._range = None

    def select(self, value):
        self.selected = value
        return self

    def eq(self, column, value):
        self.filters.append(("eq", column, value))
        return self

    def in_(self, column, value):
        self.filters.append(("in", column, tuple(value)))
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

    def insert(self, payload):
        self._pending_insert = payload
        return self

    def update(self, payload):
        self._pending_update = payload
        return self

    def delete(self):
        self._pending_delete = True
        return self

    def _matches(self, row):
        for op, column, value in self.filters:
            current = row.get(column)
            if op == "eq" and current != value:
                return False
            if op == "in" and current not in value:
                return False
        return True

    def execute(self):
        rows = self.store.setdefault(self.table_name, [])
        if self._pending_insert is not None:
            payloads = self._pending_insert if isinstance(self._pending_insert, list) else [self._pending_insert]
            inserted = []
            for payload in payloads:
                row = dict(payload)
                row.setdefault("id", len(rows) + 1)
                rows.append(row)
                inserted.append(dict(row))
            return _FakeResult(inserted)
        if self._pending_update is not None:
            updated = []
            for row in rows:
                if self._matches(row):
                    row.update(dict(self._pending_update))
                    updated.append(dict(row))
            return _FakeResult(updated)
        if self._pending_delete:
            kept = []
            deleted = []
            for row in rows:
                if self._matches(row):
                    deleted.append(dict(row))
                else:
                    kept.append(row)
            self.store[self.table_name] = kept
            return _FakeResult(deleted)
        result = [dict(row) for row in rows if self._matches(row)]
        if self._order:
            column, desc = self._order
            result.sort(key=lambda row: str(row.get(column) or ""), reverse=desc)
        if self._range is not None:
            start, end = self._range
            result = result[start : end + 1]
        if self._limit is not None:
            result = result[: self._limit]
        return _FakeResult(result)


class _FakeSupabase:
    def __init__(self, store=None):
        self.store = store or {}

    def table(self, table_name):
        return _FakeQuery(table_name, self.store)


class DeveloperWorkspaceServiceTests(unittest.TestCase):
    def setUp(self):
        authz.clear_authorization_cache()
        staff.list_staff_role_assignments.clear()
        staff.search_profiles_for_staff_access.clear()
        jobs.clear_job_cache()
        ml.clear_experiment_cache()

    def tearDown(self):
        authz.clear_authorization_cache()
        staff.list_staff_role_assignments.clear()
        staff.search_profiles_for_staff_access.clear()
        jobs.clear_job_cache()
        ml.clear_experiment_cache()

    def test_authorization_context_supports_multi_role_capabilities(self):
        fake_sb = _FakeSupabase(
            {
                "profiles": [
                    {
                        "user_id": "user-1",
                        "role": "admin",
                        "primary_role": "teacher",
                        "can_teach": True,
                        "can_study": False,
                    }
                ],
                "user_staff_roles": [
                    {"user_id": "user-1", "role_key": "developer", "is_active": True},
                    {"user_id": "user-1", "role_key": "data_scientist", "is_active": True},
                ],
            }
        )
        with patch.object(authz, "get_sb", return_value=fake_sb):
            context = authz.get_authorization_context(user_id="user-1", refresh=True)

        self.assertIn("admin", context.product_roles)
        self.assertIn("developer", context.staff_roles)
        self.assertIn(authz.CAPABILITY_MANAGE_STAFF_ROLES, context.capabilities)
        self.assertIn(authz.CAPABILITY_RUN_APPROVED_EXPERIMENTS, context.capabilities)
        self.assertIn(authz.CAPABILITY_VIEW_JOB_DIAGNOSTICS, context.capabilities)

    def test_assign_and_revoke_staff_role_require_admin_capability(self):
        fake_sb = _FakeSupabase(
            {
                "profiles": [{"user_id": "target-1", "email": "target@classio.app", "display_name": "Target", "role": "teacher"}],
                "user_staff_roles": [],
            }
        )
        with (
            patch.object(staff, "get_sb", return_value=fake_sb),
            patch.object(staff, "require_capability", return_value=None),
            patch.object(staff, "get_current_user_id", return_value="admin-1"),
            patch.object(staff, "record_privileged_action", return_value=True),
        ):
            ok, message = staff.assign_staff_role(target_user_id="target-1", role_key="developer", assignment_reason="Needed for ML review")
            self.assertTrue(ok)
            self.assertEqual("Staff role assigned.", message)
            self.assertEqual(1, len(fake_sb.store["user_staff_roles"]))
            self.assertEqual("developer", fake_sb.store["user_staff_roles"][0]["role_key"])

            ok, message = staff.revoke_staff_role(target_user_id="target-1", role_key="developer", revoke_reason="Project complete")
            self.assertTrue(ok)
            self.assertEqual("Staff role revoked.", message)
            self.assertFalse(fake_sb.store["user_staff_roles"][0]["is_active"])
            self.assertEqual("admin-1", fake_sb.store["user_staff_roles"][0]["revoked_by"])

    def test_duplicate_active_staff_role_is_blocked(self):
        fake_sb = _FakeSupabase(
            {
                "profiles": [{"user_id": "target-1", "email": "target@classio.app", "display_name": "Target", "role": "teacher"}],
                "user_staff_roles": [{"id": 1, "user_id": "target-1", "role_key": "developer", "is_active": True}],
            }
        )
        with (
            patch.object(staff, "get_sb", return_value=fake_sb),
            patch.object(staff, "require_capability", return_value=None),
            patch.object(staff, "record_privileged_action", return_value=True),
        ):
            ok, message = staff.assign_staff_role(target_user_id="target-1", role_key="developer", assignment_reason="Duplicate")
        self.assertFalse(ok)
        self.assertIn("already assigned", message)

    def test_job_creation_prevents_duplicate_active_jobs_and_obeys_transitions(self):
        fake_sb = _FakeSupabase({"system_jobs": []})
        with (
            patch.object(jobs, "get_sb", return_value=fake_sb),
            patch.object(jobs, "get_current_user_id", return_value="developer-1"),
            patch.object(jobs, "get_current_user_role", return_value="teacher"),
        ):
            created, job_row, _message = jobs.create_job(
                job_type="ml_experiment_evaluation",
                job_version="phase3_6_v1",
                idempotency_key="exp:1",
                payload_json={"run_id": "run-1"},
            )
            self.assertTrue(created)
            self.assertEqual("QUEUED", job_row["status"])

            created, duplicate_row, message = jobs.create_job(
                job_type="ml_experiment_evaluation",
                job_version="phase3_6_v1",
                idempotency_key="exp:1",
                payload_json={"run_id": "run-1"},
            )
            self.assertFalse(created)
            self.assertIn("active job", message)
            self.assertEqual(job_row["job_id"], duplicate_row["job_id"])

            ok, message = jobs.update_job_state(job_row["job_id"], next_status="RUNNING", current_stage="fit", progress_pct=50)
            self.assertTrue(ok)
            self.assertEqual("RUNNING", fake_sb.store["system_jobs"][0]["status"])

            self.assertFalse(jobs.can_transition_job_state("COMPLETED", "RUNNING"))
            ok, message = jobs.update_job_state(job_row["job_id"], next_status="COMPLETED", current_stage="done", progress_pct=100)
            self.assertTrue(ok)
            self.assertEqual("COMPLETED", fake_sb.store["system_jobs"][0]["status"])

    def test_unauthorized_developer_workspace_access_stops_server_side(self):
        with (
            patch.object(dev_workspace, "require_capability", side_effect=RuntimeError("streamlit.stop")),
        ):
            with self.assertRaisesRegex(RuntimeError, "streamlit.stop"):
                dev_workspace.render_developer_workspace()

    def test_environment_readiness_returns_structured_diagnostics_and_blockers(self):
        with (
            patch.object(ml, "_environment_table_ready", return_value=(False, "missing table")),
            patch.object(ml, "_resolve_ml_runtime", return_value=("python-current", "current")),
            patch.object(ml, "_module_ready", side_effect=[(True, ""), (True, ""), (True, "")]),
            patch.object(ml, "_sklearn_available", return_value=(False, "No module named sklearn")),
            patch.object(ml, "_callable_import_ready", side_effect=[(False, "evaluator import failed"), (True, "")]),
        ):
            readiness = ml.get_environment_readiness()

        self.assertIn("database_migration", readiness)
        self.assertIn("ml_dependencies", readiness)
        self.assertIn("experiment_launcher", readiness)
        dependency_names = [check["name"] for check in readiness["ml_dependencies"]["checks"]]
        self.assertEqual(
            ["numpy", "pandas", "scipy", "scikit-learn", "job runner", "evaluator import", "integrity review import"],
            dependency_names,
        )
        self.assertFalse(readiness["experiment_launcher"]["ready"])
        self.assertIn("scikit-learn missing", readiness["experiment_launcher"]["blocking_reasons"])
        self.assertIn("evaluator import missing", readiness["experiment_launcher"]["blocking_reasons"])

    def test_environment_readiness_can_use_external_ml_runtime(self):
        with (
            patch.object(ml, "_environment_table_ready", return_value=(True, "")),
            patch.object(ml, "_resolve_ml_runtime", return_value=("/tmp/classio-ml-python", "external")),
            patch.object(ml, "_subprocess_module_ready", return_value=(True, "")),
            patch.object(ml, "_callable_import_ready", side_effect=[(True, ""), (True, "")]),
        ):
            readiness = ml.get_environment_readiness()

        self.assertTrue(readiness["ml_dependencies"]["ready"])
        self.assertTrue(readiness["experiment_launcher"]["ready"])
        self.assertEqual("subprocess_ml_runtime", readiness["execution_mode"]["mode"])
        self.assertEqual("/tmp/classio-ml-python", readiness["execution_mode"]["python_executable"])

    def test_launch_moves_run_to_validated_and_creates_required_artifacts(self):
        fake_sb = _FakeSupabase(
            {
                "ml_experiments": [],
                "ml_experiment_runs": [],
                "ml_run_models": [],
                "ml_run_artifacts": [],
                "system_jobs": [],
                "privileged_action_audit_log": [],
            }
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            run_root = Path(tmpdir)

            def _fake_pipeline(run_dir, *, run_id=None, experiment_id=None):
                run_dir = Path(run_dir)
                run_dir.mkdir(parents=True, exist_ok=True)
                files = {
                    "assigned_resource_open_7d_dataset_summary.json": "{}",
                    "assigned_resource_open_7d_dataset_frozen.csv": "assignment_id\n1\n",
                    "assigned_resource_open_7d_label_audit.csv": "assignment_id,label_status,opened_within_7d\n1,included,1\n",
                    "assigned_resource_open_7d_feature_audit.csv": "feature,retained,exclusion_reason\nf1,True,\n",
                    "assigned_resource_open_7d_model_comparison.csv": "model_name,status,roc_auc,average_precision,balanced_accuracy,f1,brier_score,log_loss,confidence_intervals,confusion_matrix,predicted_positive_rate,train_duration_ms,inference_duration_ms,failure_reason\nDummyClassifier,success,0.5,0.5,0.5,0.5,0.25,0.69,\"{}\",\"{}\",0.5,1,1,\n",
                    "assigned_resource_open_7d_run_summary.json": "{\"evaluation\":{\"maturity_verdict\":\"EXPLORATORY_ONLY\",\"winner\":\"NO_ROBUST_WINNER\",\"feature_names\":[\"f1\"],\"cutoff_timestamp\":\"2026-07-01T00:00:00+00:00\",\"primary_metric_leader\":\"DummyClassifier\",\"best_thresholded_classifier\":\"DummyClassifier\",\"best_precision_recall_ranking\":\"DummyClassifier\",\"calibration_leader\":\"DummyClassifier\",\"overall_evidence_strength\":\"insufficient\"},\"review\":{}}",
                    "assigned_resource_open_7d_holdout_predictions.csv": "model_name,y_true,y_prob,y_pred\nDummyClassifier,1,0.5,1\n",
                    "assigned_resource_open_7d_technical_report.md": "# technical\n",
                    "assigned_resource_open_7d_findings_interpretation_report.md": "# findings interpretation\n",
                }
                for filename, content in files.items():
                    (run_dir / filename).write_text(content, encoding="utf-8")
                run_dir = Path(run_dir)
                (run_dir / "assigned_resource_open_7d_integrity_review.md").write_text("# integrity\n", encoding="utf-8")
                (run_dir / "assigned_resource_open_7d_label_reconciliation.csv").write_text("assignment_id,audit_era_label\n1,positive\n", encoding="utf-8")
                return (
                    {"evaluation": {"maturity_verdict": "EXPLORATORY_ONLY"}, "dataset": {"run_id": run_id or "run123"}},
                    {"final_verdict": "VALIDATED_NO_ROBUST_WINNER", "overall_model_conclusion": "NO_ROBUST_WINNER"},
                )

            with (
                patch.object(ml, "get_sb", return_value=fake_sb),
                patch.object(jobs, "get_sb", return_value=fake_sb),
                patch.object(ml, "ensure_experiment_registered", return_value=None),
                patch.object(ml, "ensure_historical_superseded_run_registered", return_value=None),
                patch.object(ml, "require_capability", return_value=None),
                patch.object(ml, "compute_experiment_eligibility", return_value=ml.EligibilityResult(True, (), (), "EXPLORATORY_ONLY", {"mature_labels": 100}, {})),
                patch.object(ml, "get_environment_readiness", return_value={"experiment_launcher": {"ready": True}}),
                patch.object(ml, "_run_pipeline_in_ml_runtime", side_effect=_fake_pipeline),
                patch.object(ml, "record_privileged_action", return_value=True),
                patch.object(ml, "get_current_user_id", return_value="dev-1"),
                patch.object(jobs, "get_current_user_id", return_value="dev-1"),
                patch.object(jobs, "get_current_user_role", return_value="teacher"),
                patch.object(ml, "_run_dir", side_effect=lambda run_id: run_root / run_id),
            ):
                ok, payload, message = ml.launch_assigned_resource_open_experiment()

            self.assertTrue(ok)
            self.assertEqual("Experiment completed.", message)
            run_id = payload["run_id"]
            run_row = next(row for row in fake_sb.store["ml_experiment_runs"] if row["run_id"] == run_id)
            self.assertEqual("VALIDATED_NO_ROBUST_WINNER", run_row["run_status"])
            self.assertEqual("PASSED_NO_ROBUST_WINNER", run_row["integrity_status"])
            self.assertTrue((run_root / run_id / "assigned_resource_open_7d_run_summary.json").exists())
            self.assertTrue((run_root / run_id / "assigned_resource_open_7d_label_audit.csv").exists())
            self.assertGreaterEqual(len(fake_sb.store["ml_run_artifacts"]), 1)

    def test_launch_marks_stale_active_runs_before_blocking_new_launches(self):
        fake_sb = _FakeSupabase(
            {
                "ml_experiments": [],
                "ml_experiment_runs": [
                    {
                        "run_id": "stale-run",
                        "experiment_id": ml.APPROVED_EXPERIMENT_ID,
                        "run_status": "QUEUED",
                        "integrity_status": "NOT_RUN",
                        "job_id": "stale-job",
                        "artifact_root": "/tmp/stale-run",
                        "created_at": "2026-07-16T09:00:00+00:00",
                    }
                ],
                "ml_run_models": [],
                "ml_run_artifacts": [],
                "system_jobs": [
                    {
                        "job_id": "stale-job",
                        "status": "QUEUED",
                        "heartbeat_at": "2026-07-16T09:00:00+00:00",
                        "updated_at": "2026-07-16T09:00:00+00:00",
                        "requested_at": "2026-07-16T09:00:00+00:00",
                        "related_entity_id": "stale-run",
                        "related_entity_type": "ml_experiment_run",
                    }
                ],
                "privileged_action_audit_log": [],
            }
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            run_root = Path(tmpdir)

            def _fake_pipeline(run_dir, *, run_id=None, experiment_id=None):
                run_dir = Path(run_dir)
                run_dir.mkdir(parents=True, exist_ok=True)
                files = {
                    "assigned_resource_open_7d_dataset_summary.json": "{}",
                    "assigned_resource_open_7d_dataset_frozen.csv": "assignment_id\n1\n",
                    "assigned_resource_open_7d_label_audit.csv": "assignment_id,label_status,opened_within_7d\n1,included,1\n",
                    "assigned_resource_open_7d_feature_audit.csv": "feature,retained,exclusion_reason\nf1,True,\n",
                    "assigned_resource_open_7d_model_comparison.csv": "model_name,status,roc_auc,average_precision,balanced_accuracy,f1,brier_score,log_loss,confidence_intervals,confusion_matrix,predicted_positive_rate,train_duration_ms,inference_duration_ms,failure_reason\nDummyClassifier,success,0.5,0.5,0.5,0.5,0.25,0.69,\"{}\",\"{}\",0.5,1,1,\n",
                    "assigned_resource_open_7d_run_summary.json": "{\"evaluation\":{\"maturity_verdict\":\"EXPLORATORY_ONLY\",\"winner\":\"NO_ROBUST_WINNER\",\"feature_names\":[\"f1\"],\"cutoff_timestamp\":\"2026-07-01T00:00:00+00:00\",\"primary_metric_leader\":\"DummyClassifier\",\"best_thresholded_classifier\":\"DummyClassifier\",\"best_precision_recall_ranking\":\"DummyClassifier\",\"calibration_leader\":\"DummyClassifier\",\"overall_evidence_strength\":\"insufficient\"},\"review\":{}}",
                    "assigned_resource_open_7d_holdout_predictions.csv": "model_name,y_true,y_prob,y_pred\nDummyClassifier,1,0.5,1\n",
                    "assigned_resource_open_7d_technical_report.md": "# technical\n",
                    "assigned_resource_open_7d_findings_interpretation_report.md": "# findings interpretation\n",
                }
                for filename, content in files.items():
                    (run_dir / filename).write_text(content, encoding="utf-8")
                run_dir = Path(run_dir)
                (run_dir / "assigned_resource_open_7d_integrity_review.md").write_text("# integrity\n", encoding="utf-8")
                (run_dir / "assigned_resource_open_7d_label_reconciliation.csv").write_text("assignment_id,audit_era_label\n1,positive\n", encoding="utf-8")
                return (
                    {"evaluation": {"maturity_verdict": "EXPLORATORY_ONLY"}, "dataset": {"run_id": run_id or "run123"}},
                    {"final_verdict": "VALIDATED_NO_ROBUST_WINNER", "overall_model_conclusion": "NO_ROBUST_WINNER"},
                )

            with (
                patch.object(ml, "get_sb", return_value=fake_sb),
                patch.object(jobs, "get_sb", return_value=fake_sb),
                patch.object(ml, "ensure_experiment_registered", return_value=None),
                patch.object(ml, "ensure_historical_superseded_run_registered", return_value=None),
                patch.object(ml, "require_capability", return_value=None),
                patch.object(ml, "compute_experiment_eligibility", return_value=ml.EligibilityResult(True, (), (), "EXPLORATORY_ONLY", {"mature_labels": 100}, {})),
                patch.object(ml, "get_environment_readiness", return_value={"experiment_launcher": {"ready": True}}),
                patch.object(ml, "_run_pipeline_in_ml_runtime", side_effect=_fake_pipeline),
                patch.object(ml, "record_privileged_action", return_value=True),
                patch.object(ml, "get_current_user_id", return_value="dev-1"),
                patch.object(jobs, "get_current_user_id", return_value="dev-1"),
                patch.object(jobs, "get_current_user_role", return_value="teacher"),
                patch.object(ml, "_run_dir", side_effect=lambda run_id: run_root / run_id),
                patch.object(ml, "_utc_now", return_value=__import__("datetime").datetime(2026, 7, 16, 12, 0, 0, tzinfo=__import__("datetime").timezone.utc)),
            ):
                ok, payload, message = ml.launch_assigned_resource_open_experiment()

            self.assertTrue(ok)
            self.assertEqual("Experiment completed.", message)
            stale_run = next(row for row in fake_sb.store["ml_experiment_runs"] if row["run_id"] == "stale-run")
            stale_job = next(row for row in fake_sb.store["system_jobs"] if row["job_id"] == "stale-job")
            self.assertEqual("FAILED", stale_run["run_status"])
            self.assertEqual("STALE", stale_job["status"])

    def test_integrity_rerun_is_blocked_for_queued_running_failed_and_missing_artifacts(self):
        fake_sb = _FakeSupabase(
            {
                "ml_experiment_runs": [
                    {"run_id": "queued", "artifact_root": "/tmp/queued", "run_status": "QUEUED", "integrity_status": "NOT_RUN"},
                    {"run_id": "running", "artifact_root": "/tmp/running", "run_status": "RUNNING", "integrity_status": "NOT_RUN"},
                    {"run_id": "failed", "artifact_root": "/tmp/failed", "run_status": "FAILED", "integrity_status": "FAILED"},
                    {"run_id": "missing", "artifact_root": "/tmp/missing", "run_status": "COMPLETED_PENDING_VALIDATION", "integrity_status": "NOT_RUN"},
                ]
            }
        )
        with patch.object(ml, "get_sb", return_value=fake_sb):
            allowed, message = ml.can_manually_rerun_integrity("queued")
            self.assertFalse(allowed)
            self.assertIn("queued", message.lower())
            allowed, message = ml.can_manually_rerun_integrity("running")
            self.assertFalse(allowed)
            self.assertIn("running", message.lower())
            allowed, message = ml.can_manually_rerun_integrity("failed")
            self.assertFalse(allowed)
            self.assertIn("failed", message.lower())
            allowed, message = ml.can_manually_rerun_integrity("missing")
            self.assertFalse(allowed)
            self.assertIn("missing", message.lower())

    def test_completed_ready_run_may_launch_integrity_review(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            run_dir = Path(tmpdir)
            for filename in [
                "assigned_resource_open_7d_dataset_summary.json",
                "assigned_resource_open_7d_dataset_frozen.csv",
                "assigned_resource_open_7d_label_audit.csv",
                "assigned_resource_open_7d_feature_audit.csv",
                "assigned_resource_open_7d_model_comparison.csv",
                "assigned_resource_open_7d_run_summary.json",
                "assigned_resource_open_7d_holdout_predictions.csv",
                "assigned_resource_open_7d_technical_report.md",
                "assigned_resource_open_7d_findings_interpretation_report.md",
            ]:
                (run_dir / filename).write_text("ok", encoding="utf-8")
            fake_sb = _FakeSupabase(
                {"ml_experiment_runs": [{"run_id": "ready-run", "artifact_root": str(run_dir), "run_status": "COMPLETED_PENDING_VALIDATION", "integrity_status": "NOT_RUN"}]}
            )
            with patch.object(ml, "get_sb", return_value=fake_sb):
                allowed, message = ml.can_manually_rerun_integrity("ready-run")
            self.assertTrue(allowed)
            self.assertIn("available", message.lower())

    def test_requires_rerun_ready_run_may_rerun_integrity_after_logic_fix(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            run_dir = Path(tmpdir)
            for filename in [
                "assigned_resource_open_7d_dataset_summary.json",
                "assigned_resource_open_7d_dataset_frozen.csv",
                "assigned_resource_open_7d_label_audit.csv",
                "assigned_resource_open_7d_feature_audit.csv",
                "assigned_resource_open_7d_model_comparison.csv",
                "assigned_resource_open_7d_run_summary.json",
                "assigned_resource_open_7d_holdout_predictions.csv",
                "assigned_resource_open_7d_technical_report.md",
                "assigned_resource_open_7d_findings_interpretation_report.md",
            ]:
                (run_dir / filename).write_text("ok", encoding="utf-8")
            fake_sb = _FakeSupabase(
                {"ml_experiment_runs": [{"run_id": "rerun-ready", "artifact_root": str(run_dir), "run_status": "REQUIRES_RERUN", "integrity_status": "REQUIRES_RERUN"}]}
            )
            with patch.object(ml, "get_sb", return_value=fake_sb):
                allowed, message = ml.can_manually_rerun_integrity("rerun-ready")
            self.assertTrue(allowed)
            self.assertIn("rerun", message.lower())

    def test_launch_failure_persists_failed_state(self):
        fake_sb = _FakeSupabase(
            {
                "ml_experiments": [],
                "ml_experiment_runs": [],
                "ml_run_models": [],
                "ml_run_artifacts": [],
                "system_jobs": [],
                "privileged_action_audit_log": [],
            }
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            with (
                patch.object(ml, "get_sb", return_value=fake_sb),
                patch.object(jobs, "get_sb", return_value=fake_sb),
                patch.object(ml, "ensure_experiment_registered", return_value=None),
                patch.object(ml, "ensure_historical_superseded_run_registered", return_value=None),
                patch.object(ml, "require_capability", return_value=None),
                patch.object(ml, "compute_experiment_eligibility", return_value=ml.EligibilityResult(True, (), (), "EXPLORATORY_ONLY", {"mature_labels": 100}, {})),
                patch.object(ml, "get_environment_readiness", return_value={"experiment_launcher": {"ready": True}}),
                patch.object(ml, "_run_pipeline_in_ml_runtime", side_effect=RuntimeError("missing dependency")),
                patch.object(ml, "record_privileged_action", return_value=True),
                patch.object(ml, "get_current_user_id", return_value="dev-1"),
                patch.object(jobs, "get_current_user_id", return_value="dev-1"),
                patch.object(jobs, "get_current_user_role", return_value="teacher"),
                patch.object(ml, "_run_dir", side_effect=lambda run_id: Path(tmpdir) / run_id),
            ):
                ok, payload, message = ml.launch_assigned_resource_open_experiment()
        self.assertFalse(ok)
        self.assertIn("missing dependency", message)
        run_row = next(row for row in fake_sb.store["ml_experiment_runs"] if row["run_id"] == payload["run_id"])
        self.assertEqual("FAILED", run_row["run_status"])
        self.assertEqual("FAILED", run_row["integrity_status"])

    def test_launch_audit_failure_marks_run_failed_instead_of_stranding_queued(self):
        fake_sb = _FakeSupabase(
            {
                "ml_experiments": [],
                "ml_experiment_runs": [],
                "ml_run_models": [],
                "ml_run_artifacts": [],
                "system_jobs": [],
                "privileged_action_audit_log": [],
            }
        )
        def _audit_side_effect(**kwargs):
            if kwargs.get("action_type") == "experiment_launched":
                raise RuntimeError("audit unavailable")
            return True

        with tempfile.TemporaryDirectory() as tmpdir:
            with (
                patch.object(ml, "get_sb", return_value=fake_sb),
                patch.object(jobs, "get_sb", return_value=fake_sb),
                patch.object(ml, "ensure_experiment_registered", return_value=None),
                patch.object(ml, "ensure_historical_superseded_run_registered", return_value=None),
                patch.object(ml, "require_capability", return_value=None),
                patch.object(ml, "compute_experiment_eligibility", return_value=ml.EligibilityResult(True, (), (), "EXPLORATORY_ONLY", {"mature_labels": 100}, {})),
                patch.object(ml, "get_environment_readiness", return_value={"experiment_launcher": {"ready": True}}),
                patch.object(ml, "record_privileged_action", side_effect=_audit_side_effect),
                patch.object(ml, "get_current_user_id", return_value="dev-1"),
                patch.object(jobs, "get_current_user_id", return_value="dev-1"),
                patch.object(jobs, "get_current_user_role", return_value="teacher"),
                patch.object(ml, "_run_dir", side_effect=lambda run_id: Path(tmpdir) / run_id),
            ):
                ok, payload, message = ml.launch_assigned_resource_open_experiment()
        self.assertFalse(ok)
        self.assertIn("audit unavailable", message)
        run_row = next(row for row in fake_sb.store["ml_experiment_runs"] if row["run_id"] == payload["run_id"])
        job_row = fake_sb.store["system_jobs"][0]
        self.assertEqual("FAILED", run_row["run_status"])
        self.assertEqual("FAILED", run_row["integrity_status"])
        self.assertEqual("FAILED", job_row["status"])

    def test_privileged_action_recording_swallows_authorization_context_failures(self):
        fake_sb = _FakeSupabase({"privileged_action_audit_log": []})
        with (
            patch.object(audit, "get_sb", return_value=fake_sb),
            patch.object(audit, "get_current_user_id", return_value="dev-1"),
            patch.object(audit, "get_authorization_context", side_effect=RuntimeError("auth context down")),
        ):
            ok = audit.record_privileged_action(
                action_type="experiment_launched",
                entity_type="ml_experiment_run",
                entity_id="run-1",
                before_json={},
                after_json={},
                reason="test",
            )
        self.assertFalse(ok)
        self.assertEqual([], fake_sb.store["privileged_action_audit_log"])

    def test_mark_stale_jobs_updates_related_run(self):
        fake_sb = _FakeSupabase(
            {
                "system_jobs": [
                    {
                        "job_id": "job-1",
                        "status": "RUNNING",
                        "heartbeat_at": "2026-07-16T00:00:00+00:00",
                        "related_entity_id": "run-1",
                        "related_entity_type": "ml_experiment_run",
                    }
                ],
                "ml_experiment_runs": [
                    {"run_id": "run-1", "run_status": "RUNNING", "integrity_status": "RUNNING", "artifact_root": "/tmp/run-1"}
                ],
            }
        )
        class _FrozenDateTime:
            @staticmethod
            def now(tz=None):
                from datetime import datetime, timezone
                return datetime(2026, 7, 16, 2, 0, 0, tzinfo=timezone.utc)
        with patch.object(ml, "get_sb", return_value=fake_sb), patch.object(ml, "list_jobs", wraps=jobs.list_jobs), patch.object(jobs, "get_sb", return_value=fake_sb), patch.object(ml, "_utc_now", return_value=__import__("datetime").datetime(2026, 7, 16, 2, 0, 0, tzinfo=__import__("datetime").timezone.utc)):
            count = ml.mark_stale_experiment_jobs(stale_after_minutes=30)
        self.assertEqual(1, count)
        self.assertEqual("STALE", fake_sb.store["system_jobs"][0]["status"])
        self.assertEqual("FAILED", fake_sb.store["ml_experiment_runs"][0]["run_status"])

    def test_validated_summary_ignores_non_validated_states(self):
        fake_sb = _FakeSupabase(
            {
                "ml_experiment_runs": [
                    {"run_id": "queued", "experiment_id": ml.APPROVED_EXPERIMENT_ID, "run_status": "QUEUED", "created_at": "2026-07-16T10:00:00+00:00"},
                    {"run_id": "failed", "experiment_id": ml.APPROVED_EXPERIMENT_ID, "run_status": "FAILED", "created_at": "2026-07-16T09:00:00+00:00"},
                    {"run_id": "good", "experiment_id": ml.APPROVED_EXPERIMENT_ID, "run_status": "VALIDATED_NO_ROBUST_WINNER", "created_at": "2026-07-16T08:00:00+00:00"},
                ]
            }
        )
        with patch.object(ml, "get_sb", return_value=fake_sb):
            summary = ml.get_latest_validated_run_summary(cache_bust="1")
        self.assertEqual("good", summary["run_id"])

    def test_current_validated_run_artifacts_are_protected(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            run_dir = Path(tmpdir) / "protected-run"
            run_dir.mkdir(parents=True, exist_ok=True)
            fake_sb = _FakeSupabase(
                {
                    "ml_experiment_runs": [
                        {
                            "run_id": "protected-run",
                            "experiment_id": ml.APPROVED_EXPERIMENT_ID,
                            "run_status": "VALIDATED_NO_ROBUST_WINNER",
                            "integrity_status": "PASSED_NO_ROBUST_WINNER",
                            "is_current_validated_run": True,
                            "artifact_root": str(run_dir),
                            "created_at": "2026-07-16T08:00:00+00:00",
                            "completed_at": "2026-07-16T08:10:00+00:00",
                        }
                    ],
                    "ml_run_artifacts": [{"run_id": "protected-run", "artifact_type": "run_summary_json", "storage_path": str(run_dir / "assigned_resource_open_7d_run_summary.json")}],
                }
            )
            with patch.object(ml, "get_sb", return_value=fake_sb):
                retention = ml.get_run_artifact_retention_status("protected-run")
            self.assertTrue(retention.protected)
            self.assertEqual("current_validated", retention.protection_tier)
            self.assertFalse(retention.cleanup_eligible)

    def test_old_failed_run_becomes_cleanup_candidate(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            run_dir = Path(tmpdir) / "failed-run"
            run_dir.mkdir(parents=True, exist_ok=True)
            (run_dir / "stale.txt").write_text("x", encoding="utf-8")
            fake_sb = _FakeSupabase(
                {
                    "ml_experiment_runs": [
                        {
                            "run_id": "failed-run",
                            "experiment_id": ml.APPROVED_EXPERIMENT_ID,
                            "run_status": "FAILED",
                            "integrity_status": "FAILED",
                            "artifact_root": str(run_dir),
                            "created_at": "2026-06-01T08:00:00+00:00",
                            "completed_at": "2026-06-01T08:10:00+00:00",
                        }
                    ],
                    "ml_run_artifacts": [],
                }
            )
            with (
                patch.object(ml, "get_sb", return_value=fake_sb),
                patch.object(ml, "_utc_now", return_value=__import__("datetime").datetime(2026, 7, 17, 12, 0, 0, tzinfo=__import__("datetime").timezone.utc)),
            ):
                retention = ml.get_run_artifact_retention_status("failed-run")
                cleaned = ml.cleanup_expired_local_artifacts(experiment_id=ml.APPROVED_EXPERIMENT_ID)
            self.assertFalse(retention.protected)
            self.assertTrue(retention.cleanup_eligible)
            self.assertEqual("failed-run", cleaned[0]["run_id"])
            self.assertFalse(run_dir.exists())

    def test_protected_missing_artifacts_have_repair_message(self):
        fake_sb = _FakeSupabase(
            {
                "ml_experiment_runs": [
                    {
                        "run_id": "protected-missing",
                        "experiment_id": ml.APPROVED_EXPERIMENT_ID,
                        "run_status": "VALIDATED_NO_ROBUST_WINNER",
                        "integrity_status": "PASSED_NO_ROBUST_WINNER",
                        "is_current_validated_run": True,
                        "artifact_root": "/tmp/protected-missing",
                        "created_at": "2026-07-16T08:00:00+00:00",
                        "completed_at": "2026-07-16T08:10:00+00:00",
                    }
                ],
                "ml_run_artifacts": [],
            }
        )
        with patch.object(ml, "get_sb", return_value=fake_sb):
            readiness = ml.get_run_artifact_readiness("protected-missing")
        self.assertFalse(readiness.ready)
        self.assertIn("Protected artifacts", readiness.user_message)

    def test_validated_run_does_not_offer_manual_integrity_rerun(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            run_dir = Path(tmpdir)
            for filename in [
                "assigned_resource_open_7d_dataset_summary.json",
                "assigned_resource_open_7d_dataset_frozen.csv",
                "assigned_resource_open_7d_label_audit.csv",
                "assigned_resource_open_7d_feature_audit.csv",
                "assigned_resource_open_7d_model_comparison.csv",
                "assigned_resource_open_7d_run_summary.json",
                "assigned_resource_open_7d_holdout_predictions.csv",
                "assigned_resource_open_7d_technical_report.md",
                "assigned_resource_open_7d_findings_interpretation_report.md",
            ]:
                (run_dir / filename).write_text("ok", encoding="utf-8")
            fake_sb = _FakeSupabase(
                {
                    "ml_experiment_runs": [
                        {
                            "run_id": "validated-run",
                            "artifact_root": str(run_dir),
                            "run_status": "VALIDATED_NO_ROBUST_WINNER",
                            "integrity_status": "PASSED_NO_ROBUST_WINNER",
                            "is_current_validated_run": True,
                            "experiment_id": ml.APPROVED_EXPERIMENT_ID,
                        }
                    ]
                }
            )
            with patch.object(ml, "get_sb", return_value=fake_sb):
                allowed, message = ml.can_manually_rerun_integrity("validated-run")
            self.assertFalse(allowed)
            self.assertIn("already validated", message)


if __name__ == "__main__":
    unittest.main()
