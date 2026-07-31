from __future__ import annotations

import re
import html as _html
from difflib import SequenceMatcher
from typing import Any

import pandas as pd
import streamlit as st

from core.i18n import t
from core.database import register_cache
from core.state import get_current_user_id
from helpers.recommendation_models import resource_semantic_affinity
from helpers.resource_affinity_runtime import resource_affinity_score


def _normalize_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").casefold()).strip()


def _normalize_subject(value: Any) -> str:
    text = _normalize_text(value)
    aliases = {
        "english language": "english",
        "english as a second language": "english",
        "esl": "english",
        "ela": "english",
        "mathematics": "math",
        "maths": "math",
        "science ": "science",
    }
    return aliases.get(text, text)


def _tokenize(*values: Any) -> set[str]:
    tokens: set[str] = set()
    for value in values:
        for raw in re.split(r"\W+", str(value or "").casefold()):
            cleaned = "".join(ch for ch in raw if ch.isalnum())
            if len(cleaned) >= 3:
                tokens.add(cleaned)
    return tokens


_TOPIC_STOPWORDS = {
    "the", "and", "for", "with", "from", "about", "into", "your",
    "las", "los", "una", "uno", "unos", "unas", "para", "con", "sin", "por",
    "del", "las", "mis", "mi", "de", "en", "la", "el",
}

_WORKSHEET_TYPE_ALIASES = {
    "true_false": "true_false",
    "verdadero_falso": "true_false",
    "verdadero_false": "true_false",
    "truefalse": "true_false",
    "multiple_choice": "multiple_choice",
    "opcion_multiple": "multiple_choice",
    "opción_múltiple": "multiple_choice",
    "matching": "matching",
    "emparejar": "matching",
    "fill_in_the_blanks": "fill_in_the_blanks",
    "completar_los_espacios": "fill_in_the_blanks",
    "short_answer": "short_answer",
    "respuesta_corta": "short_answer",
    "reading_comprehension": "reading_comprehension",
    "comprension_lectora": "reading_comprehension",
    "comprensión_lectora": "reading_comprehension",
    "error_correction": "error_correction",
    "correccion_de_errores": "error_correction",
    "corrección_de_errores": "error_correction",
    "word_search_vocab": "word_search_vocab",
    "sopa_de_letras": "word_search_vocab",
}


def _overlap_score(query_tokens: set[str], row_tokens: set[str]) -> float:
    if not query_tokens or not row_tokens:
        return 0.0
    shared = len(query_tokens & row_tokens)
    return shared / max(1.0, len(query_tokens))


def _text_similarity(query: str, target: str) -> float:
    if not query or not target:
        return 0.0
    if query in target:
        return 1.0
    return SequenceMatcher(None, query, target).ratio()


def _canonical_key(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(value or "").casefold()).strip("_")


def _canonical_worksheet_type(value: Any) -> str:
    key = _canonical_key(value)
    return _WORKSHEET_TYPE_ALIASES.get(key, key)


def _topic_tokens(*values: Any) -> set[str]:
    return {token for token in _tokenize(*values) if token not in _TOPIC_STOPWORDS}


