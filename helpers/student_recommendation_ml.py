from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from typing import Any

import pandas as pd
import streamlit as st

from core.database import load_profile_row
from core.database import clear_app_caches, get_sb
from core.state import get_current_user_id, with_owner
from helpers.recommendation_models import (
    _fit_linear_model,
    _load_student_history_rows,
    _norm_key,
    _norm_text,
    _overlap_score,
    _safe_float,
    _score_linear_model,
    _tokenize,
    normalize_subject,
    topic_resource_alignment_features,
)


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, float(value)))


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _base_student_weights() -> dict[str, float]:
    return {
        "bias": -0.12,
        "subject_in_program": 0.7,
        "level_fit": 0.45,
        "stage_fit": 0.28,
        "next_topic_overlap": 0.72,
        "review_topic_overlap": 0.82,
        "pending_topic_overlap": 0.46,
        "program_subject_fit": 0.4,
        "program_type_fit": 0.26,
        "topic_need": 0.84,
        "subject_need": 0.52,
        "exercise_need": 0.36,
        "completion_fit": 0.28,
        "format_fit": 0.24,
        "explicit_topic_match": 0.82,
        "explicit_topic_support": 0.28,
        "direct_topic_link": 0.54,
        "topic_kind_prior": 0.34,
        "topic_match_ambiguity": -0.22,
        "topic_success_penalty": -0.18,
    }


def build_report_profile_snapshot(student_id: str) -> dict[str, Any]:
    safe_student_id = str(student_id or "").strip()
    profile_row = load_profile_row(safe_student_id) if safe_student_id else {}
    history = _load_student_history_rows(safe_student_id)
    practice_rows = history.get("practice_sessions") or []
    assignment_rows = history.get("teacher_assignments") or []

    subject_counter: Counter[str] = Counter()
    level_counter: dict[str, Counter[str]] = {}
    topic_tokens: set[str] = set()

    for row in practice_rows:
        subject = normalize_subject(row.get("subject"))
        level = _norm_text(row.get("level"))
        topic = _norm_text(row.get("topic"))
        if subject:
            subject_counter[subject] += 1
        if subject and level:
            level_counter.setdefault(subject, Counter())
            level_counter[subject][level] += 1
        topic_tokens.update(_tokenize(topic))

    for row in assignment_rows:
        subject = normalize_subject(row.get("subject_key"))
        topic = _norm_text(row.get("topic"))
        if subject:
            subject_counter[subject] += 1
        topic_tokens.update(_tokenize(topic))

    subject_levels = {
        subject: counter.most_common(1)[0][0]
        for subject, counter in level_counter.items()
        if counter
    }
    primary_subjects = [
        normalize_subject(value)
        for value in (profile_row.get("primary_subjects") or [])
        if str(value or "").strip()
    ]
    if not primary_subjects:
        primary_subjects = [subject for subject, _count in subject_counter.most_common(3)]

    practice_df = pd.DataFrame(practice_rows) if practice_rows else pd.DataFrame()
    return {
        "primary_subjects": primary_subjects,
        "program_signals": {
            "subjects": set(subject_counter.keys()),
            "subject_levels": subject_levels,
            "topic_tokens": topic_tokens,
            "active_topic_ids": {
                int(row.get("learning_program_topic_id") or 0)
                for row in assignment_rows
                if int(row.get("learning_program_topic_id") or 0) > 0
            },
        },
        "history_rows": {
            "practice_sessions": practice_rows,
            "teacher_assignments": assignment_rows,
        },
        "practice_summary": {
            "rows": int(len(practice_rows)),
            "subjects": dict(subject_counter),
            "avg_score_pct": float(practice_df["score_pct"].fillna(0).mean()) if not practice_df.empty and "score_pct" in practice_df.columns else 0.0,
        },
    }


def _target_to_label(target: float) -> int:
    return 1 if float(target or 0.0) >= 0.62 else 0


def _safe_auc(labels: list[int], scores: list[float]) -> float:
    if len(labels) != len(scores) or not labels:
        return 0.5
    positives = [score for score, label in zip(scores, labels) if label == 1]
    negatives = [score for score, label in zip(scores, labels) if label == 0]
    if not positives or not negatives:
        return 0.5
    wins = 0.0
    total = 0.0
    for pos in positives:
        for neg in negatives:
            total += 1.0
            if pos > neg:
                wins += 1.0
            elif pos == neg:
                wins += 0.5
    return wins / total if total else 0.5


def _compute_metrics(labels: list[int], scores: list[float], threshold: float = 0.5) -> dict[str, float]:
    if not labels:
        return {
            "accuracy": 0.0,
            "precision": 0.0,
            "recall": 0.0,
            "f1": 0.0,
            "roc_auc": 0.5,
            "tp": 0.0,
            "tn": 0.0,
            "fp": 0.0,
            "fn": 0.0,
        }

    preds = [1 if score >= threshold else 0 for score in scores]
    tp = sum(1 for pred, label in zip(preds, labels) if pred == 1 and label == 1)
    tn = sum(1 for pred, label in zip(preds, labels) if pred == 0 and label == 0)
    fp = sum(1 for pred, label in zip(preds, labels) if pred == 1 and label == 0)
    fn = sum(1 for pred, label in zip(preds, labels) if pred == 0 and label == 1)
    total = max(1, len(labels))
    precision = tp / max(1, tp + fp)
    recall = tp / max(1, tp + fn)
    f1 = 0.0 if precision + recall <= 0 else (2 * precision * recall) / (precision + recall)
    return {
        "accuracy": (tp + tn) / total,
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "roc_auc": _safe_auc(labels, scores),
        "tp": float(tp),
        "tn": float(tn),
        "fp": float(fp),
        "fn": float(fn),
    }


