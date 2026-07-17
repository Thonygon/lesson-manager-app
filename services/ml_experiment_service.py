from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import importlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import traceback
from typing import Any
import uuid

import pandas as pd
import streamlit as st

from helpers.assigned_resource_open_7d_eval import (
    MODEL_COMPARISON_FILENAME,
    RUN_SUMMARY_FILENAME,
    TARGET_NAME,
    TECHNICAL_REPORT_FILENAME,
    ACADEMIC_REPORT_FILENAME,
    DATASET_SUMMARY_FILENAME,
    FEATURE_AUDIT_FILENAME,
    LABEL_AUDIT_FILENAME,
    PREDICTIONS_FILENAME,
    FROZEN_DATASET_FILENAME,
    _sklearn_available,
    build_assignment_dataset,
    extract_operational_snapshot,
    generate_assigned_resource_open_7d_evaluation,
)
from helpers.assigned_resource_open_7d_review import INTEGRITY_REVIEW_FILENAME, RECONCILIATION_FILENAME, review_assigned_resource_open_7d
from helpers.student_recommendation_open_7d_eval import (
    ACADEMIC_REPORT_FILENAME as STUDENT_RECO_ACADEMIC_REPORT_FILENAME,
    DATASET_SUMMARY_FILENAME as STUDENT_RECO_DATASET_SUMMARY_FILENAME,
    FEATURE_AUDIT_FILENAME as STUDENT_RECO_FEATURE_AUDIT_FILENAME,
    FROZEN_DATASET_FILENAME as STUDENT_RECO_FROZEN_DATASET_FILENAME,
    MODEL_COMPARISON_FILENAME as STUDENT_RECO_MODEL_COMPARISON_FILENAME,
    PREDICTIONS_FILENAME as STUDENT_RECO_PREDICTIONS_FILENAME,
    RUN_SUMMARY_FILENAME as STUDENT_RECO_RUN_SUMMARY_FILENAME,
    TECHNICAL_REPORT_FILENAME as STUDENT_RECO_TECHNICAL_REPORT_FILENAME,
    build_assignment_dataset as build_student_recommendation_dataset,
    extract_operational_snapshot as extract_student_recommendation_snapshot,
    generate_student_recommendation_open_7d_evaluation,
)
from helpers.student_recommendation_open_7d_review import (
    INTEGRITY_REVIEW_FILENAME as STUDENT_RECO_INTEGRITY_REVIEW_FILENAME,
    RECONCILIATION_FILENAME as STUDENT_RECO_RECONCILIATION_FILENAME,
    review_student_recommendation_open_7d,
)
from helpers.exposure_telemetry import load_telemetry_health_snapshot
from services.authorization_service import (
    CAPABILITY_COMPARE_EXPERIMENT_RUNS,
    CAPABILITY_RERUN_INTEGRITY_REVIEW,
    CAPABILITY_RUN_APPROVED_EXPERIMENTS,
    CAPABILITY_VIEW_AUDIT_LOG,
    CAPABILITY_VIEW_DEVELOPER_WORKSPACE,
    CAPABILITY_VIEW_JOB_DIAGNOSTICS,
    CAPABILITY_VIEW_ML_LAB,
    CAPABILITY_VIEW_TECHNICAL_ARTIFACTS,
    CAPABILITY_VIEW_TELEMETRY_DIAGNOSTICS,
    get_authorization_context,
    require_capability,
)
from services.controlled_jobs_service import ACTIVE_JOB_STATES, create_job, get_job, list_jobs, update_job_state
from services.privileged_action_service import record_privileged_action

from core.database import get_sb, json_safe
from core.state import get_current_user_id


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ML_PIPELINE_SCRIPT = PROJECT_ROOT / "scripts" / "run_assigned_resource_open_7d_pipeline.py"
STUDENT_RECOMMENDATION_PIPELINE_SCRIPT = PROJECT_ROOT / "scripts" / "run_student_recommendation_open_7d_pipeline.py"
EXPERIMENT_TABLE = "ml_experiments"
RUN_TABLE = "ml_experiment_runs"
RUN_MODEL_TABLE = "ml_run_models"
RUN_ARTIFACT_TABLE = "ml_run_artifacts"
APPROVED_EXPERIMENT_ID = "assigned_resource_open_within_7d"
STUDENT_RECOMMENDATION_EXPERIMENT_ID = "student_recommendation_open_within_7d"
APPROVED_TARGET_VERSION = "opened_within_7d_v1"
APPROVED_EXPERIMENT_VERSION = "phase3_6_v1"
STUDENT_RECOMMENDATION_TARGET_VERSION = "opened_within_7d_v1"
STUDENT_RECOMMENDATION_EXPERIMENT_VERSION = "phase4_0_v1"
RUNS_ROOT = Path("reports") / "ml_architecture" / "assigned_resource_open_7d" / "runs"
STUDENT_RECOMMENDATION_RUNS_ROOT = Path("reports") / "ml_architecture" / "student_recommendation_open_7d" / "runs"
LATEST_PHASE3_5_RUN_ID = "ca935f4e5587"
SUPPORTED_MODEL_NAMES = (
    "DummyClassifier",
    "LogisticRegression",
    "LogisticRegressionReduced",
    "DecisionTreeClassifier",
    "RandomForestClassifier",
    "HistGradientBoostingClassifier",
    "SVC",
    "KNeighborsClassifier",
)
FINAL_VALIDATED_RUN_STATES = {"VALIDATED_EXPLORATORY_RUN", "VALIDATED_NO_ROBUST_WINNER"}
READINESS_COMPATIBLE_RUN_STATES = {"COMPLETED_PENDING_VALIDATION", "REQUIRES_RERUN", "VALIDATED_EXPLORATORY_RUN", "VALIDATED_NO_ROBUST_WINNER"}
MANUAL_INTEGRITY_ALLOWED_RUN_STATES = {"COMPLETED_PENDING_VALIDATION"}
PROTECTED_VALIDATED_RUN_HISTORY_LIMIT = 5
DEFAULT_NONFINAL_RETENTION_DAYS = 14
SUPERSEDED_VALIDATED_RETENTION_DAYS = 30
ARTIFACT_RETENTION_DAYS_BY_STATUS = {
    "ARCHIVED": 7,
    "FAILED": DEFAULT_NONFINAL_RETENTION_DAYS,
    "INVALID_LABEL_CONSTRUCTION": DEFAULT_NONFINAL_RETENTION_DAYS,
    "REQUIRES_RERUN": DEFAULT_NONFINAL_RETENTION_DAYS,
    "SUPERSEDED": SUPERSEDED_VALIDATED_RETENTION_DAYS,
}

EXPERIMENT_DEFINITION = {
    "experiment_id": APPROVED_EXPERIMENT_ID,
    "experiment_version": APPROVED_EXPERIMENT_VERSION,
    "name": "Assigned Resource Open Within 7 Days",
    "business_question": "Can Classio predict whether a student will open an assigned resource within seven days of assignment?",
    "target_version": APPROVED_TARGET_VERSION,
    "unit_of_analysis": "One teacher_assignments record representing one assigned-resource exposure.",
    "primary_metric": "roc_auc",
    "definition_json": {
        "approved_models": list(SUPPORTED_MODEL_NAMES),
        "evaluation_rules": [
            "chronological development/holdout split",
            "past-only historical features",
            "no post-assignment features",
            "dummy-baseline comparison",
            "confidence intervals where supported",
            "no-robust-winner permitted",
            "no automatic deployment",
        ],
    },
}

EXPERIMENT_RUNTIME: dict[str, dict[str, Any]] = {
    APPROVED_EXPERIMENT_ID: {
        "runs_root": RUNS_ROOT,
        "pipeline_script": ML_PIPELINE_SCRIPT,
        "dataset_summary_filename": DATASET_SUMMARY_FILENAME,
        "frozen_dataset_filename": FROZEN_DATASET_FILENAME,
        "label_audit_filename": LABEL_AUDIT_FILENAME,
        "feature_audit_filename": FEATURE_AUDIT_FILENAME,
        "model_comparison_filename": MODEL_COMPARISON_FILENAME,
        "run_summary_filename": RUN_SUMMARY_FILENAME,
        "predictions_filename": PREDICTIONS_FILENAME,
        "technical_report_filename": TECHNICAL_REPORT_FILENAME,
        "academic_report_filename": ACADEMIC_REPORT_FILENAME,
        "integrity_review_filename": INTEGRITY_REVIEW_FILENAME,
        "reconciliation_filename": RECONCILIATION_FILENAME,
        "evaluator_callable": generate_assigned_resource_open_7d_evaluation,
        "review_callable": review_assigned_resource_open_7d,
    },
    STUDENT_RECOMMENDATION_EXPERIMENT_ID: {
        "runs_root": STUDENT_RECOMMENDATION_RUNS_ROOT,
        "pipeline_script": STUDENT_RECOMMENDATION_PIPELINE_SCRIPT,
        "dataset_summary_filename": STUDENT_RECO_DATASET_SUMMARY_FILENAME,
        "frozen_dataset_filename": STUDENT_RECO_FROZEN_DATASET_FILENAME,
        "label_audit_filename": "student_recommendation_open_7d_label_audit.csv",
        "feature_audit_filename": STUDENT_RECO_FEATURE_AUDIT_FILENAME,
        "model_comparison_filename": STUDENT_RECO_MODEL_COMPARISON_FILENAME,
        "run_summary_filename": STUDENT_RECO_RUN_SUMMARY_FILENAME,
        "predictions_filename": STUDENT_RECO_PREDICTIONS_FILENAME,
        "technical_report_filename": STUDENT_RECO_TECHNICAL_REPORT_FILENAME,
        "academic_report_filename": STUDENT_RECO_ACADEMIC_REPORT_FILENAME,
        "integrity_review_filename": STUDENT_RECO_INTEGRITY_REVIEW_FILENAME,
        "reconciliation_filename": STUDENT_RECO_RECONCILIATION_FILENAME,
        "evaluator_callable": generate_student_recommendation_open_7d_evaluation,
        "review_callable": review_student_recommendation_open_7d,
    },
}