def _topic_focus_features(row: dict, kind: str, request: dict) -> dict[str, float]:
    request_topic = _normalize_text(request.get("topic"))
    row_topic = _normalize_text(row.get("topic") or row.get("title"))
    request_topic_tokens = _topic_tokens(request.get("topic"), request.get("objective"))
    row_topic_tokens = _topic_tokens(row.get("topic"), row.get("title"), row.get("description"))
    topic_token_overlap = _overlap_score(request_topic_tokens, row_topic_tokens)
    topic_text_similarity = _text_similarity(request_topic, row_topic)
    exact_topic_match = 1.0 if request_topic and row_topic and request_topic == row_topic else 0.0
    contained_topic_match = 1.0 if request_topic and row_topic and not exact_topic_match and (request_topic in row_topic or row_topic in request_topic) else 0.0
    requested_type = ""
    row_type = ""
    subtype_match = 0.0
    if kind == "worksheet":
        requested_type = _canonical_worksheet_type(request.get("worksheet_type"))
        row_type = _canonical_worksheet_type(row.get("worksheet_type"))
        if requested_type and row_type:
            subtype_match = 1.0 if requested_type == row_type else 0.0
    elif kind == "plan":
        requested_type = _canonical_key(request.get("lesson_purpose"))
        row_type = _canonical_key(row.get("lesson_purpose"))
        if requested_type and row_type:
            subtype_match = 1.0 if requested_type == row_type else 0.0
    elif kind == "exam":
        requested = {_canonical_key(item) for item in (request.get("exercise_types") or []) if _canonical_key(item)}
        current = {_canonical_key(item) for item in (row.get("exercise_types") or []) if _canonical_key(item)}
        if requested and current:
            subtype_match = len(requested & current) / max(1.0, len(requested))
    return {
        "request_topic": request_topic,
        "row_topic": row_topic,
        "request_topic_token_count": float(len(request_topic_tokens)),
        "row_topic_token_count": float(len(row_topic_tokens)),
        "topic_token_overlap": topic_token_overlap,
        "topic_text_similarity": topic_text_similarity,
        "exact_topic_match": exact_topic_match,
        "contained_topic_match": contained_topic_match,
        "subtype_match": subtype_match,
        "requested_type": requested_type,
        "row_type": row_type,
    }


def _level_similarity(target_level: Any, resource_level: Any) -> float:
    target = str(target_level or "").strip()
    resource = str(resource_level or "").strip()
    if not target or not resource:
        return 0.55
    if target == resource:
        return 1.0

    cefr = ["A1", "A2", "B1", "B2", "C1", "C2"]
    generic = ["beginner_band", "intermediate_band", "advanced_band"]
    if target in cefr and resource in cefr:
        distance = abs(cefr.index(target) - cefr.index(resource))
        return {1: 0.82, 2: 0.6}.get(distance, 0.25)
    if target in generic and resource in generic:
        distance = abs(generic.index(target) - generic.index(resource))
        return {1: 0.8, 2: 0.45}.get(distance, 0.25)
    return 0.4


def _level_distance(target_level: Any, resource_level: Any) -> int | None:
    target = str(target_level or "").strip()
    resource = str(resource_level or "").strip()
    if not target or not resource:
        return None
    if target == resource:
        return 0

    cefr = ["A1", "A2", "B1", "B2", "C1", "C2"]
    generic = ["beginner_band", "intermediate_band", "advanced_band"]
    if target in cefr and resource in cefr:
        return abs(cefr.index(target) - cefr.index(resource))
    if target in generic and resource in generic:
        return abs(generic.index(target) - generic.index(resource))
    return None


def _resource_level(row: dict, kind: str) -> str:
    if kind == "exam":
        return str(row.get("level") or row.get("level_or_band") or "").strip()
    return str(row.get("level_or_band") or row.get("level") or "").strip()


def _translated_value_label(value: Any) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    key = re.sub(r"[^a-z0-9]+", "_", raw.casefold()).strip("_")
    if not key:
        return raw
    translated = t(key)
    return translated if translated != key else raw.replace("_", " ").title()


def _source_label(value: Any) -> str:
    raw = str(value or "").strip().casefold()
    if raw in {"own", "community"}:
        return t(f"recommended_resource_source_{raw}")
    return _translated_value_label(value)


def _resource_search_text(row: dict, kind: str) -> str:
    if kind == "plan":
        fields = ["title", "topic", "lesson_purpose", "subject", "learner_stage", "level_or_band", "author_name"]
    elif kind == "worksheet":
        fields = ["title", "topic", "worksheet_type", "subject", "learner_stage", "level_or_band", "author_name"]
    elif kind == "video":
        fields = ["title", "topic", "description", "subject", "learner_stage", "level_or_band", "author_name"]
    else:
        fields = ["title", "topic", "exam_length", "subject", "learner_stage", "level", "author_name"]
    return _normalize_text(" ".join(str(row.get(field) or "") for field in fields))


def _resource_tokens(row: dict, kind: str) -> set[str]:
    tokens = _tokenize(
        row.get("title"),
        row.get("topic"),
        row.get("description"),
        row.get("subject"),
        row.get("learner_stage"),
        row.get("level_or_band"),
        row.get("level"),
        row.get("lesson_purpose"),
        row.get("worksheet_type"),
        row.get("exam_length"),
    )
    if kind == "exam":
        for item in row.get("exercise_types") or []:
            tokens.update(_tokenize(item))
    return tokens


