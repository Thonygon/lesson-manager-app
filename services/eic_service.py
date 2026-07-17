from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import time
from typing import Any

import pandas as pd
import streamlit as st

from core.database import get_sb
from services.authorization_service import CAPABILITY_VIEW_TECHNICAL_ARTIFACTS, has_capability
from services.ml_experiment_service import (
    APPROVED_EXPERIMENT_ID,
    FINAL_VALIDATED_RUN_STATES,
    RUN_ARTIFACT_TABLE,
    RUN_SUMMARY_FILENAME,
    DATASET_SUMMARY_FILENAME,
    MODEL_COMPARISON_FILENAME,
    FEATURE_AUDIT_FILENAME,
    ACADEMIC_REPORT_FILENAME,
    TECHNICAL_REPORT_FILENAME,
    list_experiment_catalog,
    list_run_artifacts,
)


RUN_SUMMARY_COLUMNS = ",".join(
    [
        "run_id",
        "experiment_id",
        "created_at",
        "run_status",
        "integrity_status",
        "maturity_verdict",
        "evidence_verdict",
        "primary_metric_leader",
        "overall_model_selection",
        "included_row_count",
        "positive_label_count",
        "negative_label_count",
        "teachers_represented",
        "students_represented",
        "resources_represented",
        "dataset_fingerprint",
        "source_start_at",
        "source_end_at",
        "chronological_cutoff",
        "artifact_root",
        "is_current_validated_run",
        "validation_notes",
        "warning_summary",
    ]
)


