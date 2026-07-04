from __future__ import annotations

from datetime import datetime, timezone
import math
import re
from typing import Any

import pandas as pd
import streamlit as st

from core.database import get_sb
from core.i18n import t
from core.state import get_current_user_id, with_owner
from helpers.archive_utils import truthy_flag


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value in (None, ""):
            return default
        value = float(value)
        if pd.isna(value):
            return default
        return value
    except Exception:
        return default


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, float(value)))


def _sigmoid(value: float) -> float:
    if value >= 0:
        z = math.exp(-value)
        return 1.0 / (1.0 + z)
    z = math.exp(value)
    return z / (1.0 + z)


def _norm_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip())


def _norm_key(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(value or "").strip().casefold()).strip("_")


def _clean_display_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip())


def _resource_id_key(value: Any) -> str:
    return str(value or "").strip()


_SUBJECT_NORMALIZE = {
    "english": "english", "ingles": "english", "inglés": "english", "ingilizce": "english",
    "spanish": "spanish", "espanol": "spanish", "español": "spanish", "ispanyolca": "spanish",
    "mathematics": "mathematics", "matematicas": "mathematics", "matemáticas": "mathematics", "matematik": "mathematics",
    "math": "mathematics", "maths": "mathematics",
    "science": "science", "ciencias": "science", "fen": "science", "fen_bilimleri": "science",
    "music": "music", "musica": "music", "música": "music", "muzik": "music", "müzik": "music",
    "study_skills": "study_skills", "tecnicas_de_estudio": "study_skills", "técnicas_de_estudio": "study_skills",
    "calisma_becerileri": "study_skills", "çalışma_becerileri": "study_skills",
    "turkish": "turkish", "turco": "turkish", "turkce": "turkish", "türkçe": "turkish",
    "other": "other", "otro": "other", "otra_materia": "other", "diger": "other", "diğer": "other", "otra": "other",
}


def normalize_subject(raw: Any) -> str:
    key = str(raw or "").strip().lower().replace(" ", "_")
    return _SUBJECT_NORMALIZE.get(key, key)


def subject_label(subject_key: Any) -> str:
    key = str(subject_key or "").strip().lower().replace(" ", "_")
    if key == "other":
        return t("subject_other")
    translated = t(f"subject_{key}")
    return translated if translated and translated != f"subject_{key}" else _clean_display_text(subject_key or key)


def _tokenize(*values: Any) -> set[str]:
    tokens: set[str] = set()
    for value in values:
        for raw in re.split(r"[\W_]+", str(value or "").casefold()):
            cleaned = "".join(ch for ch in raw if ch.isalnum())
            if len(cleaned) >= 3:
                tokens.add(cleaned)
    return tokens


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _overlap_score(left: set[str], right: set[str], *, scale: float = 3.0) -> float:
    if not left or not right:
        return 0.0
    return _clamp(len(left & right) / max(scale, 1.0))


def _fit_linear_model(
    samples: list[tuple[dict[str, float], float]],
    *,
    base_weights: dict[str, float] | None = None,
    steps: int = 140,
    learning_rate: float = 0.16,
    l2: float = 0.01,
) -> dict[str, float]:
    if not samples:
        return dict(base_weights or {"bias": 0.0})

    feature_names = {"bias"}
    feature_names.update((base_weights or {}).keys())
    for features, _target in samples:
        feature_names.update(features.keys())

    weights = {name: _safe_float((base_weights or {}).get(name), 0.0) for name in feature_names}
    weights.setdefault("bias", _safe_float((base_weights or {}).get("bias"), 0.0))

    for _ in range(steps):
        gradients = {name: 0.0 for name in feature_names}
        for features, target in samples:
            row_features = {"bias": 1.0, **features}
            prediction = _sigmoid(sum(weights.get(name, 0.0) * _safe_float(value) for name, value in row_features.items()))
            error = prediction - _clamp(target)
            for name in feature_names:
                gradients[name] += error * _safe_float(row_features.get(name), 0.0)
        scale = 1.0 / max(1, len(samples))
        for name in feature_names:
            penalty = l2 * weights.get(name, 0.0) if name != "bias" else 0.0
            weights[name] = weights.get(name, 0.0) - learning_rate * ((gradients[name] * scale) + penalty)
    return weights


def _score_linear_model(weights: dict[str, float], features: dict[str, float]) -> float:
    row_features = {"bias": 1.0, **features}
    return _sigmoid(sum(_safe_float(weights.get(name), 0.0) * _safe_float(value) for name, value in row_features.items()))


def humanize_recommendation_event(value: str) -> str:
    key = _norm_key(value)
    label_map = {
        "prefill": "admin_ai_event_prefill",
        "resource_opened": "admin_ai_event_resource_opened",
        "resource_assigned": "admin_ai_event_resource_assigned",
        "assignment_created": "admin_ai_event_assignment_created",
        "teacher_marked_done": "admin_ai_event_teacher_marked_done",
        "student_started": "admin_ai_event_student_started",
        "student_completed": "admin_ai_event_student_completed",
        "student_improved": "admin_ai_event_student_improved",
    }
    translated = t(label_map.get(key, ""))
    if translated and translated != "":
        return translated
    return value.replace("_", " ").title() if value else "—"


