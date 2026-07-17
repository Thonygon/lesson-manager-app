from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import json
import math
from pathlib import Path
import time
from typing import Any
import uuid

import numpy as np
import pandas as pd


FEATURE_SCHEMA_VERSION = "assigned_resource_open_7d.v1"
OBSERVATION_DAYS = 7
DEFAULT_SEED = 20260716
DEFAULT_OUTPUT_DIR = Path("reports") / "ml_architecture" / "assigned_resource_open_7d"
FROZEN_DATASET_FILENAME = "assigned_resource_open_7d_dataset_frozen.csv"
PREDICTIONS_FILENAME = "assigned_resource_open_7d_holdout_predictions.csv"
DATASET_SUMMARY_FILENAME = "assigned_resource_open_7d_dataset_summary.json"
FEATURE_AUDIT_FILENAME = "assigned_resource_open_7d_feature_audit.csv"
LABEL_AUDIT_FILENAME = "assigned_resource_open_7d_label_audit.csv"
MODEL_COMPARISON_FILENAME = "assigned_resource_open_7d_model_comparison.csv"
RUN_SUMMARY_FILENAME = "assigned_resource_open_7d_run_summary.json"
TECHNICAL_REPORT_FILENAME = "assigned_resource_open_7d_technical_report.md"
ACADEMIC_REPORT_FILENAME = "assigned_resource_open_7d_findings_interpretation_report.md"

TARGET_NAME = "opened_within_7d"
MATURITY_VERDICTS = (
    "INSUFFICIENT_DATA",
    "EXPLORATORY_ONLY",
    "CANDIDATE_FOR_SHADOW_TESTING",
    "CANDIDATE_FOR_CONTROLLED_PILOT",
)

FORBIDDEN_FEATURE_TOKENS = (
    "opened_at",
    "viewed_at",
    "submitted_at",
    "completed_at",
    "final_status",
    "score_pct_current_assignment",
    "attempts_after_assignment",
    "reviews_after_assignment",
    "canonical_outcome_events",
    "ml_score",
    "ml_blend_weight",
    "future_",
    TARGET_NAME,
)

RAW_ASSIGNMENT_COLUMNS = ",".join(
    [
        "id",
        "teacher_id",
        "student_id",
        "assignment_type",
        "source_type",
        "source_record_id",
        "subject_key",
        "subject_label",
        "topic",
        "status",
        "score_pct",
        "assigned_at",
        "opened_at",
        "viewed_at",
        "submitted_at",
        "completed_at",
        "created_at",
        "updated_at",
        "learning_program_assignment_id",
        "learning_program_topic_id",
        "recommendation_bucket",
        "recommendation_focus_kind",
        "resource_exposure_id",
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

CATEGORICAL_FEATURES = [
    "assignment_type",
    "source_type",
    "subject_key",
    "topic",
    "assignment_weekday",
    "assignment_hour_bucket",
    "resource_topic",
    "resource_type",
    "resource_learner_stage",
    "resource_level",
    "resource_language",
    "recommendation_bucket",
    "recommendation_focus_kind",
]
NUMERIC_FEATURES = [
    "assignment_hour",
    "assignment_is_weekend",
    "is_program_assignment",
    "student_stage_known",
    "student_level_known",
    "resource_title_length",
    "resource_public_flag",
    "prior_student_mature_assignment_count",
    "prior_student_assignment_open_rate",
    "prior_student_completion_rate",
    "prior_student_practice_session_count",
    "prior_student_avg_practice_score",
    "prior_days_since_student_activity",
    "prior_teacher_mature_assignment_count",
    "prior_teacher_assignment_open_rate",
    "prior_resource_mature_assignment_count",
    "prior_resource_open_rate",
]
REDUCED_FEATURES = [
    "assignment_type",
    "subject_key",
    "assignment_weekday",
    "assignment_hour_bucket",
    "is_program_assignment",
    "prior_student_assignment_open_rate",
    "prior_student_practice_session_count",
    "prior_teacher_assignment_open_rate",
    "prior_resource_open_rate",
]


@dataclass
class LabelOutcome:
    label: int | None
    status: str
    exclusion_reason: str | None
    qualifying_event: str
    qualifying_open_at: str
    assigned_at: str
    observation_window_closed_at: str


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _json_safe(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, bool)):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(item) for item in value]
    if isinstance(value, (datetime, pd.Timestamp)):
        return value.isoformat()
    return str(value)


