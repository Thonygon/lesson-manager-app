from __future__ import annotations

import json
from pathlib import Path
from typing import Any
import uuid

import pandas as pd

from helpers.assigned_resource_open_7d_eval import (
    _clean_text,
    _fetch_all_rows,
    _fetch_resource_rows,
    _iso,
    _json_safe,
    _parse_dt,
    _safe_float,
    _utc_now,
    build_assignment_dataset,
    build_label_audit,
    evaluate_models,
    freeze_anonymized_dataset,
)


FEATURE_SCHEMA_VERSION = "student_recommendation_open_7d.v1"
OBSERVATION_DAYS = 7
DEFAULT_OUTPUT_DIR = Path("reports") / "ml_architecture" / "student_recommendation_open_7d"
FROZEN_DATASET_FILENAME = "student_recommendation_open_7d_dataset_frozen.csv"
PREDICTIONS_FILENAME = "student_recommendation_open_7d_holdout_predictions.csv"
DATASET_SUMMARY_FILENAME = "student_recommendation_open_7d_dataset_summary.json"
FEATURE_AUDIT_FILENAME = "student_recommendation_open_7d_feature_audit.csv"
LABEL_AUDIT_FILENAME = "student_recommendation_open_7d_label_audit.csv"
MODEL_COMPARISON_FILENAME = "student_recommendation_open_7d_model_comparison.csv"
RUN_SUMMARY_FILENAME = "student_recommendation_open_7d_run_summary.json"
TECHNICAL_REPORT_FILENAME = "student_recommendation_open_7d_technical_report.md"
ACADEMIC_REPORT_FILENAME = "student_recommendation_open_7d_findings_interpretation_report.md"
TARGET_NAME = "opened_within_7d"

EXPOSURE_COLUMNS = ",".join(
    [
        "exposure_id",
        "teacher_id",
        "student_id",
        "viewer_user_id",
        "resource_id",
        "resource_type",
        "exposure_type",
        "surface",
        "position",
        "shown_at",
        "model_component_id",
        "heuristic_score",
        "learned_score",
        "final_score",
        "recommendation_bucket",
        "recommendation_focus_kind",
        "learning_program_assignment_id",
        "learning_program_topic_id",
        "context_json",
        "created_at",
    ]
)
EVENT_COLUMNS = ",".join(
    [
        "exposure_id",
        "event_type",
        "event_at",
        "score_pct",
        "outcome_json",
        "teacher_id",
        "student_id",
        "viewer_user_id",
        "created_at",
    ]
)
PRACTICE_SESSION_COLUMNS = ",".join(
    [
        "id",
        "user_id",
        "source_type",
        "source_id",
        "subject",
        "topic",
        "learner_stage",
        "level",
        "score_pct",
        "started_at",
        "completed_at",
        "created_at",
    ]
)
WORKSHEET_COLUMNS = ",".join(
    [
        "id",
        "subject",
        "topic",
        "learner_stage",
        "level_or_band",
        "worksheet_type",
        "plan_language",
        "student_material_language",
        "created_at",
        "status",
        "is_public",
        "title",
    ]
)
EXAM_COLUMNS = ",".join(
    [
        "id",
        "subject",
        "topic",
        "learner_stage",
        "level",
        "title",
        "created_at",
        "status",
        "is_public",
    ]
)
VIDEO_COLUMNS = ",".join(
    [
        "id",
        "subject",
        "custom_subject_name",
        "topic",
        "learner_stage",
        "level_or_band",
        "title",
        "created_at",
        "status",
        "is_public",
    ]
)


def _read_context_json(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    text = _clean_text(value)
    if not text:
        return {}
    try:
        payload = json.loads(text)
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(_json_safe(payload), indent=2, sort_keys=True), encoding="utf-8")


def _write_frame(path: Path, frame: pd.DataFrame) -> None:
    frame.to_csv(path, index=False)