def _train_weights(samples: list[dict[str, Any]]) -> dict[str, float]:
    rows = [(dict(sample.get("features") or {}), _safe_float(sample.get("target"), 0.0)) for sample in samples]
    if not rows:
        return _base_student_weights()
    return _fit_linear_model(rows, base_weights=_base_student_weights())


def summarize_student_recommendation_samples(samples: list[dict[str, Any]]) -> dict[str, Any]:
    sample_count = len(samples)
    if sample_count < 6:
        return {
            "sample_count": sample_count,
            "train_count": sample_count,
            "test_count": 0,
            "positive_rate": 0.0 if not samples else sum(int(sample.get("label") or 0) for sample in samples) / sample_count,
            "metrics": _compute_metrics([], []),
            "blend_weight": 0.42,
            "feature_weights": _base_student_weights(),
            "top_features": [],
            "counts_by_kind": dict(Counter(str(sample.get("kind") or "") for sample in samples)),
            "counts_by_source": dict(Counter(str(sample.get("source") or "") for sample in samples)),
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

    weights = _train_weights(train_rows)
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
    }


def build_student_recommendation_samples(
    student_profile: dict[str, Any],
    *,
    student_id: str | None = None,
) -> list[dict[str, Any]]:
    safe_student_id = str(student_id or get_current_user_id() or "").strip()
    history = _load_student_history_rows(safe_student_id)
    practice_rows = history.get("practice_sessions") or []
    assignment_rows = history.get("teacher_assignments") or []
    activity_rows = history.get("recommendation_activity") or []
    program_signals = student_profile.get("program_signals") or {}
    subjects_in_program = set(program_signals.get("subjects") or set())
    topic_tokens = set(program_signals.get("topic_tokens") or set())
    subject_levels = program_signals.get("subject_levels") or {}
    active_topic_ids = set(program_signals.get("active_topic_ids") or set())

    samples: list[dict[str, Any]] = []

    for row in practice_rows:
        kind = _norm_key(row.get("source_type"))
        if kind not in {"worksheet", "exam", "video"}:
            continue
        subject = normalize_subject(row.get("subject"))
        topic = _norm_text(row.get("topic"))
        score = _safe_float(row.get("score_pct")) / 100.0
        target = 0.3 + 0.7 * score
        features = {
            f"kind_{kind}": 1.0 if kind else 0.0,
            "subject_in_program": 1.0 if subject and subject in subjects_in_program else 0.0,
            "level_fit": 1.0
            if _norm_key(row.get("level")) and _norm_key(row.get("level")) == _norm_key(subject_levels.get(subject, ""))
            else 0.0,
            "topic_in_program": _overlap_score(_tokenize(topic), topic_tokens),
        }
        samples.append(
            {
                "kind": kind,
                "subject": subject,
                "topic": topic,
                "timestamp": str(row.get("completed_at") or row.get("created_at") or ""),
                "target": target,
                "label": _target_to_label(target),
                "features": features,
                "source": "practice_session",
            }
        )

    for row in assignment_rows:
        assignment_type = _norm_key(row.get("assignment_type"))
        kind = "worksheet" if assignment_type == "worksheet" else ("exam" if assignment_type == "exam" else "")
        if assignment_type == "video":
            kind = "video"
        if not kind:
            continue
        subject = normalize_subject(row.get("subject_key"))
        topic = _norm_text(row.get("topic"))
        score = _safe_float(row.get("score_pct")) / 100.0
        status = _norm_key(row.get("status"))
        topic_id = int(row.get("learning_program_topic_id") or 0)
        topic_alignment = topic_resource_alignment_features(
            kind,
            row.get("source_record_id"),
            [topic_id] if topic_id > 0 else list(active_topic_ids),
            student_id=safe_student_id,
        )
        target = 0.2
        if status in {"graded", "completed"}:
            target = 0.4 + 0.6 * score
        elif status in {"started", "submitted"}:
            target = 0.45
        elif status in {"assigned", "overdue"} and kind == "video":
            target = 0.3
        features = {
            f"kind_{kind}": 1.0,
            "subject_in_program": 1.0 if subject and subject in subjects_in_program else 0.0,
            "topic_in_program": _overlap_score(_tokenize(topic), topic_tokens),
            "explicit_topic_match": topic_alignment["explicit_topic_match"],
            "explicit_topic_support": topic_alignment["explicit_topic_support"],
            "direct_topic_link": topic_alignment["direct_topic_link"],
            "topic_kind_prior": topic_alignment["topic_kind_prior"],
            "topic_match_ambiguity": topic_alignment["topic_match_ambiguity"],
        }
        samples.append(
            {
                "kind": kind,
                "subject": subject,
                "topic": topic,
                "timestamp": str(row.get("updated_at") or row.get("created_at") or ""),
                "target": target,
                "label": _target_to_label(target),
                "features": features,
                "source": "teacher_assignment",
            }
        )

    for row in activity_rows:
        meta = row.get("meta_json") if isinstance(row.get("meta_json"), dict) else {}
        activity_type = _norm_key(row.get("activity_type"))
        kind = _norm_key(meta.get("resource_kind"))
        if activity_type not in {"student_recommendation_impression", "student_recommendation_open"} or not kind:
            continue
        subject = normalize_subject(meta.get("subject"))
        topic = _norm_text(meta.get("topic"))
        target = 0.78 if activity_type == "student_recommendation_open" else 0.16
        features = {
            f"kind_{kind}": 1.0,
            "subject_in_program": 1.0 if subject and subject in subjects_in_program else 0.0,
            "level_fit": 1.0
            if _norm_key(meta.get("level")) and _norm_key(meta.get("level")) == _norm_key(subject_levels.get(subject, ""))
            else 0.0,
            "topic_in_program": _overlap_score(_tokenize(topic), topic_tokens),
            "program_type_fit": 1.0 if bool(meta.get("assigned_resource")) else 0.0,
            "completion_fit": _safe_float(meta.get("ml_blend_weight"), 0.0),
            "topic_need": _safe_float(meta.get("ml_score"), 0.0),
        }
        samples.append(
            {
                "kind": kind,
                "subject": subject,
                "topic": topic,
                "timestamp": str(row.get("created_at") or ""),
                "target": target,
                "label": _target_to_label(target),
                "features": features,
                "source": activity_type,
            }
        )

    samples.sort(key=lambda item: str(item.get("timestamp") or ""))
    return samples