KNOWN_EXPERIMENTS: dict[str, dict[str, Any]] = {
    APPROVED_EXPERIMENT_ID: {
        **EXPERIMENT_DEFINITION,
        "sequence_number": 1,
        "launch_supported": True,
        "eligibility_supported": True,
        "reporting_supported": True,
        "component_id": "assigned_resource_open_within_7d",
    },
    STUDENT_RECOMMENDATION_EXPERIMENT_ID: {
        "experiment_id": STUDENT_RECOMMENDATION_EXPERIMENT_ID,
        "experiment_version": STUDENT_RECOMMENDATION_EXPERIMENT_VERSION,
        "name": "Student Recommendation Open Within 7 Days",
        "business_question": "Can Classio predict whether a student will open an optional recommendation within seven days of seeing it?",
        "target_version": STUDENT_RECOMMENDATION_TARGET_VERSION,
        "unit_of_analysis": "One optional student recommendation exposure.",
        "primary_metric": "roc_auc",
        "definition_json": {
            "approved_models": list(SUPPORTED_MODEL_NAMES),
            "evaluation_rules": [
                "chronological development/holdout split",
                "first-party recommendation exposure telemetry",
                "past-only historical features",
                "no post-exposure features",
                "dummy-baseline comparison",
                "no automatic deployment",
            ],
        },
        "sequence_number": 2,
        "launch_supported": True,
        "eligibility_supported": True,
        "reporting_supported": True,
        "component_id": "student_recommendation_open_within_7d",
    },
}

RUN_TRANSITIONS = {
    "DRAFT": {"ELIGIBILITY_CHECK", "FAILED"},
    "ELIGIBILITY_CHECK": {"ELIGIBLE", "INELIGIBLE", "FAILED"},
    "ELIGIBLE": {"QUEUED", "FAILED"},
    "INELIGIBLE": set(),
    "QUEUED": {"RUNNING", "FAILED", "ARCHIVED"},
    "RUNNING": {"COMPLETED_PENDING_VALIDATION", "FAILED"},
    "COMPLETED_PENDING_VALIDATION": {
        "VALIDATED_EXPLORATORY_RUN",
        "VALIDATED_NO_ROBUST_WINNER",
        "REQUIRES_RERUN",
        "INVALID_LABEL_CONSTRUCTION",
        "FAILED",
    },
    "VALIDATED_EXPLORATORY_RUN": {"SUPERSEDED", "ARCHIVED"},
    "VALIDATED_NO_ROBUST_WINNER": {"SUPERSEDED", "ARCHIVED"},
    "REQUIRES_RERUN": {"SUPERSEDED", "ARCHIVED"},
    "INVALID_LABEL_CONSTRUCTION": {"ARCHIVED"},
    "FAILED": {"ARCHIVED"},
    "SUPERSEDED": {"ARCHIVED"},
    "ARCHIVED": set(),
}


@dataclass(frozen=True)
class EligibilityResult:
    eligible: bool
    blocking_reasons: tuple[str, ...]
    warnings: tuple[str, ...]
    expected_maturity_ceiling: str
    data_summary: dict[str, Any]
    comparison: dict[str, Any]


@dataclass(frozen=True)
class ArtifactReadiness:
    ready: bool
    missing_artifact_types: tuple[str, ...]
    missing_paths: tuple[str, ...]
    run_status_compatible: bool
    run_status: str
    artifact_root: str
    user_message: str


@dataclass(frozen=True)
class ArtifactRetentionStatus:
    protected: bool
    protection_tier: str
    reason: str
    cleanup_eligible: bool
    retention_days: int | None
    delete_after: str
    artifact_directory_exists: bool
    artifact_count: int


def _diagnostic_check(name: str, ready: bool, message: str = "", *, error: str = "", recommended_action: str = "", metadata: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "name": name,
        "ready": bool(ready),
        "message": _clean_text(message),
        "error": str(error or "").strip(),
        "recommended_action": _clean_text(recommended_action),
        "metadata": json_safe(metadata or {}),
    }


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _utc_now_iso() -> str:
    return _utc_now().isoformat()