COMPONENT_BLUEPRINT: tuple[dict[str, Any], ...] = (
    {
        "component_id": "teacher_recommendation_objective_selector",
        "name": "Teacher Recommendation Objective Selector",
        "business_question": "Which pedagogical objective should the teacher tackle next?",
        "decision_supported": "Which student-topic card should rank highest in the teacher recommendation panel.",
        "component_type": "hybrid_intelligence",
        "operational_status": "live",
        "data_maturity": "collecting_data",
        "evidence_maturity": "limited",
        "production_use": "Ranks live teacher recommendation cards.",
        "limitation": "Uses handcrafted proxy targets from recommendation-event summaries.",
        "recommended_next_action": "Continue telemetry collection before supervised training.",
        "product_surface": "Teacher recommendations in Students workspace.",
        "educational_value": "Helps teachers prioritize the next topic or review action.",
        "unit_of_analysis": "One objective candidate for one student-topic pair.",
        "relevant_rows": 8,
        "date_coverage": "2026-04-10 to 2026-07-12",
        "teachers_represented": 1,
        "students_represented": 2,
        "resources_represented": 4,
        "topics_represented": 4,
        "outcome_metric": "Not measurable yet",
        "evidence_sources": [
            "docs/classio_ml_blueprint.md",
            "helpers/teacher_recommendation_ml.py",
            "app_pages/app_page_students.py",
        ],
    },
    {
        "component_id": "teacher_recommendation_resource_ranker",
        "name": "Teacher Recommendation Resource Ranker",
        "business_question": "Which supporting resource best fits the teacher recommendation item?",
        "decision_supported": "Which worksheet, exam, or video should support the recommended objective.",
        "component_type": "heuristic_ranker",
        "operational_status": "live",
        "data_maturity": "collecting_data",
        "evidence_maturity": "limited",
        "production_use": "Ranks teacher resource options in live recommendations.",
        "limitation": "Training signal is a proxy and includes post-selection actions.",
        "recommended_next_action": "Keep as heuristic-plus-affinity ranker.",
        "product_surface": "Teacher recommendation resource picker.",
        "educational_value": "Improves the quality of supporting materials attached to teacher actions.",
        "unit_of_analysis": "One resource candidate for one teacher recommendation item.",
        "relevant_rows": 8,
        "date_coverage": "2026-04-10 to 2026-07-12",
        "teachers_represented": 1,
        "students_represented": 2,
        "resources_represented": 2,
        "topics_represented": 4,
        "outcome_metric": "Not measurable yet",
        "evidence_sources": [
            "docs/classio_ml_blueprint.md",
            "helpers/recommendation_models.py",
            "app_pages/app_page_students.py",
        ],
    },
    {
        "component_id": "teacher_material_feed_ranker",
        "name": "Teacher Material Feed Ranker",
        "business_question": "Which materials should teachers see first in their feed?",
        "decision_supported": "How teacher home and explore materials are ordered.",
        "component_type": "heuristic_ranker",
        "operational_status": "production",
        "data_maturity": "healthy",
        "evidence_maturity": "direct_observed_data",
        "production_use": "Orders teacher material feed cards today.",
        "limitation": "No tenant identifier beyond teacher_id, so cross-teacher aggregation needs care.",
        "recommended_next_action": "Maintain current logic and monitor tenant isolation.",
        "product_surface": "Teacher Home feed.",
        "educational_value": "Surfaces reusable teaching materials efficiently.",
        "unit_of_analysis": "One material candidate shown in a teacher feed.",
        "relevant_rows": 6973,
        "date_coverage": "Observed in live user activity history",
        "teachers_represented": 2,
        "students_represented": 0,
        "resources_represented": 67,
        "topics_represented": 62,
        "outcome_metric": "Teacher material opens are measurable.",
        "evidence_sources": [
            "docs/classio_ml_blueprint.md",
            "helpers/recommendation_models.py",
            "app_pages/home.py",
        ],
    },
    {
        "component_id": "student_recommendation_ranker",
        "name": "Student Recommendation Ranker",
        "business_question": "Which practice resource should the learner see next?",
        "decision_supported": "What optional practice recommendation is shown to the student.",
        "component_type": "hybrid_intelligence",
        "operational_status": "live",
        "data_maturity": "collecting_labels",
        "evidence_maturity": "limited",
        "production_use": "Ranks optional student recommendations in production.",
        "limitation": "Impression logging is inconsistent across student surfaces.",
        "recommended_next_action": "Continue collecting consistent recommendation exposures.",
        "product_surface": "Student Practice and Student Home.",
        "educational_value": "Personalizes what the learner should practice next.",
        "unit_of_analysis": "One student-resource candidate.",
        "relevant_rows": 222,
        "date_coverage": "Practice/assignment/recommendation activity through 2026-07-16",
        "teachers_represented": 0,
        "students_represented": 16,
        "resources_represented": 62,
        "topics_represented": 46,
        "outcome_metric": "Not measurable yet",
        "evidence_sources": [
            "docs/classio_ml_blueprint.md",
            "app_pages/student_practice.py",
            "app_pages/student_home.py",
            "helpers/student_recommendations.py",
        ],
    },
    {
        "component_id": "student_recommendation_acceptance_blend_model",
        "name": "Student Recommendation Acceptance / Blend Model",
        "business_question": "How much should the live student ranker trust the learned score?",
        "decision_supported": "The blend between heuristic rank score and learned proxy score.",
        "component_type": "statistical_estimator",
        "operational_status": "experimental",
        "data_maturity": "collecting_data",
        "evidence_maturity": "proxy_only",
        "production_use": "Contributes an ml_score and blend weight to the student ranker.",
        "limitation": "Uses handcrafted proxy labels, not real impression-to-open outcomes.",
        "recommended_next_action": "Retire the acceptance framing until real labels exist.",
        "product_surface": "Student recommendation scoring internals.",
        "educational_value": "Attempts to personalize optional practice ranking.",
        "unit_of_analysis": "One training row from practice, assignment, or recommendation history.",
        "relevant_rows": 49,
        "date_coverage": "Single checked-in report sample through 2026-07-16",
        "teachers_represented": 0,
        "students_represented": 1,
        "resources_represented": 0,
        "topics_represented": 0,
        "outcome_metric": "Proxy-only evaluation",
        "evidence_sources": [
            "docs/classio_ml_blueprint.md",
            "helpers/student_recommendation_ml.py",
            "helpers/recommendation_models.py",
        ],
    },
    {
        "component_id": "explicit_topic_resource_matching",
        "name": "Explicit Topic-Resource Matching",
        "business_question": "How historically aligned is a resource with a topic?",
        "decision_supported": "Whether a resource should receive topic-match support in ranking.",
        "component_type": "statistical_estimator",
        "operational_status": "production",
        "data_maturity": "partial",
        "evidence_maturity": "feature_source",
        "production_use": "Acts as a feature source for teacher and student ranking.",
        "limitation": "Sparse assignment topic coverage limits present-day support.",
        "recommended_next_action": "Keep as feature engineering, not as a standalone ML claim.",
        "product_surface": "Teacher and student resource ranking.",
        "educational_value": "Improves topic fit between content and learning needs.",
        "unit_of_analysis": "One resource-topic affinity combination.",
        "relevant_rows": 135,
        "date_coverage": "Assignments and recommendation events through 2026-07-16",
        "teachers_represented": 1,
        "students_represented": 0,
        "resources_represented": 0,
        "topics_represented": 3,
        "outcome_metric": "Not measurable yet",
        "evidence_sources": [
            "docs/classio_ml_blueprint.md",
            "helpers/recommendation_models.py",
        ],
    },
    {
        "component_id": "practice_mastery_aggregator",
        "name": "Practice Mastery Aggregator",
        "business_question": "What has the student practised and mastered?",
        "decision_supported": "How practice history is summarized for progress and recommendations.",
        "component_type": "deterministic_workflow",
        "operational_status": "production",
        "data_maturity": "healthy",
        "evidence_maturity": "direct_observed_data",
        "production_use": "Powering progress summaries and feature generation today.",
        "limitation": "None material to supervised readiness; it is deterministic by design.",
        "recommended_next_action": "Maintain current logic and monitor data quality.",
        "product_surface": "Practice progress and downstream recommendations.",
        "educational_value": "Provides a reliable mastery picture from observed student practice.",
        "unit_of_analysis": "One aggregated student progress state.",
        "relevant_rows": 88,
        "date_coverage": "Practice sessions through 2026-07-16",
        "teachers_represented": 0,
        "students_represented": 16,
        "resources_represented": 62,
        "topics_represented": 46,
        "outcome_metric": "Direct observed data",
        "evidence_sources": [
            "docs/classio_ml_blueprint.md",
            "helpers/practice_engine.py",
        ],
    },
    {
        "component_id": "review_synchronization_loop",
        "name": "Review Synchronization Loop",
        "business_question": "How should review corrections propagate back into practice and assignments?",
        "decision_supported": "How corrected answers update downstream student records.",
        "component_type": "deterministic_workflow",
        "operational_status": "production",
        "data_maturity": "healthy",
        "evidence_maturity": "direct_observed_data",
        "production_use": "Synchronizes review outcomes across practice and assignment records.",
        "limitation": "Not a supervised-learning candidate.",
        "recommended_next_action": "Maintain deterministic logic.",
        "product_surface": "Teacher review and practice correction workflows.",
        "educational_value": "Keeps progress and review outcomes consistent for the learner.",
        "unit_of_analysis": "One review correction and its downstream updates.",
        "relevant_rows": 69,
        "date_coverage": "Assignment attempts and review activity through 2026-07-16",
        "teachers_represented": 0,
        "students_represented": 0,
        "resources_represented": 0,
        "topics_represented": 0,
        "outcome_metric": "Review closure is measurable",
        "evidence_sources": [
            "docs/classio_ml_blueprint.md",
            "helpers/teacher_student_integration.py",
            "helpers/practice_engine.py",
        ],
    },
    {
        "component_id": "material_reuse_similarity_retriever",
        "name": "Material Reuse Similarity Retriever",
        "business_question": "Which previously created material can be reused for a similar need?",
        "decision_supported": "Whether to suggest an existing material instead of creating a new one.",
        "component_type": "retrieval_system",
        "operational_status": "production",
        "data_maturity": "healthy",
        "evidence_maturity": "direct_observed_data",
        "production_use": "Retrieves reusable material suggestions for teachers.",
        "limitation": "Should remain retrieval-oriented rather than framed as supervised ML.",
        "recommended_next_action": "Maintain and monitor.",
        "product_surface": "Material recommendation and reuse flows.",
        "educational_value": "Saves teacher planning time through reuse.",
        "unit_of_analysis": "One material retrieval candidate.",
        "relevant_rows": 156,
        "date_coverage": "Current material inventory through 2026-07-16",
        "teachers_represented": 0,
        "students_represented": 0,
        "resources_represented": 156,
        "topics_represented": 0,
        "outcome_metric": "Reuse opportunities observed",
        "evidence_sources": [
            "docs/classio_ml_blueprint.md",
            "helpers/material_recommendations.py",
        ],
    },
    {
        "component_id": "recommendation_event_feedback_loop",
        "name": "Recommendation Event Feedback Loop",
        "business_question": "Is recommendation telemetry capturing enough real feedback to improve the system?",
        "decision_supported": "Whether Classio has enough recommendation evidence to train or validate better rankers.",
        "component_type": "deterministic_workflow",
        "operational_status": "experimental",
        "data_maturity": "partial",
        "evidence_maturity": "limited",
        "production_use": "Collects recommendation events for analysis.",
        "limitation": "Sparse exposure logging and duplicate-risk ambiguity remain.",
        "recommended_next_action": "Improve exposure matching and grow real usage.",
        "product_surface": "Recommendation telemetry layer.",
        "educational_value": "Creates the evidence base needed for future personalization.",
        "unit_of_analysis": "One logged recommendation exposure or event.",
        "relevant_rows": 8,
        "date_coverage": "2026-04-10 to 2026-07-12",
        "teachers_represented": 1,
        "students_represented": 2,
        "resources_represented": 2,
        "topics_represented": 4,
        "outcome_metric": "Not measurable yet",
        "evidence_sources": [
            "docs/classio_ml_blueprint.md",
            "classio_supervised_ml_data_audit.md",
            "helpers/exposure_telemetry.py",
        ],
    },
    {
        "component_id": "assigned_resource_open_within_7d",
        "name": "Assigned Resource Open Within 7 Days experiment",
        "business_question": "Can Classio predict whether a student will open an assigned resource within seven days?",
        "decision_supported": "Whether supervised prediction is credible enough to compare against current heuristics.",
        "component_type": "supervised_experiment",
        "operational_status": "offline_evaluation",
        "data_maturity": "validated_evidence_ready",
        "evidence_maturity": "exploratory",
        "production_use": "Offline validated evaluation only. No live model deployment.",
        "limitation": "Current mature label set is dominated by one teacher.",
        "recommended_next_action": "Expand teacher coverage and continue collecting labels.",
        "product_surface": "Developer Workspace and EIC evidence views.",
        "educational_value": "Could eventually improve assignment follow-through decisions.",
        "unit_of_analysis": "One teacher assignment representing one assigned-resource exposure.",
        "relevant_rows": 127,
        "date_coverage": "2026-04-10 to 2026-07-12",
        "teachers_represented": 1,
        "students_represented": 0,
        "resources_represented": 0,
        "topics_represented": 0,
        "outcome_metric": "Seven-day assignment open label",
        "evidence_sources": [
            "classio_supervised_ml_data_audit.md",
            "docs/classio_ml_blueprint.md",
            "services/ml_experiment_service.py",
        ],
    },
)