def _load_df(loader) -> pd.DataFrame:
    try:
        df = loader()
    except Exception:
        df = pd.DataFrame()
    return df if isinstance(df, pd.DataFrame) else pd.DataFrame()


@st.cache_data(show_spinner=False, ttl=600)
def _load_material_pool_cached(uid: str) -> list[dict]:
    from helpers.archive_utils import is_archived_status
    from helpers.planner_storage import load_my_lesson_plans, load_public_lesson_plans
    from helpers.quick_exam_storage import load_my_exams, load_public_exams
    from helpers.video_library import load_my_videos, load_public_videos
    from helpers.worksheet_storage import load_my_worksheets, load_public_worksheets

    pool: list[dict] = []
    source_loaders = [
        ("plan", "own", load_my_lesson_plans),
        ("plan", "community", load_public_lesson_plans),
        ("worksheet", "own", load_my_worksheets),
        ("worksheet", "community", load_public_worksheets),
        ("exam", "own", load_my_exams),
        ("exam", "community", load_public_exams),
        ("video", "own", load_my_videos),
        ("video", "community", load_public_videos),
    ]

    seen_signatures: set[tuple[str, str, str, str, str]] = set()
    for kind, source, loader in source_loaders:
        df = _load_df(loader)
        if df.empty:
            continue
        for row in df.reset_index(drop=True).to_dict("records"):
            if is_archived_status(row.get("status")):
                continue
            row = dict(row)
            signature = (
                kind,
                _normalize_text(row.get("title")),
                _normalize_text(row.get("topic")),
                _normalize_text(_resource_level(row, kind)),
                _normalize_text(row.get("worksheet_type") or row.get("lesson_purpose") or row.get("exam_length") or row.get("description")),
            )
            if signature in seen_signatures:
                continue
            seen_signatures.add(signature)
            pool.append(
                {
                    "kind": kind,
                    "source": source,
                    "row": row,
                    "search_text": _resource_search_text(row, kind),
                    "tokens": _resource_tokens(row, kind),
                }
            )
    return pool


register_cache(_load_material_pool_cached)


def load_material_pool() -> list[dict]:
    return _load_material_pool_cached(str(get_current_user_id() or ""))


def build_generation_request(
    *,
    kind: str,
    subject: str,
    learner_stage: str,
    level_or_band: str,
    topic: str,
    lesson_purpose: str = "",
    worksheet_type: str = "",
    exercise_types: list[str] | None = None,
    student_profile: dict | None = None,
) -> dict:
    profile = student_profile or {}
    program_context = profile.get("program_context") or {}
    weak_topics = profile.get("weak_topics") or []
    normalized_weak_topics: list[str] = []
    for item in weak_topics:
        if isinstance(item, dict):
            text = str(item.get("topic") or item.get("title") or "").strip()
        else:
            text = str(item or "").strip()
        if text:
            normalized_weak_topics.append(text)
    return {
        "kind": str(kind or "").strip(),
        "subject": str(subject or "").strip(),
        "learner_stage": str(learner_stage or "").strip(),
        "level_or_band": str(level_or_band or "").strip(),
        "topic": str(topic or "").strip(),
        "lesson_purpose": str(lesson_purpose or "").strip(),
        "worksheet_type": str(worksheet_type or "").strip(),
        "exercise_types": [str(item or "").strip() for item in (exercise_types or []) if str(item or "").strip()],
        "objective": str(((program_context.get("next_objectives") or [""])[0]) or "").strip(),
        "next_topics": [str(item or "").strip() for item in (program_context.get("next_topics") or []) if str(item or "").strip()],
        "weak_topics": normalized_weak_topics,
    }


def _request_tokens(request: dict) -> set[str]:
    return _tokenize(
        request.get("topic"),
        request.get("objective"),
        request.get("lesson_purpose"),
        request.get("worksheet_type"),
        " ".join(request.get("exercise_types") or []),
        " ".join(request.get("next_topics") or []),
        " ".join(request.get("weak_topics") or []),
    )