def humanize_ai_feature_name(value: str) -> str:
    key = _norm_key(value)
    label_map = {
        "quick_worksheet_ai": "admin_ai_feature_quick_worksheet_ai",
        "quick_exam_ai": "admin_ai_feature_quick_exam_ai",
        "quick_lesson_plan_ai": "admin_ai_feature_quick_lesson_plan_ai",
        "quick_cv_ai": "admin_ai_feature_quick_cv_ai",
        "learning_program_ai": "admin_ai_feature_learning_program_ai",
        "learning_program_cover": "admin_ai_feature_learning_program_cover",
        "student_personalization_ai": "admin_ai_feature_student_personalization_ai",
        "goal_explorer_ai": "admin_ai_feature_goal_explorer_ai",
    }
    translated = t(label_map.get(key, ""))
    if translated and translated != "":
        return translated
    if key.startswith("learning_program"):
        return t("admin_ai_feature_learning_program_ai")
    return value.replace("_", " ").title() if value else "—"


def humanize_assignment_status(value: str) -> str:
    key = _norm_key(value)
    translated = t(f"assignment_status_{key}")
    if translated != f"assignment_status_{key}":
        return translated
    return value.replace("_", " ").title() if value else "—"


def humanize_review_status(value: str) -> str:
    key = _norm_key(value)
    translated = t(f"teacher_review_status_{key}")
    if translated != f"teacher_review_status_{key}":
        return translated
    return value.replace("_", " ").title() if value else "—"


def normalized_subject_label(value: Any) -> str:
    key = normalize_subject(str(value or "").strip())
    return subject_label(key) if key else "—"


def _resource_level(row: dict, kind: str) -> str:
    if kind == "exam":
        return _norm_text(row.get("level") or row.get("level_or_band"))
    return _norm_text(row.get("level_or_band") or row.get("level"))


def _resource_stage(row: dict) -> str:
    return _norm_text(row.get("learner_stage"))


def _resource_subject(row: dict) -> str:
    return normalize_subject(str(row.get("subject") or "").strip())


def _resource_topic_text(row: dict, kind: str) -> str:
    if kind == "program":
        return _norm_text(row.get("program_overview") or row.get("title"))
    return _norm_text(row.get("topic") or row.get("title"))


def _resource_created_stamp(row: dict) -> str:
    return _norm_text(row.get("updated_at") or row.get("created_at"))


def _resource_recency_score(row: dict) -> float:
    stamp = _resource_created_stamp(row)
    if not stamp:
        return 0.18
    try:
        ts = pd.to_datetime(stamp, errors="coerce", utc=True)
        if pd.isna(ts):
            return 0.18
        age_days = max(0.0, (datetime.now(timezone.utc) - ts.to_pydatetime()).total_seconds() / 86400.0)
        return _clamp(1.0 - min(age_days, 120.0) / 120.0, 0.12, 1.0)
    except Exception:
        return 0.18


def _weighted_token_score(token_weights: dict[str, float], tokens: set[str], *, scale: float = 3.0) -> float:
    if not token_weights or not tokens:
        return 0.0
    total = sum(_safe_float(token_weights.get(token), 0.0) for token in tokens)
    return _clamp(total / max(scale, 1.0))


def _topic_reference_target(score_pct: Any, status: Any) -> float:
    normalized_status = _norm_key(status)
    score_norm = _clamp(_safe_float(score_pct) / 100.0)
    if normalized_status in {"graded", "completed"}:
        return 0.38 + (0.62 * score_norm)
    if normalized_status in {"submitted", "started"}:
        return 0.44
    if normalized_status in {"assigned", "overdue"}:
        return 0.28
    return 0.18


def _pair_signature(kind: Any, resource_id: Any, topic_id: Any) -> tuple[str, str, int]:
    return (_norm_key(kind), _resource_id_key(resource_id), int(topic_id or 0))


@st.cache_data(ttl=90, show_spinner=False)
def _load_topic_resource_reference_rows(
    *,
    teacher_id: str = "",
    student_id: str = "",
) -> dict[str, list[dict]]:
    safe_teacher_id = str(teacher_id or "").strip()
    safe_student_id = str(student_id or "").strip()
    payload = {"assignments": [], "events": [], "video_links": []}

    try:
        query = (
            get_sb()
            .table("teacher_assignments")
            .select("teacher_id,student_id,assignment_type,source_record_id,learning_program_topic_id,score_pct,status,updated_at")
            .not_.is_("source_record_id", "null")
            .not_.is_("learning_program_topic_id", "null")
            .order("updated_at", desc=True)
            .limit(8000)
        )
        if safe_teacher_id:
            query = query.eq("teacher_id", safe_teacher_id)
        if safe_student_id:
            query = query.eq("student_id", safe_student_id)
        payload["assignments"] = getattr(query.execute(), "data", None) or []
    except Exception:
        payload["assignments"] = []

    try:
        query = (
            get_sb()
            .table("learning_program_recommendation_events")
            .select(
                "teacher_id,student_id,learning_program_topic_id,resource_kind,resource_record_id,"
                "event_type,event_weight,created_at"
            )
            .not_.is_("resource_record_id", "null")
            .not_.is_("learning_program_topic_id", "null")
            .order("created_at", desc=True)
            .limit(8000)
        )
        if safe_teacher_id:
            query = query.eq("teacher_id", safe_teacher_id)
        if safe_student_id:
            query = query.eq("student_id", safe_student_id)
        payload["events"] = getattr(query.execute(), "data", None) or []
    except Exception:
        payload["events"] = []

    try:
        query = (
            get_sb()
            .table("learning_program_topic_videos")
            .select("teacher_id,program_id,topic_id,video_id,created_at")
            .order("created_at", desc=True)
            .limit(12000)
        )
        if safe_teacher_id:
            query = query.eq("teacher_id", safe_teacher_id)
        payload["video_links"] = getattr(query.execute(), "data", None) or []
    except Exception:
        payload["video_links"] = []

    return payload