def _clean_text(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


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


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _read_csv_rows(path: Path, *, limit: int = 50) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    try:
        df = pd.read_csv(path)
    except Exception:
        return []
    if df.empty:
        return []
    return df.head(max(1, min(int(limit), 100))).fillna("").to_dict("records")


def _artifact_path_map(run_id: str) -> dict[str, Path]:
    rows = list_run_artifacts(run_id)
    artifact_paths: dict[str, Path] = {}
    for row in rows:
        artifact_type = _clean_text(row.get("artifact_type"))
        storage_path = _clean_text(row.get("storage_path"))
        if artifact_type and storage_path:
            artifact_paths[artifact_type] = Path(storage_path)
    return artifact_paths


def _validated_run_rows(*, limit: int, offset: int, cache_bust: str, experiment_id: str | None = APPROVED_EXPERIMENT_ID) -> list[dict[str, Any]]:
    query = (
        get_sb()
        .table("ml_experiment_runs")
        .select(RUN_SUMMARY_COLUMNS)
        .in_("run_status", sorted(FINAL_VALIDATED_RUN_STATES))
        .order("created_at", desc=True)
        .limit(max(1, min(int(limit), 50)))
    )
    if _clean_text(experiment_id):
        query = query.eq("experiment_id", _clean_text(experiment_id))
    if offset > 0:
        query = query.range(int(offset), int(offset + limit - 1))
    try:
        return [dict(row) for row in (query.execute().data or [])]
    except Exception:
        return []


def _run_evidence_level(run_row: dict[str, Any]) -> str:
    if not run_row:
        return "not_available"
    if _clean_text(run_row.get("run_status")) == "VALIDATED_NO_ROBUST_WINNER":
        return "validated"
    if int(run_row.get("teachers_represented") or 0) <= 1:
        return "exploratory"
    return "validated"


def _run_business_action(run_row: dict[str, Any], telemetry_summary: dict[str, Any] | None = None) -> str:
    telemetry_summary = telemetry_summary or {}
    if not run_row:
        return "continue_collecting_data"
    if int(run_row.get("teachers_represented") or 0) <= 1:
        return "expand_teacher_coverage"
    if int(telemetry_summary.get("unmatched_opens") or 0) > 0:
        return "improve_exposure_matching"
    if _clean_text(run_row.get("run_status")) == "VALIDATED_NO_ROBUST_WINNER":
        return "maintain_current_logic"
    return "reevaluate_later"


def _telemetry_status_from_counts(exposures: int, matched: int, unmatched: int) -> str:
    if exposures <= 0:
        return "insufficient_data"
    if unmatched > 0 and matched <= 0:
        return "broken"
    if exposures < 10:
        return "collecting_data"
    if unmatched > 0:
        return "partial"
    return "healthy"


@st.cache_data(ttl=30, show_spinner=False)
def get_business_telemetry_health(*, days: int = 30, cache_bust: str = "") -> dict[str, Any]:
    started = time.perf_counter()
    window_days = max(7, min(int(days or 30), 90))
    end_dt = _utc_now()
    start_dt = end_dt - timedelta(days=window_days)
    start_iso = start_dt.isoformat()
    end_iso = end_dt.isoformat()
    exposure_rows: list[dict[str, Any]]
    event_rows: list[dict[str, Any]]
    try:
        exposure_rows = (
            get_sb()
            .table("resource_exposures")
            .select("exposure_id,teacher_id,student_id,resource_id,resource_type,exposure_type,surface,shown_at,created_at")
            .gte("shown_at", start_iso)
            .lte("shown_at", end_iso)
            .order("shown_at", desc=False)
            .limit(5000)
            .execute()
        ).data or []
    except Exception:
        exposure_rows = []
    try:
        event_rows = (
            get_sb()
            .table("resource_exposure_events")
            .select("exposure_id,event_type,event_at,teacher_id,student_id,created_at")
            .gte("event_at", start_iso)
            .lte("event_at", end_iso)
            .order("event_at", desc=False)
            .limit(5000)
            .execute()
        ).data or []
    except Exception:
        event_rows = []

    exposure_df = pd.DataFrame(exposure_rows)
    event_df = pd.DataFrame(event_rows)
    if exposure_df.empty:
        exposure_df = pd.DataFrame(columns=["exposure_id", "surface", "exposure_type", "resource_type", "resource_id", "shown_at", "teacher_id", "student_id"])
    if event_df.empty:
        event_df = pd.DataFrame(columns=["exposure_id", "event_type", "event_at", "teacher_id", "student_id"])

    exposure_ids = set(exposure_df.get("exposure_id", pd.Series(dtype=str)).astype(str))
    open_df = event_df[event_df.get("event_type", pd.Series(dtype=str)).astype(str) == "opened"].copy()
    matched_open_ids = set(open_df.get("exposure_id", pd.Series(dtype=str)).astype(str))
    events_without_exposures = int(len(set(event_df.get("exposure_id", pd.Series(dtype=str)).astype(str)) - exposure_ids))
    duplicate_signatures = 0
    repeated_exposures = 0
    if not exposure_df.empty:
        repeated_exposures = int(
            exposure_df.groupby(["teacher_id", "student_id", "surface", "resource_type", "resource_id"], dropna=False).size().gt(1).sum()
        )

    surface_rows: list[dict[str, Any]] = []
    for (surface, exposure_type), group in exposure_df.groupby(["surface", "exposure_type"], dropna=False):
        surface_ids = set(group.get("exposure_id", pd.Series(dtype=str)).astype(str))
        total = int(len(group))
        matched = int(len(surface_ids & matched_open_ids))
        open_events = int(open_df[open_df.get("exposure_id", pd.Series(dtype=str)).astype(str).isin(surface_ids)].shape[0])
        unmatched = max(0, open_events - matched)
        shown_values = pd.to_datetime(group.get("shown_at", pd.Series(dtype=str)), errors="coerce", utc=True)
        mature_count = int((shown_values <= (end_dt - timedelta(days=7))).sum()) if len(shown_values) else 0
        surface_rows.append(
            {
                "surface": _clean_text(surface),
                "exposure_type": _clean_text(exposure_type),
                "exposures": total,
                "matched_opens": matched,
                "unmatched_opens": unmatched,
                "downstream_outcome_coverage": round(
                    float(
                        event_df[
                            event_df.get("exposure_id", pd.Series(dtype=str)).astype(str).isin(surface_ids)
                            & event_df.get("event_type", pd.Series(dtype=str)).astype(str).isin(
                                ["completed", "scored", "teacher_reviewed", "student_improved", "assigned", "accepted"]
                            )
                        ].shape[0]
                    )
                    / max(total, 1),
                    4,
                ),
                "mature_outcomes_7d": mature_count,
                "status": _telemetry_status_from_counts(total, matched, unmatched),
            }
        )

    freshness_candidates = [
        _parse_dt(exposure_df.get("shown_at", pd.Series(dtype=str)).max() if not exposure_df.empty else ""),
        _parse_dt(event_df.get("event_at", pd.Series(dtype=str)).max() if not event_df.empty else ""),
    ]
    latest_event = max((item for item in freshness_candidates if item is not None), default=None)
    telemetry_freshness_hours = None
    if latest_event is not None:
        telemetry_freshness_hours = round(max(0.0, (end_dt - latest_event).total_seconds() / 3600.0), 1)

    summary = {
        "total_canonical_exposures": int(len(exposure_df)),
        "matched_open_coverage": round(float(len(matched_open_ids)) / max(int(len(exposure_df)), 1), 4) if len(exposure_df) else 0.0,
        "unmatched_opens": int(sum(int(row.get("unmatched_opens") or 0) for row in surface_rows)),
        "downstream_outcome_coverage": round(
            float(
                event_df.get("event_type", pd.Series(dtype=str)).astype(str).isin(
                    ["completed", "scored", "teacher_reviewed", "student_improved", "assigned", "accepted"]
                ).sum()
            )
            / max(int(len(exposure_df)), 1),
            4,
        ) if len(exposure_df) else 0.0,
        "mature_outcomes_7d": int(
            (
                pd.to_datetime(exposure_df.get("shown_at", pd.Series(dtype=str)), errors="coerce", utc=True)
                <= (end_dt - timedelta(days=7))
            ).sum()
        ) if len(exposure_df) else 0,
        "represented_teachers": int(exposure_df.get("teacher_id", pd.Series(dtype=str)).astype(str).replace("", pd.NA).dropna().nunique()),
        "represented_students": int(exposure_df.get("student_id", pd.Series(dtype=str)).astype(str).replace("", pd.NA).dropna().nunique()),
        "represented_resources": int(exposure_df.get("resource_id", pd.Series(dtype=str)).astype(str).replace("", pd.NA).dropna().nunique()),
        "events_without_exposures": int(events_without_exposures),
        "duplicate_idempotency_signatures": int(duplicate_signatures),
        "repeated_legitimate_exposures": int(repeated_exposures),
        "telemetry_freshness_hours": telemetry_freshness_hours,
        "date_range": {"start": start_iso, "end": end_iso},
    }
    surface_rows = sorted(surface_rows, key=lambda row: (-int(row.get("exposures") or 0), _clean_text(row.get("surface"))))
    duration_ms = round((time.perf_counter() - started) * 1000.0, 2)
    return {
        "summary": summary,
        "by_surface": surface_rows,
        "diagnostics": {
            "query_duration_ms": duration_ms,
            "rows_fetched": int(len(exposure_rows) + len(event_rows)),
            "cache_scope": f"{window_days}_days",
        },
    }


@st.cache_data(ttl=120, show_spinner=False)
def get_intelligence_component_portfolio(cache_bust: str = "") -> list[dict[str, Any]]:
    validated_run = get_latest_validated_run_summary(experiment_id=APPROVED_EXPERIMENT_ID, cache_bust=cache_bust)
    rows: list[dict[str, Any]] = []
    known_component_ids = {str(item.get("component_id") or "") for item in COMPONENT_BLUEPRINT}
    for item in COMPONENT_BLUEPRINT:
        row = dict(item)
        if row["component_id"] == "assigned_resource_open_within_7d":
            row["validated_run_id"] = _clean_text(validated_run.get("run_id"))
            row["validated_evidence_status"] = _run_evidence_level(validated_run)
            if validated_run:
                row["relevant_rows"] = int(validated_run.get("included_row_count") or row["relevant_rows"])
                row["teachers_represented"] = int(validated_run.get("teachers_represented") or row["teachers_represented"])
                row["students_represented"] = int(validated_run.get("students_represented") or 0)
                row["resources_represented"] = int(validated_run.get("resources_represented") or 0)
                row["date_coverage"] = f"{_clean_text(validated_run.get('source_start_at')) or 'n/a'} to {_clean_text(validated_run.get('source_end_at')) or 'n/a'}"
                row["evidence_verdict"] = _clean_text(validated_run.get("evidence_verdict"))
                row["primary_metric_leader"] = _clean_text(validated_run.get("primary_metric_leader"))
        rows.append(row)
    for experiment in list_experiment_catalog(cache_bust=cache_bust):
        experiment_id = _clean_text(experiment.get("experiment_id"))
        if not experiment_id or experiment_id in known_component_ids:
            continue
        latest_validated = dict(experiment.get("latest_validated_run") or {})
        rows.append(
            {
                "component_id": experiment_id,
                "name": _clean_text(experiment.get("name")) or experiment_id,
                "business_question": _clean_text(experiment.get("business_question")) or "Experiment business question not documented yet.",
                "decision_supported": "Whether this supervised experiment is credible enough to influence future product decisions.",
                "component_type": "supervised_experiment",
                "operational_status": "offline_evaluation",
                "data_maturity": "validated_evidence_ready" if latest_validated else "collecting_data",
                "evidence_maturity": _run_evidence_level(latest_validated),
                "production_use": "Experiment registry visibility only until a dedicated workflow is integrated.",
                "limitation": "This experiment was discovered from the registry and still needs dedicated workflow wiring.",
                "recommended_next_action": _run_business_action(latest_validated),
                "product_surface": "Developer Workspace and Admin intelligence supervision.",
                "educational_value": "Extends Classio experiment governance to future supervised workflows.",
                "unit_of_analysis": _clean_text(experiment.get("unit_of_analysis")) or "Not documented yet.",
                "relevant_rows": int(latest_validated.get("included_row_count") or 0),
                "date_coverage": f"{_clean_text(latest_validated.get('source_start_at')) or 'n/a'} to {_clean_text(latest_validated.get('source_end_at')) or 'n/a'}",
                "teachers_represented": int(latest_validated.get("teachers_represented") or 0),
                "students_represented": int(latest_validated.get("students_represented") or 0),
                "resources_represented": int(latest_validated.get("resources_represented") or 0),
                "topics_represented": 0,
                "outcome_metric": _clean_text(experiment.get("primary_metric")) or "Not documented yet",
                "validated_run_id": _clean_text(latest_validated.get("run_id")),
                "validated_evidence_status": _run_evidence_level(latest_validated),
                "evidence_verdict": _clean_text(latest_validated.get("evidence_verdict")),
                "primary_metric_leader": _clean_text(latest_validated.get("primary_metric_leader")),
                "evidence_sources": ["services/ml_experiment_service.py", "services/eic_service.py"],
            }
        )
    return rows


@st.cache_data(ttl=30, show_spinner=False)
def list_validated_experiment_summaries(*, limit: int = 10, offset: int = 0, cache_bust: str = "", experiment_id: str | None = None) -> list[dict[str, Any]]:
    rows = _validated_run_rows(limit=limit, offset=offset, cache_bust=cache_bust, experiment_id=experiment_id)
    return [
        {
            **row,
            "evidence_level": _run_evidence_level(row),
            "recommended_business_action": _run_business_action(row),
            "robust_winner": "yes" if _clean_text(row.get("run_status")) == "VALIDATED_EXPLORATORY_RUN" else "no",
        }
        for row in rows
    ]


@st.cache_data(ttl=30, show_spinner=False)
def get_latest_validated_run_summary(*, cache_bust: str = "", experiment_id: str | None = None) -> dict[str, Any]:
    rows = list_validated_experiment_summaries(limit=1, cache_bust=cache_bust, experiment_id=experiment_id)
    return dict(rows[0]) if rows else {}


def get_component_business_detail(component_id: str, *, cache_bust: str = "") -> dict[str, Any]:
    components = get_intelligence_component_portfolio(cache_bust=cache_bust)
    component = next((row for row in components if row.get("component_id") == component_id), {})
    if not component:
        return {}
    if component.get("component_type") == "supervised_experiment":
        validated = get_latest_validated_run_summary(cache_bust=cache_bust, experiment_id=component_id)
        component["validated_run"] = validated
        component["available_reports"] = get_validated_report_downloads(_clean_text(validated.get("run_id")))
    return component


@st.cache_data(ttl=30, show_spinner=False)
def get_experiment_business_detail(run_id: str, *, cache_bust: str = "") -> dict[str, Any]:
    safe_run_id = _clean_text(run_id)
    if not safe_run_id:
        return {}
    runs = _validated_run_rows(limit=100, offset=0, cache_bust=cache_bust, experiment_id=None)
    run_row = next((row for row in runs if _clean_text(row.get("run_id")) == safe_run_id), {})
    if not run_row:
        return {}
    catalog_entry = next(
        (row for row in list_experiment_catalog(cache_bust=cache_bust) if _clean_text(row.get("experiment_id")) == _clean_text(run_row.get("experiment_id"))),
        {},
    )
    artifacts = _artifact_path_map(safe_run_id)
    run_summary = _read_json(artifacts.get("run_summary_json", Path("")))
    dataset_summary = _read_json(artifacts.get("dataset_summary_json", Path("")))
    model_rows = _read_csv_rows(artifacts.get("model_comparison_csv", Path("")), limit=12)
    review = run_summary.get("review") or {}
    evaluation = run_summary.get("evaluation") or {}
    return {
        **run_row,
        "business_question": _clean_text(catalog_entry.get("business_question")) or "Experiment business question not documented yet.",
        "experiment_label": _clean_text(catalog_entry.get("display_label")) or _clean_text(catalog_entry.get("name")),
        "evidence_level": _run_evidence_level(run_row),
        "recommended_business_action": _run_business_action(run_row),
        "robust_winner": "yes" if _clean_text(run_row.get("run_status")) == "VALIDATED_EXPLORATORY_RUN" else "no",
        "model_results": {
            "models_compared": model_rows,
            "dummy_baseline": next((row for row in model_rows if _clean_text(row.get("model_name")) == "DummyClassifier"), {}),
            "primary_metric_leader": _clean_text(run_row.get("primary_metric_leader") or evaluation.get("primary_metric_leader")),
            "best_thresholded_classifier": _clean_text(evaluation.get("best_thresholded_classifier")),
            "precision_recall_leader": _clean_text(evaluation.get("best_precision_recall_ranking")),
            "calibration_leader": _clean_text(evaluation.get("calibration_leader")),
            "overall_evidence_conclusion": _clean_text(run_row.get("evidence_verdict") or evaluation.get("overall_evidence_strength")),
            "robust_winner": "yes" if _clean_text(run_row.get("run_status")) == "VALIDATED_EXPLORATORY_RUN" else "no",
        },
        "limitations": list((review.get("label_reconciliation") or {}).get("limitations") or []),
        "dataset_summary": dataset_summary,
    }


@st.cache_data(ttl=30, show_spinner=False)
def get_validated_report_downloads(run_id: str, *, cache_bust: str = "") -> list[dict[str, Any]]:
    safe_run_id = _clean_text(run_id)
    if not safe_run_id:
        return []
    artifact_rows = list_run_artifacts(safe_run_id)
    artifact_map = {str(row.get("artifact_type") or ""): dict(row) for row in artifact_rows}
    report_specs = [
        ("executive_report", "findings_interpretation_report_md", "markdown", False),
        ("academic_report", "findings_interpretation_report_md", "markdown", False),
        ("model_comparison", "model_comparison_csv", "csv", False),
        ("feature_audit", "feature_audit_csv", "csv", False),
        ("dataset_summary", "dataset_summary_json", "json", False),
        ("run_summary", "run_summary_json", "json", False),
        ("technical_report", "technical_report_md", "markdown", True),
    ]
    downloads: list[dict[str, Any]] = []
    for report_id, artifact_type, file_kind, technical_only in report_specs:
        artifact = artifact_map.get(artifact_type) or (
            artifact_map.get("academic_report_md") if artifact_type == "findings_interpretation_report_md" else {}
        ) or {}
        storage_text = _clean_text(artifact.get("storage_path"))
        if not storage_text:
            continue
        storage_path = Path(storage_text)
        if not storage_path.exists():
            continue
        if technical_only and not has_capability(CAPABILITY_VIEW_TECHNICAL_ARTIFACTS):
            continue
        downloads.append(
            {
                "report_id": report_id,
                "artifact_type": artifact_type,
                "file_kind": file_kind,
                "file_name": storage_path.name,
                "content_type": _clean_text(artifact.get("content_type")) or "application/octet-stream",
                "size_bytes": int(artifact.get("size_bytes") or storage_path.stat().st_size),
                "path": str(storage_path),
                "technical_only": technical_only,
            }
        )
    return downloads


@st.cache_data(ttl=30, show_spinner=False)
def get_academic_evidence_summary(run_id: str, *, cache_bust: str = "") -> dict[str, Any]:
    business_detail = get_experiment_business_detail(run_id, cache_bust=cache_bust)
    if not business_detail:
        return {}
    safe_run_id = _clean_text(run_id)
    artifacts = _artifact_path_map(safe_run_id)
    dataset_summary = _read_json(artifacts.get("dataset_summary_json", Path("")))
    run_summary = _read_json(artifacts.get("run_summary_json", Path("")))
    model_rows = _read_csv_rows(artifacts.get("model_comparison_csv", Path("")), limit=25)
    if _clean_text(business_detail.get("run_status")) not in FINAL_VALIDATED_RUN_STATES:
        return {
            "run_id": safe_run_id,
            "is_final": False,
            "validation_status": _clean_text(business_detail.get("run_status")),
        }
    evaluation = run_summary.get("evaluation") or {}
    total_labels = int(business_detail.get("included_row_count") or 0)
    positive = int(business_detail.get("positive_label_count") or 0)
    negative = int(business_detail.get("negative_label_count") or 0)
    experiment_id = _clean_text(business_detail.get("experiment_id"))
    if experiment_id == "student_recommendation_open_within_7d":
        target_definition = "opened_within_7d derived from recommendation shown_at with downstream opened events inside a seven-day window."
        unit_of_analysis = "One optional student recommendation exposure."
        data_sources = ["resource_exposures", "resource_exposure_events", "practice_sessions", "worksheets", "quick_exams", "videos"]
        future_improvements = [
            "Broaden repeated telemetry coverage across student surfaces",
            "Collect more mature labels across more students",
            "Compare repeated validated runs before any live ranking replacement",
        ]
    else:
        target_definition = "opened_within_7d derived from teacher_assignments.assigned_at with opened_at/viewed_at inside a seven-day window."
        unit_of_analysis = "One teacher assignment representing one assigned-resource exposure."
        data_sources = ["teacher_assignments", "teacher_assignment_attempts", "practice_sessions", "resource_exposures", "resource_exposure_events"]
        future_improvements = [
            "Broaden teacher coverage",
            "Continue collecting mature labels",
            "Improve telemetry coverage for related recommendation surfaces",
        ]
    return {
        "run_id": safe_run_id,
        "dataset_fingerprint": _clean_text(business_detail.get("dataset_fingerprint")),
        "experiment_id": _clean_text(business_detail.get("experiment_id")),
        "experiment_label": _clean_text(business_detail.get("experiment_label")),
        "is_final": True,
        "validation_status": _clean_text(business_detail.get("run_status")),
        "company_context": "Classio is evaluating educational intelligence systems that support teaching, learning, and resource recommendation.",
        "business_problem": _clean_text(business_detail.get("business_question")) or "Experiment business question not documented yet.",
        "smart_objective": "Build credible evidence for a supervised comparison without changing live recommendation ordering.",
        "target_definition": target_definition,
        "unit_of_analysis": unit_of_analysis,
        "data_sources": data_sources,
        "dataset_size": total_labels,
        "class_balance": round(float(positive) / max(positive + negative, 1), 4),
        "date_range": {
            "start": _clean_text(business_detail.get("source_start_at")),
            "end": _clean_text(business_detail.get("source_end_at")),
        },
        "train_holdout_split": {
            "chronological_cutoff": _clean_text(business_detail.get("chronological_cutoff") or evaluation.get("cutoff_timestamp")),
        },
        "evaluation_design": "Chronological train/holdout split using past-only features.",
        "models_compared": [_clean_text(row.get("model_name")) for row in model_rows if _clean_text(row.get("model_name"))],
        "metrics": ["roc_auc", "average_precision", "balanced_accuracy", "f1", "brier_score", "log_loss"],
        "baseline": "DummyClassifier",
        "selected_metric_leader": _clean_text(business_detail.get("primary_metric_leader")),
        "overall_evidence_conclusion": _clean_text((business_detail.get("model_results") or {}).get("overall_evidence_conclusion")),
        "limitations": list(business_detail.get("limitations") or []),
        "future_improvements": future_improvements,
        "production_readiness_decision": "EXPLORATORY_ONLY" if int(business_detail.get("teachers_represented") or 0) <= 1 else "SHADOW_CANDIDATE",
    }


@st.cache_data(ttl=30, show_spinner=False)
def get_prioritized_intelligence_decisions(cache_bust: str = "") -> list[dict[str, Any]]:
    validated = get_latest_validated_run_summary(cache_bust=cache_bust, experiment_id=APPROVED_EXPERIMENT_ID)
    telemetry = get_business_telemetry_health(cache_bust=cache_bust)
    telemetry_summary = telemetry.get("summary") or {}
    decisions = [
        {
            "component_id": "student_recommendation_ranker",
            "urgency": "high",
            "responsible_area": "Data",
            "status": "open",
            "issue": "Optional recommendation outcomes remain sparse.",
            "evidence": "The supervised ML data audit found impressions are too sparse to reconstruct genuine negatives reliably.",
            "business_impact": "The student recommendation model cannot yet be validated credibly.",
            "recommended_action": "Continue collecting data",
        },
        {
            "component_id": "assigned_resource_open_within_7d",
            "urgency": "medium",
            "responsible_area": "Product",
            "status": "open",
            "issue": "The latest mature assignment-open labels represent limited teacher diversity.",
            "evidence": f"{int(validated.get('included_row_count') or 0)} mature labels and {int(validated.get('teachers_represented') or 0)} teacher(s) in the latest validated run." if validated else "No validated supervised run yet.",
            "business_impact": "Cross-teacher generalization remains unknown.",
            "recommended_action": "Reevaluate later" if validated else "Continue collecting data",
        },
        {
            "component_id": "recommendation_event_feedback_loop",
            "urgency": "medium",
            "responsible_area": "Engineering",
            "status": "open",
            "issue": "Telemetry has unmatched opens or incomplete outcome coverage.",
            "evidence": f"{int(telemetry_summary.get('unmatched_opens') or 0)} unmatched opens and {round(float(telemetry_summary.get('matched_open_coverage') or 0.0) * 100, 1)}% matched-open coverage in recent canonical telemetry.",
            "business_impact": "Exposure-to-outcome evidence remains weaker than needed for future supervised ranking.",
            "recommended_action": "Improve exposure matching",
        },
        {
            "component_id": "practice_mastery_aggregator",
            "urgency": "low",
            "responsible_area": "Teaching",
            "status": "maintain",
            "issue": "Practice mastery aggregation is deterministic and reliable.",
            "evidence": "The blueprint classifies this component as a production deterministic workflow.",
            "business_impact": "It already supports educational decisions directly.",
            "recommended_action": "Maintain current logic",
        },
    ]
    return decisions


@st.cache_data(ttl=30, show_spinner=False)
def get_intelligence_business_summary(cache_bust: str = "") -> dict[str, Any]:
    started = time.perf_counter()
    portfolio = get_intelligence_component_portfolio(cache_bust=cache_bust)
    validated = get_latest_validated_run_summary(cache_bust=cache_bust, experiment_id=APPROVED_EXPERIMENT_ID)
    telemetry = get_business_telemetry_health(cache_bust=cache_bust)
    telemetry_summary = telemetry.get("summary") or {}
    decisions = get_prioritized_intelligence_decisions(cache_bust=cache_bust)

    systems_operating = int(
        sum(1 for row in portfolio if _clean_text(row.get("operational_status")) in {"live", "production", "offline_evaluation", "experimental"})
    )
    systems_with_healthy_data = int(
        sum(1 for row in portfolio if _clean_text(row.get("data_maturity")) in {"healthy", "validated_evidence_ready"})
    )
    systems_collecting_labels = int(
        sum(1 for row in portfolio if _clean_text(row.get("data_maturity")) in {"collecting_data", "collecting_labels", "partial"})
    )
    systems_requiring_attention = int(
        sum(1 for row in portfolio if _clean_text(row.get("evidence_maturity")) in {"limited", "proxy_only"})
    )
    latest_run_label = _clean_text(validated.get("run_id")) or "none"
    latest_run_status = _run_evidence_level(validated)
    recommended_action = _run_business_action(validated, telemetry_summary)
    evidence_level = _run_evidence_level(validated)
    telemetry_status = _telemetry_status_from_counts(
        int(telemetry_summary.get("total_canonical_exposures") or 0),
        int(round(float(telemetry_summary.get("matched_open_coverage") or 0.0) * float(telemetry_summary.get("total_canonical_exposures") or 0))),
        int(telemetry_summary.get("unmatched_opens") or 0),
    )
    cards = [
        {
            "label": "systems_operating",
            "value": str(systems_operating),
            "interpretation": "Portfolio components currently operating across teaching, learning, telemetry, and evaluation.",
            "status": "healthy",
        },
        {
            "label": "systems_with_healthy_data",
            "value": str(systems_with_healthy_data),
            "interpretation": "Components with healthy direct data or validated label-ready evidence.",
            "status": "healthy" if systems_with_healthy_data else "attention",
        },
        {
            "label": "systems_collecting_labels",
            "value": str(systems_collecting_labels),
            "interpretation": "Components still collecting the evidence needed for stronger comparison or supervised learning.",
            "status": "collecting_data" if systems_collecting_labels else "not_available",
        },
        {
            "label": "latest_validated_experiment",
            "value": latest_run_label,
            "interpretation": "Latest validated supervised evidence available to the business.",
            "status": latest_run_status,
        },
        {
            "label": "evidence_level",
            "value": evidence_level,
            "interpretation": "Current strength of supervised evidence for the assignment-open university project.",
            "status": evidence_level,
        },
        {
            "label": "recommended_business_action",
            "value": recommended_action,
            "interpretation": "Most important next business action based on current evidence and telemetry.",
            "status": "attention" if recommended_action != "maintain_current_logic" else "healthy",
        },
        {
            "label": "telemetry_freshness",
            "value": "n/a" if telemetry_summary.get("telemetry_freshness_hours") is None else f"{telemetry_summary.get('telemetry_freshness_hours')}h",
            "interpretation": "Freshness of recent canonical exposure and outcome telemetry.",
            "status": telemetry_status,
        },
        {
            "label": "systems_requiring_attention",
            "value": str(systems_requiring_attention),
            "interpretation": "Components whose evidence or instrumentation still limits confident business decisions.",
            "status": "attention" if systems_requiring_attention else "healthy",
        },
    ]
    duration_ms = round((time.perf_counter() - started) * 1000.0, 2)
    return {
        "cards": cards,
        "latest_validated_run": validated,
        "telemetry_summary": telemetry_summary,
        "top_decision": decisions[0] if decisions else {},
        "diagnostics": {
            "query_duration_ms": duration_ms,
            "rows_fetched": int(len(portfolio) + len(telemetry.get("by_surface") or [])),
            "cache_scope": "business_summary",
        },
    }


@st.cache_data(ttl=30, show_spinner=False)
def get_evidence_trend(cache_bust: str = "") -> dict[str, Any]:
    runs = list_validated_experiment_summaries(limit=5, cache_bust=cache_bust, experiment_id=APPROVED_EXPERIMENT_ID)
    if len(runs) < 2:
        return {"available": False, "runs": runs}
    return {
        "available": True,
        "runs": runs,
        "observed_differences": {
            "mature_label_growth": int(runs[0].get("included_row_count") or 0) - int(runs[1].get("included_row_count") or 0),
            "teacher_coverage_change": int(runs[0].get("teachers_represented") or 0) - int(runs[1].get("teachers_represented") or 0),
            "positive_label_change": int(runs[0].get("positive_label_count") or 0) - int(runs[1].get("positive_label_count") or 0),
            "negative_label_change": int(runs[0].get("negative_label_count") or 0) - int(runs[1].get("negative_label_count") or 0),
        },
    }