def _same_task_type(kind: str, focus: dict, request: dict, row: dict) -> bool:
    subtype_match = float(focus.get("subtype_match") or 0.0)
    if kind in {"worksheet", "plan"}:
        requested_type = str(focus.get("requested_type") or "")
        row_type = str(focus.get("row_type") or "")
        if requested_type and row_type:
            return subtype_match >= 1.0
        return True
    if kind == "exam":
        row_types = {_canonical_key(item) for item in (row.get("exercise_types") or []) if _canonical_key(item)}
        requested_types = {_canonical_key(item) for item in (request.get("exercise_types") or []) if _canonical_key(item)}
        if requested_types and row_types:
            return bool(requested_types & row_types)
    return True


def _topic_evidence(focus: dict, semantic_affinity: float) -> dict[str, bool | float]:
    exact_topic_match = float(focus.get("exact_topic_match") or 0.0)
    contained_topic_match = float(focus.get("contained_topic_match") or 0.0)
    topic_token_overlap = float(focus.get("topic_token_overlap") or 0.0)
    topic_text_similarity = float(focus.get("topic_text_similarity") or 0.0)
    very_strong = bool(
        exact_topic_match
        or contained_topic_match
        or topic_token_overlap >= 0.62
        or topic_text_similarity >= 0.86
        or semantic_affinity >= 0.84
    )
    strong = bool(
        very_strong
        or topic_token_overlap >= 0.44
        or topic_text_similarity >= 0.72
        or semantic_affinity >= 0.72
    )
    moderate = bool(
        strong
        or topic_token_overlap >= 0.24
        or topic_text_similarity >= 0.46
        or semantic_affinity >= 0.56
    )
    return {
        "very_strong": very_strong,
        "strong": strong,
        "moderate": moderate,
        "exact_topic_match": exact_topic_match,
        "contained_topic_match": contained_topic_match,
        "topic_token_overlap": topic_token_overlap,
        "topic_text_similarity": topic_text_similarity,
    }