def _clean_text(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def _parse_dt(value: Any) -> datetime | None:
    text = _clean_text(value)
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except Exception:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _git_code_version() -> str:
    try:
        head = Path(".git") / "HEAD"
        if not head.exists():
            return "unknown"
        value = head.read_text(encoding="utf-8").strip()
        if value.startswith("ref:"):
            ref = value.split(" ", 1)[1].strip()
            ref_path = Path(".git") / ref
            if ref_path.exists():
                return ref_path.read_text(encoding="utf-8").strip()[:12]
        return value[:12]
    except Exception:
        return "unknown"


def _artifact_checksum(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _runtime_config(experiment_id: str) -> dict[str, Any]:
    return EXPERIMENT_RUNTIME.get(_clean_text(experiment_id), EXPERIMENT_RUNTIME[APPROVED_EXPERIMENT_ID])


def _run_dir(run_id: str, experiment_id: str = APPROVED_EXPERIMENT_ID) -> Path:
    return Path(_runtime_config(experiment_id).get("runs_root") or RUNS_ROOT) / _clean_text(run_id)


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else {}
    except Exception:
        return {}


def _required_artifact_specs(experiment_id: str = APPROVED_EXPERIMENT_ID) -> list[tuple[str, str]]:
    runtime = _runtime_config(experiment_id)
    return [
        ("dataset_summary", str(runtime.get("dataset_summary_filename") or DATASET_SUMMARY_FILENAME)),
        ("frozen_dataset", str(runtime.get("frozen_dataset_filename") or FROZEN_DATASET_FILENAME)),
        ("label_audit", str(runtime.get("label_audit_filename") or LABEL_AUDIT_FILENAME)),
        ("feature_audit", str(runtime.get("feature_audit_filename") or FEATURE_AUDIT_FILENAME)),
        ("model_comparison", str(runtime.get("model_comparison_filename") or MODEL_COMPARISON_FILENAME)),
        ("run_summary", str(runtime.get("run_summary_filename") or RUN_SUMMARY_FILENAME)),
        ("holdout_predictions", str(runtime.get("predictions_filename") or PREDICTIONS_FILENAME)),
        ("technical_report", str(runtime.get("technical_report_filename") or TECHNICAL_REPORT_FILENAME)),
        ("findings_interpretation_report", str(runtime.get("academic_report_filename") or ACADEMIC_REPORT_FILENAME)),
    ]


def _artifact_root_for_row(run_row: dict[str, Any]) -> Path:
    experiment_id = _clean_text(run_row.get("experiment_id")) or APPROVED_EXPERIMENT_ID
    artifact_root = _clean_text(run_row.get("artifact_root"))
    return Path(artifact_root) if artifact_root else _run_dir(str(run_row.get("run_id") or ""), experiment_id)


def _run_retention_reference_at(run_row: dict[str, Any]) -> datetime | None:
    for field_name in ("completed_at", "created_at", "started_at", "requested_at"):
        parsed = _parse_dt(run_row.get(field_name))
        if parsed:
            return parsed
    return None


def _is_historically_validated_run(run_row: dict[str, Any]) -> bool:
    run_status = _clean_text(run_row.get("run_status")).upper()
    integrity_status = _clean_text(run_row.get("integrity_status")).upper()
    academic_use = _clean_text(run_row.get("academic_use")).upper()
    return (
        run_status in FINAL_VALIDATED_RUN_STATES
        or (
            run_status == "SUPERSEDED"
            and (integrity_status.startswith("PASSED") or academic_use == "EXPLORATORY_ONLY")
        )
    )


def get_run_artifact_retention_status(run_id: str) -> ArtifactRetentionStatus:
    run_row = get_run(run_id)
    if not run_row:
        return ArtifactRetentionStatus(
            protected=False,
            protection_tier="missing_run",
            reason="Run not found.",
            cleanup_eligible=False,
            retention_days=None,
            delete_after="",
            artifact_directory_exists=False,
            artifact_count=0,
        )

    safe_run_id = _clean_text(run_row.get("run_id") or run_id)
    experiment_id = _clean_text(run_row.get("experiment_id")) or APPROVED_EXPERIMENT_ID
    run_status = _clean_text(run_row.get("run_status")).upper()
    artifact_dir = _artifact_root_for_row(run_row)
    artifact_rows = list_run_artifacts(safe_run_id)
    artifact_count = int(len(artifact_rows))
    artifact_directory_exists = artifact_dir.exists()
    latest_runs = list_experiment_runs(experiment_id=experiment_id, limit=200, cache_bust=f"retention:{experiment_id}:{safe_run_id}")
    validated_lineage = [row for row in latest_runs if _is_historically_validated_run(row)]
    validated_lineage_ids = [str(row.get("run_id") or "") for row in validated_lineage]
    validated_rank = validated_lineage_ids.index(safe_run_id) + 1 if safe_run_id in validated_lineage_ids else None
    retention_days = ARTIFACT_RETENTION_DAYS_BY_STATUS.get(run_status)
    delete_after = ""
    reference_at = _run_retention_reference_at(run_row)
    if retention_days is not None and reference_at is not None:
        delete_after = (reference_at + timedelta(days=retention_days)).isoformat()

    if bool(run_row.get("is_current_validated_run")) and _is_historically_validated_run(run_row):
        return ArtifactRetentionStatus(
            protected=True,
            protection_tier="current_validated",
            reason="Current validated run artifacts are always protected.",
            cleanup_eligible=False,
            retention_days=None,
            delete_after="",
            artifact_directory_exists=artifact_directory_exists,
            artifact_count=artifact_count,
        )
    if validated_rank is not None and validated_rank <= PROTECTED_VALIDATED_RUN_HISTORY_LIMIT:
        return ArtifactRetentionStatus(
            protected=True,
            protection_tier="validated_history",
            reason=f"This run is within the last {PROTECTED_VALIDATED_RUN_HISTORY_LIMIT} validated experiment histories for this experiment.",
            cleanup_eligible=False,
            retention_days=None,
            delete_after="",
            artifact_directory_exists=artifact_directory_exists,
            artifact_count=artifact_count,
        )
    if run_status in ACTIVE_JOB_STATES | FINAL_VALIDATED_RUN_STATES | {"COMPLETED_PENDING_VALIDATION", "QUEUED", "RUNNING"}:
        return ArtifactRetentionStatus(
            protected=False,
            protection_tier="active_or_pending",
            reason="Artifacts are kept while the run is active, pending validation, or currently validated.",
            cleanup_eligible=False,
            retention_days=retention_days,
            delete_after=delete_after,
            artifact_directory_exists=artifact_directory_exists,
            artifact_count=artifact_count,
        )

    cleanup_eligible = False
    if retention_days is not None and reference_at is not None:
        cleanup_eligible = _utc_now() >= (reference_at + timedelta(days=retention_days))

    reason = "Artifacts are retained until the configured cleanup window expires."
    if cleanup_eligible:
        reason = "Artifacts are eligible for cleanup under the retention policy."
    elif retention_days is None:
        reason = "No automatic cleanup rule applies to this run."

    return ArtifactRetentionStatus(
        protected=False,
        protection_tier="retained_temporarily",
        reason=reason,
        cleanup_eligible=cleanup_eligible,
        retention_days=retention_days,
        delete_after=delete_after,
        artifact_directory_exists=artifact_directory_exists,
        artifact_count=artifact_count,
    )


def _feature_exclusion_map(feature_audit_path: Path) -> list[dict[str, Any]]:
    if not feature_audit_path.exists():
        return []
    try:
        df = pd.read_csv(feature_audit_path)
    except Exception:
        return []
    rows = []
    for _, row in df.iterrows():
        if not bool(row.get("retained", True)):
            rows.append(
                {
                    "feature": str(row.get("feature") or ""),
                    "exclusion_reason": str(row.get("exclusion_reason") or ""),
                }
            )
    return rows


def _storage_bucket() -> str:
    return "protected_local_reports"


def _artifact_root_label(run_id: str) -> str:
    return str(_run_dir(run_id))


def _safe_run_update_payload(payload: dict[str, Any]) -> dict[str, Any]:
    sanitized = dict(json_safe(payload))
    sanitized.pop("updated_at", None)
    return sanitized


def _normalize_run_status_from_review(review_result: dict[str, Any]) -> tuple[str, str]:
    final_verdict = _clean_text(review_result.get("final_verdict")).upper()
    overall = _clean_text(review_result.get("overall_model_conclusion")).upper()
    if final_verdict == "INVALID_LABEL_CONSTRUCTION":
        return "INVALID_LABEL_CONSTRUCTION", "INVALID_LABEL_CONSTRUCTION"
    if final_verdict == "REQUIRES_RERUN":
        return "REQUIRES_RERUN", "REQUIRES_RERUN"
    if overall == "NO_ROBUST_WINNER":
        return "VALIDATED_NO_ROBUST_WINNER", "PASSED_NO_ROBUST_WINNER"
    return "VALIDATED_EXPLORATORY_RUN", "PASSED_EXPLORATORY"


def _run_counts_from_dataset_summary(dataset_summary: dict[str, Any]) -> dict[str, int]:
    return {
        "source_row_count": int(dataset_summary.get("source_row_count") or 0),
        "included_row_count": int(dataset_summary.get("included_row_count") or 0),
        "positive_label_count": int(dataset_summary.get("positive_count") or 0),
        "negative_label_count": int(dataset_summary.get("negative_count") or 0),
        "right_censored_count": int(dataset_summary.get("excluded_row_count") or 0),
        "invalid_row_count": int(dataset_summary.get("invalid_row_count") or 0),
        "teachers_represented": int(dataset_summary.get("teacher_count") or 0),
        "students_represented": int(dataset_summary.get("student_count") or 0),
        "resources_represented": int(dataset_summary.get("resource_count") or 0),
    }


def ensure_experiment_registered() -> None:
    for experiment_id, definition in KNOWN_EXPERIMENTS.items():
        existing = (
            get_sb()
            .table(EXPERIMENT_TABLE)
            .select("experiment_id,experiment_version")
            .eq("experiment_id", experiment_id)
            .eq("experiment_version", str(definition.get("experiment_version") or ""))
            .limit(1)
            .execute()
        ).data or []
        if existing:
            continue
        payload = dict(definition)
        payload.pop("sequence_number", None)
        payload.pop("launch_supported", None)
        payload.pop("eligibility_supported", None)
        payload.pop("reporting_supported", None)
        payload.pop("component_id", None)
        payload["is_active"] = True
        get_sb().table(EXPERIMENT_TABLE).insert(payload).execute()


def _historical_run_file_root() -> Path:
    return Path("reports") / "ml_architecture" / "assigned_resource_open_7d"


def ensure_historical_superseded_run_registered() -> None:
    try:
        existing = (
            get_sb()
            .table(RUN_TABLE)
            .select("run_id")
            .eq("run_id", LATEST_PHASE3_5_RUN_ID)
            .limit(1)
            .execute()
        ).data or []
    except Exception:
        existing = []
    if existing:
        return

    base_dir = _historical_run_file_root()
    run_summary = _read_json(base_dir / RUN_SUMMARY_FILENAME)
    dataset_summary = _read_json(base_dir / DATASET_SUMMARY_FILENAME)
    payload = {
        "run_id": LATEST_PHASE3_5_RUN_ID,
        "experiment_id": APPROVED_EXPERIMENT_ID,
        "experiment_version": APPROVED_EXPERIMENT_VERSION,
        "run_status": "SUPERSEDED",
        "integrity_status": "REQUIRES_RERUN",
        "operational_use": "NONE",
        "academic_use": "NOT_FINAL",
        "is_current_validated_run": False,
        "created_at": run_summary.get("generated_at") or dataset_summary.get("extracted_at") or _utc_now_iso(),
        "started_at": dataset_summary.get("extracted_at"),
        "completed_at": run_summary.get("generated_at"),
        "environment": "historical_phase3_5",
        "code_version": "historical",
        "extraction_timestamp": dataset_summary.get("extracted_at"),
        "source_start_at": ((dataset_summary.get("date_range") or {}).get("assigned_at_min")),
        "source_end_at": ((dataset_summary.get("date_range") or {}).get("assigned_at_max")),
        "dataset_fingerprint": dataset_summary.get("data_fingerprint"),
        "feature_schema_version": dataset_summary.get("feature_schema_version"),
        "artifact_root": str(base_dir),
        "warning_summary": "Historical Phase 3.5 run preserved as superseded; integrity review requires rerun.",
        "validation_notes": "Registered from repository artifacts without rewriting historical metrics.",
        **_run_counts_from_dataset_summary(dataset_summary),
    }
    try:
        get_sb().table(RUN_TABLE).insert(payload).execute()
    except Exception:
        return


def is_legal_run_transition(current_status: str, next_status: str) -> bool:
    safe_current = _clean_text(current_status).upper()
    safe_next = _clean_text(next_status).upper()
    return safe_next in RUN_TRANSITIONS.get(safe_current, set())


def _update_run_row(run_id: str, payload: dict[str, Any]) -> None:
    get_sb().table(RUN_TABLE).update(_safe_run_update_payload(payload)).eq("run_id", _clean_text(run_id)).execute()


def _set_run_status(run_id: str, next_status: str, *, extra_payload: dict[str, Any] | None = None) -> None:
    current = get_run(run_id)
    current_status = _clean_text(current.get("run_status")).upper() or "DRAFT"
    if next_status != current_status and not is_legal_run_transition(current_status, next_status):
        raise ValueError(f"Illegal run transition: {current_status} -> {next_status}")
    payload = {"run_status": next_status}
    if extra_payload:
        payload.update(json_safe(extra_payload))
    _update_run_row(run_id, payload)


def get_run_artifact_readiness(run_id: str) -> ArtifactReadiness:
    run_row = get_run(run_id)
    if not run_row:
        return ArtifactReadiness(
            ready=False,
            missing_artifact_types=(),
            missing_paths=(),
            run_status_compatible=False,
            run_status="",
            artifact_root="",
            user_message="Run not found.",
        )
    run_status = _clean_text(run_row.get("run_status")).upper()
    experiment_id = _clean_text(run_row.get("experiment_id")) or APPROVED_EXPERIMENT_ID
    run_dir = _artifact_root_for_row(run_row)
    missing_types: list[str] = []
    missing_paths: list[str] = []
    for artifact_type, filename in _required_artifact_specs(experiment_id):
        path = run_dir / filename
        if not path.exists():
            missing_types.append(artifact_type)
            missing_paths.append(str(path))
    retention = get_run_artifact_retention_status(run_id)
    compatible = run_status in READINESS_COMPATIBLE_RUN_STATES
    if run_status == "QUEUED":
        message = "Evaluation is still queued."
    elif run_status == "RUNNING":
        message = "Evaluation is currently running."
    elif run_status == "FAILED":
        message = "Evaluation failed; launch a new run."
    elif run_status == "SUPERSEDED":
        message = "This historical run is superseded."
    elif missing_paths and retention.protected:
        message = "Protected artifacts for this run are missing. Regenerate or restore the evidence package."
    elif missing_paths and retention.cleanup_eligible:
        message = "Local artifacts for this run have expired under the retention policy."
    elif missing_paths:
        message = "Required evaluation artifacts are missing."
    elif not compatible:
        message = f"Run status {run_status or 'unknown'} is not compatible with integrity validation."
    else:
        message = "Evaluation artifacts are ready."
    return ArtifactReadiness(
        ready=compatible and not missing_paths,
        missing_artifact_types=tuple(missing_types),
        missing_paths=tuple(missing_paths),
        run_status_compatible=compatible,
        run_status=run_status,
        artifact_root=str(run_dir),
        user_message=message,
    )


def get_run_state_summary(run_id: str) -> dict[str, Any]:
    run_row = get_run(run_id)
    readiness = get_run_artifact_readiness(run_id)
    run_status = readiness.run_status or _clean_text(run_row.get("run_status")).upper()
    integrity_status = _clean_text(run_row.get("integrity_status")).upper()
    if run_status == "QUEUED":
        current = "Waiting to start. No evaluation artifacts exist yet."
        next_action = "Wait for execution to begin."
    elif run_status == "RUNNING":
        current = "Models are being evaluated. Integrity review will start after completion."
        next_action = "Wait for evaluation to finish."
    elif run_status == "COMPLETED_PENDING_VALIDATION":
        current = "Evaluation completed. Integrity validation is ready."
        next_action = "Run integrity validation."
    elif run_status in FINAL_VALIDATED_RUN_STATES:
        current = "This run passed integrity checks and may feed business and academic reports."
        next_action = "Artifacts are readable."
    elif run_status == "FAILED":
        current = "The evaluation failed before producing a validated result."
        next_action = "Launch a new evaluation."
    elif run_status == "REQUIRES_RERUN":
        current = "Artifacts exist, but the review requires a new evaluation before this run can be trusted."
        next_action = "Launch a new evaluation."
    elif run_status == "INVALID_LABEL_CONSTRUCTION":
        current = "Integrity review found invalid label construction."
        next_action = "Fix implementation and launch a new evaluation."
    elif run_status == "SUPERSEDED":
        current = "This historical run has been superseded and is read-only."
        next_action = "Review artifacts only."
    else:
        current = "Run status is not yet fully classified."
        next_action = "Refresh this view."
    return {
        "run_status": run_status,
        "integrity_status": integrity_status,
        "current_message": current,
        "artifacts_ready": readiness.ready,
        "artifact_message": readiness.user_message,
        "next_action": next_action,
        "missing_artifact_types": list(readiness.missing_artifact_types),
        "missing_paths": list(readiness.missing_paths),
        "failure_message": str(run_row.get("failure_message") or ""),
    }


def can_manually_rerun_integrity(run_id: str) -> tuple[bool, str]:
    readiness = get_run_artifact_readiness(run_id)
    if readiness.run_status == "QUEUED":
        return False, "Evaluation is still queued."
    if readiness.run_status == "RUNNING":
        return False, "Evaluation is currently running."
    if readiness.run_status == "FAILED":
        return False, "Evaluation failed; launch a new run."
    if readiness.run_status == "SUPERSEDED":
        return False, "This historical run is superseded."
    if readiness.run_status == "INVALID_LABEL_CONSTRUCTION":
        return False, "This run needs implementation changes and a new evaluation."
    if readiness.run_status in FINAL_VALIDATED_RUN_STATES:
        return False, "This run is already validated. Manual integrity rerun is not needed; use Reports to generate the final experiment report."
    if readiness.run_status not in MANUAL_INTEGRITY_ALLOWED_RUN_STATES | {"REQUIRES_RERUN"}:
        return False, readiness.user_message
    if not readiness.ready:
        return False, readiness.user_message
    if readiness.run_status == "REQUIRES_RERUN":
        return True, "Integrity validation can be rerun with the current artifacts."
    return True, "Integrity validation is available."


def _environment_table_ready(table_name: str) -> tuple[bool, str]:
    try:
        get_sb().table(table_name).select("id").limit(1).execute()
        return True, ""
    except Exception as exc:
        return False, str(exc)


def _module_ready(module_name: str) -> tuple[bool, str]:
    try:
        importlib.import_module(module_name)
        return True, ""
    except Exception as exc:
        return False, str(exc)


def _callable_import_ready(module_name: str, attribute_name: str) -> tuple[bool, str]:
    try:
        module = importlib.import_module(module_name)
        getattr(module, attribute_name)
        return True, ""
    except Exception as exc:
        return False, str(exc)


def _normalize_path_text(path_value: str | Path | None) -> str:
    try:
        return str(Path(str(path_value or "")).resolve())
    except Exception:
        return str(path_value or "")


def _ml_runtime_candidates() -> list[str]:
    candidates: list[str] = []
    env_python = _clean_text(os.getenv("CLASSIO_ML_PYTHON"))
    if env_python:
        candidates.append(env_python)
    for venv_dir in sorted(PROJECT_ROOT.glob(".venv*")):
        venv_python = venv_dir / "bin" / "python"
        if venv_python.exists():
            candidates.append(str(venv_python))
    candidates.append(sys.executable)
    seen: set[str] = set()
    deduped: list[str] = []
    for candidate in candidates:
        normalized = _normalize_path_text(candidate)
        if normalized and normalized not in seen:
            seen.add(normalized)
            deduped.append(candidate)
    return deduped


def _subprocess_module_ready(module_name: str, python_executable: str) -> tuple[bool, str]:
    try:
        result = subprocess.run(
            [python_executable, "-c", f"import importlib; importlib.import_module({module_name!r})"],
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
        )
    except Exception as exc:
        return False, str(exc)
    if result.returncode == 0:
        return True, ""
    return False, _clean_text(result.stderr) or _clean_text(result.stdout) or f"import failed in {python_executable}"


def _current_runtime_supports_supervised_ml() -> bool:
    scipy_ready, _ = _module_ready("scipy")
    sklearn_ready, _ = _sklearn_available()
    return bool(scipy_ready and sklearn_ready)


def _resolve_ml_runtime() -> tuple[str, str]:
    current_python = _normalize_path_text(sys.executable)
    current_numpy_ready, _ = _module_ready("numpy")
    current_pandas_ready, _ = _module_ready("pandas")
    if current_python and current_numpy_ready and current_pandas_ready and _current_runtime_supports_supervised_ml():
        return current_python, "current"
    for candidate in _ml_runtime_candidates():
        normalized = _normalize_path_text(candidate)
        if not normalized:
            continue
        numpy_ready, _ = _subprocess_module_ready("numpy", candidate)
        pandas_ready, _ = _subprocess_module_ready("pandas", candidate)
        scipy_ready, _ = _subprocess_module_ready("scipy", candidate)
        sklearn_ready, _ = _subprocess_module_ready("sklearn", candidate)
        if numpy_ready and pandas_ready and scipy_ready and sklearn_ready:
            return normalized, "external"
    return current_python, "current"


def _run_pipeline_in_ml_runtime(run_dir: Path, *, run_id: str, experiment_id: str) -> tuple[dict[str, Any], dict[str, Any]]:
    runtime = _runtime_config(experiment_id)
    evaluator = runtime.get("evaluator_callable")
    reviewer = runtime.get("review_callable")
    pipeline_script = Path(runtime.get("pipeline_script") or ML_PIPELINE_SCRIPT)
    python_executable, runtime_mode = _resolve_ml_runtime()
    if runtime_mode == "current":
        result = evaluator(run_dir, run_id=run_id)
        review_result = reviewer(run_dir)
        return result, review_result
    completed = subprocess.run(
        [
            python_executable,
            str(pipeline_script),
            "--output-dir",
            str(run_dir),
            "--run-id",
            str(run_id),
        ],
        cwd=str(PROJECT_ROOT),
        capture_output=True,
        text=True,
        timeout=1800,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(_clean_text(completed.stderr) or _clean_text(completed.stdout) or f"ML runtime subprocess failed with code {completed.returncode}")
    payload_text = str(completed.stdout or "").strip()
    if not payload_text:
        raise RuntimeError("ML runtime subprocess returned no JSON payload.")
    try:
        payload = json.loads(payload_text)
    except Exception as exc:
        raise RuntimeError(f"ML runtime subprocess returned invalid JSON: {exc}") from exc
    result = payload.get("result") or {}
    review_result = payload.get("review_result") or {}
    if not isinstance(result, dict) or not isinstance(review_result, dict):
        raise RuntimeError("ML runtime subprocess did not return the expected result structure.")
    return result, review_result


def get_environment_readiness() -> dict[str, Any]:
    table_checks = {
        name: _environment_table_ready(name)
        for name in [EXPERIMENT_TABLE, RUN_TABLE, RUN_MODEL_TABLE, RUN_ARTIFACT_TABLE, "system_jobs", "user_staff_roles"]
    }
    migration_checks = [
        _diagnostic_check(
            name=table_name,
            ready=ready,
            message=f"{table_name} table is available." if ready else f"{table_name} table is unavailable.",
            error=error,
            recommended_action="" if ready else "apply migration",
        )
        for table_name, (ready, error) in table_checks.items()
    ]
    migration_ready = all(check["ready"] for check in migration_checks)
    writable = True
    writable_error = ""
    try:
        for root in [RUNS_ROOT, STUDENT_RECOMMENDATION_RUNS_ROOT]:
            root.mkdir(parents=True, exist_ok=True)
            probe = root / ".write_probe"
            probe.write_text("ok", encoding="utf-8")
            probe.unlink()
    except Exception as exc:
        writable = False
        writable_error = str(exc)
    filesystem_check = _diagnostic_check(
        name="artifact_filesystem",
        ready=writable,
        message="Run artifact directory is writable." if writable else "Run artifact directory is not writable.",
        error=writable_error,
        recommended_action="" if writable else "grant filesystem write access",
        metadata={"paths": [str(RUNS_ROOT), str(STUDENT_RECOMMENDATION_RUNS_ROOT)]},
    )

    ml_runtime_path, ml_runtime_mode = _resolve_ml_runtime()
    runtime_is_current = _normalize_path_text(ml_runtime_path) == _normalize_path_text(sys.executable)
    numpy_ready, numpy_error = (_module_ready("numpy") if runtime_is_current else _subprocess_module_ready("numpy", ml_runtime_path))
    pandas_ready, pandas_error = (_module_ready("pandas") if runtime_is_current else _subprocess_module_ready("pandas", ml_runtime_path))
    scipy_ready, scipy_error = (_module_ready("scipy") if runtime_is_current else _subprocess_module_ready("scipy", ml_runtime_path))
    sklearn_ready, sklearn_error = (_sklearn_available() if runtime_is_current else _subprocess_module_ready("sklearn", ml_runtime_path))
    job_runner_ready = True
    job_runner_error = ""
    evaluator_ready, evaluator_error = _callable_import_ready("helpers.assigned_resource_open_7d_eval", "generate_assigned_resource_open_7d_evaluation")
    integrity_ready, integrity_error = _callable_import_ready("helpers.assigned_resource_open_7d_review", "review_assigned_resource_open_7d")
    dependency_metadata = {"python_executable": ml_runtime_path, "runtime_mode": ml_runtime_mode}
    dependency_checks = [
        _diagnostic_check("numpy", numpy_ready, "numpy import ready." if numpy_ready else "numpy import failed.", error=numpy_error, recommended_action="" if numpy_ready else "pip install numpy", metadata=dependency_metadata),
        _diagnostic_check("pandas", pandas_ready, "pandas import ready." if pandas_ready else "pandas import failed.", error=pandas_error, recommended_action="" if pandas_ready else "pip install pandas", metadata=dependency_metadata),
        _diagnostic_check("scipy", scipy_ready, "scipy import ready." if scipy_ready else "scipy import failed.", error=scipy_error, recommended_action="" if scipy_ready else "pip install scipy", metadata=dependency_metadata),
        _diagnostic_check("scikit-learn", sklearn_ready, "scikit-learn import ready." if sklearn_ready else "scikit-learn import failed.", error=sklearn_error, recommended_action="" if sklearn_ready else "pip install scikit-learn", metadata=dependency_metadata),
        _diagnostic_check("job runner", job_runner_ready, "Controlled synchronous job runner is available.", error=job_runner_error, recommended_action="" if job_runner_ready else "enable synchronous execution"),
        _diagnostic_check("evaluator import", evaluator_ready, "Evaluator import is ready." if evaluator_ready else "Evaluator import failed.", error=evaluator_error, recommended_action="" if evaluator_ready else "fix evaluator import"),
        _diagnostic_check("integrity review import", integrity_ready, "Integrity review import is ready." if integrity_ready else "Integrity review import failed.", error=integrity_error, recommended_action="" if integrity_ready else "fix integrity review import"),
    ]
    dependencies_ready = all(check["ready"] for check in dependency_checks)

    execution_mode = {
        "mode": "subprocess_ml_runtime" if ml_runtime_mode == "external" else "synchronous",
        "worker_available": False,
        "synchronous_enabled": True,
        "message": (
            f"Experiment execution will use the configured ML runtime at {ml_runtime_path}."
            if ml_runtime_mode == "external"
            else "Synchronous execution is enabled in the current runtime."
        ),
        "python_executable": ml_runtime_path,
    }
    blocking_reasons: list[str] = []
    recommended_actions: list[str] = []
    if not migration_ready:
        blocking_reasons.append("migration not applied")
        recommended_actions.append("apply migration")
    if not writable:
        blocking_reasons.append("artifact filesystem is not writable")
        recommended_actions.append("grant filesystem write access")
    for check in dependency_checks:
        if not check["ready"]:
            blocking_reasons.append(f"{check['name']} missing" if "import failed" in check["message"].lower() or check["name"] in {"numpy", "pandas", "scipy", "scikit-learn"} else f"{check['name']} unavailable")
            if check["recommended_action"]:
                recommended_actions.append(check["recommended_action"])
    if not execution_mode["worker_available"] and not execution_mode["synchronous_enabled"]:
        blocking_reasons.append("background worker unavailable")
        recommended_actions.append("enable synchronous execution")
    launcher_ready = not blocking_reasons
    launcher_message = "All blocking conditions are resolved." if launcher_ready else "Launch is blocked until the listed conditions are resolved."
    return {
        "database_migration": {
            "ready": migration_ready,
            "message": "All required registry and job tables are available." if migration_ready else "One or more required tables are missing.",
            "checks": migration_checks,
        },
        "artifact_filesystem": {
            "ready": writable,
            "message": filesystem_check["message"],
            "error": writable_error,
            "checks": [filesystem_check],
        },
        "ml_dependencies": {
            "ready": dependencies_ready,
            "message": "All required ML dependencies are available." if dependencies_ready else "One or more ML dependencies are unavailable.",
            "checks": dependency_checks,
        },
        "execution_mode": execution_mode,
        "experiment_launcher": {
            "ready": launcher_ready,
            "message": launcher_message,
            "blocking_reasons": blocking_reasons,
            "recommended_actions": sorted(set(action for action in recommended_actions if action)),
        },
    }


def _safe_error_message(exc: Exception) -> str:
    text = _clean_text(str(exc))
    return text or exc.__class__.__name__


def _record_failure(run_id: str, *, job_id: str, stage: str, exc: Exception) -> tuple[bool, dict[str, Any], str]:
    safe_message = _safe_error_message(exc)
    _update_run_row(
        run_id,
        {
            "run_status": "FAILED",
            "integrity_status": "FAILED",
            "completed_at": _utc_now_iso(),
            "failure_message": safe_message,
            "validation_notes": f"failure_stage={stage}",
            "is_current_validated_run": False,
        },
    )
    update_job_state(
        job_id,
        next_status="FAILED",
        current_stage=stage,
        progress_pct=100,
        error_code="experiment_failed",
        error_message=safe_message,
        warning_json={"traceback": traceback.format_exc(), "failure_stage": stage},
    )
    record_privileged_action(
        action_type="experiment_failed",
        entity_type="ml_experiment_run",
        entity_id=run_id,
        before_json={},
        after_json={"failure_message": safe_message, "failure_stage": stage, "traceback": traceback.format_exc()},
        reason="Controlled synchronous execution failed.",
    )
    clear_experiment_cache()
    return False, {"run_id": run_id, "job_id": job_id}, safe_message


def get_run(run_id: str) -> dict[str, Any]:
    rows = (
        get_sb()
        .table(RUN_TABLE)
        .select("*")
        .eq("run_id", _clean_text(run_id))
        .limit(1)
        .execute()
    ).data or []
    return dict(rows[0]) if rows else {}


@st.cache_data(ttl=15, show_spinner=False)
def list_experiment_runs(
    *,
    experiment_id: str | None = APPROVED_EXPERIMENT_ID,
    limit: int = 50,
    offset: int = 0,
    validated_only: bool = False,
    cache_bust: str = "",
) -> list[dict[str, Any]]:
    query = (
        get_sb()
        .table(RUN_TABLE)
        .select("*")
        .order("created_at", desc=True)
        .limit(max(1, min(int(limit), 200)))
    )
    if _clean_text(experiment_id):
        query = query.eq("experiment_id", _clean_text(experiment_id))
    if offset > 0:
        query = query.range(int(offset), int(offset + limit - 1))
    if validated_only:
        query = query.in_("run_status", sorted(FINAL_VALIDATED_RUN_STATES))
    try:
        return [dict(row) for row in (query.execute().data or [])]
    except Exception:
        return []


def clear_experiment_cache() -> None:
    list_experiment_runs.clear()
    get_latest_validated_run_summary.clear()
    get_workspace_overview.clear()
    list_experiment_catalog.clear()


def _fallback_experiment_name(experiment_id: str) -> str:
    safe_id = _clean_text(experiment_id)
    if not safe_id:
        return "Unnamed experiment"
    return " ".join(part.capitalize() for part in safe_id.replace("-", "_").split("_"))


@st.cache_data(ttl=30, show_spinner=False)
def list_experiment_catalog(cache_bust: str = "") -> list[dict[str, Any]]:
    ensure_experiment_registered()
    try:
        experiment_rows = (
            get_sb()
            .table(EXPERIMENT_TABLE)
            .select("*")
            .order("created_at", desc=False)
            .limit(200)
            .execute()
        ).data or []
    except Exception:
        experiment_rows = []
    try:
        run_rows = (
            get_sb()
            .table(RUN_TABLE)
            .select("experiment_id")
            .order("created_at", desc=True)
            .limit(500)
            .execute()
        ).data or []
    except Exception:
        run_rows = []

    latest_db_row_by_experiment: dict[str, dict[str, Any]] = {}
    for row in experiment_rows:
        experiment_id = _clean_text(row.get("experiment_id"))
        if experiment_id:
            latest_db_row_by_experiment[experiment_id] = dict(row)

    experiment_ids = {
        *KNOWN_EXPERIMENTS.keys(),
        *latest_db_row_by_experiment.keys(),
        *[_clean_text(row.get("experiment_id")) for row in run_rows if _clean_text(row.get("experiment_id"))],
    }
    ordered_ids = sorted(
        [experiment_id for experiment_id in experiment_ids if experiment_id],
        key=lambda experiment_id: (
            int((KNOWN_EXPERIMENTS.get(experiment_id) or {}).get("sequence_number") or 999),
            _fallback_experiment_name(experiment_id),
        ),
    )

    catalog_rows: list[dict[str, Any]] = []
    for position, experiment_id in enumerate(ordered_ids, start=1):
        known = KNOWN_EXPERIMENTS.get(experiment_id) or {}
        db_row = latest_db_row_by_experiment.get(experiment_id) or {}
        runs = list_experiment_runs(experiment_id=experiment_id, limit=100, cache_bust=f"{cache_bust}:{experiment_id}:catalog")
        validated_runs = [row for row in runs if _clean_text(row.get("run_status")).upper() in FINAL_VALIDATED_RUN_STATES]
        sequence_number = int(known.get("sequence_number") or position)
        name = _clean_text(db_row.get("name") or known.get("name")) or _fallback_experiment_name(experiment_id)
        catalog_rows.append(
            {
                "experiment_id": experiment_id,
                "sequence_number": sequence_number,
                "display_label": f"Experiment {sequence_number}: {name}",
                "name": name,
                "experiment_version": _clean_text(db_row.get("experiment_version") or known.get("experiment_version")),
                "target_version": _clean_text(db_row.get("target_version") or known.get("target_version")),
                "business_question": _clean_text(db_row.get("business_question") or known.get("business_question")),
                "unit_of_analysis": _clean_text(db_row.get("unit_of_analysis") or known.get("unit_of_analysis")),
                "primary_metric": _clean_text(db_row.get("primary_metric") or known.get("primary_metric")),
                "status": "integrated" if known else "discovered",
                "launch_supported": bool(known.get("launch_supported")),
                "eligibility_supported": bool(known.get("eligibility_supported")),
                "reporting_supported": bool(known.get("reporting_supported")),
                "component_id": _clean_text(known.get("component_id")),
                "run_count": int(len(runs)),
                "validated_run_count": int(len(validated_runs)),
                "latest_run": dict(runs[0]) if runs else {},
                "latest_validated_run": dict(validated_runs[0]) if validated_runs else {},
            }
        )
    return catalog_rows


@st.cache_data(ttl=30, show_spinner=False)
def get_latest_validated_run_summary(experiment_id: str | None = APPROVED_EXPERIMENT_ID, cache_bust: str = "") -> dict[str, Any]:
    rows = list_experiment_runs(experiment_id=experiment_id, limit=20, validated_only=True, cache_bust=cache_bust)
    return dict(rows[0]) if rows else {}


def launch_experiment(experiment_id: str) -> tuple[bool, dict[str, Any], str]:
    safe_experiment_id = _clean_text(experiment_id)
    if safe_experiment_id == APPROVED_EXPERIMENT_ID:
        return launch_assigned_resource_open_experiment()
    if safe_experiment_id == STUDENT_RECOMMENDATION_EXPERIMENT_ID:
        return launch_student_recommendation_open_experiment()
    return False, {"experiment_id": safe_experiment_id}, "This experiment is visible in Classio, but its launch pipeline is not wired in the workspace yet."


def compute_experiment_eligibility_summary(experiment_id: str) -> dict[str, Any]:
    safe_experiment_id = _clean_text(experiment_id)
    known = KNOWN_EXPERIMENTS.get(safe_experiment_id) or {}
    if not bool(known.get("eligibility_supported")):
        return {
            "supported": False,
            "experiment_id": safe_experiment_id,
            "message": "Eligibility checks are not wired for this experiment yet.",
        }
    try:
        if safe_experiment_id == STUDENT_RECOMMENDATION_EXPERIMENT_ID:
            result = compute_student_recommendation_experiment_eligibility()
        else:
            result = compute_experiment_eligibility()
    except Exception as exc:
        return {
            "supported": True,
            "experiment_id": safe_experiment_id,
            "eligible": False,
            "blocking_reasons": ["Eligibility data could not be loaded from the current environment."],
            "warnings": [],
            "expected_maturity_ceiling": "unknown",
            "data_summary": {},
            "comparison": {},
            "message": _safe_error_message(exc) or "Eligibility data could not be loaded.",
        }
    return {
        "supported": True,
        "experiment_id": safe_experiment_id,
        "eligible": result.eligible,
        "blocking_reasons": list(result.blocking_reasons),
        "warnings": list(result.warnings),
        "expected_maturity_ceiling": result.expected_maturity_ceiling,
        "data_summary": result.data_summary,
        "comparison": result.comparison,
    }


def compute_experiment_eligibility() -> EligibilityResult:
    extraction_time = _utc_now()
    snapshot = extract_operational_snapshot(extraction_time=extraction_time)
    dataset_df, dataset_diag = build_assignment_dataset(snapshot, extraction_time=extraction_time)
    mature_df = dataset_df[dataset_df["label_status"] == "included"].copy()

    positive_count = int((mature_df[TARGET_NAME] == 1).sum()) if not mature_df.empty else 0
    negative_count = int((mature_df[TARGET_NAME] == 0).sum()) if not mature_df.empty else 0
    right_censored_count = int((dataset_df["label_status"] == "excluded").sum()) if "label_status" in dataset_df.columns else 0
    invalid_row_count = int((dataset_df["label_status"] == "invalid").sum()) if "label_status" in dataset_df.columns else 0
    teacher_count = int(mature_df["teacher_id"].replace("", pd.NA).nunique()) if not mature_df.empty else 0
    student_count = int(mature_df["student_id"].replace("", pd.NA).nunique()) if not mature_df.empty else 0
    resource_count = int(mature_df["resource_key"].replace("", pd.NA).nunique()) if not mature_df.empty else 0

    feature_missing = []
    if not mature_df.empty:
        for column in [col for col in mature_df.columns if col.startswith("prior_")]:
            if mature_df[column].isna().all():
                feature_missing.append(column)

    warnings: list[str] = []
    blocking: list[str] = []
    if teacher_count <= 1:
        warnings.append("Only one teacher is represented in the current mature label set.")
    if positive_count < 10:
        blocking.append("Fewer than 10 positive mature labels are available.")
    if negative_count < 10:
        blocking.append("Fewer than 10 negative mature labels are available.")
    if int(len(mature_df)) < 50:
        blocking.append("Fewer than 50 mature labels are available.")
    if feature_missing:
        warnings.append(f"Fully missing historical features: {', '.join(feature_missing[:6])}")

    telemetry_summary = {}
    try:
        telemetry_health = load_telemetry_health_snapshot(
            teacher_id=str(get_current_user_id() or "").strip(),
            days=30,
        )
        telemetry_summary = telemetry_health.get("summary") or {}
        if int(telemetry_summary.get("unmatched_opens") or 0) > 0:
            warnings.append("Telemetry has unmatched opens in the recent window.")
    except Exception:
        warnings.append("Telemetry diagnostics were unavailable during the eligibility check.")

    latest_attempted = list_experiment_runs(limit=1, cache_bust="eligibility-latest")
    latest_validated = list_experiment_runs(limit=20, validated_only=True, cache_bust="eligibility-validated")
    latest_attempted_row = latest_attempted[0] if latest_attempted else {}
    latest_validated_row = latest_validated[0] if latest_validated else {}

    data_summary = {
        **dataset_diag,
        "mature_labels": int(len(mature_df)),
        "positive_labels": positive_count,
        "negative_labels": negative_count,
        "right_censored_rows": right_censored_count,
        "invalid_rows": invalid_row_count,
        "teachers_represented": teacher_count,
        "students_represented": student_count,
        "resources_represented": resource_count,
        "class_balance": round(positive_count / max(1, positive_count + negative_count), 4),
        "fully_missing_features": feature_missing,
        "estimated_execution_time_seconds": 15,
        "expected_maturity_ceiling": "EXPLORATORY_ONLY" if teacher_count <= 1 else "CANDIDATE_FOR_SHADOW_TESTING",
        "telemetry_summary": telemetry_summary,
    }
    comparison = {
        "latest_attempted_run_id": str(latest_attempted_row.get("run_id") or ""),
        "latest_attempted_status": str(latest_attempted_row.get("run_status") or ""),
        "latest_validated_run_id": str(latest_validated_row.get("run_id") or ""),
        "latest_validated_status": str(latest_validated_row.get("run_status") or ""),
        "new_labels_since_latest_validated": max(
            0,
            int(len(mature_df)) - int(latest_validated_row.get("included_row_count") or 0),
        ),
    }
    return EligibilityResult(
        eligible=not blocking,
        blocking_reasons=tuple(blocking),
        warnings=tuple(warnings),
        expected_maturity_ceiling=str(data_summary["expected_maturity_ceiling"]),
        data_summary=data_summary,
        comparison=comparison,
    )


def compute_student_recommendation_experiment_eligibility() -> EligibilityResult:
    extraction_time = _utc_now()
    snapshot = extract_student_recommendation_snapshot(extraction_time=extraction_time)
    dataset_df, dataset_diag = build_student_recommendation_dataset(snapshot, extraction_time=extraction_time)
    mature_df = dataset_df[dataset_df["label_status"] == "included"].copy()

    positive_count = int((mature_df[TARGET_NAME] == 1).sum()) if not mature_df.empty else 0
    negative_count = int((mature_df[TARGET_NAME] == 0).sum()) if not mature_df.empty else 0
    right_censored_count = int((dataset_df["label_status"] == "excluded").sum()) if "label_status" in dataset_df.columns else 0
    invalid_row_count = int((dataset_df["label_status"] == "invalid").sum()) if "label_status" in dataset_df.columns else 0
    student_count = int(mature_df["student_id"].replace("", pd.NA).nunique()) if not mature_df.empty else 0
    resource_count = int(mature_df["resource_key"].replace("", pd.NA).nunique()) if not mature_df.empty else 0
    surface_count = int(mature_df["teacher_id"].replace("", pd.NA).nunique()) if not mature_df.empty else 0

    warnings: list[str] = []
    blocking: list[str] = []
    if surface_count <= 1:
        warnings.append("Only one recommendation surface is represented in the current mature label set.")
    if positive_count < 10:
        blocking.append("Fewer than 10 positive mature labels are available.")
    if negative_count < 10:
        blocking.append("Fewer than 10 negative mature labels are available.")
    if int(len(mature_df)) < 50:
        blocking.append("Fewer than 50 mature labels are available.")
    if student_count < 5:
        warnings.append("Very few students are represented in the current mature recommendation labels.")

    telemetry_summary = {}
    try:
        telemetry_health = load_telemetry_health_snapshot(
            teacher_id=str(get_current_user_id() or "").strip(),
            days=30,
        )
        telemetry_summary = telemetry_health.get("summary") or {}
    except Exception:
        warnings.append("Telemetry diagnostics were unavailable during the eligibility check.")

    latest_attempted = list_experiment_runs(experiment_id=STUDENT_RECOMMENDATION_EXPERIMENT_ID, limit=1, cache_bust="student-reco-eligibility-latest")
    latest_validated = list_experiment_runs(experiment_id=STUDENT_RECOMMENDATION_EXPERIMENT_ID, limit=20, validated_only=True, cache_bust="student-reco-eligibility-validated")
    latest_attempted_row = latest_attempted[0] if latest_attempted else {}
    latest_validated_row = latest_validated[0] if latest_validated else {}
    data_summary = {
        **dataset_diag,
        "mature_labels": int(len(mature_df)),
        "positive_labels": positive_count,
        "negative_labels": negative_count,
        "right_censored_rows": right_censored_count,
        "invalid_rows": invalid_row_count,
        "students_represented": student_count,
        "resources_represented": resource_count,
        "surfaces_represented": surface_count,
        "class_balance": round(positive_count / max(1, positive_count + negative_count), 4),
        "estimated_execution_time_seconds": 15,
        "expected_maturity_ceiling": "EXPLORATORY_ONLY" if student_count < 10 else "CANDIDATE_FOR_SHADOW_TESTING",
        "telemetry_summary": telemetry_summary,
    }
    comparison = {
        "latest_attempted_run_id": str(latest_attempted_row.get("run_id") or ""),
        "latest_attempted_status": str(latest_attempted_row.get("run_status") or ""),
        "latest_validated_run_id": str(latest_validated_row.get("run_id") or ""),
        "latest_validated_status": str(latest_validated_row.get("run_status") or ""),
        "new_labels_since_latest_validated": max(0, int(len(mature_df)) - int(latest_validated_row.get("included_row_count") or 0)),
    }
    return EligibilityResult(
        eligible=not blocking,
        blocking_reasons=tuple(blocking),
        warnings=tuple(warnings),
        expected_maturity_ceiling=str(data_summary["expected_maturity_ceiling"]),
        data_summary=data_summary,
        comparison=comparison,
    )


def _insert_run_row(payload: dict[str, Any]) -> None:
    get_sb().table(RUN_TABLE).insert(json_safe(payload)).execute()
    clear_experiment_cache()


def _insert_model_rows(run_id: str, comparison_path: Path) -> None:
    try:
        df = pd.read_csv(comparison_path)
    except Exception:
        return
    rows = []
    for _, row in df.iterrows():
        rows.append(
            {
                "run_id": run_id,
                "model_name": str(row.get("model_name") or ""),
                "execution_status": str(row.get("status") or ""),
                "parameters_json": {},
                "cv_metrics_json": {},
                "holdout_metrics_json": {
                    "roc_auc": row.get("roc_auc"),
                    "average_precision": row.get("average_precision"),
                    "balanced_accuracy": row.get("balanced_accuracy"),
                    "f1": row.get("f1"),
                    "brier_score": row.get("brier_score"),
                    "log_loss": row.get("log_loss"),
                },
                "confidence_intervals_json": json_safe(_read_json_dictish(row.get("confidence_intervals"))),
                "confusion_matrix_json": json_safe(_read_json_dictish(row.get("confusion_matrix"))),
                "predicted_positive_rate": row.get("predicted_positive_rate"),
                "train_duration_ms": _safe_int(row.get("train_duration_ms")),
                "inference_duration_ms": _safe_int(row.get("inference_duration_ms")),
                "failure_message": str(row.get("failure_reason") or ""),
            }
        )
    if rows:
        get_sb().table(RUN_MODEL_TABLE).insert(rows).execute()


def _safe_int(value: Any) -> int | None:
    try:
        if value in (None, "", "nan"):
            return None
        return int(float(value))
    except Exception:
        return None


def _read_json_dictish(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    text = _clean_text(value)
    if not text:
        return {}
    try:
        payload = json.loads(text)
        return payload if isinstance(payload, dict) else {}
    except Exception:
        return {}


def _insert_artifact_rows(run_id: str, run_dir: Path, experiment_id: str) -> None:
    runtime = _runtime_config(experiment_id)
    artifact_specs = [
        ("dataset_summary_json", str(runtime.get("dataset_summary_filename") or DATASET_SUMMARY_FILENAME), "application/json", False),
        ("label_audit_csv", str(runtime.get("label_audit_filename") or LABEL_AUDIT_FILENAME), "text/csv", True),
        ("feature_audit_csv", str(runtime.get("feature_audit_filename") or FEATURE_AUDIT_FILENAME), "text/csv", False),
        ("model_comparison_csv", str(runtime.get("model_comparison_filename") or MODEL_COMPARISON_FILENAME), "text/csv", False),
        ("run_summary_json", str(runtime.get("run_summary_filename") or RUN_SUMMARY_FILENAME), "application/json", False),
        ("technical_report_md", str(runtime.get("technical_report_filename") or TECHNICAL_REPORT_FILENAME), "text/markdown", False),
        ("findings_interpretation_report_md", str(runtime.get("academic_report_filename") or ACADEMIC_REPORT_FILENAME), "text/markdown", False),
        ("holdout_predictions_csv", str(runtime.get("predictions_filename") or PREDICTIONS_FILENAME), "text/csv", True),
        ("frozen_dataset_csv", str(runtime.get("frozen_dataset_filename") or FROZEN_DATASET_FILENAME), "text/csv", True),
        ("integrity_review_md", str(runtime.get("integrity_review_filename") or INTEGRITY_REVIEW_FILENAME), "text/markdown", False),
        ("label_reconciliation_csv", str(runtime.get("reconciliation_filename") or RECONCILIATION_FILENAME), "text/csv", True),
    ]
    rows = []
    for artifact_type, filename, content_type, sensitive in artifact_specs:
        path = run_dir / filename
        if not path.exists():
            continue
        rows.append(
            {
                "run_id": run_id,
                "artifact_type": artifact_type,
                "storage_bucket": _storage_bucket(),
                "storage_path": str(path),
                "checksum": _artifact_checksum(path),
                "content_type": content_type,
                "size_bytes": path.stat().st_size,
                "contains_sensitive_data": bool(sensitive),
            }
        )
    if rows:
        get_sb().table(RUN_ARTIFACT_TABLE).insert(rows).execute()


def _promote_current_validated_run(run_id: str, experiment_id: str) -> None:
    rows = list_experiment_runs(experiment_id=experiment_id, limit=100, cache_bust=f"promote-{run_id}")
    for row in rows:
        if row.get("run_id") == run_id:
            continue
        if bool(row.get("is_current_validated_run")):
            _update_run_row(
                str(row.get("run_id") or ""),
                {"is_current_validated_run": False, "superseded_by_run_id": run_id, "run_status": "SUPERSEDED"},
            )
            record_privileged_action(
                action_type="run_superseded",
                entity_type="ml_experiment_run",
                entity_id=str(row.get("run_id") or ""),
                before_json=row,
                after_json={"superseded_by_run_id": run_id, "run_status": "SUPERSEDED"},
                reason=f"Superseded by validated run {run_id}",
            )
    _update_run_row(run_id, {"is_current_validated_run": True})


def _persist_run_results(run_id: str, job_id: str, run_dir: Path, review_result: dict[str, Any]) -> dict[str, Any]:
    run_row = get_run(run_id)
    experiment_id = _clean_text(run_row.get("experiment_id")) or APPROVED_EXPERIMENT_ID
    runtime = _runtime_config(experiment_id)
    dataset_summary = _read_json(run_dir / str(runtime.get("dataset_summary_filename") or DATASET_SUMMARY_FILENAME))
    run_summary = _read_json(run_dir / str(runtime.get("run_summary_filename") or RUN_SUMMARY_FILENAME))
    evaluation = run_summary.get("evaluation") or {}
    review_section = run_summary.get("review") or {}
    run_status, integrity_status = _normalize_run_status_from_review(review_result)
    feature_excluded = _feature_exclusion_map(run_dir / str(runtime.get("feature_audit_filename") or FEATURE_AUDIT_FILENAME))

    payload = {
        "job_id": job_id,
        "run_status": run_status,
        "integrity_status": integrity_status,
        "maturity_verdict": str(evaluation.get("maturity_verdict") or ""),
        "evidence_verdict": str(evaluation.get("overall_evidence_strength") or review_result.get("overall_model_conclusion") or ""),
        "operational_use": "NONE",
        "academic_use": "EXPLORATORY_ONLY" if run_status in FINAL_VALIDATED_RUN_STATES else "NOT_FINAL",
        "started_at": dataset_summary.get("extracted_at"),
        "completed_at": _utc_now_iso(),
        "environment": "streamlit_sync_controlled_job",
        "code_version": _git_code_version(),
        "extraction_timestamp": dataset_summary.get("extracted_at"),
        "source_start_at": ((dataset_summary.get("date_range") or {}).get("assigned_at_min")),
        "source_end_at": ((dataset_summary.get("date_range") or {}).get("assigned_at_max")),
        "dataset_fingerprint": dataset_summary.get("data_fingerprint"),
        "chronological_cutoff": evaluation.get("cutoff_timestamp"),
        "feature_schema_version": dataset_summary.get("feature_schema_version"),
        "features_used_json": evaluation.get("feature_names") or [],
        "features_excluded_json": feature_excluded,
        "primary_metric_leader": evaluation.get("primary_metric_leader") or evaluation.get("winner"),
        "thresholded_classifier_leader": evaluation.get("best_thresholded_classifier"),
        "precision_recall_leader": evaluation.get("best_precision_recall_ranking"),
        "calibration_leader": evaluation.get("calibration_leader"),
        "overall_model_selection": evaluation.get("winner"),
        "artifact_root": _artifact_root_label(run_id),
        "validation_notes": str(review_section.get("label_reconciliation", {}).get("summary") or ""),
        "warning_summary": "; ".join(review_section.get("label_reconciliation", {}).get("limitations") or []),
        **_run_counts_from_dataset_summary(dataset_summary),
    }
    _update_run_row(run_id, payload)

    try:
        get_sb().table(RUN_MODEL_TABLE).delete().eq("run_id", run_id).execute()
    except Exception:
        pass
    try:
        get_sb().table(RUN_ARTIFACT_TABLE).delete().eq("run_id", run_id).execute()
    except Exception:
        pass
    _insert_model_rows(run_id, run_dir / str(runtime.get("model_comparison_filename") or MODEL_COMPARISON_FILENAME))
    _insert_artifact_rows(run_id, run_dir, experiment_id)
    if run_status in FINAL_VALIDATED_RUN_STATES:
        _promote_current_validated_run(run_id, experiment_id)
        record_privileged_action(
            action_type="run_marked_validated",
            entity_type="ml_experiment_run",
            entity_id=run_id,
            before_json={},
            after_json={"run_status": run_status, "integrity_status": integrity_status},
            reason="Automatic integrity validation passed.",
        )
    clear_experiment_cache()
    return payload


def launch_assigned_resource_open_experiment() -> tuple[bool, dict[str, Any], str]:
    return _launch_registered_experiment(APPROVED_EXPERIMENT_ID)


def launch_student_recommendation_open_experiment() -> tuple[bool, dict[str, Any], str]:
    return _launch_registered_experiment(STUDENT_RECOMMENDATION_EXPERIMENT_ID)


def _launch_registered_experiment(experiment_id: str) -> tuple[bool, dict[str, Any], str]:
    require_capability(CAPABILITY_RUN_APPROVED_EXPERIMENTS, message="Developer or data scientist access required.")
    ensure_experiment_registered()
    if experiment_id == APPROVED_EXPERIMENT_ID:
        ensure_historical_superseded_run_registered()
    environment = get_environment_readiness()
    if not bool(((environment.get("experiment_launcher") or {}).get("ready"))):
        return False, {"environment": environment}, "Experiment launcher is not ready in this environment."

    eligibility = (
        compute_student_recommendation_experiment_eligibility()
        if experiment_id == STUDENT_RECOMMENDATION_EXPERIMENT_ID
        else compute_experiment_eligibility()
    )
    record_privileged_action(
        action_type="experiment_eligibility_check",
        entity_type="ml_experiment",
        entity_id=experiment_id,
        before_json={},
        after_json={
            "eligible": eligibility.eligible,
            "blocking_reasons": list(eligibility.blocking_reasons),
            "warnings": list(eligibility.warnings),
            "data_summary": eligibility.data_summary,
        },
        reason="Manual developer workspace eligibility check.",
    )
    if not eligibility.eligible:
        return False, {"eligibility": eligibility.data_summary}, "Experiment is not eligible yet."

    mark_stale_experiment_jobs()
    active_runs = [
        row
        for row in list_experiment_runs(experiment_id=experiment_id, limit=50, cache_bust=f"{experiment_id}:active-run-check")
        if _clean_text(row.get("run_status")).upper() in ACTIVE_JOB_STATES
    ]
    if active_runs:
        return False, {"active_run": active_runs[0]}, "An active run already exists."

    run_id = uuid.uuid4().hex[:12]
    runtime = _runtime_config(experiment_id)
    experiment_version = _clean_text((KNOWN_EXPERIMENTS.get(experiment_id) or {}).get("experiment_version"))
    run_dir = _run_dir(run_id) if experiment_id == APPROVED_EXPERIMENT_ID else _run_dir(run_id, experiment_id)
    idempotency_key = f"{experiment_id}:{run_id}"
    created, job_row, job_message = create_job(
        job_type="ml_experiment_evaluation",
        job_version=experiment_version,
        idempotency_key=idempotency_key,
        payload_json={"experiment_id": experiment_id, "run_id": run_id},
        related_entity_type="ml_experiment_run",
        related_entity_id=run_id,
    )
    if not created or not job_row:
        return False, {"job": job_row or {}}, job_message

    initiated_by = str(get_current_user_id() or "").strip()
    run_inserted = False

    try:
        _insert_run_row(
            {
                "run_id": run_id,
                "experiment_id": experiment_id,
                "experiment_version": experiment_version,
                "job_id": str(job_row.get("job_id") or ""),
                "run_status": "QUEUED",
                "integrity_status": "NOT_RUN",
                "operational_use": "NONE",
                "academic_use": "NOT_FINAL",
                "initiated_by": initiated_by or None,
                "environment": "streamlit_sync_controlled_job",
                "code_version": _git_code_version(),
                "artifact_root": _artifact_root_label(run_id),
                "is_current_validated_run": False,
                "validation_notes": "",
            }
        )
        run_inserted = True
        record_privileged_action(
            action_type="experiment_launched",
            entity_type="ml_experiment_run",
            entity_id=run_id,
            before_json={},
            after_json={"job_id": job_row.get("job_id"), "run_status": "QUEUED"},
            reason="Launch requested from Developer Workspace.",
        )
        update_job_state(str(job_row.get("job_id") or ""), current_stage="starting", progress_pct=1)
        _set_run_status(run_id, "RUNNING", extra_payload={"started_at": _utc_now_iso()})
        update_job_state(str(job_row.get("job_id") or ""), next_status="RUNNING", current_stage="prepare_artifact_directory", progress_pct=5)
        run_dir.mkdir(parents=True, exist_ok=True)
        update_job_state(str(job_row.get("job_id") or ""), current_stage="extract_and_train", progress_pct=10)
        result, review_result = _run_pipeline_in_ml_runtime(run_dir, run_id=run_id, experiment_id=experiment_id)
        update_job_state(str(job_row.get("job_id") or ""), current_stage="integrity_review", progress_pct=80)
        _set_run_status(run_id, "COMPLETED_PENDING_VALIDATION")
        _update_run_row(run_id, {"integrity_status": "RUNNING"})
        persisted = _persist_run_results(run_id, str(job_row.get("job_id") or ""), run_dir, review_result)
        update_job_state(
            str(job_row.get("job_id") or ""),
            next_status="COMPLETED",
            current_stage="completed",
            progress_pct=100,
            result_json={"run_id": run_id, "review_result": review_result, "summary": persisted},
        )
        clear_experiment_cache()
        return True, {"run_id": run_id, "job_id": job_row.get("job_id"), "review_result": review_result, "summary": persisted, "result": result}, "Experiment completed."
    except Exception as exc:
        if not run_inserted:
            safe_message = _safe_error_message(exc)
            update_job_state(
                str(job_row.get("job_id") or ""),
                next_status="FAILED",
                current_stage="launch",
                progress_pct=100,
                error_code="experiment_failed_before_run_insert",
                error_message=safe_message,
                warning_json={"traceback": traceback.format_exc(), "failure_stage": "launch"},
            )
            clear_experiment_cache()
            return False, {"job_id": job_row.get("job_id")}, safe_message
        failure_stage = _clean_text((get_job(str(job_row.get("job_id") or "")).get("current_stage") or "launch"))
        return _record_failure(run_id, job_id=str(job_row.get("job_id") or ""), stage=failure_stage, exc=exc)


def rerun_integrity_review_for_run(run_id: str) -> tuple[bool, dict[str, Any], str]:
    require_capability(CAPABILITY_RERUN_INTEGRITY_REVIEW, message="Developer or data scientist access required.")
    run_row = get_run(run_id)
    if not run_row:
        return False, {}, "Run not found."
    allowed, message = can_manually_rerun_integrity(run_id)
    if not allowed:
        return False, {"readiness": get_run_artifact_readiness(run_id).__dict__}, message
    run_dir = Path(str(run_row.get("artifact_root") or ""))
    experiment_id = _clean_text(run_row.get("experiment_id")) or APPROVED_EXPERIMENT_ID
    experiment_version = _clean_text((KNOWN_EXPERIMENTS.get(experiment_id) or {}).get("experiment_version"))
    reviewer = _runtime_config(experiment_id).get("review_callable") or review_assigned_resource_open_7d
    created, job_row, message = create_job(
        job_type="ml_integrity_review",
        job_version=experiment_version,
        idempotency_key=f"integrity:{run_id}:{uuid.uuid4().hex[:8]}",
        payload_json={"run_id": run_id},
        related_entity_type="ml_experiment_run",
        related_entity_id=run_id,
    )
    if not created or not job_row:
        return False, {"job": job_row or {}}, message
    try:
        _update_run_row(run_id, {"integrity_status": "RUNNING"})
        record_privileged_action(
            action_type="integrity_review_started",
            entity_type="ml_experiment_run",
            entity_id=run_id,
            before_json={"run_status": run_row.get("run_status"), "integrity_status": run_row.get("integrity_status")},
            after_json={"integrity_status": "RUNNING"},
            reason="Manual integrity rerun from Developer Workspace.",
        )
        update_job_state(str(job_row.get("job_id") or ""), next_status="RUNNING", current_stage="integrity_review", progress_pct=20)
        review_result = reviewer(run_dir)
        payload = _persist_run_results(run_id, str(job_row.get("job_id") or ""), run_dir, review_result)
        update_job_state(
            str(job_row.get("job_id") or ""),
            next_status="COMPLETED",
            current_stage="completed",
            progress_pct=100,
            result_json={"run_id": run_id, "review_result": review_result},
        )
        record_privileged_action(
            action_type="integrity_review_completed",
            entity_type="ml_experiment_run",
            entity_id=run_id,
            before_json={},
            after_json={"review_result": review_result, "summary": payload},
            reason="Manual integrity rerun completed.",
        )
        return True, {"review_result": review_result, "summary": payload}, "Integrity review completed."
    except Exception as exc:
        _update_run_row(run_id, {"integrity_status": "FAILED", "failure_message": _safe_error_message(exc)})
        update_job_state(
            str(job_row.get("job_id") or ""),
            next_status="FAILED",
            current_stage="failed",
            progress_pct=100,
            error_code="integrity_review_failed",
            error_message=_safe_error_message(exc),
            warning_json={"traceback": traceback.format_exc()},
        )
        return False, {"job_id": job_row.get("job_id")}, _safe_error_message(exc)


@st.cache_data(ttl=20, show_spinner=False)
def get_workspace_overview(cache_bust: str = "") -> dict[str, Any]:
    ensure_experiment_registered()
    latest_runs = list_experiment_runs(experiment_id=None, limit=25, cache_bust=cache_bust)
    latest_validated = get_latest_validated_run_summary(experiment_id=None, cache_bust=cache_bust)
    experiment_catalog = list_experiment_catalog(cache_bust=cache_bust)
    jobs = list_jobs(limit=50, cache_bust=cache_bust)
    failed_jobs = [row for row in jobs if str(row.get("status") or "").upper() == "FAILED"]
    active_jobs = [row for row in jobs if str(row.get("status") or "").upper() in ACTIVE_JOB_STATES]
    telemetry_health = {}
    try:
        telemetry_health = load_telemetry_health_snapshot(teacher_id=str(get_current_user_id() or "").strip(), days=30)
    except Exception:
        telemetry_health = {}
    environment_readiness = get_environment_readiness()
    return {
        "environment": "streamlit",
        "code_version": _git_code_version(),
        "latest_successful_experiment": next(
            (row for row in latest_runs if str(row.get("run_status") or "").upper() in FINAL_VALIDATED_RUN_STATES | {"REQUIRES_RERUN"}),
            {},
        ),
        "latest_attempted_experiment": latest_runs[0] if latest_runs else {},
        "active_jobs": active_jobs,
        "failed_jobs": failed_jobs,
        "latest_validated_run": latest_validated,
        "experiment_catalog": experiment_catalog,
        "telemetry_status": (telemetry_health.get("summary") or {}),
        "environment_readiness": environment_readiness,
        "migration_status": {
            "staff_roles_table_expected": bool((((environment_readiness.get("database_migration") or {}).get("details") or {}).get("user_staff_roles") or {}).get("ready")),
            "ml_registry_expected": bool((((environment_readiness.get("database_migration") or {}).get("details") or {}).get(RUN_TABLE) or {}).get("ready")),
            "controlled_jobs_expected": bool((((environment_readiness.get("database_migration") or {}).get("details") or {}).get("system_jobs") or {}).get("ready")),
        },
        "warnings": [
            "No validated run yet." if not latest_validated else "",
            "Historical run ca935f4e5587 remains superseded and not final.",
        ],
    }


def list_run_models(run_id: str) -> list[dict[str, Any]]:
    try:
        rows = (
            get_sb()
            .table(RUN_MODEL_TABLE)
            .select("*")
            .eq("run_id", _clean_text(run_id))
            .order("created_at", desc=False)
            .execute()
        ).data or []
        return [dict(row) for row in rows]
    except Exception:
        return []


def list_run_artifacts(run_id: str) -> list[dict[str, Any]]:
    try:
        rows = (
            get_sb()
            .table(RUN_ARTIFACT_TABLE)
            .select("*")
            .eq("run_id", _clean_text(run_id))
            .order("created_at", desc=False)
            .execute()
        ).data or []
        return [dict(row) for row in rows]
    except Exception:
        return []


def cleanup_expired_local_artifacts(*, experiment_id: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
    cleaned_rows: list[dict[str, Any]] = []
    scan_runs = list_experiment_runs(experiment_id=experiment_id, limit=max(1, min(int(limit), 200)), cache_bust=f"cleanup:{experiment_id or 'all'}")
    for row in scan_runs:
        run_id = _clean_text(row.get("run_id"))
        if not run_id:
            continue
        retention = get_run_artifact_retention_status(run_id)
        if retention.protected or not retention.cleanup_eligible:
            continue
        artifact_dir = _artifact_root_for_row(row)
        if not artifact_dir.exists():
            continue
        try:
            shutil.rmtree(artifact_dir)
        except Exception:
            continue
        cleaned_rows.append(
            {
                "run_id": run_id,
                "experiment_id": _clean_text(row.get("experiment_id")),
                "artifact_root": str(artifact_dir),
                "retention_tier": retention.protection_tier,
            }
        )
    return cleaned_rows


def mark_stale_experiment_jobs(*, stale_after_minutes: int = 30) -> int:
    stale_count = 0
    stale_before = _utc_now() - timedelta(minutes=max(1, int(stale_after_minutes)))
    for row in list_jobs(statuses=sorted(ACTIVE_JOB_STATES), limit=200, cache_bust="stale-run-scan"):
        job_id = str(row.get("job_id") or "")
        related_run_id = str(row.get("related_entity_id") or "")
        heartbeat_text = _clean_text(row.get("heartbeat_at") or row.get("updated_at") or row.get("requested_at"))
        if not heartbeat_text:
            continue
        try:
            heartbeat_at = datetime.fromisoformat(heartbeat_text.replace("Z", "+00:00"))
        except Exception:
            continue
        if heartbeat_at.tzinfo is None:
            heartbeat_at = heartbeat_at.replace(tzinfo=timezone.utc)
        if heartbeat_at >= stale_before:
            continue
        ok, _message = update_job_state(job_id, next_status="STALE", current_stage="stale", error_code="stale_job", error_message="Job became stale before completion.")
        if ok:
            stale_count += 1
            if related_run_id:
                _update_run_row(
                    related_run_id,
                    {
                        "run_status": "FAILED",
                        "integrity_status": "FAILED",
                        "failure_message": "Related job became stale before evaluation completed.",
                        "validation_notes": "failure_stage=stale_job",
                        "is_current_validated_run": False,
                    },
                )
    clear_experiment_cache()
    return stale_count