@st.cache_data(ttl=120, show_spinner=False)
def evaluate_student_recommendation_pipeline(
    student_id: str,
    profile_snapshot: dict[str, Any],
) -> dict[str, Any]:
    samples = build_student_recommendation_samples(profile_snapshot, student_id=student_id)
    return summarize_student_recommendation_samples(samples)


def student_recommendation_blend_weight(student_id: str, profile_snapshot: dict[str, Any]) -> float:
    diagnostics = evaluate_student_recommendation_pipeline(student_id, profile_snapshot)
    return float(diagnostics.get("blend_weight") or 0.42)


def _student_reco_meta(item: dict[str, Any], surface: str) -> dict[str, Any]:
    row = item.get("row") or {}
    return {
        "surface": str(surface or "").strip(),
        "resource_kind": str(item.get("resource_type") or "").strip(),
        "resource_id": item.get("id"),
        "title": str(item.get("title") or "").strip(),
        "subject": str(item.get("subject") or "").strip(),
        "topic": str(item.get("topic") or "").strip(),
        "level": str(item.get("level") or "").strip(),
        "exercise_type": str(item.get("exercise_type") or "").strip(),
        "assigned_resource": bool(item.get("assigned_resource")),
        "score": _safe_float(item.get("score"), 0.0),
        "ml_score": _safe_float(item.get("ml_score"), 0.0),
        "ml_blend_weight": _safe_float(item.get("ml_blend_weight"), 0.0),
        "source_created_at": row.get("created_at"),
    }


def log_student_recommendation_impressions(rows: list[dict[str, Any]], *, surface: str) -> None:
    safe_rows = [row for row in (rows or []) if isinstance(row, dict)]
    if not safe_rows:
        return
    user_id = str(get_current_user_id() or "").strip()
    if not user_id:
        return
    seen = set(st.session_state.get("_student_reco_impressions_seen") or [])
    payloads = []
    for item in safe_rows[:12]:
        signature = f"{surface}:{item.get('resource_type')}:{item.get('id')}"
        if item.get("id") in (None, "", 0, "0") or signature in seen:
            continue
        seen.add(signature)
        payloads.append(
            with_owner(
                {
                    "activity_type": "student_recommendation_impression",
                    "feature_name": "student_recommendation_feed",
                    "meta_json": _student_reco_meta(item, surface),
                    "created_at": _now_iso(),
                }
            )
        )
    if not payloads:
        return
    st.session_state["_student_reco_impressions_seen"] = list(seen)
    try:
        get_sb().table("user_activity_log").insert(payloads).execute()
        clear_app_caches()
    except Exception:
        pass


def log_student_recommendation_open(item: dict[str, Any], *, surface: str) -> None:
    if not isinstance(item, dict) or item.get("id") in (None, "", 0, "0"):
        return
    try:
        get_sb().table("user_activity_log").insert(
            with_owner(
                {
                    "activity_type": "student_recommendation_open",
                    "feature_name": "student_recommendation_feed",
                    "meta_json": _student_reco_meta(item, surface),
                    "created_at": _now_iso(),
                }
            )
        ).execute()
        clear_app_caches()
    except Exception:
        pass