def _classify_recommendation_bucket(resource: dict, request: dict) -> dict | None:
    kind = str(resource.get("kind") or "")
    row = resource.get("row") or {}
    request_kind = str(request.get("kind") or "")
    if request_kind and request_kind != kind:
        return None

    request_subject = _normalize_subject(request.get("subject"))
    row_subject = _normalize_subject(row.get("subject"))
    if request_subject and row_subject and request_subject != row_subject:
        return None

    request_stage = _normalize_text(request.get("learner_stage"))
    row_stage = _normalize_text(row.get("learner_stage"))
    focus = _topic_focus_features(row, kind, request)
    query_text = _normalize_text(" ".join(
        [
            str(request.get("topic") or ""),
            str(request.get("objective") or ""),
            str(request.get("lesson_purpose") or ""),
            str(request.get("worksheet_type") or ""),
            " ".join(request.get("exercise_types") or []),
        ]
    ))
    topic_similarity = _text_similarity(query_text, str(resource.get("search_text") or ""))
    token_overlap = _overlap_score(_request_tokens(request), resource.get("tokens") or set())
    topic_token_overlap = float(focus.get("topic_token_overlap") or 0.0)
    topic_text_similarity = float(focus.get("topic_text_similarity") or 0.0)
    semantic_affinity = resource_semantic_affinity(row, kind, request)
    unsupervised_affinity, _unsupervised_affinity_meta = resource_affinity_score(row, kind, request)
    request_topic = str(focus.get("request_topic") or "")
    row_topic = str(focus.get("row_topic") or "")
    level_score = _level_similarity(request.get("level_or_band"), _resource_level(row, kind))
    level_distance = _level_distance(request.get("level_or_band"), _resource_level(row, kind))
    exact_level = level_distance == 0
    adjacent_level = level_distance in {0, 1}
    stage_match = not (request_stage and row_stage) or request_stage == row_stage
    same_task_type = _same_task_type(kind, focus, request, row)
    topic_evidence = _topic_evidence(focus, semantic_affinity)

    if request_topic and row_topic and not topic_evidence["moderate"]:
        return None

    if kind == "worksheet" and focus.get("requested_type") and focus.get("row_type") and not same_task_type and not topic_evidence["strong"]:
        return None

    strong_cluster_affinity = bool(
        unsupervised_affinity >= 0.68
        or semantic_affinity >= 0.66
        or topic_token_overlap >= 0.34
        or topic_similarity >= 0.64
    )
    moderate_cluster_affinity = bool(
        strong_cluster_affinity
        or unsupervised_affinity >= 0.54
        or semantic_affinity >= 0.56
        or topic_token_overlap >= 0.24
        or topic_similarity >= 0.52
    )

    bucket = ""
    if topic_evidence["strong"] and same_task_type and exact_level and stage_match:
        bucket = "very_close"
    elif strong_cluster_affinity and adjacent_level and stage_match:
        bucket = "close"
    elif moderate_cluster_affinity and stage_match and (
        (level_distance is not None and level_distance >= 1)
        or not same_task_type
    ):
        bucket = "related"
    else:
        return None

    score = 0.0
    score += 6.6 * topic_similarity
    score += 6.0 * topic_token_overlap
    score += 3.2 * token_overlap
    score += 3.0 * semantic_affinity
    score += 2.2 * unsupervised_affinity
    score += 5.2 * float(topic_evidence["exact_topic_match"] or 0.0)
    score += 3.0 * float(topic_evidence["contained_topic_match"] or 0.0)
    score += 1.5 * level_score

    if kind == "worksheet":
        requested_type = str(focus.get("requested_type") or "")
        row_type = str(focus.get("row_type") or "")
        if requested_type and row_type:
            score += 2.4 if requested_type == row_type else -0.8
    elif kind == "plan":
        requested_purpose = _canonical_key(request.get("lesson_purpose"))
        row_purpose = _canonical_key(row.get("lesson_purpose"))
        if requested_purpose and row_purpose:
            score += 2.1 if requested_purpose == row_purpose else -0.6
    elif kind == "exam":
        row_types = {_canonical_key(item) for item in (row.get("exercise_types") or []) if _canonical_key(item)}
        requested_types = {_canonical_key(item) for item in (request.get("exercise_types") or []) if _canonical_key(item)}
        if requested_types and row_types:
            overlap = len(requested_types & row_types) / max(1.0, len(requested_types))
            score += 2.2 * overlap

    return {
        "bucket": bucket,
        "score": score,
        "topic_focus": focus,
        "semantic_affinity": semantic_affinity,
        "unsupervised_affinity": unsupervised_affinity,
        "topic_evidence": topic_evidence,
        "level_distance": level_distance,
        "same_task_type": same_task_type,
        "stage_match": stage_match,
    }


def _bucket_priority(bucket: str) -> int:
    return {"very_close": 0, "close": 1, "related": 2}.get(str(bucket or ""), 99)


def find_similar_materials(
    request: dict,
    *,
    limit: int = 3,
    min_score: float = 0.0,
) -> list[dict]:
    ranked: list[dict] = []
    for resource in load_material_pool():
        classified = _classify_recommendation_bucket(resource, request)
        if not classified:
            continue
        score = float(classified.get("score") or 0.0)
        if score < min_score:
            continue
        ranked.append(
            {
                **resource,
                "request": dict(request or {}),
                "recommendation_bucket": classified.get("bucket"),
                "score": score,
                "topic_focus": classified.get("topic_focus") or {},
                "semantic_affinity": float(classified.get("semantic_affinity") or 0.0),
                "unsupervised_affinity": float(classified.get("unsupervised_affinity") or 0.0),
                "topic_evidence": classified.get("topic_evidence") or {},
                "level_distance": classified.get("level_distance"),
                "same_task_type": bool(classified.get("same_task_type")),
                "stage_match": bool(classified.get("stage_match")),
            }
        )
    if not ranked:
        return []
    best_bucket_priority = min(_bucket_priority(str(item.get("recommendation_bucket") or "")) for item in ranked)
    filtered = [item for item in ranked if _bucket_priority(str(item.get("recommendation_bucket") or "")) == best_bucket_priority]
    filtered.sort(
        key=lambda item: (
            0 if str(item.get("source") or "") == "own" else 1,
            -float(item.get("score") or 0.0),
        )
    )
    return filtered[: max(1, int(limit))]


def has_strong_material_match(resources: list[dict]) -> bool:
    if not resources:
        return False
    top = resources[0]
    return str(top.get("recommendation_bucket") or "") == "very_close"