def _render_technical_report(summary: dict[str, Any]) -> str:
    dataset = summary.get("dataset") or {}
    evaluation = summary.get("evaluation") or {}
    lines = [
        "# Student Recommendation Open Within 7 Days Technical Report",
        "",
        "Business question: Can Classio predict whether a student will open an optional recommendation within seven days of seeing it?",
        "",
        "Target construction:",
        "- `opened_within_7d = 1` when a recommendation exposure records an `opened` event within seven days of `shown_at`.",
        "- `opened_within_7d = 0` when the seven-day window closes without a qualifying `opened` event.",
        "- Rows with still-open observation windows are excluded from training and evaluation.",
        "",
        "Evidence sources:",
        "- `resource_exposures` for optional student recommendation impressions.",
        "- `resource_exposure_events` for downstream recommendation opens.",
        "- `practice_sessions` for student-history context.",
        "- resource metadata from `worksheets`, `quick_exams`, and `videos`.",
        "",
        "Dataset summary:",
        f"- extraction timestamp: {dataset.get('extracted_at')}",
        f"- source rows inspected: {dataset.get('source_row_count')}",
        f"- mature included rows: {dataset.get('included_row_count')}",
        f"- positives: {dataset.get('positive_count')}",
        f"- negatives: {dataset.get('negative_count')}",
        f"- excluded rows: {dataset.get('excluded_row_count')}",
        f"- students represented: {dataset.get('student_count')}",
        f"- surfaces represented: {dataset.get('surface_count')}",
        "",
        "Evaluation summary:",
        f"- chronological cutoff: {evaluation.get('cutoff_timestamp')}",
        f"- development rows: {evaluation.get('development_count')}",
        f"- holdout rows: {evaluation.get('holdout_count')}",
        f"- winning candidate: {evaluation.get('winner')}",
        f"- maturity verdict: {evaluation.get('maturity_verdict')}",
        "",
        "Limitations:",
    ]
    for item in evaluation.get("limitations") or ["No additional limitations recorded."]:
        lines.append(f"- {item}")
    return "\n".join(lines) + "\n"


def _render_academic_report(summary: dict[str, Any]) -> str:
    dataset = summary.get("dataset") or {}
    evaluation = summary.get("evaluation") or {}
    lines = [
        "# Student Recommendation Open Within 7 Days Academic Report",
        "",
        "## General Academic Purpose",
        "This document records a supervised-learning evaluation inside Classio for internal academic and product-learning purposes.",
        "",
        "## Research Question",
        "Can a classifier predict whether a student will open an optional recommendation within seven days, using only information available when the recommendation is shown?",
        "",
        "## Unit of Analysis",
        "One optional student recommendation exposure.",
        "",
        "## Outcome Definition",
        "The target is `opened_within_7d`, derived from recommendation `shown_at` timestamps and subsequent `opened` telemetry events inside a seven-day window.",
        "",
        "## Dataset",
        f"- extraction timestamp: {dataset.get('extracted_at')}",
        f"- included mature labels: {dataset.get('included_row_count')}",
        f"- positives: {dataset.get('positive_count')}",
        f"- negatives: {dataset.get('negative_count')}",
        f"- excluded rows: {dataset.get('excluded_row_count')}",
        f"- students represented: {dataset.get('student_count')}",
        f"- resources represented: {dataset.get('resource_count')}",
        "",
        "## Evaluation Design",
        f"- chronological holdout cutoff: {evaluation.get('cutoff_timestamp')}",
        f"- development rows: {evaluation.get('development_count')}",
        f"- holdout rows: {evaluation.get('holdout_count')}",
        "- comparisons remain exploratory until the evidence base broadens across usage contexts and repeated runs.",
        "",
        "## Result",
        f"- best evaluated candidate: {evaluation.get('winner')}",
        f"- maturity verdict: {evaluation.get('maturity_verdict')}",
        "",
        "## Validity Threats",
    ]
    for item in evaluation.get("limitations") or []:
        lines.append(f"- {item}")
    return "\n".join(lines) + "\n"