def build_explicit_topic_resource_model(
    *,
    teacher_id: str | None = None,
    student_id: str | None = None,
) -> dict[str, Any]:
    reference_rows = _load_topic_resource_reference_rows(
        teacher_id=str(teacher_id or "").strip(),
        student_id=str(student_id or "").strip(),
    )
    pair_scores: dict[tuple[str, str, int], list[float]] = {}
    kind_topic_scores: dict[tuple[str, int], list[float]] = {}
    resource_topics: dict[tuple[str, str], set[int]] = {}
    direct_pairs: set[tuple[str, str, int]] = set()

    for row in reference_rows.get("assignments") or []:
        kind = _norm_key(row.get("assignment_type"))
        if kind == "lesson_plan_topic":
            kind = "plan"
        resource_id = _resource_id_key(row.get("source_record_id"))
        topic_id = int(row.get("learning_program_topic_id") or 0)
        if not kind or not resource_id or resource_id in {"0", "None", "nan"} or topic_id <= 0:
            continue
        target = _topic_reference_target(row.get("score_pct"), row.get("status"))
        pair_scores.setdefault((kind, resource_id, topic_id), []).append(target)
        kind_topic_scores.setdefault((kind, topic_id), []).append(target)
        resource_topics.setdefault((kind, resource_id), set()).add(topic_id)

    for row in reference_rows.get("events") or []:
        kind = _norm_key(row.get("resource_kind"))
        resource_id = _resource_id_key(row.get("resource_record_id"))
        topic_id = int(row.get("learning_program_topic_id") or 0)
        if not kind or not resource_id or resource_id in {"0", "None", "nan"} or topic_id <= 0:
            continue
        target = max(_teacher_event_target(row), _clamp(_safe_float(row.get("event_weight"))))
        pair_scores.setdefault((kind, resource_id, topic_id), []).append(target)
        kind_topic_scores.setdefault((kind, topic_id), []).append(target)
        resource_topics.setdefault((kind, resource_id), set()).add(topic_id)

    for row in reference_rows.get("video_links") or []:
        topic_id = int(row.get("topic_id") or 0)
        video_id = int(row.get("video_id") or 0)
        if topic_id <= 0 or video_id <= 0:
            continue
        signature = ("video", str(video_id), topic_id)
        direct_pairs.add(signature)
        pair_scores.setdefault(signature, []).append(1.0)
        kind_topic_scores.setdefault(("video", topic_id), []).append(0.96)
        resource_topics.setdefault(("video", str(video_id)), set()).add(topic_id)

    return {
        "pair_prior": {
            key: sum(values) / max(1, len(values))
            for key, values in pair_scores.items()
        },
        "pair_support": {
            key: _clamp(len(values) / 4.0)
            for key, values in pair_scores.items()
        },
        "kind_topic_prior": {
            key: sum(values) / max(1, len(values))
            for key, values in kind_topic_scores.items()
        },
        "resource_topic_span": {
            key: len(value)
            for key, value in resource_topics.items()
        },
        "direct_pairs": direct_pairs,
    }


def topic_resource_alignment_features(
    kind: str,
    resource_id: Any,
    topic_ids: list[int] | set[int] | tuple[int, ...],
    *,
    teacher_id: str | None = None,
    student_id: str | None = None,
) -> dict[str, float]:
    topic_list = [int(item or 0) for item in (topic_ids or []) if int(item or 0) > 0]
    resource_id_key = _resource_id_key(resource_id)
    if not kind or not resource_id_key or resource_id_key in {"0", "None", "nan"} or not topic_list:
        return {
            "explicit_topic_match": 0.0,
            "explicit_topic_support": 0.0,
            "direct_topic_link": 0.0,
            "topic_kind_prior": 0.0,
            "topic_match_ambiguity": 0.0,
    }
    model = build_explicit_topic_resource_model(teacher_id=teacher_id, student_id=student_id)
    kind_key = _norm_key(kind)
    resource_key = (kind_key, resource_id_key)

    explicit_topic_match = 0.0
    explicit_topic_support = 0.0
    direct_topic_link = 0.0
    topic_kind_prior = 0.0
    for topic_id in topic_list:
        signature = _pair_signature(kind_key, resource_id_key, topic_id)
        explicit_topic_match = max(explicit_topic_match, _safe_float((model.get("pair_prior") or {}).get(signature), 0.0))
        explicit_topic_support = max(explicit_topic_support, _safe_float((model.get("pair_support") or {}).get(signature), 0.0))
        topic_kind_prior = max(topic_kind_prior, _safe_float((model.get("kind_topic_prior") or {}).get((kind_key, topic_id)), 0.0))
        if signature in (model.get("direct_pairs") or set()):
            direct_topic_link = 1.0

    topic_span = int((model.get("resource_topic_span") or {}).get(resource_key, 0))
    ambiguity = _clamp((max(0, topic_span - 1)) / 4.0) if explicit_topic_match < 0.45 and direct_topic_link < 1.0 else 0.0
    return {
        "explicit_topic_match": explicit_topic_match,
        "explicit_topic_support": explicit_topic_support,
        "direct_topic_link": direct_topic_link,
        "topic_kind_prior": topic_kind_prior,
        "topic_match_ambiguity": ambiguity,
    }


@st.cache_data(ttl=90, show_spinner=False)
def _load_teacher_material_activity_rows(teacher_id: str) -> list[dict]:
    teacher_id = str(teacher_id or "").strip()
    if not teacher_id:
        return []
    try:
        res = (
            get_sb()
            .table("user_activity_log")
            .select("user_id,activity_type,feature_name,meta_json,created_at")
            .eq("user_id", teacher_id)
            .in_("activity_type", ["teacher_material_impression", "teacher_material_open"])
            .order("created_at", desc=True)
            .limit(5000)
            .execute()
        )
        return getattr(res, "data", None) or []
    except Exception:
        return []