def request_signature(request: dict) -> str:
    return "|".join(
        [
            str(request.get("kind") or "").strip(),
            str(request.get("subject") or "").strip(),
            str(request.get("learner_stage") or "").strip(),
            str(request.get("level_or_band") or "").strip(),
            str(request.get("topic") or "").strip(),
            str(request.get("lesson_purpose") or "").strip(),
            str(request.get("worksheet_type") or "").strip(),
            ",".join(request.get("exercise_types") or []),
        ]
    )


def maybe_pause_generation_for_matches(request: dict, *, state_prefix: str) -> bool:
    matches = find_similar_materials(request, limit=3)
    if not has_strong_material_match(matches):
        st.session_state.pop(f"{state_prefix}_reuse_gate_pending", None)
        return False
    signature = request_signature(request)
    approved_signature = str(st.session_state.get(f"{state_prefix}_reuse_gate_approved") or "")
    if approved_signature == signature:
        return False
    st.session_state[f"{state_prefix}_reuse_gate_pending"] = signature
    return True


def is_generation_reuse_gate_pending(request: dict, *, state_prefix: str) -> bool:
    signature = request_signature(request)
    pending_signature = str(st.session_state.get(f"{state_prefix}_reuse_gate_pending") or "")
    return bool(signature and pending_signature == signature)


def approve_generation_reuse_gate(request: dict, *, state_prefix: str) -> None:
    signature = request_signature(request)
    if signature:
        st.session_state[f"{state_prefix}_reuse_gate_approved"] = signature


def _score_label(bucket: str) -> str:
    if bucket == "very_close":
        return t("material_similarity_very_close")
    if bucket == "close":
        return t("material_similarity_close")
    return t("material_similarity_related")


