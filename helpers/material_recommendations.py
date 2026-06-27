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


def _resource_level(row: dict, kind: str) -> str:
    if kind == "exam":
        return str(row.get("level") or row.get("level_or_band") or "").strip()
    return str(row.get("level_or_band") or row.get("level") or "").strip()


def _resource_search_text(row: dict, kind: str) -> str:
    if kind == "plan":
        fields = ["title", "topic", "lesson_purpose", "subject", "learner_stage", "level_or_band", "author_name"]
    elif kind == "worksheet":
        fields = ["title", "topic", "worksheet_type", "subject", "learner_stage", "level_or_band", "author_name"]
    else:
        fields = ["title", "topic", "exam_length", "subject", "learner_stage", "level", "author_name"]
    return _normalize_text(" ".join(str(row.get(field) or "") for field in fields))


def _resource_tokens(row: dict, kind: str) -> set[str]:
    tokens = _tokenize(
        row.get("title"),
        row.get("topic"),
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
    from helpers.worksheet_storage import load_my_worksheets, load_public_worksheets

    pool: list[dict] = []
    source_loaders = [
        ("plan", "own", load_my_lesson_plans),
        ("plan", "community", load_public_lesson_plans),
        ("worksheet", "own", load_my_worksheets),
        ("worksheet", "community", load_public_worksheets),
        ("exam", "own", load_my_exams),
        ("exam", "community", load_public_exams),
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
                _normalize_text(row.get("worksheet_type") or row.get("lesson_purpose") or row.get("exam_length")),
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


def _material_score(resource: dict, request: dict) -> float:
    kind = str(resource.get("kind") or "")
    row = resource.get("row") or {}
    request_kind = str(request.get("kind") or "")
    if request_kind and request_kind != kind:
        return -1.0

    request_subject = _normalize_subject(request.get("subject"))
    row_subject = _normalize_subject(row.get("subject"))
    if request_subject and row_subject and request_subject != row_subject:
        return -1.0

    score = 0.0
    request_stage = _normalize_text(request.get("learner_stage"))
    row_stage = _normalize_text(row.get("learner_stage"))
    if request_stage and row_stage:
        score += 1.3 if request_stage == row_stage else -0.6

    level_score = _level_similarity(request.get("level_or_band"), _resource_level(row, kind))
    score += 2.0 * level_score

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
    score += 5.2 * topic_similarity
    score += 4.0 * token_overlap

    row_topic = _normalize_text(row.get("topic"))
    request_topic = _normalize_text(request.get("topic"))
    if request_topic and row_topic:
        if request_topic == row_topic:
            score += 4.0
        elif request_topic in row_topic or row_topic in request_topic:
            score += 2.4

    if kind == "worksheet":
        requested_type = _normalize_text(request.get("worksheet_type"))
        row_type = _normalize_text(row.get("worksheet_type"))
        if requested_type and row_type:
            score += 2.0 if requested_type == row_type else -0.4
    elif kind == "plan":
        requested_purpose = _normalize_text(request.get("lesson_purpose"))
        row_purpose = _normalize_text(row.get("lesson_purpose"))
        if requested_purpose and row_purpose:
            score += 1.8 if requested_purpose == row_purpose else -0.2
    elif kind == "exam":
        row_types = {_normalize_text(item) for item in (row.get("exercise_types") or []) if _normalize_text(item)}
        requested_types = {_normalize_text(item) for item in (request.get("exercise_types") or []) if _normalize_text(item)}
        if requested_types and row_types:
            overlap = len(requested_types & row_types) / max(1.0, len(requested_types))
            score += 2.4 * overlap

    if resource.get("source") == "own":
        score += 0.9
    return score


def find_similar_materials(
    request: dict,
    *,
    limit: int = 3,
    min_score: float = 5.2,
) -> list[dict]:
    ranked: list[dict] = []
    for resource in load_material_pool():
        score = _material_score(resource, request)
        if score < min_score:
            continue
        ranked.append({**resource, "score": score})
    ranked.sort(key=lambda item: float(item.get("score") or 0.0), reverse=True)
    return ranked[: max(1, int(limit))]


def has_strong_material_match(resources: list[dict]) -> bool:
    return bool(resources and float(resources[0].get("score") or 0.0) >= 8.8)


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


def _score_label(score: float) -> str:
    if score >= 11.0:
        return t("material_similarity_very_close")
    if score >= 8.5:
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
        st.caption(t("material_recommendations_empty"))
        return []

    signature = request_signature(request)
    pending_signature = str(st.session_state.get(f"{state_prefix}_reuse_gate_pending") or "")

    if pending_signature and pending_signature != signature:
        st.session_state.pop(f"{state_prefix}_reuse_gate_pending", None)
        st.session_state.pop(f"{state_prefix}_reuse_gate_approved", None)
        pending_signature = ""

    card_html = [
        "<div style='margin:10px 0 14px 0;padding:14px 14px 8px;border-radius:18px;"
        "border:1px solid rgba(16,185,129,.18);background:linear-gradient(180deg,rgba(255,255,255,.98),rgba(236,253,245,.98));'>"
        f"<div style='font-weight:900;color:#0f172a;'>{_html.escape(t(title_key))}</div>"
        f"<div style='margin-top:4px;color:#64748b;font-size:.86rem;line-height:1.45;'>{_html.escape(t(subtitle_key))}</div>"
    ]
    for match in matches:
        row = match.get("row") or {}
        meta = [
            str(match.get("source") or "").title(),
            str(row.get("subject") or "").strip(),
            str(_resource_level(row, str(match.get("kind") or "")) or "").strip(),
        ]
        if match.get("kind") == "worksheet":
            meta.append(str(row.get("worksheet_type") or "").strip())
        elif match.get("kind") == "plan":
            meta.append(str(row.get("lesson_purpose") or "").strip())
        else:
            meta.append(str(row.get("exam_length") or "").strip())
        meta_text = " · ".join(part for part in meta if part)
        card_html.append(
            "<div style='margin-top:10px;padding:10px 11px;border-radius:14px;border:1px solid rgba(148,163,184,.18);background:rgba(255,255,255,.9);'>"
            f"<div style='display:flex;justify-content:space-between;gap:8px;align-items:flex-start;'><div style='font-weight:800;color:#0f172a;'>{_html.escape(str(row.get('title') or t('untitled_plan')).strip())}</div>"
            f"<div style='flex:0 0 auto;border-radius:999px;padding:4px 8px;background:rgba(16,185,129,.12);color:#047857;font-size:.72rem;font-weight:800;'>{_html.escape(_score_label(float(match.get('score') or 0.0)))}</div></div>"
            f"<div style='margin-top:4px;color:#64748b;font-size:.8rem;line-height:1.35;'>{_html.escape(str(row.get('topic') or '').strip())}</div>"
            f"<div style='margin-top:6px;color:#475569;font-size:.76rem;'>{_html.escape(meta_text)}</div>"
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
            st.caption(f"{str(row.get('title') or t('untitled_plan')).strip()}  |  {_score_label(float(match.get('score') or 0.0))}")
        with columns[1]:
            if st.button(t("material_recommendations_open"), key=f"{state_prefix}_match_open_{idx}", use_container_width=True):
                open_material_recommendation(match, assign=False, open_in_files=False)
        with columns[2]:
            if st.button(t("material_recommendations_assign"), key=f"{state_prefix}_match_assign_{idx}", use_container_width=True):
                open_material_recommendation(match, assign=True, open_in_files=False)

    return matches


def open_material_recommendation(resource: dict, *, assign: bool = False, open_in_files: bool = False) -> None:
    kind = str(resource.get("kind") or "")
    row = dict(resource.get("row") or {})
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