@st.cache_data(ttl=90, show_spinner=False)
def _load_teacher_recommendation_events(teacher_id: str) -> list[dict]:
    teacher_id = str(teacher_id or "").strip()
    if not teacher_id:
        return []
    try:
        res = (
            get_sb()
            .table("learning_program_recommendation_events")
            .select(
                "teacher_id,student_id,recommendation_bucket,recommendation_focus_kind,"
                "resource_kind,resource_record_id,learning_program_topic_id,event_type,event_weight,created_at"
            )
            .eq("teacher_id", teacher_id)
            .order("created_at", desc=True)
            .limit(4000)
            .execute()
        )
        return getattr(res, "data", None) or []
    except Exception:
        return []


def _teacher_event_target(row: dict) -> float:
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


def build_teacher_recommendation_model(teacher_id: str | None = None) -> dict[str, Any]:
    safe_teacher_id = str(teacher_id or get_current_user_id() or "").strip()
    rows = _load_teacher_recommendation_events(safe_teacher_id)
    base_weights = {
        "bias": -0.2,
        "subject_match": 0.85,
        "stage_match": 0.36,
        "level_match": 0.42,
        "topic_overlap": 0.9,
        "title_match": 0.75,
        "objective_match": 0.55,
        "source_own": 0.18,
        "kind_plan": 0.22,
        "kind_worksheet": 0.26,
        "kind_exam": 0.14,
        "kind_video": 0.18,
        "bucket_next_topic": 0.2,
        "bucket_review": 0.26,
        "bucket_pending_gap": 0.18,
        "focus_needs_practice": 0.18,
        "focus_reteach": 0.16,
        "focus_reinforce": 0.12,
        "focus_stretch": 0.08,
        "topic_reference_present": 0.16,
        "exact_topic_match": 0.78,
        "exact_topic_support": 0.32,
        "direct_topic_link": 0.64,
        "topic_kind_prior": 0.34,
        "topic_match_ambiguity": -0.26,
        "prior_kind_success": 0.24,
        "prior_bucket_success": 0.3,
        "prior_focus_success": 0.22,
    }
    if not rows:
        return {
            "weights": base_weights,
            "priors": {"kind": {}, "bucket": {}, "focus": {}},
        }

    topic_model = build_explicit_topic_resource_model(teacher_id=safe_teacher_id)
    samples: list[tuple[dict[str, float], float]] = []
    kind_scores: dict[str, list[float]] = {}
    bucket_scores: dict[str, list[float]] = {}
    focus_scores: dict[str, list[float]] = {}
    for row in rows:
        kind = _norm_key(row.get("resource_kind"))
        bucket = _norm_key(row.get("recommendation_bucket"))
        focus = _norm_key(row.get("recommendation_focus_kind"))
        topic_id = int(row.get("learning_program_topic_id") or 0)
        resource_id = int(row.get("resource_record_id") or 0)
        target = _teacher_event_target(row)
        topic_features = {
            "exact_topic_match": 0.0,
            "exact_topic_support": 0.0,
            "direct_topic_link": 0.0,
            "topic_kind_prior": 0.0,
            "topic_match_ambiguity": 0.0,
        }
        if topic_id > 0 and resource_id > 0:
            topic_features = topic_resource_alignment_features(
                kind,
                resource_id,
                [topic_id],
                teacher_id=safe_teacher_id,
            )
        features = {
            f"kind_{kind}": 1.0 if kind else 0.0,
            f"bucket_{bucket}": 1.0 if bucket else 0.0,
            f"focus_{focus}": 1.0 if focus else 0.0,
            "topic_reference_present": 1.0 if topic_id > 0 else 0.0,
            "exact_topic_match": topic_features["explicit_topic_match"],
            "exact_topic_support": topic_features["explicit_topic_support"],
            "direct_topic_link": topic_features["direct_topic_link"],
            "topic_kind_prior": topic_features["topic_kind_prior"],
            "topic_match_ambiguity": topic_features["topic_match_ambiguity"],
        }
        samples.append((features, target))
        if kind:
            kind_scores.setdefault(kind, []).append(target)
        if bucket:
            bucket_scores.setdefault(bucket, []).append(target)
        if focus:
            focus_scores.setdefault(focus, []).append(target)

    weights = _fit_linear_model(samples, base_weights=base_weights)
    priors = {
        "kind": {key: sum(values) / max(1, len(values)) for key, values in kind_scores.items()},
        "bucket": {key: sum(values) / max(1, len(values)) for key, values in bucket_scores.items()},
        "focus": {key: sum(values) / max(1, len(values)) for key, values in focus_scores.items()},
    }
    return {"weights": weights, "priors": priors}


