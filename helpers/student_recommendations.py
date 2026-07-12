from __future__ import annotations

from datetime import datetime, timezone
import math
import os
from typing import Any

import pandas as pd
import streamlit as st

from core.database import _execute_query_with_diagnostics, get_sb, load_profile_row, register_cache
from core.i18n import t
from core.state import get_current_user_id
from helpers.archive_utils import truthy_flag
from helpers.lesson_planner import normalize_subject, subject_label
from helpers.practice_engine import get_completed_source_ids, load_practice_progress
from helpers.recommendation_models import score_student_resource_candidate, topic_resource_alignment_features
from helpers.student_recommendation_ml import student_recommendation_blend_weight
from helpers.learning_programs import load_enriched_program_assignments_for_current_student


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, float(value)))


def _sigmoid(value: float) -> float:
    if value >= 0:
        z = math.exp(-value)
        return 1.0 / (1.0 + z)
    z = math.exp(value)
    return z / (1.0 + z)


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value in (None, ""):
            return default
        return float(value)
    except Exception:
        return default


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        if value in (None, ""):
            return default
        return int(value)
    except Exception:
        return default


def _frame_records(df: pd.DataFrame | None) -> list[dict]:
    if df is None or df.empty:
        return []
    return df.to_dict("records")


@st.cache_data(ttl=20, show_spinner=False)
def _build_recommended_materials_cached(
    user_id: str,
    worksheet_rows: list[dict],
    exam_rows: list[dict],
    video_rows: list[dict],
    *,
    limit: int = 6,
    ranked_only: bool = False,
) -> list[dict[str, Any]]:
    worksheets_df = pd.DataFrame(worksheet_rows) if worksheet_rows else None
    exams_df = pd.DataFrame(exam_rows) if exam_rows else None
    videos_df = pd.DataFrame(video_rows) if video_rows else None

    ranked: list[dict[str, Any]] = []
    student_profile = _build_student_need_profile()
    student_profile["program_signals"] = _load_program_signals()
    student_profile["assignment_behavior"] = _load_assignment_behavior_profile()
    student_profile["assignment_signals"] = _load_assignment_signal_profile()
    completed = get_completed_source_ids()
    assigned = _load_assignment_exclusions()
    assignment_lookup = student_profile.get("assignment_signals", {}).get("resource_assignments", {}) or {}

    def _append_rows(df: pd.DataFrame | None, resource_type: str) -> None:
        if df is None or df.empty:
            return
        for row in df.to_dict("records"):
            row_id = row.get("id")
            if resource_type in completed and row_id in completed.get(resource_type, set()):
                continue
            if str(row_id or "").strip() in assigned.get(resource_type, set()):
                continue
            score, reasons, ml_meta = _resource_feature_score(row, resource_type, student_profile)
            if score < 0:
                continue
            assignment_state = assignment_lookup.get((resource_type, str(row_id or "").strip()))
            ranked.append(_normalize_recommendation_row(row, resource_type, score, reasons, assignment_state, ml_meta))

    _append_rows(worksheets_df, "worksheet")
    _append_rows(exams_df, "exam")
    _append_rows(videos_df, "video")
    ranked.sort(
        key=lambda item: (
            -_safe_float(item.get("score", 0.0)),
            str(item.get("topic") or "").casefold(),
            str(item.get("title") or "").casefold(),
        )
    )
    if ranked_only:
        return ranked

    deduped: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    for item in ranked:
        key = (
            str(item.get("resource_type") or ""),
            str(item.get("topic") or "").casefold(),
            str(item.get("exercise_type") or "").casefold(),
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
        if len(deduped) >= max(1, limit):
            break
    return deduped


register_cache(_build_recommended_materials_cached)


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _history_window_days() -> int:
    raw_value = os.getenv("RECOMMENDATION_HISTORY_DAYS", "180")
    try:
        return max(30, min(int(raw_value), 3650))
    except Exception:
        return 180


def _history_cutoff_iso() -> str:
    return (_now_utc() - pd.Timedelta(days=_history_window_days())).isoformat()


def _days_since(value: Any) -> float:
    if value in (None, ""):
        return 999.0
    try:
        ts = pd.to_datetime(value, errors="coerce", utc=True)
        if pd.isna(ts):
            return 999.0
        return max(0.0, (_now_utc() - ts.to_pydatetime()).total_seconds() / 86400.0)
    except Exception:
        return 999.0


def _normalize_level(value: Any) -> str:
    return str(value or "").strip()


def _resource_level(row: dict, resource_type: str) -> str:
    if resource_type == "worksheet":
        return _normalize_level(row.get("level_or_band") or row.get("level"))
    if resource_type == "video":
        return _normalize_level(row.get("level_or_band") or row.get("level"))
    return _normalize_level(row.get("level") or row.get("level_or_band"))


def _resource_subject(row: dict) -> str:
    return normalize_subject(str(row.get("subject") or "").strip())


def _resource_stage(row: dict) -> str:
    return str(row.get("learner_stage") or "").strip()


def _resource_topic(row: dict) -> str:
    return str(row.get("topic") or "").strip()


def _dominant_exam_type(row: dict) -> str:
    exercise_types = row.get("exercise_types") or []
    if isinstance(exercise_types, list) and exercise_types:
        return str(exercise_types[0] or "").strip()
    exam_data = row.get("exam_data") or {}
    if isinstance(exam_data, dict):
        sections = exam_data.get("sections") or []
        if sections and isinstance(sections[0], dict):
            return str(sections[0].get("type") or "").strip()
    return ""


def _resource_exercise_type(row: dict, resource_type: str) -> str:
    if resource_type == "worksheet":
        return str(row.get("worksheet_type") or "").strip()
    if resource_type == "video":
        return "video"
    return _dominant_exam_type(row)


def _format_activity_label(value: Any) -> str:
    key = str(value or "").strip()
    if not key:
        return ""
    translated = t(key)
    if translated and translated != key:
        return translated
    return key.replace("_", " ").title()


@st.cache_data(ttl=45, show_spinner=False)
def _load_student_assignment_signal_rows(student_id: str) -> list[dict[str, Any]]:
    safe_student_id = str(student_id or "").strip()
    if not safe_student_id:
        return []
    try:
        assignment_rows = getattr(
            _execute_query_with_diagnostics(
                get_sb()
                .table("teacher_assignments")
                .select("id,teacher_id,assignment_type,source_record_id,status,topic,title,teacher_note,score_pct,updated_at")
                .eq("student_id", safe_student_id)
                .neq("status", "archived")
                .gte("updated_at", _history_cutoff_iso())
                .order("updated_at", desc=True)
                .limit(800),
                function_name="_load_student_assignment_signal_rows",
                source_name="teacher_assignments",
            ),
            "data",
            None,
        ) or []
    except Exception:
        return []

    teacher_ids = sorted({str(row.get("teacher_id") or "").strip() for row in assignment_rows if str(row.get("teacher_id") or "").strip()})
    teacher_names: dict[str, str] = {}
    if teacher_ids:
        try:
            profile_rows = getattr(
                _execute_query_with_diagnostics(
                    get_sb()
                    .table("profiles")
                    .select("user_id,display_name,username,email")
                    .in_("user_id", teacher_ids),
                    function_name="_load_student_assignment_signal_rows",
                    source_name="profiles",
                ),
                "data",
                None,
            ) or []
        except Exception:
            profile_rows = []
        for row in profile_rows:
            teacher_id = str(row.get("user_id") or "").strip()
            if not teacher_id:
                continue
            teacher_names[teacher_id] = str(
                row.get("display_name") or row.get("username") or row.get("email") or ""
            ).strip()

    return [
        {
            **row,
            "teacher_name": teacher_names.get(str(row.get("teacher_id") or "").strip(), ""),
        }
        for row in assignment_rows
    ]


register_cache(_load_student_assignment_signal_rows)


def _load_assignment_exclusions() -> dict[str, set]:
    excluded: dict[str, set] = {"worksheet": set(), "exam": set(), "video": set()}
    finalized_statuses = {"submitted", "graded", "completed", "cancelled", "archived"}
    for row in _load_student_assignment_signal_rows(str(get_current_user_id() or "")):
        assignment_type = str(row.get("assignment_type") or "").strip()
        source_record_id = row.get("source_record_id")
        status = str(row.get("status") or "").strip().lower()
        if assignment_type in excluded and source_record_id not in (None, "", 0, "0") and status in finalized_statuses:
            excluded[assignment_type].add(str(source_record_id).strip())
    return excluded


def _load_assignment_signal_profile() -> dict[str, Any]:
    profile = {
        "resource_assignments": {},
        "active_assigned_topic_tokens": set(),
        "unseen_video_topic_tokens": set(),
    }
    finalized_statuses = {"submitted", "graded", "completed", "cancelled", "archived"}

    for row in _load_student_assignment_signal_rows(str(get_current_user_id() or "")):
        assignment_type = str(row.get("assignment_type") or "").strip()
        if assignment_type not in {"worksheet", "exam", "video"}:
            continue
        source_record_id = str(row.get("source_record_id") or "").strip()
        if not source_record_id or source_record_id in {"0", "None", "nan"}:
            continue

        status = str(row.get("status") or "").strip().lower()
        attempt_count = _safe_int(row.get("attempt_count"), 0)
        topic = str(row.get("topic") or row.get("title") or "").strip()
        title = str(row.get("title") or "").strip()
        teacher_name = str(row.get("teacher_name") or "").strip()
        teacher_note = str(row.get("teacher_note") or "").strip()
        is_completed = status in finalized_statuses or (assignment_type == "video" and attempt_count > 0)
        is_unseen = assignment_type == "video" and attempt_count <= 0 and status in {"assigned", "started", "overdue"}

        assignment_key = (assignment_type, source_record_id)
        existing = profile["resource_assignments"].get(assignment_key)
        current_priority = 0 if not is_completed else 1
        existing_priority = 99
        if existing:
            existing_priority = 0 if not bool(existing.get("is_completed")) else 1
        if existing is None or current_priority < existing_priority:
            profile["resource_assignments"][assignment_key] = {
                "assignment_id": _safe_int(row.get("id"), 0),
                "status": status,
                "attempt_count": attempt_count,
                "teacher_name": teacher_name,
                "teacher_note": teacher_note,
                "topic": topic,
                "title": title,
                "is_completed": is_completed,
                "is_unseen": is_unseen,
            }

        if not is_completed:
            profile["active_assigned_topic_tokens"].update(_topic_tokens(topic, title, teacher_note))
        if is_unseen:
            profile["unseen_video_topic_tokens"].update(_topic_tokens(topic, title, teacher_note))

    return profile


def _load_assignment_behavior_profile() -> dict[str, Any]:
    profile = {
        "kind_success": {},
        "kind_completion": {},
        "topic_success": {},
        "recent_teacher_topics": set(),
    }
    kind_map = {
        "lesson_plan_topic": "plan",
        "worksheet": "worksheet",
        "exam": "exam",
    }
    for row in _load_student_assignment_signal_rows(str(get_current_user_id() or "")):
        kind = kind_map.get(str(row.get("assignment_type") or "").strip())
        if not kind:
            continue
        topic = str(row.get("topic") or row.get("title") or "").strip()
        status = str(row.get("status") or "").strip().lower()
        score = row.get("score_pct")
        try:
            score_value = float(score) if score not in (None, "") else None
        except Exception:
            score_value = None
        if status in {"started", "submitted", "graded", "completed"} and topic:
            profile["recent_teacher_topics"].update(_topic_tokens(topic))
        stats = profile["kind_success"].setdefault(kind, {"count": 0.0, "score_total": 0.0})
        completion_stats = profile["kind_completion"].setdefault(kind, {"assigned": 0.0, "completed": 0.0})
        completion_stats["assigned"] += 1.0
        if status in {"graded", "completed"}:
            completion_stats["completed"] += 1.0
        if score_value is not None:
            stats["count"] += 1.0
            stats["score_total"] += score_value
        if topic:
            topic_stats = profile["topic_success"].setdefault(topic.casefold(), {"count": 0.0, "score_total": 0.0})
            if score_value is not None:
                topic_stats["count"] += 1.0
                topic_stats["score_total"] += score_value

    for kind, stats in list(profile["kind_success"].items()):
        count = stats.get("count") or 0.0
        profile["kind_success"][kind] = ((stats.get("score_total") or 0.0) / count / 100.0) if count else 0.0
    for kind, stats in list(profile["kind_completion"].items()):
        assigned = stats.get("assigned") or 0.0
        profile["kind_completion"][kind] = ((stats.get("completed") or 0.0) / assigned) if assigned else 0.0
    for topic_key, stats in list(profile["topic_success"].items()):
        count = stats.get("count") or 0.0
        profile["topic_success"][topic_key] = ((stats.get("score_total") or 0.0) / count / 100.0) if count else 0.0
    return profile


def _topic_tokens(*values: Any) -> set[str]:
    tokens: set[str] = set()
    for value in values:
        for raw in str(value or "").replace("/", " ").replace("-", " ").split():
            cleaned = "".join(ch for ch in raw.casefold() if ch.isalnum())
            if len(cleaned) >= 3:
                tokens.add(cleaned)
    return tokens


def _topic_overlap_score(topic_tokens: set[str], reference_tokens: set[str], *, scale: float = 3.0) -> float:
    if not topic_tokens or not reference_tokens:
        return 0.0
    overlap = len(topic_tokens & reference_tokens)
    return _clamp(overlap / max(scale, 1.0))


def _load_program_signals() -> dict[str, Any]:
    enriched = load_enriched_program_assignments_for_current_student()
    signals = {
        "subjects": set(),
        "subject_levels": {},
        "subject_stages": {},
        "active_topic_ids": set(),
        "next_topic_ids": set(),
        "pending_topic_ids": set(),
        "review_topic_ids": set(),
        "next_topic_titles": [],
        "topic_tokens": set(),
        "next_topic_tokens": set(),
        "pending_topic_tokens": set(),
        "review_topic_tokens": set(),
        "worksheet_types": set(),
        "exam_types": set(),
    }
    latest_by_subject: dict[str, dict] = {}
    for assignment in enriched:
        program = assignment.get("program") or {}
        subject = normalize_subject(program.get("subject") or assignment.get("subject_key") or "")
        if not subject:
            continue
        raw_sequence = program.get("sequence_order") or assignment.get("sequence_order") or 0
        try:
            sequence = int(raw_sequence or 0)
        except Exception:
            sequence = 0
        stamp = str(
            assignment.get("updated_at")
            or assignment.get("assigned_at")
            or program.get("updated_at")
            or program.get("created_at")
            or ""
        ).strip()
        current = latest_by_subject.get(subject)
        current_sequence = int((current or {}).get("_sequence_order") or 0)
        current_stamp = str((current or {}).get("_sort_stamp") or "")
        if current is None or sequence > current_sequence or (sequence == current_sequence and stamp > current_stamp):
            latest_by_subject[subject] = {
                **assignment,
                "_sequence_order": sequence,
                "_sort_stamp": stamp,
            }

    for assignment in latest_by_subject.values():
        program = assignment.get("program") or {}
        subject = normalize_subject(program.get("subject") or assignment.get("subject_key") or "")
        if subject:
            signals["subjects"].add(subject)
            level = _normalize_level(program.get("level_or_band") or assignment.get("level_or_band") or "")
            stage = str(program.get("learner_stage") or assignment.get("learner_stage") or "").strip()
            if level and subject not in signals["subject_levels"]:
                signals["subject_levels"][subject] = level
            if stage and subject not in signals["subject_stages"]:
                signals["subject_stages"][subject] = stage
        progress_map = assignment.get("progress_map") or {}
        latest_completed_position = 0
        topic_position = 0
        ordered_topics: list[tuple[int, dict, dict]] = []
        for unit in program.get("units") or []:
            for topic in unit.get("topics") or []:
                topic_position += 1
                topic_id = int(topic.get("topic_id") or 0)
                topic_progress = progress_map.get(topic_id, {}) if topic_id else {}
                if truthy_flag(topic_progress.get("teacher_done")):
                    latest_completed_position = max(latest_completed_position, topic_position)
                ordered_topics.append((topic_position, topic, topic_progress))

        next_topic_added = False
        for position, topic, topic_progress in ordered_topics:
            title = str(topic.get("title") or "").strip()
            summary = str(topic.get("student_summary") or topic.get("lesson_focus") or topic.get("subtopic") or "").strip()
            topic_tokens = _topic_tokens(title, summary)
            topic_id = int(topic.get("topic_id") or 0)
            if truthy_flag(topic_progress.get("teacher_done")) and truthy_flag(topic_progress.get("student_done")):
                signals["review_topic_tokens"].update(topic_tokens)
                if topic_id > 0:
                    signals["review_topic_ids"].add(topic_id)
            if not truthy_flag(topic_progress.get("teacher_done")) and latest_completed_position > 0 and position < latest_completed_position:
                signals["pending_topic_tokens"].update(topic_tokens)
                if topic_id > 0:
                    signals["pending_topic_ids"].add(topic_id)
            if truthy_flag(topic_progress.get("teacher_done")):
                continue
            if topic_id > 0:
                signals["active_topic_ids"].add(topic_id)
            if title:
                signals["next_topic_titles"].append(title)
            signals["topic_tokens"].update(topic_tokens)
            if not next_topic_added:
                signals["next_topic_tokens"].update(topic_tokens)
                if topic_id > 0:
                    signals["next_topic_ids"].add(topic_id)
                next_topic_added = True
            if not title:
                continue
            for worksheet_type in topic.get("suggested_worksheet_types") or []:
                cleaned = str(worksheet_type or "").strip()
                if cleaned:
                    signals["worksheet_types"].add(cleaned)
            for exam_type in topic.get("suggested_exam_exercise_types") or []:
                cleaned = str(exam_type or "").strip()
                if cleaned:
                    signals["exam_types"].add(cleaned)
    return signals


def _level_similarity(target_level: str, resource_level: str) -> float:
    target_level = _normalize_level(target_level)
    resource_level = _normalize_level(resource_level)
    if not target_level or not resource_level:
        return 0.55
    if target_level == resource_level:
        return 1.0

    cefr = ["A1", "A2", "B1", "B2", "C1", "C2"]
    bands = ["beginner_band", "intermediate_band", "advanced_band"]
    if target_level in cefr and resource_level in cefr:
        distance = abs(cefr.index(target_level) - cefr.index(resource_level))
        return {1: 0.82, 2: 0.6}.get(distance, 0.25)
    if target_level in bands and resource_level in bands:
        distance = abs(bands.index(target_level) - bands.index(resource_level))
        return {1: 0.8, 2: 0.45}.get(distance, 0.25)
    return 0.4


def _fit_need_weights(progress_df: pd.DataFrame) -> list[float]:
    rows = []
    for _, row in progress_df.iterrows():
        accuracy = _safe_float(row.get("accuracy_pct")) / 100.0
        attempted = _safe_float(row.get("total_attempted"))
        days = _days_since(row.get("last_practiced"))
        rows.append(
            (
                1.0,
                _clamp(1.0 - accuracy),
                _clamp(min(attempted, 12.0) / 12.0),
                _clamp(min(days, 30.0) / 30.0),
            )
        )

    if not rows:
        return [-0.1, 2.2, 0.7, 0.9]

    weights = [0.0, 1.4, 0.4, 0.5]
    learning_rate = 0.35
    targets = []
    for _, row in progress_df.iterrows():
        accuracy = _safe_float(row.get("accuracy_pct"))
        attempted = _safe_float(row.get("total_attempted"))
        target = 1.0 if accuracy < 78.0 else 0.0
        if accuracy < 88.0 and attempted <= 2:
            target = 1.0
        targets.append(target)

    for _ in range(120):
        grads = [0.0, 0.0, 0.0, 0.0]
        for features, target in zip(rows, targets):
            prediction = _sigmoid(sum(weight * value for weight, value in zip(weights, features)))
            error = prediction - target
            for idx, value in enumerate(features):
                grads[idx] += error * value
        scale = 1.0 / max(1, len(rows))
        for idx in range(len(weights)):
            weights[idx] -= learning_rate * grads[idx] * scale
    return weights


def _build_student_need_profile() -> dict[str, Any]:
    progress = load_practice_progress()
    user_id = get_current_user_id()
    profile_row = load_profile_row(user_id) if user_id else {}

    profile = {
        "primary_subjects": [normalize_subject(value) for value in (profile_row.get("primary_subjects") or []) if str(value or "").strip()],
        "subject_need": {},
        "subject_attempts": {},
        "topic_need": {},
        "exercise_need": {},
        "subject_level": {},
        "subject_stage": {},
        "overall_accuracy": {},
        "weights": _fit_need_weights(progress) if not progress.empty else [-0.1, 2.2, 0.7, 0.9],
    }

    if progress.empty:
        return profile

    weighted_level_votes: dict[str, dict[str, float]] = {}
    weighted_stage_votes: dict[str, dict[str, float]] = {}

    for _, row in progress.iterrows():
        subject = normalize_subject(row.get("subject"))
        topic = str(row.get("topic") or "").strip()
        exercise_type = str(row.get("exercise_type") or "").strip()
        level = _normalize_level(row.get("level"))
        accuracy = _safe_float(row.get("accuracy_pct")) / 100.0
        attempted = _safe_float(row.get("total_attempted"))
        stage = str(row.get("learner_stage") or "").strip()
        days = _days_since(row.get("last_practiced"))
        x = (
            1.0,
            _clamp(1.0 - accuracy),
            _clamp(min(attempted, 12.0) / 12.0),
            _clamp(min(days, 30.0) / 30.0),
        )
        need_strength = _sigmoid(sum(weight * value for weight, value in zip(profile["weights"], x)))
        profile["subject_need"][subject] = max(
            need_strength,
            _safe_float(profile["subject_need"].get(subject, 0.0)),
        )
        if topic:
            profile["topic_need"][topic.casefold()] = max(
                need_strength,
                _safe_float(profile["topic_need"].get(topic.casefold(), 0.0)),
            )
        if exercise_type:
            current = _safe_float(profile["exercise_need"].get(exercise_type, 0.0))
            profile["exercise_need"][exercise_type] = max(current, need_strength)

        profile["overall_accuracy"].setdefault(subject, {"correct": 0.0, "attempted": 0.0})
        profile["overall_accuracy"][subject]["correct"] += attempted * accuracy
        profile["overall_accuracy"][subject]["attempted"] += attempted
        profile["subject_attempts"][subject] = _safe_float(profile["subject_attempts"].get(subject, 0.0)) + attempted

        if level:
            weighted_level_votes.setdefault(subject, {})
            weighted_level_votes[subject][level] = weighted_level_votes[subject].get(level, 0.0) + attempted
        if stage:
            weighted_stage_votes.setdefault(subject, {})
            weighted_stage_votes[subject][stage] = weighted_stage_votes[subject].get(stage, 0.0) + attempted

    for subject, levels in weighted_level_votes.items():
        if levels:
            profile["subject_level"][subject] = max(levels.items(), key=lambda item: item[1])[0]
    for subject, stages in weighted_stage_votes.items():
        if stages:
            profile["subject_stage"][subject] = max(stages.items(), key=lambda item: item[1])[0]
    for subject, totals in profile["overall_accuracy"].items():
        attempted = totals.get("attempted") or 0.0
        profile["overall_accuracy"][subject] = (totals.get("correct") or 0.0) / attempted if attempted else 0.0

    return profile


def _resource_feature_score(row: dict, resource_type: str, student_profile: dict[str, Any]) -> tuple[float, list[str], dict[str, float]]:
    subject = _resource_subject(row)
    topic = _resource_topic(row)
    stage = _resource_stage(row)
    level = _resource_level(row, resource_type)
    exercise_type = _resource_exercise_type(row, resource_type)

    primary_subjects = student_profile.get("primary_subjects") or []
    subject_need = _safe_float(student_profile.get("subject_need", {}).get(subject, 0.0))
    topic_need = _safe_float(student_profile.get("topic_need", {}).get(topic.casefold(), 0.0)) if topic else 0.0
    exercise_need = _safe_float(student_profile.get("exercise_need", {}).get(exercise_type, 0.0)) if exercise_type else 0.0
    program_subjects = set(student_profile.get("program_signals", {}).get("subjects") or set())
    program_levels = student_profile.get("program_signals", {}).get("subject_levels", {}) or {}
    program_stages = student_profile.get("program_signals", {}).get("subject_stages", {}) or {}
    subject_attempts = _safe_float(student_profile.get("subject_attempts", {}).get(subject, 0.0))
    bootstrap_mode = bool(program_subjects) and subject_attempts < 5.0
    target_level = student_profile.get("subject_level", {}).get(subject, "") or program_levels.get(subject, "")
    target_stage = student_profile.get("subject_stage", {}).get(subject, "") or program_stages.get(subject, "")
    accuracy = _safe_float(student_profile.get("overall_accuracy", {}).get(subject, 0.0))
    program_signals = student_profile.get("program_signals", {}) or {}
    behavior_profile = student_profile.get("assignment_behavior", {}) or {}
    assignment_signals = student_profile.get("assignment_signals", {}) or {}
    resource_tokens = _topic_tokens(topic, row.get("title"))
    resource_assignment = (assignment_signals.get("resource_assignments") or {}).get(
        (resource_type, str(row.get("id") or "").strip())
    )
    assigned_active = bool(resource_assignment) and not bool((resource_assignment or {}).get("is_completed"))
    assigned_unseen = bool(resource_assignment) and bool((resource_assignment or {}).get("is_unseen"))
    active_topic_ids = list(program_signals.get("active_topic_ids") or set())
    priority_topic_ids = list(
        (program_signals.get("next_topic_ids") or set())
        | (program_signals.get("pending_topic_ids") or set())
        | (program_signals.get("review_topic_ids") or set())
    )
    topic_alignment = topic_resource_alignment_features(
        resource_type,
        row.get("id"),
        priority_topic_ids or active_topic_ids,
        student_id=get_current_user_id(),
    )

    if bootstrap_mode and program_subjects and subject not in program_subjects:
        return -1.0, [], {}
    if bootstrap_mode and target_level and level and _normalize_level(level) != _normalize_level(target_level):
        return -1.0, [], {}

    subject_focus = 1.0 if subject_need > 0 else (0.8 if subject in primary_subjects else 0.45)
    if program_subjects:
        if subject in program_subjects:
            subject_focus = max(subject_focus, 1.0 if bootstrap_mode else 0.92)
        else:
            subject_focus = min(subject_focus, 0.2)
    topic_support = max(topic_need, subject_need * 0.55)
    type_support = max(exercise_need, subject_need * 0.45)
    level_fit = _level_similarity(target_level, level)
    stage_fit = 1.0 if target_stage and stage and target_stage == stage else (0.65 if not target_stage or not stage else 0.35)
    program_topic_overlap = 0.0
    if resource_tokens and program_signals.get("topic_tokens"):
        overlap = len(resource_tokens & set(program_signals.get("topic_tokens") or set()))
        program_topic_overlap = _clamp(overlap / 3.0)
    next_topic_overlap = _topic_overlap_score(resource_tokens, set(program_signals.get("next_topic_tokens") or set()))
    pending_topic_overlap = _topic_overlap_score(resource_tokens, set(program_signals.get("pending_topic_tokens") or set()))
    review_topic_overlap = _topic_overlap_score(resource_tokens, set(program_signals.get("review_topic_tokens") or set()))
    assigned_topic_overlap = _topic_overlap_score(resource_tokens, set(assignment_signals.get("active_assigned_topic_tokens") or set()), scale=2.0)
    unseen_video_overlap = _topic_overlap_score(resource_tokens, set(assignment_signals.get("unseen_video_topic_tokens") or set()), scale=2.0)
    program_subject_fit = 1.0 if subject and subject in (program_signals.get("subjects") or set()) else 0.0
    program_type_fit = 0.0
    if resource_type == "worksheet" and exercise_type and exercise_type in (program_signals.get("worksheet_types") or set()):
        program_type_fit = 1.0
    elif resource_type == "exam" and exercise_type and exercise_type in (program_signals.get("exam_types") or set()):
        program_type_fit = 1.0

    review_boost = 0.0
    stretch_boost = 0.0
    format_fit = _safe_float((behavior_profile.get("kind_success") or {}).get(resource_type, 0.0))
    completion_fit = _safe_float((behavior_profile.get("kind_completion") or {}).get(resource_type, 0.0))
    topic_success = _safe_float((behavior_profile.get("topic_success") or {}).get(topic.casefold(), 0.0)) if topic else 0.0
    recent_teacher_overlap = _topic_overlap_score(resource_tokens, set(behavior_profile.get("recent_teacher_topics") or set()), scale=2.0)
    if topic_need >= 0.6:
        review_boost = 0.18
    if review_topic_overlap >= 0.34:
        review_boost = max(review_boost, 0.16)
    if accuracy >= 0.82 and level_fit >= 0.8 and topic_need < 0.35:
        stretch_boost = 0.1
    if next_topic_overlap >= 0.34:
        stretch_boost = max(stretch_boost, 0.12)
    assignment_boost = 0.0
    if assigned_active:
        assignment_boost += 0.14
    if assigned_active and assigned_topic_overlap >= 0.34:
        assignment_boost += 0.08
    if assigned_unseen:
        assignment_boost += 0.12
    if assigned_unseen and resource_type == "video":
        assignment_boost += 0.08
    if assigned_unseen and resource_type == "video" and (
        topic_need >= 0.45
        or review_topic_overlap >= 0.34
        or recent_teacher_overlap >= 0.34
        or unseen_video_overlap >= 0.34
        or topic_alignment["direct_topic_link"] >= 1.0
        or topic_alignment["explicit_topic_match"] >= 0.5
    ):
        assignment_boost += 0.22

    score = (
        0.28 * subject_focus
        + 0.28 * topic_support
        + 0.18 * type_support
        + 0.14 * level_fit
        + 0.08 * stage_fit
        + 0.08 * program_topic_overlap
        + 0.08 * next_topic_overlap
        + 0.06 * review_topic_overlap
        + 0.04 * pending_topic_overlap
        + 0.04 * program_subject_fit
        + 0.04 * program_type_fit
        + 0.06 * format_fit
        + 0.04 * completion_fit
        + 0.05 * recent_teacher_overlap
        + 0.05 * assigned_topic_overlap
        + 0.05 * unseen_video_overlap
        + 0.08 * topic_alignment["explicit_topic_match"]
        + 0.04 * topic_alignment["explicit_topic_support"]
        + 0.06 * topic_alignment["direct_topic_link"]
        + 0.04 * topic_alignment["topic_kind_prior"]
        + review_boost
        + stretch_boost
        + assignment_boost
    )
    score -= 0.04 * topic_alignment["topic_match_ambiguity"]
    if topic_success >= 0.82 and topic_need < 0.28:
        score -= 0.08
    elif topic_success <= 0.68 and topic:
        score += 0.08

    ml_features = {
        f"kind_{resource_type}": 1.0,
        "subject_in_program": 1.0 if subject and subject in (program_signals.get("subjects") or set()) else 0.0,
        "level_fit": level_fit,
        "stage_fit": stage_fit,
        "next_topic_overlap": next_topic_overlap,
        "review_topic_overlap": review_topic_overlap,
        "pending_topic_overlap": pending_topic_overlap,
        "program_subject_fit": program_subject_fit,
        "program_type_fit": program_type_fit,
        "topic_need": topic_need,
        "subject_need": subject_need,
        "exercise_need": exercise_need,
        "completion_fit": completion_fit,
        "format_fit": format_fit,
        "assigned_active": 1.0 if assigned_active else 0.0,
        "assigned_unseen": 1.0 if assigned_unseen else 0.0,
        "assigned_topic_overlap": assigned_topic_overlap,
        "unseen_video_overlap": unseen_video_overlap,
        "explicit_topic_match": topic_alignment["explicit_topic_match"],
        "explicit_topic_support": topic_alignment["explicit_topic_support"],
        "direct_topic_link": topic_alignment["direct_topic_link"],
        "topic_kind_prior": topic_alignment["topic_kind_prior"],
        "topic_match_ambiguity": topic_alignment["topic_match_ambiguity"],
        "topic_success_penalty": 1.0 if topic_success >= 0.82 and topic_need < 0.28 else 0.0,
        "topic_in_program": program_topic_overlap,
    }
    safe_student_id = str(get_current_user_id() or "").strip()
    ml_score = score_student_resource_candidate(ml_features, student_profile, student_id=safe_student_id)
    ml_blend_weight = student_recommendation_blend_weight(safe_student_id, student_profile) if safe_student_id else 0.42
    score += ml_blend_weight * ml_score

    reasons: list[str] = []
    if assigned_unseen and resource_type == "video" and topic:
        reasons.append(t("student_material_reason_teacher_assigned_review", topic=topic))
    elif assigned_active:
        reasons.append(t("student_material_reason_teacher_assigned"))
    if topic_alignment["direct_topic_link"] >= 1.0 and topic:
        reasons.append(t("student_material_reason_program_topic", topic=topic))
    if topic_need >= 0.65 and topic:
        reasons.append(t("student_material_reason_revisit_topic", topic=topic))
    elif subject_need >= 0.55 and subject:
        reasons.append(t("student_material_reason_subject_support", subject=subject_label(subject)))
    if exercise_need >= 0.58 and exercise_type:
        reasons.append(t("student_material_reason_exercise_support", exercise_type=_format_activity_label(exercise_type)))
    if next_topic_overlap >= 0.34 and topic:
        reasons.append(t("student_material_reason_program_topic", topic=topic))
    elif review_topic_overlap >= 0.34 and topic:
        reasons.append(t("student_material_reason_revisit_topic", topic=topic))
    elif pending_topic_overlap >= 0.34 and topic:
        reasons.append(t("student_material_reason_program_topic", topic=topic))
    elif program_topic_overlap >= 0.34 and topic:
        reasons.append(t("student_material_reason_program_topic", topic=topic))
    elif recent_teacher_overlap >= 0.34 and topic:
        reasons.append(t("student_material_reason_subject_support", subject=subject_label(subject)))
    elif program_type_fit >= 1.0 and exercise_type:
        reasons.append(t("student_material_reason_program_style"))
    if level_fit >= 0.95 and level:
        reasons.append(t("student_material_reason_level_fit", level=level))
    elif stretch_boost > 0 and level:
        reasons.append(t("student_material_reason_level_stretch", level=level))
    if ml_score >= 0.72:
        reasons.append(t("student_material_reason_ml_fit"))
    if not reasons:
        reasons.append(t("student_material_reason_balanced"))

    return score, reasons[:3], {"ml_score": round(ml_score, 4), "ml_blend_weight": round(ml_blend_weight, 4)}


def _normalize_recommendation_row(
    row: dict,
    resource_type: str,
    score: float,
    reasons: list[str],
    assignment_state: dict[str, Any] | None = None,
    ml_meta: dict[str, float] | None = None,
) -> dict[str, Any]:
    return {
        "resource_type": resource_type,
        "id": row.get("id"),
        "title": str(row.get("title") or "").strip(),
        "subject": str(row.get("subject") or "").strip(),
        "topic": _resource_topic(row),
        "learner_stage": _resource_stage(row),
        "level": _resource_level(row, resource_type),
        "exercise_type": _resource_exercise_type(row, resource_type),
        "score": round(score, 4),
        "reasons": reasons,
        "assigned_resource": bool(assignment_state),
        "assignment_id": _safe_int((assignment_state or {}).get("assignment_id"), 0),
        "assignment_status": str((assignment_state or {}).get("status") or "").strip(),
        "assignment_attempt_count": _safe_int((assignment_state or {}).get("attempt_count"), 0),
        "assignment_teacher_name": str((assignment_state or {}).get("teacher_name") or "").strip(),
        "ml_score": _safe_float((ml_meta or {}).get("ml_score"), 0.0),
        "ml_blend_weight": _safe_float((ml_meta or {}).get("ml_blend_weight"), 0.0),
        "row": row,
    }


def build_recommended_materials(
    worksheets_df: pd.DataFrame | None = None,
    exams_df: pd.DataFrame | None = None,
    videos_df: pd.DataFrame | None = None,
    *,
    limit: int = 6,
) -> list[dict[str, Any]]:
    return _build_recommended_materials_cached(
        str(get_current_user_id() or ""),
        _frame_records(worksheets_df),
        _frame_records(exams_df),
        _frame_records(videos_df),
        limit=limit,
        ranked_only=False,
    )


def rank_recommended_materials(
    worksheets_df: pd.DataFrame | None = None,
    exams_df: pd.DataFrame | None = None,
    videos_df: pd.DataFrame | None = None,
) -> list[dict[str, Any]]:
    return _build_recommended_materials_cached(
        str(get_current_user_id() or ""),
        _frame_records(worksheets_df),
        _frame_records(exams_df),
        _frame_records(videos_df),
        ranked_only=True,
    )
