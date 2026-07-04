from __future__ import annotations

from collections import Counter
import math
from typing import Any

import pandas as pd

from core.database import get_sb
from core.state import get_current_user_id
from helpers.archive_utils import truthy_flag
from helpers.learning_programs import _load_program_assignments_for_teacher_cached, load_assignment_progress_map, load_learning_program
from helpers.teacher_student_integration import _load_teacher_assignment_progress_cached
from helpers.recommendation_models import (
    _fit_linear_model,
    _load_teacher_material_activity_rows,
    _load_teacher_recommendation_events,
    _norm_key,
    _score_linear_model,
    _safe_float,
    _tokenize,
    _weighted_token_score,
    build_teacher_material_feed_profile,
    normalize_subject,
    topic_resource_alignment_features,
)
from helpers.student_recommendation_ml import _clamp, _compute_metrics


def _target_to_label(target: float) -> int:
    return 1 if float(target or 0.0) >= 0.62 else 0


def _sigmoid(value: float) -> float:
    if value >= 0:
        z = math.exp(-value)
        return 1.0 / (1.0 + z)
    z = math.exp(value)
    return z / (1.0 + z)


def _assignment_score_value(row: dict[str, Any]) -> float | None:
    latest = row.get("latest_attempt") if isinstance(row.get("latest_attempt"), dict) else {}
    value = latest.get("score_pct", row.get("score_pct"))
    try:
        if value in (None, ""):
            return None
        return float(value)
    except Exception:
        return None


def _assignment_status_pressure(status: str) -> float:
    status = str(status or "").strip().lower()
    mapping = {
        "overdue": 1.0,
        "assigned": 0.9,
        "started": 0.82,
        "submitted": 0.7,
        "graded": 0.28,
        "completed": 0.2,
        "cancelled": 0.05,
    }
    return mapping.get(status, 0.25)


def _topic_tokens(*values: Any) -> set[str]:
    tokens: set[str] = set()
    for value in values:
        for raw in _tokenize(value):
            if len(raw) >= 3:
                tokens.add(raw)
    return tokens