def score_teacher_resource_candidate(
    row: dict,
    kind: str,
    source: str,
    recommendation_item: dict,
    *,
    teacher_id: str | None = None,
) -> tuple[float, dict[str, float]]:
    model = build_teacher_recommendation_model(teacher_id)
    recommendation_topic_id = int(recommendation_item.get("learning_program_topic_id") or 0)
    topic_features = topic_resource_alignment_features(
        kind,
        row.get("id"),
        [recommendation_topic_id] if recommendation_topic_id > 0 else [],
        teacher_id=teacher_id,
    )
    subject_match = 1.0 if normalize_subject(row.get("subject")) == normalize_subject(recommendation_item.get("subject_key")) else 0.0
    stage_match = 1.0 if _norm_key(row.get("learner_stage")) and _norm_key(row.get("learner_stage")) == _norm_key(recommendation_item.get("learner_stage")) else 0.0
    row_level = _norm_key(row.get("level") if kind == "exam" else row.get("level_or_band"))
    item_level = _norm_key(recommendation_item.get("level_or_band"))
    level_match = 1.0 if row_level and item_level and row_level == item_level else 0.0
    title_tokens = _tokenize(row.get("title"), row.get("topic"))
    query_tokens = _tokenize(recommendation_item.get("title"), recommendation_item.get("objective"))
    title_match = 1.0 if _norm_text(recommendation_item.get("title")) and _norm_text(recommendation_item.get("title")).casefold() in _norm_text(row.get("title")).casefold() else 0.0
    objective_match = 1.0 if _norm_text(recommendation_item.get("objective")) and _norm_text(recommendation_item.get("objective")).casefold() in _norm_text(row.get("title")).casefold() else 0.0
    topic_overlap = _overlap_score(title_tokens, query_tokens)
    bucket = _norm_key(recommendation_item.get("recommendation_bucket"))
    focus = _norm_key(recommendation_item.get("focus_kind"))
    kind_key = _norm_key(kind)

    features = {
        "subject_match": subject_match,
        "stage_match": stage_match,
        "level_match": level_match,
        "title_match": title_match,
        "objective_match": objective_match,
        "topic_overlap": topic_overlap,
        "source_own": 1.0 if source == "own" else 0.0,
        f"kind_{kind_key}": 1.0 if kind_key else 0.0,
        f"bucket_{bucket}": 1.0 if bucket else 0.0,
        f"focus_{focus}": 1.0 if focus else 0.0,
        "topic_reference_present": 1.0 if recommendation_topic_id > 0 else 0.0,
        "exact_topic_match": topic_features["explicit_topic_match"],
        "exact_topic_support": topic_features["explicit_topic_support"],
        "direct_topic_link": topic_features["direct_topic_link"],
        "topic_kind_prior": topic_features["topic_kind_prior"],
        "topic_match_ambiguity": topic_features["topic_match_ambiguity"],
        "prior_kind_success": _safe_float((model.get("priors") or {}).get("kind", {}).get(kind_key), 0.0),
        "prior_bucket_success": _safe_float((model.get("priors") or {}).get("bucket", {}).get(bucket), 0.0),
        "prior_focus_success": _safe_float((model.get("priors") or {}).get("focus", {}).get(focus), 0.0),
    }
    return _score_linear_model(model.get("weights") or {}, features), features


def _accumulate_signal(bucket: dict[str, float], key: str, weight: float) -> None:
    key = str(key or "").strip()
    if not key:
        return
    bucket[key] = _safe_float(bucket.get(key), 0.0) + _safe_float(weight)


def _normalize_signal_map(values: dict[str, float]) -> dict[str, float]:
    if not values:
        return {}
    top = max((_safe_float(value) for value in values.values()), default=0.0)
    if top <= 0:
        return {}
    return {key: _clamp(_safe_float(value) / top) for key, value in values.items()}