def _parse_dt(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _iso(value: datetime | None) -> str:
    return value.astimezone(timezone.utc).isoformat() if value else ""


def _clean_text(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def _safe_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        number = float(value)
    except Exception:
        return None
    return number if math.isfinite(number) else None


def _hash_identifier(scope_salt: str, kind: str, raw_value: Any) -> str:
    text = f"{scope_salt}|{kind}|{raw_value}"
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    return digest[:16]


def build_open_within_7d_label(row: dict, extraction_time: datetime | None = None) -> LabelOutcome:
    extraction_dt = extraction_time or _utc_now()
    assigned_dt = _parse_dt(row.get("assigned_at") or row.get("created_at"))
    if assigned_dt is None:
        return LabelOutcome(
            label=None,
            status="invalid",
            exclusion_reason="missing_assigned_at",
            qualifying_event="",
            qualifying_open_at="",
            assigned_at="",
            observation_window_closed_at="",
        )
    observation_close = assigned_dt + timedelta(days=OBSERVATION_DAYS)
    candidate_events = [
        ("opened_at", _parse_dt(row.get("opened_at"))),
        ("viewed_at", _parse_dt(row.get("viewed_at"))),
    ]
    qualifying_name = ""
    qualifying_dt = None
    invalid_name = ""
    invalid_dt = None
    for event_name, event_dt in candidate_events:
        if event_dt is None:
            continue
        if event_dt < assigned_dt:
            if invalid_dt is None or event_dt < invalid_dt:
                invalid_name = event_name
                invalid_dt = event_dt
            continue
        if event_dt <= observation_close and (qualifying_dt is None or event_dt < qualifying_dt):
            qualifying_name = event_name
            qualifying_dt = event_dt
    if qualifying_dt is not None:
        return LabelOutcome(
            label=1,
            status="included",
            exclusion_reason=None,
            qualifying_event=qualifying_name,
            qualifying_open_at=_iso(qualifying_dt),
            assigned_at=_iso(assigned_dt),
            observation_window_closed_at=_iso(observation_close),
        )
    if extraction_dt < observation_close:
        return LabelOutcome(
            label=None,
            status="right_censored",
            exclusion_reason="observation_window_open",
            qualifying_event="",
            qualifying_open_at="",
            assigned_at=_iso(assigned_dt),
            observation_window_closed_at=_iso(observation_close),
        )
    if invalid_dt is not None:
        return LabelOutcome(
            label=None,
            status="invalid",
            exclusion_reason=f"{invalid_name}_before_assigned_at",
            qualifying_event="",
            qualifying_open_at="",
            assigned_at=_iso(assigned_dt),
            observation_window_closed_at=_iso(observation_close),
        )
    return LabelOutcome(
        label=0,
        status="included",
        exclusion_reason=None,
        qualifying_event="",
        qualifying_open_at="",
        assigned_at=_iso(assigned_dt),
        observation_window_closed_at=_iso(observation_close),
    )


def _fetch_all_rows(table_name: str, columns: str, *, page_size: int = 1000) -> list[dict]:
    from core.database import get_sb

    sb = get_sb()
    rows: list[dict] = []
    start = 0
    while True:
        result = (
            sb.table(table_name)
            .select(columns)
            .range(start, start + page_size - 1)
            .execute()
        )
        page_rows = getattr(result, "data", None) or []
        if not page_rows:
            break
        rows.extend(page_rows)
        if len(page_rows) < page_size:
            break
        start += page_size
    return rows


def _fetch_resource_rows(table_name: str, columns: str, ids: list[int]) -> dict[str, dict]:
    from core.database import get_sb

    if not ids:
        return {}
    sb = get_sb()
    resource_map: dict[str, dict] = {}
    chunk_size = 100
    for chunk_start in range(0, len(ids), chunk_size):
        chunk = ids[chunk_start : chunk_start + chunk_size]
        result = (
            sb.table(table_name)
            .select(columns)
            .in_("id", chunk)
            .execute()
        )
        for row in getattr(result, "data", None) or []:
            resource_map[str(row.get("id"))] = row
    return resource_map


def extract_operational_snapshot(extraction_time: datetime | None = None) -> dict[str, Any]:
    extracted_at = extraction_time or _utc_now()
    assignment_rows = _fetch_all_rows("teacher_assignments", RAW_ASSIGNMENT_COLUMNS)
    practice_rows = _fetch_all_rows("practice_sessions", PRACTICE_SESSION_COLUMNS)

    worksheet_ids = sorted(
        {
            int(row.get("source_record_id"))
            for row in assignment_rows
            if str(row.get("assignment_type") or "").strip() == "worksheet"
            and str(row.get("source_record_id") or "").strip().isdigit()
        }
    )
    exam_ids = sorted(
        {
            int(row.get("source_record_id"))
            for row in assignment_rows
            if str(row.get("assignment_type") or "").strip() == "exam"
            and str(row.get("source_record_id") or "").strip().isdigit()
        }
    )
    video_ids = sorted(
        {
            int(row.get("source_record_id"))
            for row in assignment_rows
            if str(row.get("assignment_type") or "").strip() == "video"
            and str(row.get("source_record_id") or "").strip().isdigit()
        }
    )
    resources = {
        "worksheet": _fetch_resource_rows("worksheets", WORKSHEET_COLUMNS, worksheet_ids),
        "exam": _fetch_resource_rows("quick_exams", EXAM_COLUMNS, exam_ids),
        "video": _fetch_resource_rows("videos", VIDEO_COLUMNS, video_ids),
    }
    return {
        "extracted_at": _iso(extracted_at),
        "assignments": assignment_rows,
        "practice_sessions": practice_rows,
        "resources": resources,
    }


def _resource_metadata_for_assignment(row: dict, resources: dict[str, dict[str, dict]]) -> dict[str, Any]:
    assignment_type = str(row.get("assignment_type") or "").strip().lower()
    resource_id = str(row.get("source_record_id") or "").strip()
    resource_row = (resources.get(assignment_type) or {}).get(resource_id) or {}
    if assignment_type == "worksheet":
        resource_level = _clean_text(resource_row.get("level_or_band"))
        resource_language = _clean_text(resource_row.get("student_material_language") or resource_row.get("plan_language"))
        resource_type = _clean_text(resource_row.get("worksheet_type")) or "worksheet"
        subject_value = _clean_text(resource_row.get("subject"))
    elif assignment_type == "exam":
        resource_level = _clean_text(resource_row.get("level"))
        resource_language = ""
        resource_type = "exam"
        subject_value = _clean_text(resource_row.get("subject"))
    elif assignment_type == "video":
        resource_level = _clean_text(resource_row.get("level_or_band"))
        resource_language = ""
        resource_type = "video"
        subject_value = _clean_text(resource_row.get("subject") or resource_row.get("custom_subject_name"))
    else:
        resource_level = ""
        resource_language = ""
        resource_type = assignment_type or _clean_text(row.get("source_type")) or "resource"
        subject_value = ""
    return {
        "resource_subject": subject_value,
        "resource_topic": _clean_text(resource_row.get("topic")),
        "resource_learner_stage": _clean_text(resource_row.get("learner_stage")),
        "resource_level": resource_level,
        "resource_language": resource_language,
        "resource_type": resource_type,
        "resource_public_flag": 1.0 if bool(resource_row.get("is_public")) else 0.0,
        "resource_title_length": float(len(_clean_text(resource_row.get("title")))),
        "resource_created_at": _clean_text(resource_row.get("created_at")),
    }


def _topic_value(row: dict, resource_meta: dict[str, Any]) -> str:
    return _clean_text(row.get("topic")) or _clean_text(resource_meta.get("resource_topic"))


def _build_practice_index(practice_rows: list[dict]) -> dict[str, list[dict]]:
    practice_by_student: dict[str, list[dict]] = {}
    for row in practice_rows:
        student_id = _clean_text(row.get("user_id"))
        if not student_id:
            continue
        enriched = dict(row)
        enriched["_activity_dt"] = _parse_dt(row.get("completed_at") or row.get("started_at") or row.get("created_at"))
        practice_by_student.setdefault(student_id, []).append(enriched)
    for rows in practice_by_student.values():
        rows.sort(key=lambda item: _iso(item.get("_activity_dt")))
    return practice_by_student


def _past_practice_rows(practice_index: dict[str, list[dict]], student_id: str, assigned_dt: datetime) -> list[dict]:
    return [
        row for row in (practice_index.get(student_id) or [])
        if row.get("_activity_dt") is not None and row["_activity_dt"] < assigned_dt
    ]


def _historical_feature_snapshot(history_rows: list[dict], current_assigned_dt: datetime) -> dict[str, float]:
    matured_history = [
        item for item in history_rows
        if item.get("_window_closed_dt") is not None and item["_window_closed_dt"] <= current_assigned_dt and item.get("label") in (0, 1)
    ]
    completed_history = [
        item for item in history_rows
        if item.get("_completed_dt") is not None and item["_completed_dt"] <= current_assigned_dt
    ]
    if matured_history:
        student_open_rate = float(sum(int(item["label"]) for item in matured_history)) / float(len(matured_history))
    else:
        student_open_rate = math.nan
    if completed_history:
        completion_rate = float(len(completed_history)) / float(len(matured_history) or len(history_rows) or 1)
    else:
        completion_rate = math.nan
    return {
        "prior_student_mature_assignment_count": float(len(matured_history)),
        "prior_student_assignment_open_rate": student_open_rate,
        "prior_student_completion_rate": completion_rate,
    }


def _choose_student_activity_timestamp(row: dict) -> datetime | None:
    candidates = [
        _parse_dt(row.get("opened_at")),
        _parse_dt(row.get("viewed_at")),
        _parse_dt(row.get("completed_at")),
        _parse_dt(row.get("assigned_at")),
        _parse_dt(row.get("created_at")),
    ]
    candidates = [item for item in candidates if item is not None]
    return max(candidates) if candidates else None


def build_assignment_dataset(snapshot: dict[str, Any], extraction_time: datetime | None = None) -> tuple[pd.DataFrame, dict[str, Any]]:
    extracted_at = extraction_time or _parse_dt(snapshot.get("extracted_at")) or _utc_now()
    resources = snapshot.get("resources") or {}
    assignments = list(snapshot.get("assignments") or [])
    practice_index = _build_practice_index(list(snapshot.get("practice_sessions") or []))
    assignments.sort(
        key=lambda row: (
            _iso(_parse_dt(row.get("assigned_at") or row.get("created_at"))),
            int(row.get("id") or 0),
        )
    )
    student_history: dict[str, list[dict]] = {}
    teacher_history: dict[str, list[dict]] = {}
    resource_history: dict[str, list[dict]] = {}
    rows: list[dict] = []
    earliest_dt = None
    latest_dt = None
    for row in assignments:
        row_id = int(row.get("id") or 0)
        student_id = _clean_text(row.get("student_id"))
        teacher_id = _clean_text(row.get("teacher_id"))
        assignment_type = _clean_text(row.get("assignment_type"))
        source_record_id = _clean_text(row.get("source_record_id"))
        resource_key = f"{assignment_type}:{source_record_id}"
        label_outcome = build_open_within_7d_label(row, extraction_time=extracted_at)
        assigned_dt = _parse_dt(label_outcome.assigned_at)
        if assigned_dt is not None:
            earliest_dt = assigned_dt if earliest_dt is None else min(earliest_dt, assigned_dt)
            latest_dt = assigned_dt if latest_dt is None else max(latest_dt, assigned_dt)
        resource_meta = _resource_metadata_for_assignment(row, resources)
        student_rows = student_history.get(student_id, [])
        teacher_rows = teacher_history.get(teacher_id, [])
        resource_rows = resource_history.get(resource_key, [])
        student_history_features = _historical_feature_snapshot(student_rows, assigned_dt) if assigned_dt else _historical_feature_snapshot([], extracted_at)
        teacher_history_features = _historical_feature_snapshot(teacher_rows, assigned_dt) if assigned_dt else _historical_feature_snapshot([], extracted_at)
        resource_history_features = _historical_feature_snapshot(resource_rows, assigned_dt) if assigned_dt else _historical_feature_snapshot([], extracted_at)
        previous_practice = _past_practice_rows(practice_index, student_id, assigned_dt) if assigned_dt else []
        previous_scores = [_safe_float(item.get("score_pct")) for item in previous_practice]
        usable_scores = [score for score in previous_scores if score is not None]
        latest_activity_candidates = [item.get("_activity_dt") for item in previous_practice if item.get("_activity_dt") is not None]
        latest_assignment_activity = [
            _choose_student_activity_timestamp(item) for item in student_rows if _choose_student_activity_timestamp(item) is not None
        ]
        latest_activity = None
        combined_activity = latest_activity_candidates + latest_assignment_activity
        if combined_activity:
            latest_activity = max(combined_activity)
        days_since_activity = math.nan
        if assigned_dt is not None and latest_activity is not None:
            days_since_activity = (assigned_dt - latest_activity).total_seconds() / 86400.0
        topic_value = _topic_value(row, resource_meta)
        feature_row = {
            "assignment_id": row_id,
            "teacher_id": teacher_id,
            "student_id": student_id,
            "resource_key": resource_key,
            "assignment_type": assignment_type,
            "source_type": _clean_text(row.get("source_type")),
            "source_record_id": source_record_id,
            "subject_key": _clean_text(row.get("subject_key") or row.get("subject_label") or resource_meta.get("resource_subject")),
            "topic": topic_value,
            "status": _clean_text(row.get("status")),
            "assigned_at": label_outcome.assigned_at,
            "opened_at": _clean_text(row.get("opened_at")),
            "viewed_at": _clean_text(row.get("viewed_at")),
            "completed_at": _clean_text(row.get("completed_at")),
            "submitted_at": _clean_text(row.get("submitted_at")),
            "observation_window_closed_at": label_outcome.observation_window_closed_at,
            "label_status": label_outcome.status,
            "label_exclusion_reason": label_outcome.exclusion_reason or "",
            "qualifying_event": label_outcome.qualifying_event,
            "qualifying_open_at": label_outcome.qualifying_open_at,
            TARGET_NAME: label_outcome.label,
            "assignment_hour": float(assigned_dt.hour) if assigned_dt else math.nan,
            "assignment_weekday": assigned_dt.strftime("%A") if assigned_dt else "",
            "assignment_hour_bucket": f"{assigned_dt.hour:02d}:00" if assigned_dt else "",
            "assignment_is_weekend": 1.0 if assigned_dt and assigned_dt.weekday() >= 5 else 0.0,
            "is_program_assignment": 1.0 if int(row.get("learning_program_assignment_id") or 0) > 0 else 0.0,
            "recommendation_bucket": _clean_text(row.get("recommendation_bucket")),
            "recommendation_focus_kind": _clean_text(row.get("recommendation_focus_kind")),
            "student_stage_known": 1.0 if _clean_text(resource_meta.get("resource_learner_stage")) else 0.0,
            "student_level_known": 1.0 if _clean_text(resource_meta.get("resource_level")) else 0.0,
            **resource_meta,
            **student_history_features,
            "prior_student_practice_session_count": float(len(previous_practice)),
            "prior_student_avg_practice_score": float(sum(usable_scores) / len(usable_scores)) if usable_scores else math.nan,
            "prior_days_since_student_activity": days_since_activity,
            "prior_teacher_mature_assignment_count": teacher_history_features["prior_student_mature_assignment_count"],
            "prior_teacher_assignment_open_rate": teacher_history_features["prior_student_assignment_open_rate"],
            "prior_resource_mature_assignment_count": resource_history_features["prior_student_mature_assignment_count"],
            "prior_resource_open_rate": resource_history_features["prior_student_assignment_open_rate"],
        }
        rows.append(feature_row)
        history_row = {
            "id": row_id,
            "assigned_at": label_outcome.assigned_at,
            "opened_at": _clean_text(row.get("opened_at")),
            "viewed_at": _clean_text(row.get("viewed_at")),
            "completed_at": _clean_text(row.get("completed_at")),
            "created_at": _clean_text(row.get("created_at")),
            "label": label_outcome.label,
            "_window_closed_dt": _parse_dt(label_outcome.observation_window_closed_at),
            "_completed_dt": _parse_dt(row.get("completed_at")),
        }
        student_history.setdefault(student_id, []).append(history_row)
        teacher_history.setdefault(teacher_id, []).append(history_row)
        resource_history.setdefault(resource_key, []).append(history_row)
    df = pd.DataFrame(rows)
    diagnostics = {
        "source_row_count": int(len(assignments)),
        "included_row_count": int((df["label_status"] == "included").sum()) if not df.empty else 0,
        "excluded_row_count": int((df["label_status"] != "included").sum()) if not df.empty else 0,
        "date_range": {
            "assigned_at_min": _iso(earliest_dt),
            "assigned_at_max": _iso(latest_dt),
        },
        "exclusion_reasons": {
            str(key): int(value)
            for key, value in (df["label_exclusion_reason"].replace("", "included").value_counts().to_dict().items() if not df.empty else [])
        },
    }
    return df, diagnostics


def validate_feature_eligibility(feature_names: list[str]) -> list[str]:
    violations = []
    for feature_name in feature_names:
        lowered = str(feature_name or "").strip().lower()
        if any(token in lowered for token in FORBIDDEN_FEATURE_TOKENS):
            violations.append(feature_name)
    return violations


def _series_missing_mask(series: pd.Series) -> pd.Series:
    if series.dtype == object:
        return series.isna() | series.astype(str).str.strip().eq("")
    return series.isna()


def active_features_for_training_frame(frame: pd.DataFrame, feature_names: list[str]) -> tuple[list[str], dict[str, str]]:
    active: list[str] = []
    dropped: dict[str, str] = {}
    for feature_name in feature_names:
        if feature_name not in frame.columns:
            dropped[feature_name] = "feature_missing_from_frame"
            continue
        series = frame[feature_name]
        if bool(_series_missing_mask(series).all()):
            dropped[feature_name] = "fully_missing_in_training_frame"
            continue
        active.append(feature_name)
    return active, dropped


def build_feature_audit(df: pd.DataFrame, feature_names: list[str]) -> pd.DataFrame:
    source_map = {
        "assignment_type": ("teacher_assignments", "assignment_type"),
        "source_type": ("teacher_assignments", "source_type"),
        "subject_key": ("teacher_assignments", "subject_key"),
        "topic": ("teacher_assignments", "topic"),
        "assignment_weekday": ("teacher_assignments", "assigned_at"),
        "assignment_hour": ("teacher_assignments", "assigned_at"),
        "assignment_hour_bucket": ("teacher_assignments", "assigned_at"),
        "assignment_is_weekend": ("teacher_assignments", "assigned_at"),
        "is_program_assignment": ("teacher_assignments", "learning_program_assignment_id"),
        "recommendation_bucket": ("teacher_assignments", "recommendation_bucket"),
        "recommendation_focus_kind": ("teacher_assignments", "recommendation_focus_kind"),
        "student_stage_known": ("worksheets/quick_exams/videos", "learner_stage"),
        "student_level_known": ("worksheets/quick_exams/videos", "level_or_band|level"),
        "resource_topic": ("worksheets/quick_exams/videos", "topic"),
        "resource_type": ("worksheets/quick_exams/videos", "worksheet_type|assignment_type"),
        "resource_learner_stage": ("worksheets/quick_exams/videos", "learner_stage"),
        "resource_level": ("worksheets/quick_exams/videos", "level_or_band|level"),
        "resource_language": ("worksheets", "student_material_language|plan_language"),
        "resource_title_length": ("worksheets/quick_exams/videos", "title"),
        "resource_public_flag": ("worksheets/quick_exams/videos", "is_public"),
        "prior_student_mature_assignment_count": ("teacher_assignments", "assigned_at,opened_at,viewed_at,completed_at"),
        "prior_student_assignment_open_rate": ("teacher_assignments", "assigned_at,opened_at,viewed_at"),
        "prior_student_completion_rate": ("teacher_assignments", "assigned_at,completed_at"),
        "prior_student_practice_session_count": ("practice_sessions", "user_id,completed_at|started_at"),
        "prior_student_avg_practice_score": ("practice_sessions", "score_pct"),
        "prior_days_since_student_activity": ("practice_sessions/teacher_assignments", "completed_at|started_at|opened_at|viewed_at"),
        "prior_teacher_mature_assignment_count": ("teacher_assignments", "teacher_id,assigned_at,opened_at,viewed_at"),
        "prior_teacher_assignment_open_rate": ("teacher_assignments", "teacher_id,assigned_at,opened_at,viewed_at"),
        "prior_resource_mature_assignment_count": ("teacher_assignments", "source_record_id,assignment_type,assigned_at,opened_at,viewed_at"),
        "prior_resource_open_rate": ("teacher_assignments", "source_record_id,assignment_type,assigned_at,opened_at,viewed_at"),
    }
    retained_set = set(feature_names)
    violations = set(validate_feature_eligibility(feature_names))
    rows = []
    for feature_name in CATEGORICAL_FEATURES + NUMERIC_FEATURES:
        source_table, source_column = source_map.get(feature_name, ("derived", "derived"))
        if feature_name in df.columns:
            series = df[feature_name]
            missing_pct = float(series.isna().mean()) if len(series) else 0.0
            if series.dtype == object:
                missing_pct = float(series.replace("", pd.NA).isna().mean()) if len(series) else 0.0
            unique_values = int(series.replace("", pd.NA).nunique(dropna=True)) if len(series) else 0
        else:
            missing_pct = 1.0
            unique_values = 0
        retained = feature_name in retained_set and feature_name not in violations
        exclusion_reason = ""
        if feature_name in violations:
            exclusion_reason = "forbidden_post_assignment_signal"
        elif feature_name not in retained_set:
            exclusion_reason = "not_selected_for_pipeline"
        rows.append(
            {
                "feature": feature_name,
                "source_table": source_table,
                "source_column": source_column,
                "timestamp_constraint": "must be known at or before teacher_assignments.assigned_at",
                "missing_percentage": round(missing_pct * 100.0, 2),
                "unique_values": unique_values,
                "retained": retained,
                "exclusion_reason": exclusion_reason,
            }
        )
    return pd.DataFrame(rows)


def build_chronological_split(df: pd.DataFrame, holdout_fraction: float = 0.2) -> dict[str, Any]:
    mature_df = df[df["label_status"] == "included"].copy()
    if mature_df.empty:
        return {
            "cutoff_timestamp": "",
            "development_df": mature_df,
            "holdout_df": mature_df,
            "train_count": 0,
            "holdout_count": 0,
        }
    mature_df["assigned_dt"] = pd.to_datetime(mature_df["assigned_at"], utc=True)
    mature_df = mature_df.sort_values(["assigned_dt", "assignment_id"]).reset_index(drop=True)
    holdout_count = max(1, int(math.ceil(len(mature_df) * holdout_fraction)))
    if holdout_count >= len(mature_df):
        holdout_count = max(1, len(mature_df) - 1)
    split_index = max(1, len(mature_df) - holdout_count)
    development_df = mature_df.iloc[:split_index].copy()
    holdout_df = mature_df.iloc[split_index:].copy()
    cutoff_timestamp = _clean_text(holdout_df.iloc[0]["assigned_at"]) if not holdout_df.empty else _clean_text(mature_df.iloc[-1]["assigned_at"])
    return {
        "cutoff_timestamp": cutoff_timestamp,
        "development_df": development_df.drop(columns=["assigned_dt"]),
        "holdout_df": holdout_df.drop(columns=["assigned_dt"]),
        "train_count": int(len(development_df)),
        "holdout_count": int(len(holdout_df)),
    }


def build_time_series_folds(df: pd.DataFrame, max_splits: int = 5) -> tuple[list[tuple[np.ndarray, np.ndarray]], str]:
    if len(df) < 6:
        return [], "too_few_rows_for_cv"
    y = df[TARGET_NAME].astype(int).to_numpy()
    from_splits = min(max_splits, max(2, len(df) // 8))
    for split_count in range(from_splits, 1, -1):
        fold_size = len(df) // (split_count + 1)
        if fold_size < 2:
            continue
        folds: list[tuple[np.ndarray, np.ndarray]] = []
        valid = True
        for fold_idx in range(split_count):
            train_end = fold_size * (fold_idx + 1)
            val_end = fold_size * (fold_idx + 2) if fold_idx < split_count - 1 else len(df)
            train_idx = np.arange(0, train_end)
            val_idx = np.arange(train_end, val_end)
            if len(train_idx) < 2 or len(val_idx) < 2:
                valid = False
                break
            if len(np.unique(y[train_idx])) < 2 or len(np.unique(y[val_idx])) < 2:
                valid = False
                break
            folds.append((train_idx, val_idx))
        if valid and folds:
            return folds, ""
    return [], "unable_to_form_class_balanced_time_series_folds"


def _safe_auc(y_true: np.ndarray, y_score: np.ndarray) -> float | None:
    if len(np.unique(y_true)) < 2:
        return None
    positives = y_score[y_true == 1]
    negatives = y_score[y_true == 0]
    if len(positives) == 0 or len(negatives) == 0:
        return None
    pair_total = float(len(positives) * len(negatives))
    wins = 0.0
    for pos in positives:
        wins += float(np.sum(pos > negatives))
        wins += 0.5 * float(np.sum(pos == negatives))
    return wins / pair_total if pair_total else None


def _safe_average_precision(y_true: np.ndarray, y_score: np.ndarray) -> float | None:
    positives = int(np.sum(y_true == 1))
    if positives == 0:
        return None
    order = np.argsort(-y_score)
    y_sorted = y_true[order]
    precisions = []
    hit_count = 0
    for idx, value in enumerate(y_sorted, start=1):
        if int(value) == 1:
            hit_count += 1
            precisions.append(hit_count / idx)
    return float(sum(precisions) / positives) if precisions else 0.0


def _safe_log_loss(y_true: np.ndarray, y_prob: np.ndarray) -> float | None:
    if y_prob is None:
        return None
    clipped = np.clip(y_prob.astype(float), 1e-6, 1 - 1e-6)
    return float(-np.mean(y_true * np.log(clipped) + (1 - y_true) * np.log(1 - clipped)))


def _metric_dict(y_true: np.ndarray, y_pred: np.ndarray, y_score: np.ndarray | None = None, y_prob: np.ndarray | None = None) -> dict[str, Any]:
    y_true = y_true.astype(int)
    y_pred = y_pred.astype(int)
    tp = int(np.sum((y_true == 1) & (y_pred == 1)))
    tn = int(np.sum((y_true == 0) & (y_pred == 0)))
    fp = int(np.sum((y_true == 0) & (y_pred == 1)))
    fn = int(np.sum((y_true == 1) & (y_pred == 0)))
    total = max(1, len(y_true))
    accuracy = (tp + tn) / total
    recall = tp / max(1, tp + fn)
    specificity = tn / max(1, tn + fp)
    precision = tp / max(1, tp + fp)
    f1 = 0.0 if precision + recall == 0 else (2 * precision * recall) / (precision + recall)
    roc_auc = _safe_auc(y_true, y_score if y_score is not None else y_pred.astype(float))
    average_precision = _safe_average_precision(y_true, y_score if y_score is not None else y_pred.astype(float))
    brier = float(np.mean((y_prob - y_true) ** 2)) if y_prob is not None else None
    log_loss = _safe_log_loss(y_true, y_prob) if y_prob is not None else None
    balanced_accuracy = (recall + specificity) / 2.0
    return {
        "accuracy": float(accuracy),
        "balanced_accuracy": float(balanced_accuracy),
        "precision": float(precision),
        "recall": float(recall),
        "specificity": float(specificity),
        "f1": float(f1),
        "roc_auc": None if roc_auc is None else float(roc_auc),
        "average_precision": None if average_precision is None else float(average_precision),
        "log_loss": None if log_loss is None else float(log_loss),
        "brier_score": None if brier is None else float(brier),
        "predicted_positive_rate": float(np.mean(y_pred)),
        "confusion_matrix": [[tn, fp], [fn, tp]],
        "single_class_prediction": bool(len(np.unique(y_pred)) < 2),
    }


def _bootstrap_metric_intervals(y_true: np.ndarray, y_pred: np.ndarray, y_score: np.ndarray | None, y_prob: np.ndarray | None, *, seed: int, iterations: int = 300) -> dict[str, dict[str, float] | None]:
    if len(y_true) < 8:
        return {}
    rng = np.random.default_rng(seed)
    tracked_metrics = [
        "accuracy",
        "balanced_accuracy",
        "precision",
        "recall",
        "specificity",
        "f1",
        "roc_auc",
        "average_precision",
        "brier_score",
        "log_loss",
    ]
    samples: dict[str, list[float]] = {name: [] for name in tracked_metrics}
    for _ in range(iterations):
        indices = rng.integers(0, len(y_true), size=len(y_true))
        sample_true = y_true[indices]
        if len(np.unique(sample_true)) < 2:
            continue
        sample_pred = y_pred[indices]
        sample_score = y_score[indices] if y_score is not None else None
        sample_prob = y_prob[indices] if y_prob is not None else None
        metrics = _metric_dict(sample_true, sample_pred, sample_score, sample_prob)
        for metric_name in tracked_metrics:
            metric_value = metrics.get(metric_name)
            if metric_value is None:
                continue
            samples[metric_name].append(float(metric_value))
    intervals: dict[str, dict[str, float] | None] = {}
    for metric_name, values in samples.items():
        if len(values) < 20:
            intervals[metric_name] = None
            continue
        arr = np.asarray(values, dtype=float)
        intervals[metric_name] = {
            "low": float(np.quantile(arr, 0.025)),
            "high": float(np.quantile(arr, 0.975)),
        }
    return intervals


def _majority_baseline_predictions(y_train: np.ndarray, holdout_size: int) -> tuple[np.ndarray, np.ndarray]:
    positive_rate = float(np.mean(y_train)) if len(y_train) else 0.0
    majority_label = 1 if positive_rate >= 0.5 else 0
    y_pred = np.full(holdout_size, majority_label, dtype=int)
    y_prob = np.full(holdout_size, positive_rate, dtype=float)
    return y_pred, y_prob


def _sklearn_available() -> tuple[bool, str]:
    try:
        import sklearn  # noqa: F401
        return True, ""
    except Exception as exc:
        return False, str(exc)


def _build_model_specs() -> list[dict[str, Any]]:
    return [
        {"name": "DummyClassifier", "kind": "baseline", "scaled": False, "reduced": False},
        {"name": "MajorityClassRule", "kind": "baseline_manual", "scaled": False, "reduced": False},
        {"name": "LogisticRegression", "kind": "supervised", "scaled": True, "reduced": False},
        {"name": "LogisticRegressionReduced", "kind": "supervised", "scaled": True, "reduced": True},
        {"name": "DecisionTreeClassifier", "kind": "supervised", "scaled": False, "reduced": False},
        {"name": "RandomForestClassifier", "kind": "supervised", "scaled": False, "reduced": False},
        {"name": "HistGradientBoostingClassifier", "kind": "supervised", "scaled": False, "reduced": False},
        {"name": "SVC", "kind": "supervised", "scaled": True, "reduced": False},
        {"name": "KNeighborsClassifier", "kind": "supervised", "scaled": True, "reduced": False},
    ]


def _instantiate_sklearn_pipeline(model_name: str, feature_names: list[str], scaled: bool):
    from sklearn.compose import ColumnTransformer
    from sklearn.dummy import DummyClassifier
    from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier
    from sklearn.impute import SimpleImputer
    from sklearn.neighbors import KNeighborsClassifier
    from sklearn.pipeline import Pipeline
    from sklearn.preprocessing import OneHotEncoder, StandardScaler
    from sklearn.svm import SVC
    from sklearn.tree import DecisionTreeClassifier
    from sklearn.linear_model import LogisticRegression

    numeric_features = [name for name in feature_names if name in NUMERIC_FEATURES]
    categorical_features = [name for name in feature_names if name in CATEGORICAL_FEATURES]
    numeric_steps: list[tuple[str, Any]] = [("imputer", SimpleImputer(strategy="median"))]
    if scaled:
        numeric_steps.append(("scaler", StandardScaler()))
    categorical_pipeline = Pipeline(
        steps=[
            ("imputer", SimpleImputer(strategy="most_frequent")),
            ("onehot", OneHotEncoder(handle_unknown="ignore", sparse_output=False)),
        ]
    )
    preprocessor = ColumnTransformer(
        transformers=[
            ("num", Pipeline(steps=numeric_steps), numeric_features),
            ("cat", categorical_pipeline, categorical_features),
        ]
    )
    random_state = DEFAULT_SEED
    if model_name == "DummyClassifier":
        estimator = DummyClassifier(strategy="prior")
    elif model_name == "LogisticRegression":
        estimator = LogisticRegression(max_iter=500, C=1.0, random_state=random_state)
    elif model_name == "LogisticRegressionReduced":
        estimator = LogisticRegression(max_iter=500, C=1.0, random_state=random_state)
    elif model_name == "DecisionTreeClassifier":
        estimator = DecisionTreeClassifier(max_depth=3, min_samples_leaf=4, random_state=random_state)
    elif model_name == "RandomForestClassifier":
        estimator = RandomForestClassifier(
            n_estimators=80,
            max_depth=4,
            min_samples_leaf=3,
            random_state=random_state,
        )
    elif model_name == "HistGradientBoostingClassifier":
        estimator = HistGradientBoostingClassifier(
            max_depth=3,
            learning_rate=0.08,
            max_iter=80,
            random_state=random_state,
        )
    elif model_name == "SVC":
        estimator = SVC(C=1.0, kernel="rbf", gamma="scale", probability=True, random_state=random_state)
    elif model_name == "KNeighborsClassifier":
        estimator = KNeighborsClassifier(n_neighbors=5, weights="distance")
    else:
        raise ValueError(f"unsupported_model:{model_name}")
    return Pipeline(steps=[("preprocessor", preprocessor), ("model", estimator)])


def _extract_feature_importance(model_name: str, fitted_pipeline, feature_names: list[str]) -> list[dict[str, Any]]:
    try:
        preprocessor = fitted_pipeline.named_steps["preprocessor"]
        transformed_names = list(preprocessor.get_feature_names_out())
        estimator = fitted_pipeline.named_steps["model"]
        if hasattr(estimator, "coef_"):
            weights = np.ravel(estimator.coef_)
        elif hasattr(estimator, "feature_importances_"):
            weights = np.ravel(estimator.feature_importances_)
        else:
            return []
        rows = []
        for name, value in zip(transformed_names, weights):
            rows.append({"model_name": model_name, "feature_name": str(name), "importance": float(value)})
        rows.sort(key=lambda item: abs(float(item["importance"])), reverse=True)
        return rows[:20]
    except Exception:
        return []


def _predict_scores(pipeline, frame: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
    if hasattr(pipeline, "predict_proba"):
        probs = pipeline.predict_proba(frame)[:, 1]
        preds = (probs >= 0.5).astype(int)
        return preds, probs
    if hasattr(pipeline, "decision_function"):
        scores = np.asarray(pipeline.decision_function(frame), dtype=float)
        probs = 1.0 / (1.0 + np.exp(-scores))
        preds = (probs >= 0.5).astype(int)
        return preds, probs
    preds = np.asarray(pipeline.predict(frame), dtype=int)
    return preds, preds.astype(float)


def evaluate_models(dataset_df: pd.DataFrame) -> dict[str, Any]:
    split = build_chronological_split(dataset_df)
    development_df = split["development_df"]
    holdout_df = split["holdout_df"]
    if len(development_df) < 8 or len(holdout_df) < 2:
        return {
            "status": "insufficient_data",
            "cutoff_timestamp": split["cutoff_timestamp"],
            "development_count": int(len(development_df)),
            "holdout_count": int(len(holdout_df)),
            "feature_names": [],
            "feature_audit": build_feature_audit(dataset_df, REDUCED_FEATURES),
            "model_rows": [],
            "predictions": [],
            "winner": "no credible winner",
            "maturity_verdict": "INSUFFICIENT_DATA",
            "limitations": ["Too few mature labelled assignments for a credible chronological comparison."],
        }

    feature_names = [name for name in CATEGORICAL_FEATURES + NUMERIC_FEATURES if name in dataset_df.columns]
    forbidden = validate_feature_eligibility(feature_names)
    if forbidden:
        raise ValueError(f"forbidden_features_detected:{','.join(forbidden)}")
    development_feature_names, dropped_run_features = active_features_for_training_frame(development_df, feature_names)
    feature_audit = build_feature_audit(dataset_df, development_feature_names)
    if dropped_run_features:
        feature_audit.loc[feature_audit["feature"].isin(dropped_run_features.keys()), "retained"] = False
        feature_audit.loc[feature_audit["feature"].isin(dropped_run_features.keys()), "exclusion_reason"] = "fully_missing_in_development_split"
    feature_frame_dev = development_df[development_feature_names].copy()
    feature_frame_holdout = holdout_df[development_feature_names].copy()
    y_dev = development_df[TARGET_NAME].astype(int).to_numpy()
    y_holdout = holdout_df[TARGET_NAME].astype(int).to_numpy()
    folds, fold_issue = build_time_series_folds(development_df)

    model_rows: list[dict[str, Any]] = []
    prediction_rows: list[dict[str, Any]] = []
    feature_importance_rows: list[dict[str, Any]] = []
    sklearn_ok, sklearn_error = _sklearn_available()

    majority_pred, majority_prob = _majority_baseline_predictions(y_dev, len(y_holdout))
    majority_metrics = _metric_dict(y_holdout, majority_pred, majority_prob, majority_prob)
    majority_ci = _bootstrap_metric_intervals(y_holdout, majority_pred, majority_prob, majority_prob, seed=DEFAULT_SEED)
    model_rows.append(
        {
            "model_name": "MajorityClassRule",
            "model_kind": "baseline_manual",
            "status": "success",
            "failure_reason": "",
            "used_reduced_features": False,
            "cv_fold_count": 0,
            "cv_status": "not_applicable",
            "cv_primary_metric_mean": None,
            "cv_primary_metric_variance": None,
            "train_duration_seconds": 0.0,
            "inference_duration_seconds": 0.0,
            "holdout_positive_rate": float(np.mean(y_holdout)),
            **majority_metrics,
            "confidence_intervals": majority_ci,
            "parameters_json": json.dumps({"strategy": "majority_class_rule"}),
        }
    )
    for idx, (assignment_id, y_true, y_pred, y_prob) in enumerate(
        zip(holdout_df["assignment_id"], y_holdout, majority_pred, majority_prob)
    ):
        prediction_rows.append(
            {
                "row_order": idx,
                "assignment_id": int(assignment_id),
                "model_name": "MajorityClassRule",
                "actual_label": int(y_true),
                "predicted_label": int(y_pred),
                "predicted_probability": float(y_prob),
                "assigned_at": _clean_text(holdout_df.iloc[idx]["assigned_at"]),
            }
        )

    for spec in _build_model_specs():
        if spec["name"] == "MajorityClassRule":
            continue
        used_feature_names = [name for name in REDUCED_FEATURES if name in feature_names] if spec.get("reduced") else feature_names
        if spec["name"] == "DummyClassifier" and not sklearn_ok:
            model_rows.append(
                {
                    "model_name": spec["name"],
                    "model_kind": spec["kind"],
                    "status": "failed",
                    "failure_reason": f"missing_dependency:{sklearn_error}",
                    "used_reduced_features": bool(spec.get("reduced")),
                    "cv_fold_count": 0,
                    "cv_status": "skipped",
                    "cv_primary_metric_mean": None,
                    "cv_primary_metric_variance": None,
                    "train_duration_seconds": None,
                    "inference_duration_seconds": None,
                    "holdout_positive_rate": float(np.mean(y_holdout)),
                    "accuracy": None,
                    "balanced_accuracy": None,
                    "precision": None,
                    "recall": None,
                    "specificity": None,
                    "f1": None,
                    "roc_auc": None,
                    "average_precision": None,
                    "log_loss": None,
                    "brier_score": None,
                    "predicted_positive_rate": None,
                    "confusion_matrix": None,
                    "single_class_prediction": None,
                    "confidence_intervals": None,
                    "parameters_json": "{}",
                }
            )
            continue
        if spec["kind"] != "baseline_manual" and not sklearn_ok:
            model_rows.append(
                {
                    "model_name": spec["name"],
                    "model_kind": spec["kind"],
                    "status": "failed",
                    "failure_reason": f"missing_dependency:{sklearn_error}",
                    "used_reduced_features": bool(spec.get("reduced")),
                    "cv_fold_count": 0,
                    "cv_status": "skipped",
                    "cv_primary_metric_mean": None,
                    "cv_primary_metric_variance": None,
                    "train_duration_seconds": None,
                    "inference_duration_seconds": None,
                    "holdout_positive_rate": float(np.mean(y_holdout)),
                    "accuracy": None,
                    "balanced_accuracy": None,
                    "precision": None,
                    "recall": None,
                    "specificity": None,
                    "f1": None,
                    "roc_auc": None,
                    "average_precision": None,
                    "log_loss": None,
                    "brier_score": None,
                    "predicted_positive_rate": None,
                    "confusion_matrix": None,
                    "single_class_prediction": None,
                    "confidence_intervals": None,
                    "parameters_json": "{}",
                }
            )
            continue
        try:
            if spec.get("reduced"):
                used_feature_names = [name for name in REDUCED_FEATURES if name in development_feature_names]
            else:
                used_feature_names = list(development_feature_names)
            used_feature_names, dropped_model_features = active_features_for_training_frame(development_df[used_feature_names], used_feature_names)
            pipeline = _instantiate_sklearn_pipeline(spec["name"], used_feature_names, bool(spec.get("scaled")))
            cv_scores: list[float] = []
            cv_status = "skipped"
            if folds:
                for train_idx, val_idx in folds:
                    fold_train = development_df.iloc[train_idx][used_feature_names]
                    fold_val = development_df.iloc[val_idx][used_feature_names]
                    y_train_fold = y_dev[train_idx]
                    y_val_fold = y_dev[val_idx]
                    fold_active_features, _dropped_fold_features = active_features_for_training_frame(fold_train, used_feature_names)
                    fitted_fold = _instantiate_sklearn_pipeline(spec["name"], fold_active_features, bool(spec.get("scaled"))).fit(
                        fold_train[fold_active_features],
                        y_train_fold,
                    )
                    _pred, _score = _predict_scores(fitted_fold, fold_val[fold_active_features])
                    primary = _safe_auc(y_val_fold, _score)
                    if primary is None:
                        primary = _safe_average_precision(y_val_fold, _score)
                    if primary is not None:
                        cv_scores.append(float(primary))
                cv_status = "success" if cv_scores else (fold_issue or "failed")
            else:
                cv_status = fold_issue or "skipped"

            started = time.perf_counter()
            fitted_pipeline = pipeline.fit(feature_frame_dev[used_feature_names], y_dev)
            train_duration = time.perf_counter() - started
            started = time.perf_counter()
            y_pred, y_prob = _predict_scores(fitted_pipeline, feature_frame_holdout[used_feature_names])
            inference_duration = time.perf_counter() - started
            metrics = _metric_dict(y_holdout, y_pred, y_prob, y_prob)
            confidence_intervals = _bootstrap_metric_intervals(y_holdout, y_pred, y_prob, y_prob, seed=DEFAULT_SEED + len(model_rows))
            params = {}
            try:
                params = fitted_pipeline.named_steps["model"].get_params()
            except Exception:
                params = {}
            feature_importance_rows.extend(_extract_feature_importance(spec["name"], fitted_pipeline, used_feature_names))
            model_rows.append(
                {
                    "model_name": spec["name"],
                    "model_kind": spec["kind"],
                    "status": "success",
                    "failure_reason": "",
                    "used_reduced_features": bool(spec.get("reduced")),
                    "cv_fold_count": int(len(folds)),
                    "cv_status": cv_status,
                    "cv_primary_metric_mean": float(np.mean(cv_scores)) if cv_scores else None,
                    "cv_primary_metric_variance": float(np.var(cv_scores)) if len(cv_scores) > 1 else (0.0 if len(cv_scores) == 1 else None),
                    "train_duration_seconds": float(train_duration),
                    "inference_duration_seconds": float(inference_duration),
                    "holdout_positive_rate": float(np.mean(y_holdout)),
                    **metrics,
                    "confidence_intervals": confidence_intervals,
                    "dropped_feature_reasons_json": json.dumps(dropped_model_features, sort_keys=True),
                    "parameters_json": json.dumps(_json_safe(params), sort_keys=True),
                }
            )
            for idx, (assignment_id, y_true, pred, prob) in enumerate(
                zip(holdout_df["assignment_id"], y_holdout, y_pred, y_prob)
            ):
                prediction_rows.append(
                    {
                        "row_order": idx,
                        "assignment_id": int(assignment_id),
                        "model_name": spec["name"],
                        "actual_label": int(y_true),
                        "predicted_label": int(pred),
                        "predicted_probability": float(prob),
                        "assigned_at": _clean_text(holdout_df.iloc[idx]["assigned_at"]),
                    }
                )
        except Exception as exc:
            model_rows.append(
                {
                    "model_name": spec["name"],
                    "model_kind": spec["kind"],
                    "status": "failed",
                    "failure_reason": str(exc),
                    "used_reduced_features": bool(spec.get("reduced")),
                    "cv_fold_count": int(len(folds)),
                    "cv_status": "failed",
                    "cv_primary_metric_mean": None,
                    "cv_primary_metric_variance": None,
                    "train_duration_seconds": None,
                    "inference_duration_seconds": None,
                    "holdout_positive_rate": float(np.mean(y_holdout)),
                    "accuracy": None,
                    "balanced_accuracy": None,
                    "precision": None,
                    "recall": None,
                    "specificity": None,
                    "f1": None,
                    "roc_auc": None,
                    "average_precision": None,
                    "log_loss": None,
                    "brier_score": None,
                    "predicted_positive_rate": None,
                    "confusion_matrix": None,
                    "single_class_prediction": None,
                    "confidence_intervals": None,
                    "dropped_feature_reasons_json": "{}",
                    "parameters_json": "{}",
                }
            )

    winner = select_best_candidate(model_rows)
    maturity_verdict = derive_maturity_verdict(dataset_df, model_rows, winner)
    limitations = build_limitations(dataset_df, model_rows, folds, fold_issue, sklearn_ok, sklearn_error)
    return {
        "status": "ok",
        "cutoff_timestamp": split["cutoff_timestamp"],
        "development_count": int(len(development_df)),
        "holdout_count": int(len(holdout_df)),
        "development_positive_count": int(np.sum(y_dev)),
        "development_negative_count": int(len(y_dev) - np.sum(y_dev)),
        "holdout_positive_count": int(np.sum(y_holdout)),
        "holdout_negative_count": int(len(y_holdout) - np.sum(y_holdout)),
        "feature_names": feature_names,
        "feature_audit": feature_audit,
        "model_rows": model_rows,
        "predictions": prediction_rows,
        "feature_importance_rows": feature_importance_rows,
        "dropped_run_features": dropped_run_features,
        "winner": winner,
        "maturity_verdict": maturity_verdict,
        "limitations": limitations,
        "sklearn_available": sklearn_ok,
        "sklearn_error": sklearn_error,
    }


def select_best_candidate(model_rows: list[dict[str, Any]]) -> str:
    successful_rows = [row for row in model_rows if row.get("status") == "success"]
    if not successful_rows:
        return "no credible winner"
    positive_rate = float(successful_rows[0].get("holdout_positive_rate") or 0.0)
    primary_metric = "roc_auc" if 0.35 <= positive_rate <= 0.65 else "average_precision"
    baseline = next((row for row in successful_rows if row.get("model_name") == "DummyClassifier"), None)
    if baseline is None:
        baseline = next((row for row in successful_rows if row.get("model_name") == "MajorityClassRule"), None)
    candidates = [
        row for row in successful_rows
        if row.get("model_kind") == "supervised"
        and row.get(primary_metric) is not None
    ]
    if not candidates:
        return "no credible winner"
    candidates = [
        row for row in candidates
        if not bool(row.get("single_class_prediction"))
    ]
    if not candidates:
        return "no credible winner"
    sorted_candidates = sorted(candidates, key=lambda item: float(item.get(primary_metric) or -1.0), reverse=True)
    best = sorted_candidates[0]
    baseline_score = float(baseline.get(primary_metric) or -1.0) if baseline else -1.0
    best_score = float(best.get(primary_metric) or -1.0)
    if best_score <= baseline_score + 0.01:
        return "no credible winner"
    if len(sorted_candidates) > 1:
        runner_up = sorted_candidates[1]
        best_ci = (best.get("confidence_intervals") or {}).get(primary_metric) or {}
        runner_ci = (runner_up.get("confidence_intervals") or {}).get(primary_metric) or {}
        if best_ci and runner_ci:
            if not (
                float(best_ci.get("low", -1.0)) > float(runner_ci.get("high", 2.0))
                or float(runner_ci.get("low", -1.0)) > float(best_ci.get("high", 2.0))
            ):
                simplicity_order = {
                    "LogisticRegression": 1,
                    "LogisticRegressionReduced": 1,
                    "DecisionTreeClassifier": 2,
                    "RandomForestClassifier": 3,
                    "HistGradientBoostingClassifier": 4,
                    "SVC": 5,
                    "KNeighborsClassifier": 6,
                }
                close_candidates = [best, runner_up]
                close_candidates.sort(key=lambda item: (simplicity_order.get(str(item.get("model_name")), 99), -float(item.get(primary_metric) or -1.0)))
                best = close_candidates[0]
    return str(best.get("model_name") or "no credible winner")


def derive_maturity_verdict(dataset_df: pd.DataFrame, model_rows: list[dict[str, Any]], winner: str) -> str:
    mature_count = int((dataset_df["label_status"] == "included").sum()) if not dataset_df.empty else 0
    teacher_column = "teacher_id" if "teacher_id" in dataset_df.columns else ("teacher_hash" if "teacher_hash" in dataset_df.columns else "")
    teacher_count = int(dataset_df.loc[dataset_df["label_status"] == "included", teacher_column].replace("", pd.NA).nunique()) if (not dataset_df.empty and teacher_column) else 0
    if mature_count < 60:
        return "INSUFFICIENT_DATA"
    if teacher_count <= 1 or mature_count < 250:
        return "EXPLORATORY_ONLY"
    winning_row = next((row for row in model_rows if row.get("model_name") == winner), None)
    if not winning_row or winner == "no credible winner":
        return "EXPLORATORY_ONLY"
    auc = winning_row.get("roc_auc")
    if auc is not None and float(auc) >= 0.75 and teacher_count >= 5 and mature_count >= 1000:
        return "CANDIDATE_FOR_CONTROLLED_PILOT"
    return "CANDIDATE_FOR_SHADOW_TESTING"


def build_limitations(dataset_df: pd.DataFrame, model_rows: list[dict[str, Any]], folds: list[tuple[np.ndarray, np.ndarray]], fold_issue: str, sklearn_ok: bool, sklearn_error: str) -> list[str]:
    limitations: list[str] = []
    mature_df = dataset_df[dataset_df["label_status"] == "included"].copy()
    teacher_column = "teacher_id" if "teacher_id" in mature_df.columns else ("teacher_hash" if "teacher_hash" in mature_df.columns else "")
    teacher_count = int(mature_df[teacher_column].replace("", pd.NA).nunique()) if (not mature_df.empty and teacher_column) else 0
    mature_count = int(len(mature_df))
    if teacher_count <= 1:
        limitations.append("Only one teacher is represented in the mature labelled dataset, so cross-teacher generalization cannot be established.")
    if mature_count < 150:
        limitations.append("The mature labelled sample is small, so all comparisons should be treated as exploratory with high variance.")
    if not sklearn_ok:
        limitations.append(f"scikit-learn is unavailable in this runtime, so the required supervised model comparison cannot run until the dependency is installed. Error: {sklearn_error}")
    if not folds:
        limitations.append(f"Chronological cross-validation folds could not be formed with both classes in every fold ({fold_issue or 'unknown_reason'}).")
    if any(bool(row.get("single_class_prediction")) for row in model_rows if row.get("status") == "success" and row.get("model_kind") == "supervised"):
        limitations.append("At least one supervised candidate collapsed to single-class predictions on the holdout set.")
    return limitations


def freeze_anonymized_dataset(df: pd.DataFrame, *, run_id: str, output_dir: Path) -> tuple[Path, str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    frozen = df.copy()
    for raw_col in ("teacher_id", "student_id", "resource_key", "source_record_id"):
        if raw_col in frozen.columns:
            if raw_col == "teacher_id":
                frozen["teacher_hash"] = frozen[raw_col].map(lambda value: _hash_identifier(run_id, "teacher", value))
            elif raw_col == "student_id":
                frozen["student_hash"] = frozen[raw_col].map(lambda value: _hash_identifier(run_id, "student", value))
            else:
                frozen["resource_hash"] = frozen[raw_col].map(lambda value: _hash_identifier(run_id, "resource", value))
    frozen = frozen.drop(columns=[name for name in ["teacher_id", "student_id", "resource_key", "source_record_id"] if name in frozen.columns])
    dataset_path = output_dir / FROZEN_DATASET_FILENAME
    frozen.to_csv(dataset_path, index=False)
    fingerprint = hashlib.sha256(dataset_path.read_bytes()).hexdigest()
    return dataset_path, fingerprint


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(_json_safe(payload), indent=2, sort_keys=True), encoding="utf-8")


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fieldnames = sorted({key for row in rows for key in row.keys()})
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: _json_safe(row.get(key)) for key in fieldnames})


def _render_technical_report(summary: dict[str, Any]) -> str:
    dataset = summary["dataset"]
    evaluation = summary["evaluation"]
    model_rows = evaluation.get("model_rows") or []
    winner = evaluation.get("winner") or "no credible winner"
    top_rows = sorted(
        [row for row in model_rows if row.get("status") == "success" and row.get("model_kind") == "supervised"],
        key=lambda item: float(item.get("roc_auc") or -1.0),
        reverse=True,
    )[:5]
    lines = [
        "# Assigned Resource Open Within 7 Days Technical Report",
        "",
        "Business question: Can Classio predict whether a student will open an assigned resource within seven days of assignment?",
        "",
        "Target construction:",
        "- `opened_within_7d = 1` when `teacher_assignments.opened_at` or `teacher_assignments.viewed_at` falls on or after `teacher_assignments.assigned_at` and no later than seven complete days afterward.",
        "- `opened_within_7d = 0` when the seven-day window has closed and no qualifying open or view occurred.",
        "- Rows with an open window or invalid timestamps are excluded from training and evaluation.",
        "",
        "Evidence sources:",
        "- `teacher_assignments.id`, `teacher_assignments.assigned_at`, `teacher_assignments.opened_at`, `teacher_assignments.viewed_at`, `teacher_assignments.completed_at`, `teacher_assignments.learning_program_assignment_id`, `teacher_assignments.recommendation_bucket`, `teacher_assignments.recommendation_focus_kind`",
        "- `practice_sessions.user_id`, `practice_sessions.score_pct`, `practice_sessions.completed_at`, `practice_sessions.started_at`",
        "- resource metadata from `worksheets`, `quick_exams`, and `videos`",
        "- implementation in `helpers/assigned_resource_open_7d_eval.py`",
        "",
        "Dataset summary:",
        f"- extraction timestamp: {dataset.get('extracted_at')}",
        f"- source date range: {dataset.get('date_range', {}).get('assigned_at_min')} to {dataset.get('date_range', {}).get('assigned_at_max')}",
        f"- source rows inspected: {dataset.get('source_row_count')}",
        f"- mature included rows: {dataset.get('included_row_count')}",
        f"- excluded rows: {dataset.get('excluded_row_count')}",
        f"- data fingerprint: {dataset.get('data_fingerprint')}",
        "",
        "Chronological evaluation:",
        f"- development rows: {evaluation.get('development_count')}",
        f"- holdout rows: {evaluation.get('holdout_count')}",
        f"- split cutoff timestamp: {evaluation.get('cutoff_timestamp')}",
        f"- winner status: {winner}",
        f"- maturity verdict: {evaluation.get('maturity_verdict')}",
        "",
        "Model comparison snapshot:",
    ]
    if top_rows:
        for row in top_rows:
            lines.append(
                f"- {row.get('model_name')}: ROC AUC={row.get('roc_auc')}, AP={row.get('average_precision')}, balanced_accuracy={row.get('balanced_accuracy')}, F1={row.get('f1')}, single_class={row.get('single_class_prediction')}"
            )
    else:
        lines.append("- No supervised candidate completed successfully in this runtime.")
    lines.extend(
        [
            "",
            "Limitations:",
            *[f"- {item}" for item in (evaluation.get("limitations") or ["No additional limitations recorded."])],
            "",
            "Conclusion:",
            f"- The best evaluated candidate is `{winner}`." if winner != "no credible winner" else "- No credible winner was identified.",
            f"- Final maturity verdict: `{evaluation.get('maturity_verdict')}`.",
        ]
    )
    return "\n".join(lines) + "\n"


def build_label_audit(df: pd.DataFrame) -> pd.DataFrame:
    ordered = [
        "assignment_id",
        "teacher_id",
        "student_id",
        "resource_key",
        "assignment_type",
        "source_type",
        "assigned_at",
        "opened_at",
        "viewed_at",
        "submitted_at",
        "completed_at",
        "observation_window_closed_at",
        "label_status",
        "label_exclusion_reason",
        "qualifying_event",
        "qualifying_open_at",
        TARGET_NAME,
    ]
    available = [column for column in ordered if column in df.columns]
    return df[available].copy() if available else pd.DataFrame()


def _render_academic_report(summary: dict[str, Any]) -> str:
    dataset = summary["dataset"]
    evaluation = summary["evaluation"]
    lines = [
        "# Assigned Resource Open Within 7 Days Academic Report",
        "",
        "## Research Question",
        "Can a classifier predict whether a student will open an assigned Classio resource within seven days, using only information available at assignment time?",
        "",
        "## Unit of Analysis",
        "One `teacher_assignments` row, with `teacher_assignments.id` as the event identity.",
        "",
        "## Outcome Definition",
        "The canonical target is `opened_within_7d`, derived from `teacher_assignments.assigned_at`, `teacher_assignments.opened_at`, and `teacher_assignments.viewed_at`.",
        "",
        "## Dataset",
        f"- extraction timestamp: {dataset.get('extracted_at')}",
        f"- included mature labels: {dataset.get('included_row_count')}",
        f"- positives: {dataset.get('positive_count')}",
        f"- negatives: {dataset.get('negative_count')}",
        f"- excluded rows: {dataset.get('excluded_row_count')}",
        f"- teachers represented: {dataset.get('teacher_count')}",
        f"- students represented: {dataset.get('student_count')}",
        f"- resources represented: {dataset.get('resource_count')}",
        "",
        "## Evaluation Design",
        f"- chronological holdout cutoff: {evaluation.get('cutoff_timestamp')}",
        f"- development rows: {evaluation.get('development_count')}",
        f"- holdout rows: {evaluation.get('holdout_count')}",
        "- comparisons are exploratory because the current dataset is small and teacher coverage is narrow.",
        "",
        "## Result",
        f"- best evaluated candidate: {evaluation.get('winner')}",
        f"- maturity verdict: {evaluation.get('maturity_verdict')}",
        "",
        "## Validity Threats",
        *[f"- {item}" for item in (evaluation.get("limitations") or [])],
    ]
    return "\n".join(lines) + "\n"


def generate_assigned_resource_open_7d_evaluation(
    output_dir: Path | str = DEFAULT_OUTPUT_DIR,
    *,
    run_id: str | None = None,
) -> dict[str, Any]:
    resolved_output_dir = Path(output_dir)
    resolved_output_dir.mkdir(parents=True, exist_ok=True)
    extraction_time = _utc_now()
    run_id = str(run_id or uuid.uuid4().hex[:12]).strip()
    snapshot = extract_operational_snapshot(extraction_time=extraction_time)
    dataset_df, dataset_diag = build_assignment_dataset(snapshot, extraction_time=extraction_time)
    dataset_path, fingerprint = freeze_anonymized_dataset(dataset_df, run_id=run_id, output_dir=resolved_output_dir)
    mature_df = dataset_df[dataset_df["label_status"] == "included"].copy()
    dataset_summary = {
        "run_id": run_id,
        "feature_schema_version": FEATURE_SCHEMA_VERSION,
        "extracted_at": _iso(extraction_time),
        "data_fingerprint": fingerprint,
        "frozen_dataset_path": str(dataset_path),
        **dataset_diag,
        "positive_count": int((mature_df[TARGET_NAME] == 1).sum()) if not mature_df.empty else 0,
        "negative_count": int((mature_df[TARGET_NAME] == 0).sum()) if not mature_df.empty else 0,
        "teacher_count": int(mature_df["teacher_id"].replace("", pd.NA).nunique()) if not mature_df.empty else 0,
        "student_count": int(mature_df["student_id"].replace("", pd.NA).nunique()) if not mature_df.empty else 0,
        "resource_count": int(mature_df["resource_key"].replace("", pd.NA).nunique()) if not mature_df.empty else 0,
    }
    evaluation = evaluate_models(dataset_df)
    run_summary = {
        "run_id": run_id,
        "feature_schema_version": FEATURE_SCHEMA_VERSION,
        "generated_at": _iso(extraction_time),
        "dataset": dataset_summary,
        "evaluation": {
            key: value
            for key, value in evaluation.items()
            if key not in {"feature_audit", "predictions", "model_rows", "feature_importance_rows"}
        },
    }
    feature_audit_path = resolved_output_dir / FEATURE_AUDIT_FILENAME
    evaluation["feature_audit"].to_csv(feature_audit_path, index=False)
    label_audit_path = resolved_output_dir / LABEL_AUDIT_FILENAME
    build_label_audit(dataset_df).to_csv(label_audit_path, index=False)
    model_comparison_path = resolved_output_dir / MODEL_COMPARISON_FILENAME
    model_rows_for_csv = []
    for row in evaluation.get("model_rows") or []:
        flat = dict(row)
        flat["confidence_intervals"] = json.dumps(_json_safe(flat.get("confidence_intervals")), sort_keys=True)
        flat["confusion_matrix"] = json.dumps(_json_safe(flat.get("confusion_matrix")))
        model_rows_for_csv.append(flat)
    _write_csv(model_comparison_path, model_rows_for_csv)
    predictions_path = resolved_output_dir / PREDICTIONS_FILENAME
    _write_csv(predictions_path, evaluation.get("predictions") or [])
    dataset_summary_path = resolved_output_dir / DATASET_SUMMARY_FILENAME
    _write_json(dataset_summary_path, dataset_summary)
    run_summary_path = resolved_output_dir / RUN_SUMMARY_FILENAME
    _write_json(run_summary_path, run_summary)
    technical_report_path = resolved_output_dir / TECHNICAL_REPORT_FILENAME
    academic_report_path = resolved_output_dir / ACADEMIC_REPORT_FILENAME
    full_summary = {
        "dataset": dataset_summary,
        "evaluation": evaluation,
        "artifacts": {
            "dataset_summary": str(dataset_summary_path),
            "feature_audit": str(feature_audit_path),
            "label_audit": str(label_audit_path),
            "model_comparison": str(model_comparison_path),
            "run_summary": str(run_summary_path),
            "technical_report": str(technical_report_path),
            "academic_report": str(academic_report_path),
            "predictions": str(predictions_path),
            "frozen_dataset": str(dataset_path),
        },
    }
    technical_report_path.write_text(_render_technical_report(full_summary), encoding="utf-8")
    academic_report_path.write_text(_render_academic_report(full_summary), encoding="utf-8")
    return full_summary