def _optional_recommendation_assignments(
    exposures: list[dict[str, Any]],
    events: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    event_map: dict[str, list[dict[str, Any]]] = {}
    for row in events:
        exposure_id = _clean_text(row.get("exposure_id"))
        if exposure_id:
            event_map.setdefault(exposure_id, []).append(dict(row))
    for rows in event_map.values():
        rows.sort(key=lambda item: _clean_text(item.get("event_at") or item.get("created_at")))

    assignments: list[dict[str, Any]] = []
    for idx, exposure in enumerate(
        sorted(
            exposures,
            key=lambda item: (
                _clean_text(item.get("shown_at") or item.get("created_at")),
                _clean_text(item.get("exposure_id")),
            ),
        ),
        start=1,
    ):
        context = _read_context_json(exposure.get("context_json"))
        exposure_id = _clean_text(exposure.get("exposure_id"))
        shown_at = _clean_text(exposure.get("shown_at") or exposure.get("created_at"))
        shown_dt = _parse_dt(shown_at)
        opened_at = ""
        completed_at = ""
        latest_event_at = shown_at
        status = "shown"
        for event in event_map.get(exposure_id, []):
            event_type = _clean_text(event.get("event_type")).lower()
            event_at = _clean_text(event.get("event_at") or event.get("created_at"))
            event_dt = _parse_dt(event_at)
            if event_dt and shown_dt and event_dt < shown_dt:
                continue
            if event_at and event_at > latest_event_at:
                latest_event_at = event_at
            if event_type == "opened" and not opened_at:
                opened_at = event_at
                status = "opened"
            elif event_type in {"completed", "accepted"} and not completed_at:
                completed_at = event_at
                status = event_type
        student_id = _clean_text(exposure.get("student_id") or exposure.get("viewer_user_id"))
        assignments.append(
            {
                "id": idx,
                "teacher_id": _clean_text(exposure.get("surface")) or "student_surface",
                "student_id": student_id,
                "assignment_type": _clean_text(exposure.get("resource_type")),
                "source_type": "optional_student_recommendation",
                "source_record_id": _clean_text(exposure.get("resource_id")),
                "subject_key": _clean_text(context.get("subject")),
                "subject_label": _clean_text(context.get("subject")),
                "topic": _clean_text(context.get("topic")),
                "status": status,
                "score_pct": None,
                "assigned_at": shown_at,
                "opened_at": opened_at,
                "viewed_at": "",
                "submitted_at": "",
                "completed_at": completed_at,
                "created_at": shown_at,
                "updated_at": latest_event_at,
                "learning_program_assignment_id": exposure.get("learning_program_assignment_id"),
                "learning_program_topic_id": exposure.get("learning_program_topic_id"),
                "recommendation_bucket": _clean_text(exposure.get("recommendation_bucket")),
                "recommendation_focus_kind": _clean_text(exposure.get("recommendation_focus_kind")),
                "resource_exposure_id": exposure_id,
            }
        )
    return assignments


def extract_operational_snapshot(extraction_time: Any | None = None) -> dict[str, Any]:
    extracted_at = extraction_time or _utc_now()
    exposures = [
        row
        for row in _fetch_all_rows("resource_exposures", EXPOSURE_COLUMNS)
        if _clean_text(row.get("exposure_type")) == "optional_student_recommendation"
    ]
    events = _fetch_all_rows("resource_exposure_events", EVENT_COLUMNS)
    assignments = _optional_recommendation_assignments(exposures, events)
    practice_rows = _fetch_all_rows("practice_sessions", PRACTICE_SESSION_COLUMNS)

    worksheet_ids = sorted(
        {
            int(row.get("source_record_id"))
            for row in assignments
            if _clean_text(row.get("assignment_type")) == "worksheet" and _clean_text(row.get("source_record_id")).isdigit()
        }
    )
    exam_ids = sorted(
        {
            int(row.get("source_record_id"))
            for row in assignments
            if _clean_text(row.get("assignment_type")) == "exam" and _clean_text(row.get("source_record_id")).isdigit()
        }
    )
    video_ids = sorted(
        {
            int(row.get("source_record_id"))
            for row in assignments
            if _clean_text(row.get("assignment_type")) == "video" and _clean_text(row.get("source_record_id")).isdigit()
        }
    )
    resources = {
        "worksheet": _fetch_resource_rows("worksheets", WORKSHEET_COLUMNS, worksheet_ids),
        "exam": _fetch_resource_rows("quick_exams", EXAM_COLUMNS, exam_ids),
        "video": _fetch_resource_rows("videos", VIDEO_COLUMNS, video_ids),
    }
    return {
        "extracted_at": _iso(extracted_at),
        "assignments": assignments,
        "practice_sessions": practice_rows,
        "resources": resources,
    }


def generate_student_recommendation_open_7d_evaluation(
    output_dir: Path | str = DEFAULT_OUTPUT_DIR,
    *,
    run_id: str | None = None,
) -> dict[str, Any]:
    resolved_output_dir = Path(output_dir)
    resolved_output_dir.mkdir(parents=True, exist_ok=True)
    extraction_time = _utc_now()
    safe_run_id = str(run_id or uuid.uuid4().hex[:12]).strip()
    snapshot = extract_operational_snapshot(extraction_time=extraction_time)
    dataset_df, dataset_diag = build_assignment_dataset(snapshot, extraction_time=extraction_time)
    dataset_path, fingerprint = freeze_anonymized_dataset(dataset_df, run_id=safe_run_id, output_dir=resolved_output_dir)
    mature_df = dataset_df[dataset_df["label_status"] == "included"].copy()
    dataset_summary = {
        "run_id": safe_run_id,
        "feature_schema_version": FEATURE_SCHEMA_VERSION,
        "target_version": "opened_within_7d_v1",
        "extracted_at": _iso(extraction_time),
        "data_fingerprint": fingerprint,
        "frozen_dataset_path": str(dataset_path),
        **dataset_diag,
        "positive_count": int((mature_df[TARGET_NAME] == 1).sum()) if not mature_df.empty else 0,
        "negative_count": int((mature_df[TARGET_NAME] == 0).sum()) if not mature_df.empty else 0,
        "teacher_count": int(mature_df["teacher_id"].replace("", pd.NA).nunique()) if not mature_df.empty else 0,
        "student_count": int(mature_df["student_id"].replace("", pd.NA).nunique()) if not mature_df.empty else 0,
        "resource_count": int(mature_df["resource_key"].replace("", pd.NA).nunique()) if not mature_df.empty else 0,
        "surface_count": int(mature_df["teacher_id"].replace("", pd.NA).nunique()) if not mature_df.empty else 0,
        "telemetry_source": "resource_exposures/resource_exposure_events",
    }
    evaluation = evaluate_models(dataset_df)
    run_summary = {
        "run_id": safe_run_id,
        "feature_schema_version": FEATURE_SCHEMA_VERSION,
        "generated_at": _iso(extraction_time),
        "dataset": dataset_summary,
        "evaluation": {
            key: value
            for key, value in evaluation.items()
            if key not in {"feature_audit", "predictions", "model_rows", "feature_importance_rows"}
        },
        "review": {},
    }

    _write_json(resolved_output_dir / DATASET_SUMMARY_FILENAME, dataset_summary)
    _write_frame(resolved_output_dir / LABEL_AUDIT_FILENAME, build_label_audit(dataset_df))
    _write_frame(resolved_output_dir / FEATURE_AUDIT_FILENAME, pd.DataFrame(evaluation.get("feature_audit") or []))
    _write_frame(resolved_output_dir / MODEL_COMPARISON_FILENAME, pd.DataFrame(evaluation.get("model_rows") or []))
    _write_frame(resolved_output_dir / PREDICTIONS_FILENAME, pd.DataFrame(evaluation.get("predictions") or []))
    _write_json(resolved_output_dir / RUN_SUMMARY_FILENAME, run_summary)
    (resolved_output_dir / TECHNICAL_REPORT_FILENAME).write_text(_render_technical_report(run_summary), encoding="utf-8")
    (resolved_output_dir / ACADEMIC_REPORT_FILENAME).write_text(_render_academic_report(run_summary), encoding="utf-8")

    return {
        "run_id": safe_run_id,
        "dataset": dataset_summary,
        "evaluation": evaluation,
        "run_summary": run_summary,
    }