@st.cache_data(ttl=90, show_spinner=False)
def build_teacher_material_feed_profile(teacher_id: str | None = None) -> dict[str, Any]:
    safe_teacher_id = str(teacher_id or get_current_user_id() or "").strip()
    profile: dict[str, Any] = {
        "subject_demand": {},
        "stage_demand": {},
        "level_demand": {},
        "kind_demand": {},
        "topic_demand": {},
        "kind_open_rate": {},
        "source_open_rate": {},
        "subject_open_rate": {},
        "topic_open_rate": {},
    }
    if not safe_teacher_id:
        return profile

    try:
        from helpers.learning_programs import load_assignment_progress_map, load_learning_program, load_program_assignments_for_teacher
        from helpers.teacher_student_integration import load_teacher_assignment_progress, load_teacher_review_requests
    except Exception:
        return profile

    try:
        assignment_df = load_program_assignments_for_teacher(limit=240)
    except Exception:
        assignment_df = pd.DataFrame()

    if assignment_df is not None and not assignment_df.empty:
        for row in assignment_df.to_dict("records"):
            program_id = int(row.get("program_id") or 0)
            assignment_id = int(row.get("id") or 0)
            if program_id <= 0 or assignment_id <= 0:
                continue
            try:
                program = load_learning_program(program_id)
            except Exception:
                program = {}
            if not isinstance(program, dict) or not program:
                continue
            subject = normalize_subject(program.get("subject") or row.get("subject_key") or "")
            stage = _norm_text(program.get("learner_stage") or row.get("learner_stage"))
            level = _norm_text(program.get("level_or_band") or row.get("level_or_band"))
            _accumulate_signal(profile["subject_demand"], subject, 1.3)
            _accumulate_signal(profile["stage_demand"], stage, 1.0)
            _accumulate_signal(profile["level_demand"], level, 1.0)
            _accumulate_signal(profile["kind_demand"], "program", 0.5)
            try:
                progress_map = load_assignment_progress_map(assignment_id)
            except Exception:
                progress_map = {}
            latest_completed_position = 0
            ordered_topics: list[tuple[int, dict, dict[str, Any]]] = []
            topic_position = 0
            for unit in program.get("units") or []:
                for topic in unit.get("topics") or []:
                    topic_position += 1
                    topic_id = int(topic.get("topic_id") or 0)
                    topic_progress = progress_map.get(topic_id, {}) if topic_id else {}
                    if truthy_flag(topic_progress.get("teacher_done")):
                        latest_completed_position = max(latest_completed_position, topic_position)
                    ordered_topics.append((topic_position, topic, topic_progress))

            next_topic_recorded = False
            for position, topic, topic_progress in ordered_topics:
                title = _norm_text(topic.get("title"))
                summary = _norm_text(topic.get("student_summary") or topic.get("lesson_focus") or topic.get("subtopic"))
                tokens = _tokenize(title, summary)
                if not tokens:
                    continue
                if not truthy_flag(topic_progress.get("teacher_done")) and not next_topic_recorded:
                    for token in tokens:
                        _accumulate_signal(profile["topic_demand"], token, 1.8)
                    next_topic_recorded = True
                if not truthy_flag(topic_progress.get("teacher_done")) and latest_completed_position > 0 and position < latest_completed_position:
                    for token in tokens:
                        _accumulate_signal(profile["topic_demand"], token, 1.35)
                if truthy_flag(topic_progress.get("teacher_done")) and truthy_flag(topic_progress.get("student_done")):
                    for token in tokens:
                        _accumulate_signal(profile["topic_demand"], token, 0.42)

    try:
        teacher_assignments = load_teacher_assignment_progress()
    except Exception:
        teacher_assignments = []
    for row in teacher_assignments or []:
        latest_attempt = row.get("latest_attempt") or {}
        score_pct = _safe_float(latest_attempt.get("score_pct"), default=_safe_float(row.get("score_pct")))
        weight = 0.0
        if score_pct and score_pct < 75.0:
            weight = 1.45
        elif _norm_key(row.get("status")) in {"requested", "submitted", "started"}:
            weight = 0.74
        if weight <= 0:
            continue
        subject = normalize_subject(row.get("subject_key") or row.get("subject"))
        kind = _norm_key(row.get("assignment_type"))
        if kind == "lesson_plan_topic":
            kind = "plan"
        for token in _tokenize(row.get("topic"), row.get("title")):
            _accumulate_signal(profile["topic_demand"], token, weight)
        _accumulate_signal(profile["subject_demand"], subject, 0.9 + (0.35 if weight > 1.0 else 0.0))
        _accumulate_signal(profile["kind_demand"], kind, 0.8)

    try:
        review_rows = load_teacher_review_requests()
    except Exception:
        review_rows = []
    for row in review_rows or []:
        status = _norm_key(row.get("status"))
        if status not in {"requested", "reviewed"}:
            continue
        weight = 1.25 if status == "requested" else 0.55
        subject = normalize_subject(row.get("subject_key") or row.get("subject_label"))
        for token in _tokenize(row.get("title"), row.get("request_note"), row.get("teacher_feedback")):
            _accumulate_signal(profile["topic_demand"], token, weight)
        _accumulate_signal(profile["subject_demand"], subject, 0.7)
        _accumulate_signal(profile["kind_demand"], _norm_key(row.get("source_type")), 0.6)

    activity_rows = _load_teacher_material_activity_rows(safe_teacher_id)
    impression_counts = {"kind": {}, "source": {}, "subject": {}, "topic": {}}
    open_counts = {"kind": {}, "source": {}, "subject": {}, "topic": {}}
    for row in activity_rows:
        activity_type = _norm_key(row.get("activity_type"))
        meta = row.get("meta_json") if isinstance(row.get("meta_json"), dict) else {}
        kind = _norm_key(meta.get("resource_kind"))
        source = _norm_key(meta.get("source"))
        subject = normalize_subject(meta.get("subject"))
        topic_tokens = _tokenize(meta.get("topic"), meta.get("title"))
        target_map = open_counts if activity_type == "teacher_material_open" else impression_counts
        if kind:
            _accumulate_signal(target_map["kind"], kind, 1.0)
        if source:
            _accumulate_signal(target_map["source"], source, 1.0)
        if subject:
            _accumulate_signal(target_map["subject"], subject, 1.0)
        for token in topic_tokens:
            _accumulate_signal(target_map["topic"], token, 1.0)

    for bucket_name in ("kind", "source", "subject", "topic"):
        exposure_map = impression_counts[bucket_name]
        opened_map = open_counts[bucket_name]
        rate_map = {}
        for key in set(exposure_map) | set(opened_map):
            exposures = _safe_float(exposure_map.get(key), 0.0)
            opens = _safe_float(opened_map.get(key), 0.0)
            if opens <= 0 and exposures <= 0:
                continue
            denominator = max(1.0, exposures + opens)
            rate_map[key] = _clamp(opens / denominator, 0.0, 1.0)
        profile[f"{bucket_name}_open_rate"] = rate_map

    profile["subject_demand"] = _normalize_signal_map(profile["subject_demand"])
    profile["stage_demand"] = _normalize_signal_map(profile["stage_demand"])
    profile["level_demand"] = _normalize_signal_map(profile["level_demand"])
    profile["kind_demand"] = _normalize_signal_map(profile["kind_demand"])
    profile["topic_demand"] = _normalize_signal_map(profile["topic_demand"])
    return profile