def render_generation_recommendations(
    request: dict,
    *,
    state_prefix: str,
    title_key: str = "material_recommendations_title",
    subtitle_key: str = "material_recommendations_subtitle",
) -> list[dict]:
    topic = str(request.get("topic") or "").strip()
    if not topic:
        return []

    matches = find_similar_materials(request, limit=3)
    if not matches:
        return []

    signature = request_signature(request)
    pending_signature = str(st.session_state.get(f"{state_prefix}_reuse_gate_pending") or "")

    if pending_signature and pending_signature != signature:
        st.session_state.pop(f"{state_prefix}_reuse_gate_pending", None)
        st.session_state.pop(f"{state_prefix}_reuse_gate_approved", None)
        pending_signature = ""

    card_html = [
        "<div style='margin:10px 0 14px 0;padding:14px 14px 8px;border-radius:18px;"
        "border:1px solid color-mix(in srgb, var(--success, #10b981) 24%, var(--border, rgba(148,163,184,.18)) 76%);"
        "background:linear-gradient(180deg,"
        "color-mix(in srgb, var(--panel, rgba(255,255,255,.96)) 94%, white 6%),"
        "color-mix(in srgb, var(--panel-soft, rgba(236,253,245,.96)) 82%, var(--success, #10b981) 18%));"
        "box-shadow:var(--shadow-sm, 0 2px 8px rgba(15,23,42,.06));'>"
        f"<div style='font-weight:900;color:var(--text, #0f172a);'>{_html.escape(t(title_key))}</div>"
        f"<div style='margin-top:4px;color:var(--muted, #64748b);font-size:.86rem;line-height:1.45;'>{_html.escape(t(subtitle_key))}</div>"
    ]
    for match in matches:
        row = match.get("row") or {}
        meta = [
            _source_label(match.get("source")),
            _translated_value_label(row.get("subject")),
            str(_resource_level(row, str(match.get("kind") or "")) or "").strip(),
        ]
        if match.get("kind") == "worksheet":
            meta.append(_translated_value_label(row.get("worksheet_type")))
        elif match.get("kind") == "plan":
            meta.append(_translated_value_label(row.get("lesson_purpose")))
        elif match.get("kind") == "video":
            meta.append(t("video_label"))
        else:
            meta.append(_translated_value_label(row.get("exam_length")))
        meta_text = " · ".join(part for part in meta if part)
        card_html.append(
            "<div style='margin-top:10px;padding:10px 11px;border-radius:14px;"
            "border:1px solid var(--border, rgba(148,163,184,.18));"
            "background:linear-gradient(180deg,"
            "color-mix(in srgb, var(--panel, rgba(255,255,255,.94)) 96%, white 4%),"
            "color-mix(in srgb, var(--panel-soft, rgba(248,250,252,.92)) 90%, var(--success, #10b981) 10%));"
            "box-shadow:var(--shadow-sm, 0 2px 8px rgba(15,23,42,.06));'>"
            f"<div style='display:flex;justify-content:space-between;gap:8px;align-items:flex-start;'><div style='font-weight:800;color:var(--text, #0f172a);'>{_html.escape(str(row.get('title') or t('untitled_plan')).strip())}</div>"
            f"<div style='flex:0 0 auto;border-radius:999px;padding:4px 8px;"
            "background:color-mix(in srgb, var(--success, #10b981) 16%, transparent);"
            "color:var(--success, #047857);font-size:.72rem;font-weight:800;"
            "border:1px solid color-mix(in srgb, var(--success, #10b981) 22%, transparent);'>"
            f"{_html.escape(_score_label(str(match.get('recommendation_bucket') or '')))}</div></div>"
            f"<div style='margin-top:4px;color:var(--muted, #64748b);font-size:.8rem;line-height:1.35;'>{_html.escape(str(row.get('topic') or '').strip())}</div>"
            f"<div style='margin-top:6px;color:color-mix(in srgb, var(--muted, #64748b) 82%, var(--text, #0f172a) 18%);font-size:.76rem;'>{_html.escape(meta_text)}</div>"
            "</div>"
        )
    card_html.append("</div>")
    st.markdown("".join(card_html), unsafe_allow_html=True)

    if pending_signature == signature and has_strong_material_match(matches):
        st.warning(t("material_recommendations_generate_anyway_warning"))

    for idx, match in enumerate(matches):
        row = match.get("row") or {}
        columns = st.columns([3, 1, 1], gap="small")
        with columns[0]:
            st.caption(f"{str(row.get('title') or t('untitled_plan')).strip()}  |  {_score_label(str(match.get('recommendation_bucket') or ''))}")
        with columns[1]:
            if st.button(t("material_recommendations_open"), key=f"{state_prefix}_match_open_{idx}", use_container_width=True):
                open_material_recommendation(match, assign=False, open_in_files=False)
        with columns[2]:
            if st.button(t("material_recommendations_assign"), key=f"{state_prefix}_match_assign_{idx}", use_container_width=True):
                open_material_recommendation(match, assign=True, open_in_files=False)

    from helpers.teacher_student_integration import render_resource_bulk_assign_dialog

    for kind in ("worksheet", "exam", "plan", "video"):
        render_resource_bulk_assign_dialog(kind_filter=kind)
    try:
        from helpers.learning_programs import render_learning_program_assign_dialog

        render_learning_program_assign_dialog()
    except Exception:
        pass

    return matches


def open_material_recommendation(
    resource: dict,
    *,
    assign: bool = False,
    open_in_files: bool = False,
    fixed_link_id: int | str | None = None,
) -> None:
    kind = str(resource.get("kind") or "")
    row = dict(resource.get("row") or {})
    if assign:
        if kind == "program":
            from helpers.learning_programs import open_learning_program_assign_dialog

            open_learning_program_assign_dialog(row)
            return
        from helpers.teacher_student_integration import open_resource_bulk_assign_dialog

        open_resource_bulk_assign_dialog(kind, row, fixed_link_id=fixed_link_id)
        return
    if kind == "worksheet":
        from helpers.worksheet_storage import _open_worksheet_library_record

        _open_worksheet_library_record(row, open_in_files=open_in_files, expand_assign=assign)
        return
    if kind == "exam":
        from helpers.quick_exam_storage import _open_exam_library_record

        _open_exam_library_record(row, open_in_files=open_in_files, expand_assign=assign)
        return
    if kind == "plan":
        from helpers.planner_storage import _open_plan_library_record

        _open_plan_library_record(row, open_in_files=open_in_files, expand_assign=assign)
        return
    if kind == "video":
        from helpers.video_library import _open_video_library_record

        _open_video_library_record(row, open_in_files=open_in_files, expand_assign=assign)