def _topic_progress_rows(topic: dict[str, Any], progress_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    topic_title = str(topic.get("title") or topic.get("lesson_focus") or topic.get("subtopic") or "").strip()
    topic_tokens = _topic_tokens(topic_title, topic.get("student_summary"), topic.get("lesson_focus"))
    if not topic_tokens:
        return []
    matches: list[dict[str, Any]] = []
    for row in progress_rows or []:
        row_topic = str(row.get("topic") or row.get("title") or "").strip()
        row_tokens = _topic_tokens(row_topic)
        if not row_tokens:
            continue
        if row_topic.casefold() == topic_title.casefold() or len(topic_tokens & row_tokens) >= 2:
            matches.append(row)
    return matches


def _build_recommendation_signal(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not rows:
        return {
            "score_gap": 0.2,
            "retry_pressure": 0.1,
            "status_pressure": 0.25,
            "recent_score": None,
            "active_assignments": 0,
        }

    score_gaps: list[float] = []
    retry_pressures: list[float] = []
    status_pressures: list[float] = []
    scores: list[float] = []
    active_assignments = 0
    for row in rows:
        score = _assignment_score_value(row)
        score_gaps.append(_clamp((82.0 - score) / 42.0) if score is not None else 0.35)
        retry_pressures.append(_clamp((max(int(row.get("attempt_count") or 0), 1) - 1.0) / 3.0))
        status_value = _assignment_status_pressure(str(row.get("status") or ""))
        status_pressures.append(status_value)
        if status_value >= 0.7:
            active_assignments += 1
        if score is not None:
            scores.append(score)
    return {
        "score_gap": max(score_gaps) if score_gaps else 0.2,
        "retry_pressure": max(retry_pressures) if retry_pressures else 0.1,
        "status_pressure": max(status_pressures) if status_pressures else 0.25,
        "recent_score": min(scores) if scores else None,
        "active_assignments": active_assignments,
    }


def _topic_signal_from_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    signal = _build_recommendation_signal(rows)
    signal["attempt_count"] = max((int(row.get("attempt_count") or 0) for row in rows), default=0)
    return signal


def _load_teacher_objective_events(teacher_id: str) -> list[dict[str, Any]]:
    safe_teacher_id = str(teacher_id or "").strip()
    if not safe_teacher_id:
        return []
    try:
        return (
            get_sb()
            .table("learning_program_recommendation_events")
            .select(
                "teacher_id,student_id,learning_program_assignment_id,learning_program_topic_id,"
                "recommendation_bucket,recommendation_focus_kind,event_type,event_weight,created_at,metadata"
            )
            .eq("teacher_id", safe_teacher_id)
            .order("created_at", desc=True)
            .limit(4000)
            .execute()
            .data
            or []
        )
    except Exception:
        return []


def _summarize_teacher_objective_events(rows: list[dict[str, Any]]) -> dict[tuple[int, int, str], dict[str, Any]]:
    summary: dict[tuple[int, int, str], dict[str, Any]] = {}
    for row in rows:
        assignment_id = int(row.get("learning_program_assignment_id") or 0)
        topic_id = int(row.get("learning_program_topic_id") or 0)
        bucket = _norm_key(row.get("recommendation_bucket"))
        if assignment_id <= 0 or topic_id <= 0 or not bucket:
            continue
        key = (assignment_id, topic_id, bucket)
        item = summary.setdefault(
            key,
            {
                "count": 0,
                "assigned_count": 0,
                "started_count": 0,
                "completed_count": 0,
                "improved_count": 0,
                "last_event_type": "",
                "last_event_at": "",
            },
        )
        item["count"] += 1
        event_type = _norm_key(row.get("event_type"))
        if event_type == "assignment_created":
            item["assigned_count"] += 1
        elif event_type == "student_started":
            item["started_count"] += 1
        elif event_type in {"student_completed", "teacher_marked_done"}:
            item["completed_count"] += 1
        elif event_type == "student_improved":
            item["improved_count"] += 1
        created_at = str(row.get("created_at") or "")
        if created_at > str(item.get("last_event_at") or ""):
            item["last_event_at"] = created_at
            item["last_event_type"] = event_type
    return summary


def _teacher_objective_target(event_summary: dict[str, Any]) -> float:
    if not event_summary:
        return 0.18
    if int(event_summary.get("improved_count") or 0) > 0:
        return 1.0
    if int(event_summary.get("completed_count") or 0) > 0:
        return 0.9
    if int(event_summary.get("started_count") or 0) > 0:
        return 0.78
    if int(event_summary.get("assigned_count") or 0) > 0:
        return 0.64
    if int(event_summary.get("count") or 0) > 0:
        return 0.28
    return 0.18


def _base_teacher_objective_weights() -> dict[str, float]:
    return {
        "bias": -0.18,
        "bucket_next_topic": 0.16,
        "bucket_review": 0.24,
        "bucket_pending_gap": 0.18,
        "progress_gap": 0.34,
        "overall_score_gap": 0.24,
        "overall_retry_pressure": 0.18,
        "overall_status_pressure": 0.26,
        "topic_score_gap": 0.42,
        "topic_retry_pressure": 0.28,
        "topic_status_pressure": 0.26,
        "needs_practice": 0.52,
        "teacher_done": -0.22,
        "student_done": 0.18,
        "is_after_latest_completed": 0.22,
        "is_before_latest_completed": 0.34,
        "is_next_unfinished": 0.46,
        "has_recent_low_score": 0.22,
        "historical_event_density": 0.18,
        "historical_assignment_rate": 0.28,
        "historical_improvement_rate": 0.42,
    }


def _teacher_objective_candidate_features(candidate: dict[str, Any]) -> dict[str, float]:
    bucket = _norm_key(candidate.get("recommendation_bucket"))
    overall_signal = candidate.get("overall_signal") if isinstance(candidate.get("overall_signal"), dict) else {}
    topic_signal = candidate.get("topic_signal") if isinstance(candidate.get("topic_signal"), dict) else {}
    event_summary = candidate.get("event_summary") if isinstance(candidate.get("event_summary"), dict) else {}
    historical_count = max(1, int(event_summary.get("count") or 0))
    return {
        f"bucket_{bucket}": 1.0 if bucket else 0.0,
        "progress_gap": _safe_float(candidate.get("progress_gap"), 0.0),
        "overall_score_gap": _safe_float(overall_signal.get("score_gap"), 0.0),
        "overall_retry_pressure": _safe_float(overall_signal.get("retry_pressure"), 0.0),
        "overall_status_pressure": _safe_float(overall_signal.get("status_pressure"), 0.0),
        "topic_score_gap": _safe_float(topic_signal.get("score_gap"), 0.0),
        "topic_retry_pressure": _safe_float(topic_signal.get("retry_pressure"), 0.0),
        "topic_status_pressure": _safe_float(topic_signal.get("status_pressure"), 0.0),
        "needs_practice": 1.0 if bool(candidate.get("needs_practice")) else 0.0,
        "teacher_done": 1.0 if bool(candidate.get("teacher_done")) else 0.0,
        "student_done": 1.0 if bool(candidate.get("student_done")) else 0.0,
        "is_after_latest_completed": 1.0 if bool(candidate.get("is_after_latest_completed")) else 0.0,
        "is_before_latest_completed": 1.0 if bool(candidate.get("is_before_latest_completed")) else 0.0,
        "is_next_unfinished": 1.0 if bool(candidate.get("is_next_unfinished")) else 0.0,
        "has_recent_low_score": 1.0 if _safe_float(topic_signal.get("recent_score"), 100.0) < 75.0 else 0.0,
        "historical_event_density": _clamp(historical_count / 6.0),
        "historical_assignment_rate": _clamp(_safe_float(event_summary.get("assigned_count"), 0.0) / historical_count),
        "historical_improvement_rate": _clamp(_safe_float(event_summary.get("improved_count"), 0.0) / historical_count),
    }


def build_teacher_objective_samples(teacher_id: str | None = None) -> list[dict[str, Any]]:
    safe_teacher_id = str(teacher_id or get_current_user_id() or "").strip()
    if not safe_teacher_id:
        return []
    assignments_df = _load_program_assignments_for_teacher_cached(safe_teacher_id, limit=240)
    if assignments_df is None or assignments_df.empty:
        return []
    teacher_assignments = _load_teacher_assignment_progress_cached(safe_teacher_id)
    teacher_assignments_df = pd.DataFrame(teacher_assignments) if teacher_assignments else pd.DataFrame()
    objective_events = _summarize_teacher_objective_events(_load_teacher_objective_events(safe_teacher_id))
    samples: list[dict[str, Any]] = []

    for row in assignments_df.to_dict("records"):
        assignment_id = int(row.get("id") or 0)
        program_id = int(row.get("program_id") or 0)
        student_id = str(row.get("student_user_id") or "").strip()
        if assignment_id <= 0 or program_id <= 0:
            continue
        program = load_learning_program(program_id)
        if not isinstance(program, dict) or not program:
            continue
        progress_map = load_assignment_progress_map(assignment_id)
        subject_key = str(program.get("subject") or row.get("subject_key") or "").strip()
        student_progress_rows = (
            teacher_assignments_df[
                (teacher_assignments_df["student_id"].astype(str) == student_id)
                & (teacher_assignments_df["subject_key"].astype(str) == subject_key)
            ].to_dict("records")
            if not teacher_assignments_df.empty and {"student_id", "subject_key"}.issubset(teacher_assignments_df.columns)
            else []
        )
        overall_signal = _build_recommendation_signal(student_progress_rows)
        total_topics = sum(len(unit.get("topics") or []) for unit in (program.get("units") or []))
        completed_topics = len([1 for item in progress_map.values() if item.get("teacher_done")])
        progress_gap = _clamp(1.0 - ((completed_topics / total_topics) if total_topics else 0.0))

        ordered_topics: list[tuple[int, dict[str, Any], dict[str, Any]]] = []
        latest_completed_position = 0
        topic_position = 0
        for unit in program.get("units") or []:
            for topic in unit.get("topics") or []:
                topic_position += 1
                topic_id = int(topic.get("topic_id") or 0)
                topic_progress = progress_map.get(topic_id, {}) if topic_id else {}
                if truthy_flag(topic_progress.get("teacher_done")):
                    latest_completed_position = max(latest_completed_position, topic_position)
                ordered_topics.append((topic_position, topic, topic_progress))

        next_topic_taken = False
        for position, topic, topic_progress in ordered_topics:
            topic_id = int(topic.get("topic_id") or 0)
            if topic_id <= 0:
                continue
            teacher_done = truthy_flag(topic_progress.get("teacher_done"))
            student_done = truthy_flag(topic_progress.get("student_done"))
            topic_signal = _topic_signal_from_rows(_topic_progress_rows(topic, student_progress_rows))
            if not teacher_done and (position > latest_completed_position or latest_completed_position == 0):
                bucket = "next_topic"
                candidate = {
                    "recommendation_bucket": bucket,
                    "progress_gap": progress_gap,
                    "overall_signal": overall_signal,
                    "topic_signal": topic_signal,
                    "needs_practice": False,
                    "teacher_done": teacher_done,
                    "student_done": student_done,
                    "is_after_latest_completed": position > latest_completed_position,
                    "is_before_latest_completed": False,
                    "is_next_unfinished": not next_topic_taken,
                    "event_summary": objective_events.get((assignment_id, topic_id, bucket), {}),
                }
                next_topic_taken = True
                target = _teacher_objective_target(candidate["event_summary"])
                samples.append(
                    {
                        "kind": bucket,
                        "timestamp": str((candidate["event_summary"] or {}).get("last_event_at") or row.get("updated_at") or ""),
                        "target": target,
                        "label": _target_to_label(target),
                        "features": _teacher_objective_candidate_features(candidate),
                        "source": "teacher_objective_candidate",
                    }
                )
            if teacher_done:
                bucket = "review"
                candidate = {
                    "recommendation_bucket": bucket,
                    "progress_gap": progress_gap,
                    "overall_signal": overall_signal,
                    "topic_signal": topic_signal,
                    "needs_practice": student_done,
                    "teacher_done": teacher_done,
                    "student_done": student_done,
                    "is_after_latest_completed": False,
                    "is_before_latest_completed": False,
                    "is_next_unfinished": False,
                    "event_summary": objective_events.get((assignment_id, topic_id, bucket), {}),
                }
                target = _teacher_objective_target(candidate["event_summary"])
                samples.append(
                    {
                        "kind": bucket,
                        "timestamp": str((candidate["event_summary"] or {}).get("last_event_at") or row.get("updated_at") or ""),
                        "target": target,
                        "label": _target_to_label(target),
                        "features": _teacher_objective_candidate_features(candidate),
                        "source": "teacher_objective_candidate",
                    }
                )
            if not teacher_done and latest_completed_position > 0 and position < latest_completed_position:
                bucket = "pending_gap"
                candidate = {
                    "recommendation_bucket": bucket,
                    "progress_gap": progress_gap,
                    "overall_signal": overall_signal,
                    "topic_signal": topic_signal,
                    "needs_practice": False,
                    "teacher_done": teacher_done,
                    "student_done": student_done,
                    "is_after_latest_completed": False,
                    "is_before_latest_completed": True,
                    "is_next_unfinished": False,
                    "event_summary": objective_events.get((assignment_id, topic_id, bucket), {}),
                }
                target = _teacher_objective_target(candidate["event_summary"])
                samples.append(
                    {
                        "kind": bucket,
                        "timestamp": str((candidate["event_summary"] or {}).get("last_event_at") or row.get("updated_at") or ""),
                        "target": target,
                        "label": _target_to_label(target),
                        "features": _teacher_objective_candidate_features(candidate),
                        "source": "teacher_objective_candidate",
                    }
                )

    samples.sort(key=lambda item: str(item.get("timestamp") or ""))
    return samples


def _train_teacher_objective_weights(samples: list[dict[str, Any]]) -> dict[str, float]:
    rows = [(dict(sample.get("features") or {}), _safe_float(sample.get("target"), 0.0)) for sample in samples]
    if not rows:
        return _base_teacher_objective_weights()
    return _fit_linear_model(rows, base_weights=_base_teacher_objective_weights())


def summarize_teacher_objective_samples(samples: list[dict[str, Any]]) -> dict[str, Any]:
    sample_count = len(samples)
    if sample_count < 6:
        return {
            "sample_count": sample_count,
            "train_count": sample_count,
            "test_count": 0,
            "positive_rate": 0.0 if not samples else sum(int(sample.get("label") or 0) for sample in samples) / sample_count,
            "metrics": _compute_metrics([], []),
            "feature_weights": _base_teacher_objective_weights(),
            "top_features": [],
            "counts_by_kind": dict(Counter(str(sample.get("kind") or "") for sample in samples)),
        }
    ordered_samples = sorted(samples, key=lambda item: str(item.get("timestamp") or ""))
    split_idx = max(4, int(sample_count * 0.7))
    if split_idx >= sample_count:
        split_idx = sample_count - 1
    train_rows = ordered_samples[:split_idx]
    test_rows = ordered_samples[split_idx:] or ordered_samples[-1:]
    if not test_rows:
        train_rows = ordered_samples[:-1]
        test_rows = ordered_samples[-1:]
    weights = _train_teacher_objective_weights(train_rows)
    labels = [int(row.get("label") or 0) for row in test_rows]
    scores = [_score_linear_model(weights, dict(row.get("features") or {})) for row in test_rows]
    metrics = _compute_metrics(labels, scores)
    top_features = sorted(
        (
            {"name": key, "weight": float(value)}
            for key, value in weights.items()
            if key != "bias" and abs(_safe_float(value)) >= 0.08
        ),
        key=lambda item: abs(item["weight"]),
        reverse=True,
    )[:8]
    return {
        "sample_count": sample_count,
        "train_count": len(train_rows),
        "test_count": len(test_rows),
        "positive_rate": sum(int(sample.get("label") or 0) for sample in ordered_samples) / max(1, sample_count),
        "metrics": metrics,
        "feature_weights": weights,
        "top_features": top_features,
        "counts_by_kind": dict(Counter(str(sample.get("kind") or "") for sample in ordered_samples)),
    }


def build_teacher_recommendation_objective_model(teacher_id: str | None = None) -> dict[str, Any]:
    safe_teacher_id = str(teacher_id or get_current_user_id() or "").strip()
    samples = build_teacher_objective_samples(safe_teacher_id)
    diagnostics = summarize_teacher_objective_samples(samples)
    return {
        "weights": diagnostics.get("feature_weights") or _base_teacher_objective_weights(),
        "diagnostics": diagnostics,
    }


def score_teacher_recommendation_objective(candidate: dict[str, Any], *, teacher_id: str | None = None) -> tuple[float, dict[str, float]]:
    model = build_teacher_recommendation_objective_model(teacher_id)
    features = _teacher_objective_candidate_features(candidate)
    return _score_linear_model(model.get("weights") or {}, features), features


def _teacher_event_target(row: dict[str, Any]) -> float:
    event_type = _norm_key(row.get("event_type"))
    score_map = {
        "prefill": 0.2,
        "resource_opened": 0.32,
        "resource_assigned": 0.55,
        "assignment_created": 0.74,
        "teacher_marked_done": 0.78,
        "student_started": 0.84,
        "student_completed": 0.92,
        "student_improved": 1.0,
    }
    return score_map.get(event_type, 0.1)


def _base_teacher_weights() -> dict[str, float]:
    return {
        "bias": -0.2,
        "subject_demand": 0.24,
        "kind_demand": 0.10,
        "topic_demand": 0.22,
        "kind_open_rate": 0.07,
        "source_open_rate": 0.04,
        "subject_open_rate": 0.05,
        "topic_open_rate": 0.04,
        "source_own": 0.04,
        "topic_reference_present": 0.16,
        "event_weight": 0.22,
        "exact_topic_match": 0.78,
        "exact_topic_support": 0.32,
        "direct_topic_link": 0.64,
        "topic_kind_prior": 0.34,
        "topic_match_ambiguity": -0.26,
        "kind_plan": 0.22,
        "kind_worksheet": 0.26,
        "kind_exam": 0.14,
        "kind_video": 0.18,
        "bucket_next_topic": 0.20,
        "bucket_review": 0.26,
        "bucket_pending_gap": 0.18,
        "focus_needs_practice": 0.18,
        "focus_reteach": 0.16,
        "focus_reinforce": 0.12,
        "focus_stretch": 0.08,
    }


def build_teacher_report_profile_snapshot(teacher_id: str) -> dict[str, Any]:
    safe_teacher_id = str(teacher_id or "").strip()
    recommendation_rows = _load_teacher_recommendation_events(safe_teacher_id)
    activity_rows = _load_teacher_material_activity_rows(safe_teacher_id)
    feed_profile = build_teacher_material_feed_profile(safe_teacher_id)

    kind_counter: Counter[str] = Counter()
    bucket_counter: Counter[str] = Counter()
    activity_counter: Counter[str] = Counter()
    subject_counter: Counter[str] = Counter()

    for row in recommendation_rows:
        kind = _norm_key(row.get("resource_kind"))
        bucket = _norm_key(row.get("recommendation_bucket"))
        if kind:
            kind_counter[kind] += 1
        if bucket:
            bucket_counter[bucket] += 1

    for row in activity_rows:
        activity_type = _norm_key(row.get("activity_type"))
        meta = row.get("meta_json") if isinstance(row.get("meta_json"), dict) else {}
        subject = normalize_subject(meta.get("subject"))
        if activity_type:
            activity_counter[activity_type] += 1
        if subject:
            subject_counter[subject] += 1

    if not subject_counter:
        for subject, value in (feed_profile.get("subject_demand") or {}).items():
            if float(value or 0.0) > 0:
                subject_counter[str(subject)] += int(round(float(value) * 100))

    return {
        "teacher_id": safe_teacher_id,
        "top_subjects": [subject for subject, _count in subject_counter.most_common(4)],
        "recommendation_summary": {
            "rows": len(recommendation_rows),
            "kinds": dict(kind_counter),
            "buckets": dict(bucket_counter),
        },
        "material_activity_summary": {
            "rows": len(activity_rows),
            "activity_types": dict(activity_counter),
        },
        "feed_profile": feed_profile,
    }


def build_teacher_recommendation_samples(
    teacher_profile: dict[str, Any],
    *,
    teacher_id: str | None = None,
) -> list[dict[str, Any]]:
    safe_teacher_id = str(teacher_id or get_current_user_id() or "").strip()
    feed_profile = dict(teacher_profile.get("feed_profile") or {})
    recommendation_rows = _load_teacher_recommendation_events(safe_teacher_id)
    activity_rows = _load_teacher_material_activity_rows(safe_teacher_id)

    samples: list[dict[str, Any]] = []

    for row in recommendation_rows:
        kind = _norm_key(row.get("resource_kind"))
        bucket = _norm_key(row.get("recommendation_bucket"))
        focus = _norm_key(row.get("recommendation_focus_kind"))
        topic_id = int(row.get("learning_program_topic_id") or 0)
        resource_id = int(row.get("resource_record_id") or 0)
        topic_features = {
            "explicit_topic_match": 0.0,
            "explicit_topic_support": 0.0,
            "direct_topic_link": 0.0,
            "topic_kind_prior": 0.0,
            "topic_match_ambiguity": 0.0,
        }
        if topic_id > 0 and resource_id > 0 and kind:
            topic_features = topic_resource_alignment_features(
                kind,
                resource_id,
                [topic_id],
                teacher_id=safe_teacher_id,
            )

        target = _teacher_event_target(row)
        samples.append(
            {
                "kind": kind,
                "subject": "",
                "topic": str(topic_id) if topic_id > 0 else "",
                "timestamp": str(row.get("created_at") or ""),
                "target": target,
                "label": _target_to_label(target),
                "features": {
                    f"kind_{kind}": 1.0 if kind else 0.0,
                    f"bucket_{bucket}": 1.0 if bucket else 0.0,
                    f"focus_{focus}": 1.0 if focus else 0.0,
                    "topic_reference_present": 1.0 if topic_id > 0 else 0.0,
                    "event_weight": _safe_float(row.get("event_weight"), 0.0),
                    "exact_topic_match": _safe_float(topic_features.get("explicit_topic_match"), 0.0),
                    "exact_topic_support": _safe_float(topic_features.get("explicit_topic_support"), 0.0),
                    "direct_topic_link": _safe_float(topic_features.get("direct_topic_link"), 0.0),
                    "topic_kind_prior": _safe_float(topic_features.get("topic_kind_prior"), 0.0),
                    "topic_match_ambiguity": _safe_float(topic_features.get("topic_match_ambiguity"), 0.0),
                },
                "source": "recommendation_event",
            }
        )

    for row in activity_rows:
        activity_type = _norm_key(row.get("activity_type"))
        meta = row.get("meta_json") if isinstance(row.get("meta_json"), dict) else {}
        kind = _norm_key(meta.get("resource_kind"))
        source = _norm_key(meta.get("source"))
        subject = normalize_subject(meta.get("subject"))
        topic = str(meta.get("topic") or "").strip()
        tokens = _tokenize(meta.get("topic"), meta.get("title"))
        target = 0.78 if activity_type == "teacher_material_open" else 0.28
        samples.append(
            {
                "kind": kind,
                "subject": subject,
                "topic": topic,
                "timestamp": str(row.get("created_at") or ""),
                "target": target,
                "label": _target_to_label(target),
                "features": {
                    "subject_demand": _safe_float((feed_profile.get("subject_demand") or {}).get(subject), 0.0),
                    "kind_demand": _safe_float((feed_profile.get("kind_demand") or {}).get(kind), 0.0),
                    "topic_demand": _weighted_token_score(feed_profile.get("topic_demand") or {}, tokens, scale=2.8),
                    "kind_open_rate": _safe_float((feed_profile.get("kind_open_rate") or {}).get(kind), 0.0),
                    "source_open_rate": _safe_float((feed_profile.get("source_open_rate") or {}).get(source), 0.0),
                    "subject_open_rate": _safe_float((feed_profile.get("subject_open_rate") or {}).get(subject), 0.0),
                    "topic_open_rate": _weighted_token_score(feed_profile.get("topic_open_rate") or {}, tokens, scale=2.4),
                    "source_own": 1.0 if source == "own" else 0.0,
                    f"kind_{kind}": 1.0 if kind else 0.0,
                },
                "source": activity_type or "teacher_material_activity",
            }
        )

    samples.sort(key=lambda item: str(item.get("timestamp") or ""))
    return samples


def summarize_teacher_recommendation_samples(samples: list[dict[str, Any]]) -> dict[str, Any]:
    sample_count = len(samples)
    if sample_count < 6:
        positive_rate = 0.0 if not samples else sum(int(sample.get("label") or 0) for sample in samples) / sample_count
        return {
            "sample_count": sample_count,
            "train_count": sample_count,
            "test_count": 0,
            "positive_rate": positive_rate,
            "metrics": _compute_metrics([], []),
            "blend_weight": 0.42,
            "feature_weights": _base_teacher_weights(),
            "top_features": [],
            "counts_by_kind": dict(Counter(str(sample.get("kind") or "") for sample in samples)),
            "counts_by_source": dict(Counter(str(sample.get("source") or "") for sample in samples)),
            "class_imbalance": positive_rate < 0.10,
            "degenerate_model": False,
            "maturity_level": "Experimental",
        }

    ordered_samples = sorted(samples, key=lambda item: str(item.get("timestamp") or ""))
    split_idx = max(4, int(sample_count * 0.7))
    if split_idx >= sample_count:
        split_idx = sample_count - 1
    train_rows = ordered_samples[:split_idx]
    test_rows = ordered_samples[split_idx:]
    if not test_rows:
        train_rows = ordered_samples[:-1]
        test_rows = ordered_samples[-1:]

    rows = [(dict(sample.get("features") or {}), _safe_float(sample.get("target"), 0.0)) for sample in train_rows]
    weights = _base_teacher_weights() if not rows else _fit_linear_model(rows, base_weights=_base_teacher_weights())
    labels = [int(row.get("label") or 0) for row in test_rows]
    scores = [_score_linear_model(weights, dict(row.get("features") or {})) for row in test_rows]
    metrics = _compute_metrics(labels, scores)
    positive_rate = sum(int(sample.get("label") or 0) for sample in ordered_samples) / max(1, sample_count)
    quality_signal = max(metrics.get("f1", 0.0), metrics.get("roc_auc", 0.5) - 0.15)
    blend_weight = _clamp(0.32 + (0.42 * quality_signal) + (0.08 if sample_count >= 12 else 0.0), 0.35, 0.72)
    top_features = sorted(
        (
            {"name": key, "weight": float(value)}
            for key, value in weights.items()
            if key != "bias" and abs(_safe_float(value)) >= 0.08
        ),
        key=lambda item: abs(item["weight"]),
        reverse=True,
    )[:8]
    class_imbalance = positive_rate < 0.10
    degenerate_model = (
        len(test_rows) > 0
        and float(metrics.get("precision", 0.0)) == 0.0
        and float(metrics.get("recall", 0.0)) == 0.0
        and float(metrics.get("f1", 0.0)) == 0.0
    )
    roc_auc = float(metrics.get("roc_auc", 0.0))
    f1 = float(metrics.get("f1", 0.0))
    if roc_auc > 0.90 and f1 > 0.80:
        maturity_level = "Production Ready"
    elif roc_auc >= 0.75 and f1 >= 0.30:
        maturity_level = "Operational Candidate"
    elif roc_auc >= 0.60 and f1 >= 0.10:
        maturity_level = "Prototype"
    else:
        maturity_level = "Experimental"
    return {
        "sample_count": sample_count,
        "train_count": len(train_rows),
        "test_count": len(test_rows),
        "positive_rate": positive_rate,
        "metrics": metrics,
        "blend_weight": blend_weight,
        "feature_weights": weights,
        "top_features": top_features,
        "counts_by_kind": dict(Counter(str(sample.get("kind") or "") for sample in ordered_samples)),
        "counts_by_source": dict(Counter(str(sample.get("source") or "") for sample in ordered_samples)),
        "class_imbalance": class_imbalance,
        "degenerate_model": degenerate_model,
        "maturity_level": maturity_level,
    }