def score_teacher_feed_resource(
    row: dict,
    kind: str,
    source: str,
    *,
    teacher_id: str | None = None,
) -> tuple[float, dict[str, float]]:
    profile = build_teacher_material_feed_profile(teacher_id)
    kind_key = _norm_key(kind)
    source_key = _norm_key(source)
    subject = _resource_subject(row)
    stage = _resource_stage(row)
    level = _resource_level(row, kind_key)
    tokens = _tokenize(row.get("title"), _resource_topic_text(row, kind_key), row.get("program_overview"))

    features = {
        "subject_demand": _safe_float((profile.get("subject_demand") or {}).get(subject), 0.0),
        "stage_demand": _safe_float((profile.get("stage_demand") or {}).get(stage), 0.0),
        "level_demand": _safe_float((profile.get("level_demand") or {}).get(level), 0.0),
        "kind_demand": _safe_float((profile.get("kind_demand") or {}).get(kind_key), 0.0),
        "topic_demand": _weighted_token_score(profile.get("topic_demand") or {}, tokens, scale=2.8),
        "kind_open_rate": _safe_float((profile.get("kind_open_rate") or {}).get(kind_key), 0.0),
        "source_open_rate": _safe_float((profile.get("source_open_rate") or {}).get(source_key), 0.0),
        "subject_open_rate": _safe_float((profile.get("subject_open_rate") or {}).get(subject), 0.0),
        "topic_open_rate": _weighted_token_score(profile.get("topic_open_rate") or {}, tokens, scale=2.4),
        "recency": _resource_recency_score(row),
        "source_own": 1.0 if source_key == "own" else 0.0,
    }
    score = (
        0.24 * features["subject_demand"]
        + 0.1 * features["stage_demand"]
        + 0.12 * features["level_demand"]
        + 0.1 * features["kind_demand"]
        + 0.22 * features["topic_demand"]
        + 0.07 * features["kind_open_rate"]
        + 0.04 * features["source_open_rate"]
        + 0.05 * features["subject_open_rate"]
        + 0.04 * features["topic_open_rate"]
        + 0.06 * features["recency"]
        + 0.04 * features["source_own"]
    )
    return score, features


def rank_teacher_resource_feed(
    df: pd.DataFrame,
    kind: str,
    source: str,
    *,
    teacher_id: str | None = None,
) -> pd.DataFrame:
    if df is None or df.empty:
        return df
    ranked = df.copy()
    scored_rows = []
    for row in ranked.to_dict("records"):
        score, _features = score_teacher_feed_resource(row, kind, source, teacher_id=teacher_id)
        scored_rows.append(score)
    ranked["_teacher_feed_score"] = scored_rows
    sort_cols = ["_teacher_feed_score"]
    ascending = [False]
    if "updated_at" in ranked.columns:
        sort_cols.append("updated_at")
        ascending.append(False)
    elif "created_at" in ranked.columns:
        sort_cols.append("created_at")
        ascending.append(False)
    ranked = ranked.sort_values(sort_cols, ascending=ascending, na_position="last").reset_index(drop=True)
    return ranked.drop(columns=["_teacher_feed_score"], errors="ignore")


def _material_log_meta(row: dict, kind: str, source: str, surface: str) -> dict[str, Any]:
    return {
        "surface": str(surface or "").strip(),
        "resource_kind": str(kind or "").strip(),
        "source": str(source or "").strip(),
        "resource_id": row.get("id"),
        "title": _norm_text(row.get("title")),
        "subject": _norm_text(row.get("subject")),
        "learner_stage": _resource_stage(row),
        "level_or_band": _resource_level(row, kind),
        "topic": _resource_topic_text(row, kind),
    }


def log_teacher_material_impressions(
    rows: list[dict],
    kind: str,
    source: str,
    *,
    surface: str,
) -> None:
    safe_rows = [row for row in (rows or []) if isinstance(row, dict)]
    if not safe_rows:
        return
    seen = set(st.session_state.get("_teacher_material_impression_seen") or [])
    payloads = []
    for row in safe_rows[:12]:
        row_id = row.get("id")
        signature = f"{surface}:{kind}:{source}:{row_id}"
        if row_id in (None, "", 0, "0") or signature in seen:
            continue
        seen.add(signature)
        payloads.append(
            with_owner(
                {
                    "activity_type": "teacher_material_impression",
                    "feature_name": "teacher_material_feed",
                    "meta_json": _material_log_meta(row, kind, source, surface),
                    "created_at": _now_iso(),
                }
            )
        )
    if not payloads:
        return
    st.session_state["_teacher_material_impression_seen"] = list(seen)
    try:
        get_sb().table("user_activity_log").insert(payloads).execute()
    except Exception:
        pass


def log_teacher_material_open(
    row: dict,
    kind: str,
    source: str,
    *,
    surface: str,
) -> None:
    if not isinstance(row, dict) or row.get("id") in (None, "", 0, "0"):
        return
    try:
        get_sb().table("user_activity_log").insert(
            with_owner(
                {
                    "activity_type": "teacher_material_open",
                    "feature_name": "teacher_material_feed",
                    "meta_json": _material_log_meta(row, kind, source, surface),
                    "created_at": _now_iso(),
                }
            )
        ).execute()
    except Exception:
        pass


@st.cache_data(ttl=90, show_spinner=False)
def _load_student_history_rows(student_id: str) -> dict[str, list[dict]]:
    safe_student_id = str(student_id or "").strip()
    if not safe_student_id:
        return {"practice_sessions": [], "teacher_assignments": [], "recommendation_activity": []}

    rows = {"practice_sessions": [], "teacher_assignments": [], "recommendation_activity": []}
    try:
        rows["practice_sessions"] = getattr(
            get_sb()
            .table("practice_sessions")
            .select("source_type,subject,topic,level,score_pct,status,created_at,completed_at")
            .eq("user_id", safe_student_id)
            .order("created_at", desc=True)
            .limit(4000)
            .execute(),
            "data",
            None,
        ) or []
    except Exception:
        rows["practice_sessions"] = []

    try:
        rows["teacher_assignments"] = getattr(
            get_sb()
            .table("teacher_assignments")
            .select(
                "assignment_type,subject_key,topic,score_pct,status,created_at,updated_at,"
                "source_record_id,learning_program_topic_id,recommendation_bucket"
            )
            .eq("student_id", safe_student_id)
            .neq("status", "archived")
            .order("updated_at", desc=True)
            .limit(4000)
            .execute(),
            "data",
            None,
        ) or []
    except Exception:
        rows["teacher_assignments"] = []

    try:
        rows["recommendation_activity"] = getattr(
            get_sb()
            .table("user_activity_log")
            .select("activity_type,meta_json,created_at")
            .eq("user_id", safe_student_id)
            .in_("activity_type", ["student_recommendation_impression", "student_recommendation_open"])
            .order("created_at", desc=True)
            .limit(4000)
            .execute(),
            "data",
            None,
        ) or []
    except Exception:
        rows["recommendation_activity"] = []

    return rows


def build_student_recommendation_model(
    student_profile: dict[str, Any],
    *,
    student_id: str | None = None,
) -> dict[str, Any]:
    safe_student_id = str(student_id or get_current_user_id() or "").strip()
    history = _load_student_history_rows(safe_student_id)
    practice_rows = history.get("practice_sessions") or []
    assignment_rows = history.get("teacher_assignments") or []
    activity_rows = history.get("recommendation_activity") or []
    program_signals = student_profile.get("program_signals") or {}

    samples: list[tuple[dict[str, float], float]] = []
    kind_scores: dict[str, list[float]] = {}
    subject_scores: dict[str, list[float]] = {}
    for row in practice_rows:
        kind = _norm_key(row.get("source_type"))
        subject = normalize_subject(row.get("subject"))
        topic = _norm_text(row.get("topic"))
        score = _safe_float(row.get("score_pct")) / 100.0
        features = {
            f"kind_{kind}": 1.0 if kind else 0.0,
            "subject_in_program": 1.0 if subject and subject in set(program_signals.get("subjects") or set()) else 0.0,
            "level_fit": 1.0 if _norm_key(row.get("level")) and _norm_key(row.get("level")) == _norm_key((program_signals.get("subject_levels") or {}).get(subject, "")) else 0.0,
            "topic_in_program": _overlap_score(_tokenize(topic), set(program_signals.get("topic_tokens") or set())),
        }
        target = 0.3 + 0.7 * score
        samples.append((features, target))
        if kind:
            kind_scores.setdefault(kind, []).append(target)
        if subject:
            subject_scores.setdefault(subject, []).append(target)

    for row in assignment_rows:
        assignment_type = _norm_key(row.get("assignment_type"))
        kind = "worksheet" if assignment_type == "worksheet" else ("exam" if assignment_type == "exam" else "")
        if assignment_type == "video":
            kind = "video"
        if not kind:
            continue
        subject = normalize_subject(row.get("subject_key"))
        score = _safe_float(row.get("score_pct")) / 100.0
        status = _norm_key(row.get("status"))
        active_topic_ids = set(program_signals.get("active_topic_ids") or set())
        topic_id = int(row.get("learning_program_topic_id") or 0)
        explicit_alignment = topic_resource_alignment_features(
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
            "subject_in_program": 1.0 if subject and subject in set(program_signals.get("subjects") or set()) else 0.0,
            "topic_in_program": _overlap_score(_tokenize(row.get("topic")), set(program_signals.get("topic_tokens") or set())),
            "explicit_topic_match": explicit_alignment["explicit_topic_match"],
            "explicit_topic_support": explicit_alignment["explicit_topic_support"],
            "direct_topic_link": explicit_alignment["direct_topic_link"],
            "topic_kind_prior": explicit_alignment["topic_kind_prior"],
            "topic_match_ambiguity": explicit_alignment["topic_match_ambiguity"],
        }
        samples.append((features, target))
        kind_scores.setdefault(kind, []).append(target)
        if subject:
            subject_scores.setdefault(subject, []).append(target)

    for row in activity_rows:
        meta = row.get("meta_json") if isinstance(row.get("meta_json"), dict) else {}
        activity_type = _norm_key(row.get("activity_type"))
        kind = _norm_key(meta.get("resource_kind"))
        subject = normalize_subject(meta.get("subject"))
        topic = _norm_text(meta.get("topic"))
        if not kind:
            continue
        target = 0.76 if activity_type == "student_recommendation_open" else 0.18
        features = {
            f"kind_{kind}": 1.0,
            "subject_in_program": 1.0 if subject and subject in set(program_signals.get("subjects") or set()) else 0.0,
            "level_fit": 1.0 if _norm_key(meta.get("level")) and _norm_key(meta.get("level")) == _norm_key((program_signals.get("subject_levels") or {}).get(subject, "")) else 0.0,
            "topic_in_program": _overlap_score(_tokenize(topic), set(program_signals.get("topic_tokens") or set())),
            "program_type_fit": 1.0 if bool(meta.get("assigned_resource")) else 0.0,
            "completion_fit": _safe_float(meta.get("ml_blend_weight"), 0.0),
            "topic_need": _safe_float(meta.get("ml_score"), 0.0),
        }
        samples.append((features, target))
        kind_scores.setdefault(kind, []).append(target)
        if subject:
            subject_scores.setdefault(subject, []).append(target)

    base_weights = {
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
    weights = _fit_linear_model(samples, base_weights=base_weights) if samples else base_weights
    priors = {
        "kind": {key: sum(values) / max(1, len(values)) for key, values in kind_scores.items()},
        "subject": {key: sum(values) / max(1, len(values)) for key, values in subject_scores.items()},
    }
    return {"weights": weights, "priors": priors}


def score_student_resource_candidate(
    feature_values: dict[str, float],
    student_profile: dict[str, Any],
    *,
    student_id: str | None = None,
) -> float:
    model = build_student_recommendation_model(student_profile, student_id=student_id)
    return _score_linear_model(model.get("weights") or {}, feature_values)
