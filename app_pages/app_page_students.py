import streamlit as st
import datetime
import html as _html
import math
import re
import urllib.parse
import pandas as pd
from core.i18n import t
from core.navigation import page_header, go_to
from core.database import load_profile_row, load_table, load_students, get_sb
from core.database import (
    ensure_student,
    clear_app_caches,
    norm_student,
    update_student_profile,
    rename_student_everywhere
)
from core.state import get_current_user_id
from helpers.lesson_planner import normalize_subject as _normalize_subject_key, subject_label as _subject_label
from helpers.student_meta import load_students_df
from helpers.student_personalization import NATIVE_LANGUAGE_OPTIONS, is_language_subject, native_language_label, normalize_native_language
from helpers.history import show_student_history
from helpers.archive_utils import truthy_flag
from helpers.ui_components import translate_df_headers, render_styled_dataframe
from helpers.whatsapp import _digits_only, normalize_phone_for_whatsapp, build_whatsapp_url
from helpers.student_report import (
    build_student_report_pdf,
    build_report_whatsapp_url,
    build_report_email_url,
)
from helpers.dashboard import rebuild_dashboard
from helpers.empty_states import render_empty_state
from helpers.teacher_student_integration import (
    archive_teacher_assignment_for_teacher,
    archive_teacher_student_link,
    ensure_teacher_review_request_for_attempt,
    get_teacher_request_resolution,
    load_active_linked_students_for_teacher,
    load_incoming_teacher_requests,
    load_teacher_assignment_progress,
    load_teacher_review_request_detail,
    load_teacher_review_requests,
    respond_to_teacher_request,
    submit_teacher_review,
    _clean_teacher_feedback_text,
    _strip_html_fragments,
)
from helpers.learning_programs import (
    load_program_assignments_for_teacher,
    archive_learning_program_assignment,
    load_learning_program,
    load_assignment_progress_map,
    set_assignment_topic_progress,
)
from helpers.material_recommendations import build_generation_request, find_similar_materials, load_material_pool, open_material_recommendation
from helpers.planner_storage import load_my_lesson_plans, load_public_lesson_plans
from helpers.worksheet_storage import load_my_worksheets, load_public_worksheets
from helpers.quick_exam_storage import load_my_exams, load_public_exams
from helpers.archive_utils import is_archived_status
from helpers.resource_gallery import (
    extract_gallery_image_url,
    inject_resource_gallery_styles,
    render_gallery_card_html,
)
from helpers.recommendation_memory import (
    clear_active_recommendation_context,
    load_recommendation_event_summary,
    record_recommendation_event,
    set_active_recommendation_context,
)
from helpers.recommendation_models import score_teacher_resource_candidate
from helpers.teacher_recommendation_ml import score_teacher_recommendation_objective

# 12.2) PAGE: STUDENTS
# =========================

_TEACHER_PAGE_SIZE = 6

_RECOMMENDED_RESOURCE_GROUP_LIMIT = 24
_RECOMMENDED_RESOURCE_PAGE_SIZE = 2

_RECOMMENDED_RESOURCE_ASSIGNMENT_TYPES = {
    "lesson_plan_topic": "plan",
    "worksheet": "worksheet",
    "exam": "exam",
    "video": "video",
}


def _norm_search_text(value) -> str:
    return re.sub(r"\s+", " ", str(value or "").casefold()).strip()


def _recommendation_resource_query(item: dict) -> str:
    return _norm_search_text(" ".join([str(item.get("title") or ""), str(item.get("objective") or "")]))


def _resource_match_band(score: float) -> str:
    if score >= 12:
        return t("recommended_resource_match_strong")
    if score >= 7:
        return t("recommended_resource_match_good")
    return t("recommended_resource_match_related")


def _recommended_resource_kind_label(kind: str) -> str:
    return {
        "plan": t("recommended_resource_kind_plan"),
        "worksheet": t("recommended_resource_kind_worksheet"),
        "exam": t("recommended_resource_kind_exam"),
        "video": t("video_label"),
    }.get(kind, kind.title())


def _resource_source_label(source: str) -> str:
    return t("recommended_resource_source_own") if source == "own" else t("recommended_resource_source_community")


def _resource_record_key(kind: str, record_id) -> tuple[str, str] | None:
    record_text = str(record_id or "").strip()
    if not kind or not record_text or record_text in {"0", "None", "nan"}:
        return None
    return str(kind).strip(), record_text


def _resource_preview_text(row: dict, kind: str) -> str:
    if kind == "plan":
        return str(row.get("topic") or row.get("lesson_purpose") or "").strip()
    if kind == "worksheet":
        return str(row.get("topic") or row.get("worksheet_type") or "").strip()
    if kind == "exam":
        return str(row.get("topic") or row.get("exam_length") or "").strip()
    if kind == "video":
        return str(row.get("topic") or row.get("description") or "").strip()
    return ""


def _resource_search_blob(row: dict, kind: str) -> str:
    fields_by_kind = {
        "plan": ["title", "topic", "lesson_purpose", "subject", "learner_stage", "level_or_band", "author_name"],
        "worksheet": ["title", "topic", "worksheet_type", "subject", "learner_stage", "level_or_band", "author_name"],
        "exam": ["title", "topic", "subject", "learner_stage", "level", "exam_length", "author_name"],
        "video": ["title", "topic", "description", "subject", "learner_stage", "level_or_band", "author_name"],
    }
    return _norm_search_text(" ".join(str(row.get(field) or "") for field in fields_by_kind.get(kind, [])))


def _recommendation_topic_tokens(*values) -> set[str]:
    tokens: set[str] = set()
    for value in values:
        for raw in re.split(r"[\s/,-]+", str(value or "").casefold()):
            token = "".join(ch for ch in raw if ch.isalnum())
            if len(token) >= 3:
                tokens.add(token)
    return tokens


def _topic_progress_rows(topic: dict, progress_rows: list[dict]) -> list[dict]:
    topic_title = str(topic.get("title") or topic.get("lesson_focus") or topic.get("subtopic") or "").strip()
    topic_tokens = _recommendation_topic_tokens(topic_title, topic.get("student_summary"), topic.get("lesson_focus"))
    if not topic_tokens:
        return []

    matches: list[dict] = []
    for row in progress_rows or []:
        row_topic = str(row.get("topic") or row.get("title") or "").strip()
        row_tokens = _recommendation_topic_tokens(row_topic)
        if not row_tokens:
            continue
        if row_topic.casefold() == topic_title.casefold() or len(topic_tokens & row_tokens) >= 2:
            matches.append(row)
    return matches


def _topic_signal_from_rows(rows: list[dict]) -> dict:
    signal = _build_recommendation_signal(rows)
    low_score = min(
        (_assignment_score_value(row) for row in rows if _assignment_score_value(row) is not None),
        default=None,
    )
    latest_attempts = max((int(row.get("attempt_count") or 0) for row in rows), default=0)
    signal["recent_score"] = low_score
    signal["attempt_count"] = latest_attempts
    return signal


def _topic_payload(
    *,
    row: dict,
    topic: dict,
    score: float,
    focus_kind: str,
    reasons: list[str],
    recent_score=None,
    needs_practice: bool = False,
) -> dict:
    program = row.get("program") or {}
    total_topics = max(int(row.get("total_topics") or 0), 0)
    completed_topics = max(int(row.get("completed_topics") or 0), 0)
    progress_pct = int(round((completed_topics / total_topics) * 100)) if total_topics else 0
    return {
        "title": str(topic.get("title") or t("assigned_learning_program")).strip(),
        "subject_key": str(row.get("subject_key") or program.get("subject") or "").strip(),
        "subject_display": str(row.get("subject_display") or program.get("subject_display") or "—").strip(),
        "custom_subject_name": str(program.get("custom_subject_name") or "").strip(),
        "learner_stage": str(row.get("learner_stage") or program.get("learner_stage") or "").strip(),
        "level_or_band": str(row.get("level_or_band") or program.get("level_or_band") or "").strip(),
        "program_title": str(program.get("title") or t("learning_program_singular")).strip(),
        "objective": _topic_objective(topic),
        "focus_kind": focus_kind,
        "priority_label": _recommendation_priority_label(score),
        "focus_label": _recommendation_focus_label(focus_kind),
        "score": score,
        "needs_practice": needs_practice,
        "program_progress": progress_pct,
        "recent_score": recent_score,
        "reasons": reasons[:3],
        "actions": _recommendation_actions(focus_kind),
    }


def _localized_subject_display(subject_key, subject_label_text="") -> str:
    normalized = _normalize_subject_key(subject_key or subject_label_text)
    if normalized and normalized != "other":
        try:
            return str(_subject_label(normalized) or subject_label_text or subject_key or "—").strip()
        except Exception:
            pass
    return str(subject_label_text or subject_key or "—").strip()


def _score_resource_for_recommendation(row: dict, kind: str, source: str, item: dict) -> float:
    query = _recommendation_resource_query(item)
    title = _norm_search_text(item.get("title"))
    objective = _norm_search_text(item.get("objective"))
    blob = str(row.get("_recommended_search_blob") or "") or _resource_search_blob(row, kind)
    if not query or not blob:
        return 0.0

    score = 0.0
    if title and title in blob:
        score += 8.0
    if objective and objective in blob:
        score += 5.0
    for token in [tok for tok in re.split(r"\W+", query) if len(tok) >= 3]:
        if token in blob:
            score += 1.4

    rec_subject = _norm_search_text(item.get("subject_key"))
    rec_stage = _norm_search_text(item.get("learner_stage"))
    rec_level = _norm_search_text(item.get("level_or_band"))
    row_subject = _norm_search_text(row.get("subject"))
    row_stage = _norm_search_text(row.get("learner_stage"))
    row_level = _norm_search_text(row.get("level") if kind == "exam" else row.get("level_or_band"))

    if rec_subject and rec_subject == row_subject:
        score += 3.0
    if rec_stage and rec_stage == row_stage:
        score += 1.5
    if rec_level and rec_level == row_level:
        score += 1.5
    if source == "own":
        score += 1.2

    focus_kind = str(item.get("focus_kind") or "")
    if focus_kind == "needs_practice" and kind == "worksheet":
        score += 2.0
    elif focus_kind == "needs_practice" and kind == "video":
        score += 1.1
    elif focus_kind == "reteach" and kind == "plan":
        score += 2.0
    elif focus_kind == "reteach" and kind == "video":
        score += 2.4
    elif focus_kind == "reinforce" and kind in {"worksheet", "plan"}:
        score += 1.2
    elif focus_kind == "reinforce" and kind == "video":
        score += 1.0
    ml_score, _features = score_teacher_resource_candidate(
        row=row,
        kind=kind,
        source=source,
        recommendation_item=item,
    )
    return score + (5.0 * ml_score)


def _load_recommendation_resource_pool() -> list[dict]:
    return load_material_pool()


def _recommended_resources_for_item(item: dict, resource_pool: list[dict]) -> dict[str, list[dict]]:
    grouped: dict[str, list[dict]] = {"plan": [], "worksheet": [], "exam": [], "video": []}
    base_kwargs = {
        "subject": item.get("subject_key"),
        "learner_stage": item.get("learner_stage"),
        "level_or_band": item.get("level_or_band"),
        "topic": item.get("title"),
        "student_profile": {
            "program_context": {
                "next_topics": [item.get("title")],
                "next_objectives": [item.get("objective")],
            },
            "weak_topics": [item.get("objective"), item.get("title")],
        },
    }
    for kind in grouped:
        request = build_generation_request(
            kind=kind,
            lesson_purpose=item.get("objective") if kind == "plan" else "",
            worksheet_type=item.get("objective") if kind == "worksheet" else "",
            exercise_types=[],
            **base_kwargs,
        )
        grouped[kind] = find_similar_materials(
            request,
            limit=_RECOMMENDED_RESOURCE_GROUP_LIMIT,
            min_score=5.0,
        )
    return grouped


def _load_assigned_resource_keys_for_student(selected_link: dict, program_rows: list[dict]) -> set[tuple[str, str]]:
    assigned: set[tuple[str, str]] = set()

    student_id = str((selected_link or {}).get("student_id") or "").strip()
    if not student_id:
        return assigned

    for row in load_teacher_assignment_progress(student_id=student_id):
        if is_archived_status(row.get("status")):
            continue
        kind = _RECOMMENDED_RESOURCE_ASSIGNMENT_TYPES.get(str(row.get("assignment_type") or "").strip())
        key = _resource_record_key(kind or "", row.get("source_record_id"))
        if key:
            assigned.add(key)
    return assigned


def _recommended_resource_is_assigned(resource: dict, assigned_resource_keys: set[tuple[str, str]]) -> bool:
    row = resource.get("row") or {}
    key = _resource_record_key(str(resource.get("kind") or ""), row.get("id"))
    return bool(key and key in assigned_resource_keys)


def _recommended_resource_kind_order(focus_kind: str) -> list[str]:
    if focus_kind == "needs_practice":
        return ["worksheet", "video", "plan", "exam"]
    if focus_kind == "reteach":
        return ["video", "plan", "worksheet", "exam"]
    if focus_kind == "stretch":
        return ["plan", "video", "exam", "worksheet"]
    return ["worksheet", "video", "plan", "exam"]


def _open_recommended_resource(resource: dict, recommendation_item: dict | None = None, *, assign: bool = False) -> None:
    kind = resource.get("kind")
    source = resource.get("source")
    row = resource.get("row") or {}
    recommendation_item = dict(recommendation_item or {})
    if recommendation_item:
        set_active_recommendation_context(recommendation_item)
        record_recommendation_event(
            event_type="resource_assigned" if assign else "resource_opened",
            teacher_id=str(get_current_user_id() or "").strip(),
            student_id=str(recommendation_item.get("student_id") or "").strip(),
            learning_program_assignment_id=int(recommendation_item.get("learning_program_assignment_id") or 0) or None,
            learning_program_topic_id=int(recommendation_item.get("learning_program_topic_id") or 0) or None,
            program_id=int(recommendation_item.get("program_id") or 0) or None,
            recommendation_bucket=str(recommendation_item.get("recommendation_bucket") or "").strip(),
            recommendation_focus_kind=str(recommendation_item.get("focus_kind") or "").strip(),
            resource_kind=str(kind or ""),
            resource_record_id=int(row.get("id") or 0) or None,
            event_weight=0.3 if assign else 0.12,
            metadata={"source": source, "title": str(row.get("title") or "").strip()},
        )

    if kind == "program":
        program_id = int(row.get("id") or 0)
        if program_id <= 0:
            return
        target_key = "my_learning_programs_selected_program_id" if source == "own" else "public_learning_programs_selected_program_id"
        for key in [
            "my_learning_programs_selected_program_id",
            "archived_learning_programs_selected_program_id",
            "public_learning_programs_selected_program_id",
            "home_public_learning_programs_selected_program_id",
        ]:
            st.session_state.pop(key, None)
        st.session_state[target_key] = program_id
        if assign:
            st.session_state[f"show_assign_learning_program_{program_id}"] = True
        go_to("resources")
        st.rerun()

    if kind in {"plan", "worksheet", "exam", "video"}:
        open_material_recommendation(resource, assign=assign, open_in_files=True)


def _current_teacher_teaches_languages() -> bool:
    profile = load_profile_row(get_current_user_id())
    subjects = profile.get("primary_subjects") or []
    custom_subjects = profile.get("custom_subjects") or []
    for subject in subjects:
        if is_language_subject(str(subject or "")):
            return True
    for custom_subject in custom_subjects:
        if is_language_subject("other", str(custom_subject or "")):
            return True
    return False


def _student_has_language_subject(student_name: str) -> bool:
    student_key = norm_student(student_name)
    if not student_key:
        return False
    try:
        linked_students = load_active_linked_students_for_teacher()
    except Exception:
        linked_students = []
    for linked_student in linked_students or []:
        if norm_student(linked_student.get("student_name") or "") != student_key:
            continue
        for subject in linked_student.get("subjects") or []:
            if is_language_subject(str(subject.get("subject_key") or ""), str(subject.get("subject_label") or "")):
                return True
    return False


def _slice_teacher_page(rows: list, state_key: str, *, page_size: int = _TEACHER_PAGE_SIZE):
    total_items = len(rows or [])
    total_pages = max(1, math.ceil(total_items / page_size)) if total_items else 1
    current_page = int(st.session_state.get(state_key, 1) or 1)
    current_page = max(1, min(current_page, total_pages))
    st.session_state[state_key] = current_page
    start_idx = (current_page - 1) * page_size
    end_idx = min(start_idx + page_size, total_items)
    return list((rows or [])[start_idx:end_idx]), current_page, total_pages, start_idx, end_idx, total_items


def _slice_teacher_program_page(rows: list[dict], state_key_prefix: str, *, page_size: int = 1):
    page_key = f"{state_key_prefix}_page"
    anchor_key = f"{state_key_prefix}_assignment"
    rows = list(rows or [])
    row_ids = [int(row.get("id") or 0) for row in rows]
    total_items = len(rows)
    total_pages = max(1, math.ceil(total_items / page_size)) if total_items else 1

    current_page = int(st.session_state.get(page_key, 1) or 1)
    anchor_assignment_id = int(st.session_state.get(anchor_key, 0) or 0)
    if anchor_assignment_id > 0 and anchor_assignment_id in row_ids:
        current_page = (row_ids.index(anchor_assignment_id) // page_size) + 1

    current_page = max(1, min(current_page, total_pages))
    start_idx = (current_page - 1) * page_size
    end_idx = min(start_idx + page_size, total_items)
    page_rows = rows[start_idx:end_idx]
    current_assignment_id = int((page_rows[0] if page_rows else {}).get("id") or 0)

    st.session_state[page_key] = current_page
    if current_assignment_id > 0:
        st.session_state[anchor_key] = current_assignment_id
    elif anchor_key in st.session_state:
        st.session_state.pop(anchor_key, None)

    return page_rows, current_page, total_pages, start_idx, end_idx, total_items


def _render_teacher_pagination(rows: list, state_key: str, *, page_size: int = _TEACHER_PAGE_SIZE) -> None:
    _, current_page, total_pages, start_idx, end_idx, total_items = _slice_teacher_page(
        rows, state_key, page_size=page_size,
    )
    if total_items <= page_size:
        return
    prev_col, info_col, next_col = st.columns([1, 3, 1])
    with prev_col:
        if st.button("←", key=f"{state_key}_prev", use_container_width=True, disabled=current_page <= 1):
            st.session_state[state_key] = max(1, current_page - 1)
            st.rerun()
    with info_col:
        st.caption(f"{start_idx + 1}-{end_idx} / {total_items} · {current_page}/{total_pages}")
    with next_col:
        if st.button("→", key=f"{state_key}_next", use_container_width=True, disabled=current_page >= total_pages):
            st.session_state[state_key] = min(total_pages, current_page + 1)
            st.rerun()


def _render_teacher_program_pagination(rows: list[dict], state_key_prefix: str, *, page_size: int = 1) -> None:
    page_key = f"{state_key_prefix}_page"
    anchor_key = f"{state_key_prefix}_assignment"
    _, current_page, total_pages, start_idx, end_idx, total_items = _slice_teacher_program_page(
        rows,
        state_key_prefix,
        page_size=page_size,
    )
    if total_items <= page_size:
        return

    prev_col, info_col, next_col = st.columns([1, 3, 1])
    with prev_col:
        if st.button("←", key=f"{state_key_prefix}_prev", use_container_width=True, disabled=current_page <= 1):
            target_page = max(1, current_page - 1)
            target_index = (target_page - 1) * page_size
            target_row = list(rows or [])[target_index] if target_index < len(rows or []) else {}
            st.session_state[page_key] = target_page
            st.session_state[anchor_key] = int(target_row.get("id") or 0)
            st.rerun()
    with info_col:
        st.caption(f"{start_idx + 1}-{end_idx} / {total_items} · {current_page}/{total_pages}")
    with next_col:
        if st.button("→", key=f"{state_key_prefix}_next", use_container_width=True, disabled=current_page >= total_pages):
            target_page = min(total_pages, current_page + 1)
            target_index = (target_page - 1) * page_size
            target_row = list(rows or [])[target_index] if target_index < len(rows or []) else {}
            st.session_state[page_key] = target_page
            st.session_state[anchor_key] = int(target_row.get("id") or 0)
            st.rerun()


def _render_end_relationship_action(*, link_id: int, key_prefix: str) -> None:
    with st.popover(t("end_relationship"), use_container_width=True):
        st.warning(t("relationship_end_warning"))
        confirm = st.checkbox(
            t("relationship_end_confirm_checkbox"),
            key=f"{key_prefix}_confirm_end_relationship",
        )
        if st.button(
            t("relationship_end_confirm_button"),
            key=f"{key_prefix}_confirm_end_relationship_btn",
            use_container_width=True,
            type="primary",
            disabled=not confirm,
        ):
            ok, msg = archive_teacher_student_link(int(link_id))
            if ok:
                st.success(t(msg))
                st.rerun()
            st.error(t(msg))


def _review_note_block(label_key: str, raw_value, *, feedback: bool = False) -> str:
    text = _clean_teacher_feedback_text(raw_value) if feedback else _strip_html_fragments(raw_value)
    # Final display-side cleanup so serialized HTML cannot leak into the UI.
    text = _strip_html_fragments(text)
    if feedback:
        text = _clean_teacher_feedback_text(text)
    if not text:
        return ""
    return (
        f"<div class='classio-student-link-note'><strong>{_html.escape(t(label_key))}:</strong> "
        f"{_html.escape(text)}</div>"
    )


def _safe_float(value, default: float = 0.0) -> float:
    try:
        if value in (None, ""):
            return default
        return float(value)
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


def _assignment_score_value(row: dict) -> float | None:
    latest = row.get("latest_attempt") or {}
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


def _fit_recommendation_weights(progress_rows: list[dict]) -> list[float]:
    if not progress_rows:
        return [-0.25, 1.85, 0.75, 0.95]

    features: list[tuple[float, float, float, float]] = []
    targets: list[float] = []
    for row in progress_rows:
        score = _assignment_score_value(row)
        score_gap = _clamp((82.0 - score) / 42.0) if score is not None else 0.42
        retry_pressure = _clamp((max(int(row.get("attempt_count") or 0), 1) - 1.0) / 3.0)
        status_pressure = _assignment_status_pressure(row.get("status"))
        features.append((1.0, score_gap, retry_pressure, status_pressure))
        target = 1.0 if (score is not None and score < 78.0) or status_pressure >= 0.78 else 0.0
        targets.append(target)

    weights = [-0.2, 1.45, 0.55, 0.85]
    learning_rate = 0.35
    for _ in range(120):
        gradients = [0.0, 0.0, 0.0, 0.0]
        for row_features, target in zip(features, targets):
            prediction = _sigmoid(sum(weight * value for weight, value in zip(weights, row_features)))
            error = prediction - target
            for idx, value in enumerate(row_features):
                gradients[idx] += error * value
        scale = 1.0 / max(1, len(features))
        for idx in range(len(weights)):
            weights[idx] -= learning_rate * gradients[idx] * scale
    return weights


def _build_recommendation_signal(rows: list[dict]) -> dict:
    if not rows:
        return {
            "score_gap": 0.2,
            "retry_pressure": 0.1,
            "status_pressure": 0.25,
            "recent_score": None,
            "active_assignments": 0,
        }

    score_gaps = []
    retry_pressures = []
    status_pressures = []
    scores = []
    active_assignments = 0

    for row in rows:
        score = _assignment_score_value(row)
        score_gaps.append(_clamp((82.0 - score) / 42.0) if score is not None else 0.35)
        retry_pressures.append(_clamp((max(int(row.get("attempt_count") or 0), 1) - 1.0) / 3.0))
        status_value = _assignment_status_pressure(row.get("status"))
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


def _load_teacher_program_rows_for_student(selected_link: dict, selected_student_name: str) -> list[dict]:
    program_assignments_df = load_program_assignments_for_teacher()
    selected_student_id = str(selected_link.get("student_id") or "").strip()
    selected_student_label = str(selected_student_name or "").strip().casefold()
    program_rows = []
    if program_assignments_df is None or program_assignments_df.empty:
        return program_rows

    for _, row in program_assignments_df.iterrows():
        row_dict = row.to_dict()
        row_student_id = str(row_dict.get("student_user_id") or "").strip()
        row_student_name = str(row_dict.get("student_name") or "").strip().casefold()
        if (selected_student_id and row_student_id == selected_student_id) or (selected_student_label and row_student_name == selected_student_label):
            program_id = int(row_dict.get("program_id") or 0)
            program = load_learning_program(program_id) if program_id > 0 else {}
            progress_map = load_assignment_progress_map(int(row_dict.get("id") or 0)) if int(row_dict.get("id") or 0) > 0 else {}
            total_topics = sum(len(unit.get("topics") or []) for unit in (program.get("units") or []))
            completed_topics = len([1 for item in progress_map.values() if item.get("teacher_done")])
            row_dict["program"] = program
            row_dict["progress_map"] = progress_map
            row_dict["subject_key"] = str(program.get("subject") or "").strip() or str(row_dict.get("subject_key") or "").strip()
            row_dict["subject_display"] = str(program.get("subject_display") or row_dict.get("subject_label") or row_dict.get("subject_key") or "—").strip()
            row_dict["learner_stage"] = str(program.get("learner_stage") or row_dict.get("learner_stage") or "").strip()
            row_dict["level_or_band"] = str(program.get("level_or_band") or row_dict.get("level_or_band") or "").strip()
            row_dict["sequence_order"] = int(program.get("sequence_order") or row_dict.get("sequence_order") or 0)
            row_dict["total_topics"] = total_topics
            row_dict["completed_topics"] = completed_topics
            row_dict["progress_pct"] = int(round((completed_topics / total_topics) * 100)) if total_topics else 0
            program_rows.append(row_dict)
    return sorted(program_rows, key=_teacher_program_sort_key, reverse=True)


def _teacher_program_sort_key(row: dict) -> tuple[int, str]:
    sequence_order = int(row.get("sequence_order") or 0)
    stamp = str(
        row.get("updated_at")
        or row.get("assigned_at")
        or (row.get("program") or {}).get("updated_at")
        or (row.get("program") or {}).get("created_at")
        or ""
    ).strip()
    return (sequence_order, stamp)


def _teacher_program_subject_groups(program_rows: list[dict]) -> list[tuple[str, str, list[dict]]]:
    grouped: dict[str, dict[str, object]] = {}
    for row in program_rows or []:
        subject_key = str(row.get("subject_key") or "").strip() or "other"
        subject_display = str(row.get("subject_display") or subject_key or "—").strip()
        bucket = grouped.setdefault(subject_key, {"label": subject_display, "rows": []})
        bucket["rows"].append(row)

    ordered_groups: list[tuple[str, str, list[dict]]] = []
    for subject_key, payload in grouped.items():
        rows = sorted(list(payload.get("rows") or []), key=_teacher_program_sort_key, reverse=True)
        ordered_groups.append((subject_key, str(payload.get("label") or subject_key), rows))
    ordered_groups.sort(
        key=lambda item: (
            -max((int(row.get("sequence_order") or 0) for row in item[2]), default=0),
            item[1].casefold(),
        )
    )
    return ordered_groups


def _current_teacher_program_rows(program_rows: list[dict], selected_subject: str) -> list[dict]:
    rows = list(program_rows or [])
    if selected_subject != "__all__":
        rows = [row for row in rows if str(row.get("subject_key") or "").strip() == selected_subject]
    current_by_subject: dict[str, dict] = {}
    for row in rows:
        subject_key = str(row.get("subject_key") or "").strip() or "other"
        current = current_by_subject.get(subject_key)
        if current is None or _teacher_program_sort_key(row) > _teacher_program_sort_key(current):
            current_by_subject[subject_key] = row
    return sorted(current_by_subject.values(), key=_teacher_program_sort_key, reverse=True)


def _teacher_program_count(program_rows: list[dict], selected_subject: str) -> int:
    rows = list(program_rows or [])
    if selected_subject != "__all__":
        rows = [row for row in rows if str(row.get("subject_key") or "").strip() == selected_subject]
    assignment_ids = {
        int(row.get("id") or 0)
        for row in rows
        if int(row.get("id") or 0) > 0
    }
    return len(assignment_ids) if assignment_ids else len(rows)


def _render_teacher_program_assignment_list(rows: list[dict], state_key_prefix: str) -> None:
    if not rows:
        st.info(t("no_assignments"))
        return
    inject_resource_gallery_styles()
    page_rows, *_ = _slice_teacher_program_page(rows, state_key_prefix, page_size=1)
    for row in page_rows:
        program = row.get("program") or {}
        student_name = str(row.get("student_name") or "—").strip()
        program_title = str(program.get("title") or t("learning_program_singular")).strip()
        subject_display = str(row.get("subject_display") or "—").strip()
        level_label = str(row.get("level_or_band") or "").strip()
        sequence_order = int(row.get("sequence_order") or 0)
        progress_pct = int(row.get("progress_pct") or 0)
        completed_topics = int(row.get("completed_topics") or 0)
        total_topics = int(row.get("total_topics") or 0)
        teacher_note = _strip_html_fragments(row.get("teacher_note"))
        target_completion_on = str(row.get("target_completion_on") or "").strip()
        target_label = (
            f"{t('assignment_target_completion_on')}: {target_completion_on[:10]}"
            if target_completion_on
            else t("start_from_lesson_1")
        )
        chips = "".join(
            [
                f'<span class="cm-resource-chip">👤 {_html.escape(student_name)}</span>',
                f'<span class="cm-resource-chip">📚 {_html.escape(subject_display)}</span>',
                f'<span class="cm-resource-chip">🏷️ {_html.escape(level_label)}</span>' if level_label else "",
                f'<span class="cm-resource-chip">🪜 {_html.escape(t("path_step_label", step=sequence_order))}</span>' if sequence_order > 0 else "",
                f'<span class="cm-resource-chip">📈 {completed_topics}/{total_topics} {_html.escape(t("topics_label").lower())}</span>',
                f'<span class="cm-resource-chip">🎯 {progress_pct}%</span>',
            ]
        )
        meta_html = (
            f'<div class="cm-resource-meta">📘 {_html.escape(t("assigned_learning_program"))}</div>'
            f'<div class="cm-resource-meta">🗓️ {_html.escape(target_label)}</div>'
        )
        st.markdown(
            render_gallery_card_html(
                kind="program",
                title=program_title,
                chips_html=chips,
                description=teacher_note or str(program.get("program_overview") or t("no_description_available")),
                meta_html=meta_html,
                image_url=extract_gallery_image_url(program),
                placeholder_label=t("learning_program"),
            ),
            unsafe_allow_html=True,
        )
        assignment_id = int(row.get("id") or 0)
        progress_map = load_assignment_progress_map(assignment_id) if assignment_id else {}
        for unit in program.get("units") or []:
            with st.expander(
                f"{t('unit_title_format', number=unit.get('unit_number'), title=unit.get('title'))}",
                expanded=int(unit.get("unit_number") or 0) == 1,
            ):
                for topic in unit.get("topics") or []:
                    topic_id = int(topic.get("topic_id") or 0)
                    done = truthy_flag(progress_map.get(topic_id, {}).get("teacher_done"))
                    topic_cols = st.columns([0.14, 0.86], gap="small")
                    with topic_cols[0]:
                        checkbox_key = f"teacher_learning_program_done_{assignment_id}_{topic_id}"
                        new_done = st.checkbox(
                            t("done_label"),
                            value=done,
                            key=checkbox_key,
                            label_visibility="collapsed",
                        )
                        if new_done != done and topic_id > 0:
                            saved = set_assignment_topic_progress(
                                assignment_id=assignment_id,
                                topic_id=topic_id,
                                done_by_teacher=new_done,
                            )
                            if saved:
                                st.session_state.pop(checkbox_key, None)
                                clear_app_caches()
                                st.rerun()
                            st.error(t("save_failed"))
                    with topic_cols[1]:
                        st.markdown(
                            f"**{t('topic_title_format', number=topic.get('topic_number'), title=topic.get('title'))}**"
                        )
                        topic_summary = (
                            topic.get("student_summary")
                            or topic.get("lesson_focus")
                            or topic.get("subtopic")
                            or ""
                        )
                        if topic_summary:
                            st.caption(str(topic_summary))
        action_cols = st.columns([1, 1, 4], gap="small")
        with action_cols[0]:
            if st.button(
                t("delete_assignment"),
                key=f"archive_program_assignment_{row.get('id')}",
                use_container_width=True,
            ):
                ok, msg = archive_learning_program_assignment(int(row.get("id") or 0))
                if ok:
                    st.success(t(msg))
                    st.rerun()
                st.error(t(msg) if msg in {"assignment_archived"} else msg)
    _render_teacher_program_pagination(rows, state_key_prefix, page_size=1)


def _recommendation_actions(focus_kind: str) -> list[str]:
    if focus_kind == "needs_practice":
        return [
            t("student_recommendation_action_need_practice_1"),
            t("student_recommendation_action_need_practice_2"),
        ]
    if focus_kind == "reteach":
        return [
            t("student_recommendation_action_reteach_1"),
            t("student_recommendation_action_reteach_2"),
        ]
    if focus_kind == "stretch":
        return [
            t("student_recommendation_action_stretch_1"),
            t("student_recommendation_action_stretch_2"),
        ]
    return [
        t("student_recommendation_action_reinforce_1"),
        t("student_recommendation_action_reinforce_2"),
    ]


def _recommendation_focus_kind(signal: dict, score: float) -> str:
    if signal.get("score_gap", 0.0) >= 0.5 or signal.get("status_pressure", 0.0) >= 0.82:
        return "reteach"
    if signal.get("retry_pressure", 0.0) >= 0.34 or score >= 0.66:
        return "reinforce"
    return "stretch"


def _recommendation_priority_label(score: float) -> str:
    if score >= 0.78:
        return t("student_recommendation_priority_high")
    if score >= 0.6:
        return t("student_recommendation_priority_medium")
    return t("student_recommendation_priority_low")


def _recommendation_focus_label(focus_kind: str) -> str:
    return t(f"student_recommendation_focus_{focus_kind}")


def _recommendation_badge_label(item: dict) -> str:
    return t("student_recommendation_badge_needs_practice") if item.get("needs_practice") else ""


def _topic_objective(topic: dict) -> str:
    learning_objectives = topic.get("learning_objectives") or []
    if learning_objectives:
        return str(learning_objectives[0] or "").strip()
    success_criteria = topic.get("success_criteria") or []
    if success_criteria:
        return str(success_criteria[0] or "").strip()
    for key in ("lesson_focus", "student_summary", "subtopic", "title"):
        value = str(topic.get(key) or "").strip()
        if value:
            return value
    return ""


def _student_personalization_label(student_name: str, student_profile: dict) -> str:
    name = str(student_name or "").strip()
    email = str(student_profile.get("email") or "").strip()
    return f"{name} · {email}" if email else name


def _prefill_smart_tool_from_recommendation(recommendation: dict, tool_kind: str) -> None:
    subject_key = str(recommendation.get("subject_key") or "").strip() or "other"
    custom_subject = str(recommendation.get("custom_subject_name") or "").strip()
    learner_stage = str(recommendation.get("learner_stage") or "").strip()
    level_or_band = str(recommendation.get("level_or_band") or "").strip()
    topic = str(recommendation.get("title") or recommendation.get("objective") or "").strip()
    student_label = str(recommendation.get("student_label") or "").strip()
    exam_title = f"{topic} {t('exam_title') if t('exam_title') != 'exam_title' else 'Exam'}".strip()
    set_active_recommendation_context(recommendation)
    record_recommendation_event(
        event_type="prefill",
        teacher_id=str(get_current_user_id() or "").strip(),
        student_id=str(recommendation.get("student_id") or "").strip(),
        learning_program_assignment_id=int(recommendation.get("learning_program_assignment_id") or 0) or None,
        learning_program_topic_id=int(recommendation.get("learning_program_topic_id") or 0) or None,
        program_id=int(recommendation.get("program_id") or 0) or None,
        recommendation_bucket=str(recommendation.get("recommendation_bucket") or "").strip(),
        recommendation_focus_kind=str(recommendation.get("focus_kind") or "").strip(),
        resource_kind=tool_kind,
        event_weight=0.18,
        metadata={"title": topic},
    )

    if tool_kind == "lesson_plan":
        st.session_state["quick_plan_subject"] = subject_key
        st.session_state["quick_plan_other_subject"] = custom_subject
        if learner_stage:
            st.session_state["quick_plan_learner_stage"] = learner_stage
        if level_or_band:
            st.session_state["quick_plan_level"] = level_or_band
        st.session_state["quick_plan_topic"] = topic
        st.session_state["quick_plan_student_personalization"] = student_label
        st.session_state["open_quick_plan_expander"] = True
    elif tool_kind == "worksheet":
        st.session_state["quick_ws_subject"] = subject_key
        st.session_state["ws_other_subject"] = custom_subject
        if learner_stage:
            st.session_state["ws_stage"] = learner_stage
        if level_or_band:
            st.session_state["ws_level"] = level_or_band
        st.session_state["ws_topic"] = topic
        st.session_state["quick_ws_student_personalization"] = student_label
        st.session_state["open_quick_ws_expander"] = True
    elif tool_kind == "exam":
        st.session_state["quick_exam_subject"] = subject_key
        st.session_state["exam_other_subject"] = custom_subject
        if learner_stage:
            st.session_state["exam_stage"] = learner_stage
        if level_or_band:
            st.session_state["exam_level"] = level_or_band
        st.session_state["quick_exam_topic"] = topic
        st.session_state["quick_exam_title"] = exam_title
        st.session_state["quick_exam_student_personalization"] = student_label
        st.session_state["open_quick_exam_expander"] = True

    go_to("smart_tools")
    st.rerun()


def _build_program_recommendations(
    *,
    progress_rows: list[dict],
    program_rows: list[dict],
    selected_subject: str,
) -> tuple[list[dict], dict]:
    filtered_progress_rows = [
        row for row in (progress_rows or [])
        if selected_subject == "__all__" or str(row.get("subject_key") or "").strip() == selected_subject
    ]
    rows_by_subject: dict[str, list[dict]] = {}
    for row in filtered_progress_rows:
        key = str(row.get("subject_key") or "").strip()
        rows_by_subject.setdefault(key, []).append(row)
    overall_signal = _build_recommendation_signal(filtered_progress_rows)
    recommendations: list[dict] = []
    current_program_rows = _current_teacher_program_rows(program_rows, selected_subject)
    recommendation_events = load_recommendation_event_summary(
        tuple(sorted({int(r.get("id") or 0) for r in current_program_rows if int(r.get("id") or 0) > 0})),
        str((filtered_progress_rows[0] if filtered_progress_rows else {}).get("student_id") or ""),
    )

    for row in current_program_rows:
        assignment_id = int(row.get("id") or 0)
        program_id = int(row.get("program_id") or 0)
        if assignment_id <= 0 or program_id <= 0:
            continue
        program = row.get("program") or load_learning_program(program_id)
        if not program:
            continue
        subject_key = str(program.get("subject") or "").strip()
        progress_map = load_assignment_progress_map(assignment_id)
        total_topics = sum(len(unit.get("topics") or []) for unit in (program.get("units") or []))
        completed_topics = len([1 for item in progress_map.values() if item.get("teacher_done")])
        progress_gap = _clamp(1.0 - ((completed_topics / total_topics) if total_topics else 0.0))
        signal = _build_recommendation_signal(rows_by_subject.get(subject_key, [])) if rows_by_subject.get(subject_key) else overall_signal

        ordered_topics: list[tuple[int, dict, dict]] = []
        topic_position = 0
        for unit in program.get("units") or []:
            for topic in unit.get("topics") or []:
                topic_position += 1
                topic_id = int(topic.get("topic_id") or 0)
                ordered_topics.append((topic_position, topic, progress_map.get(topic_id, {}) if topic_id else {}))

        completed_positions = [position for position, _topic, topic_progress in ordered_topics if truthy_flag(topic_progress.get("teacher_done"))]
        latest_completed_position = max(completed_positions, default=0)
        next_topic = None
        pending_topic = None
        review_candidates: list[tuple[float, dict, dict, dict]] = []

        for position, topic, topic_progress in ordered_topics:
            teacher_done = truthy_flag(topic_progress.get("teacher_done"))
            needs_practice = truthy_flag(topic_progress.get("student_done"))
            topic_rows = _topic_progress_rows(topic, rows_by_subject.get(subject_key, []))
            topic_signal = _topic_signal_from_rows(topic_rows)
            topic_id = int(topic.get("topic_id") or 0)
            next_event = recommendation_events.get((assignment_id, topic_id, "next_topic"), {})
            review_event = recommendation_events.get((assignment_id, topic_id, "review"), {})
            pending_event = recommendation_events.get((assignment_id, topic_id, "pending_gap"), {})

            if not teacher_done and position > latest_completed_position and next_topic is None:
                next_topic = (topic, topic_signal, next_event)
            if not teacher_done and latest_completed_position > 0 and position < latest_completed_position and pending_topic is None:
                pending_topic = (topic, topic_signal, pending_event)

            if teacher_done:
                review_score = 0.0
                if needs_practice:
                    review_score = max(review_score, 0.98)
                if topic_signal.get("recent_score") is not None:
                    review_score = max(review_score, 0.74 + _clamp((78.0 - float(topic_signal["recent_score"])) / 45.0))
                review_score = max(
                    review_score,
                    0.58
                    + 0.24 * topic_signal.get("score_gap", 0.0)
                    + 0.12 * topic_signal.get("retry_pressure", 0.0)
                    + 0.06 * topic_signal.get("status_pressure", 0.0),
                )
                if review_event.get("last_event_type") in {"teacher_marked_done", "assignment_created"}:
                    review_score -= 0.12
                if review_event.get("improved_count", 0) > 0 and not needs_practice:
                    review_score -= 0.34
                if needs_practice or topic_signal.get("score_gap", 0.0) >= 0.18 or topic_signal.get("retry_pressure", 0.0) >= 0.34:
                    review_candidates.append((review_score, topic, topic_signal, topic_progress))

        if next_topic is None:
            for _position, topic, topic_progress in ordered_topics:
                if not truthy_flag(topic_progress.get("teacher_done")):
                    topic_id = int(topic.get("topic_id") or 0)
                    next_topic = (
                        topic,
                        _topic_signal_from_rows(_topic_progress_rows(topic, rows_by_subject.get(subject_key, []))),
                        recommendation_events.get((assignment_id, topic_id, "next_topic"), {}),
                    )
                    break

        if next_topic is not None:
            topic, topic_signal, next_event = next_topic
            next_score = 0.62 + 0.18 * progress_gap + 0.12 * signal.get("status_pressure", 0.0) + 0.08 * topic_signal.get("retry_pressure", 0.0)
            if next_event.get("last_event_type") in {"teacher_marked_done", "assignment_created"}:
                next_score -= 0.16
            focus_kind = "stretch" if signal.get("score_gap", 0.0) < 0.26 else "reinforce"
            candidate = {
                "recommendation_bucket": "next_topic",
                "progress_gap": progress_gap,
                "overall_signal": signal,
                "topic_signal": topic_signal,
                "needs_practice": False,
                "teacher_done": False,
                "student_done": False,
                "is_after_latest_completed": True,
                "is_before_latest_completed": False,
                "is_next_unfinished": True,
                "event_summary": next_event,
            }
            objective_score, _ = score_teacher_recommendation_objective(candidate)
            blended_score = (0.58 * next_score) + (0.42 * objective_score)
            recommendations.append(
                _topic_payload(
                    row=row,
                    topic=topic,
                    score=blended_score,
                    focus_kind=focus_kind,
                    reasons=[
                        t("student_recommendation_reason_next_topic"),
                        t("student_recommendation_reason_program_gap") if progress_gap >= 0.2 else t("student_recommendation_reason_active_assignment"),
                    ],
                    recent_score=topic_signal.get("recent_score"),
                )
            )
            recommendations[-1]["recommendation_bucket"] = "next_topic"
            recommendations[-1]["learning_program_assignment_id"] = assignment_id
            recommendations[-1]["learning_program_topic_id"] = int(topic.get("topic_id") or 0)
            recommendations[-1]["program_id"] = int(program_id or 0)
            recommendations[-1]["objective_score"] = round(objective_score, 4)

        if review_candidates:
            review_candidates.sort(key=lambda item: item[0], reverse=True)
            review_score, topic, topic_signal, topic_progress = review_candidates[0]
            review_topic_id = int(topic.get("topic_id") or 0)
            review_event = recommendation_events.get((assignment_id, review_topic_id, "review"), {})
            if (
                review_event.get("last_event_type") == "teacher_marked_done"
                and not truthy_flag(topic_progress.get("student_done"))
                and review_event.get("improved_count", 0) <= 0
            ):
                review_candidates = []
            elif review_event.get("improved_count", 0) > 0 and not truthy_flag(topic_progress.get("student_done")):
                review_candidates = []

        if review_candidates:
            review_score, topic, topic_signal, topic_progress = review_candidates[0]
            review_reasons = []
            if truthy_flag(topic_progress.get("student_done")):
                review_reasons.append(t("student_recommendation_reason_needs_practice"))
            if topic_signal.get("recent_score") is not None:
                review_reasons.append(t("student_recommendation_reason_low_score", score=int(round(topic_signal["recent_score"]))))
            if topic_signal.get("retry_pressure", 0.0) >= 0.34:
                review_reasons.append(t("student_recommendation_reason_retries"))
            if not review_reasons:
                review_reasons.append(t("student_recommendation_reason_active_assignment"))
            focus_kind = "needs_practice" if truthy_flag(topic_progress.get("student_done")) else "reteach"
            review_event = recommendation_events.get((assignment_id, int(topic.get("topic_id") or 0), "review"), {})
            candidate = {
                "recommendation_bucket": "review",
                "progress_gap": progress_gap,
                "overall_signal": signal,
                "topic_signal": topic_signal,
                "needs_practice": truthy_flag(topic_progress.get("student_done")),
                "teacher_done": True,
                "student_done": truthy_flag(topic_progress.get("student_done")),
                "is_after_latest_completed": False,
                "is_before_latest_completed": False,
                "is_next_unfinished": False,
                "event_summary": review_event,
            }
            objective_score, _ = score_teacher_recommendation_objective(candidate)
            blended_score = (0.58 * review_score) + (0.42 * objective_score)
            recommendations.append(
                _topic_payload(
                    row=row,
                    topic=topic,
                    score=blended_score,
                    focus_kind=focus_kind,
                    reasons=review_reasons,
                    recent_score=topic_signal.get("recent_score"),
                    needs_practice=truthy_flag(topic_progress.get("student_done")),
                )
            )
            recommendations[-1]["recommendation_bucket"] = "review"
            recommendations[-1]["learning_program_assignment_id"] = assignment_id
            recommendations[-1]["learning_program_topic_id"] = int(topic.get("topic_id") or 0)
            recommendations[-1]["program_id"] = int(program_id or 0)
            recommendations[-1]["objective_score"] = round(objective_score, 4)

        if pending_topic is not None:
            topic, topic_signal, pending_event = pending_topic
            pending_score = 0.68 + 0.18 * progress_gap + 0.14 * signal.get("status_pressure", 0.0)
            if pending_event.get("last_event_type") in {"teacher_marked_done", "assignment_created"}:
                pending_score -= 0.16
            pending_reasons = [
                t("student_recommendation_reason_program_gap"),
                t("student_recommendation_reason_next_topic"),
            ]
            if topic_signal.get("recent_score") is not None:
                pending_reasons.insert(1, t("student_recommendation_reason_low_score", score=int(round(topic_signal["recent_score"]))))
            candidate = {
                "recommendation_bucket": "pending_gap",
                "progress_gap": progress_gap,
                "overall_signal": signal,
                "topic_signal": topic_signal,
                "needs_practice": False,
                "teacher_done": False,
                "student_done": False,
                "is_after_latest_completed": False,
                "is_before_latest_completed": True,
                "is_next_unfinished": False,
                "event_summary": pending_event,
            }
            objective_score, _ = score_teacher_recommendation_objective(candidate)
            blended_score = (0.58 * pending_score) + (0.42 * objective_score)
            recommendations.append(
                _topic_payload(
                    row=row,
                    topic=topic,
                    score=blended_score,
                    focus_kind="reinforce",
                    reasons=pending_reasons,
                    recent_score=topic_signal.get("recent_score"),
                )
            )
            recommendations[-1]["recommendation_bucket"] = "pending_gap"
            recommendations[-1]["learning_program_assignment_id"] = assignment_id
            recommendations[-1]["learning_program_topic_id"] = int(topic.get("topic_id") or 0)
            recommendations[-1]["program_id"] = int(program_id or 0)
            recommendations[-1]["objective_score"] = round(objective_score, 4)

    if recommendations:
        deduped: list[dict] = []
        seen_titles: set[tuple[str, str]] = set()
        for item in sorted(recommendations, key=lambda rec: -_safe_float(rec.get("score"), 0.0)):
            key = (str(item.get("subject_key") or ""), str(item.get("title") or "").casefold())
            if key in seen_titles:
                continue
            seen_titles.add(key)
            deduped.append(item)
        recommendations = deduped
        return recommendations[:3], overall_signal

    fallback_recommendations = []
    weakest_rows = sorted(
        filtered_progress_rows,
        key=lambda row: (
            -(
                0.55 * (_clamp((82.0 - (_assignment_score_value(row) if _assignment_score_value(row) is not None else 64.0)) / 42.0))
                + 0.45 * _assignment_status_pressure(row.get("status"))
            ),
            -_clamp((max(int(row.get("attempt_count") or 0), 1) - 1.0) / 3.0),
        ),
    )
    for row in weakest_rows[:3]:
        score = _assignment_score_value(row)
        signal = {
            "score_gap": _clamp((82.0 - score) / 42.0) if score is not None else 0.35,
            "retry_pressure": _clamp((max(int(row.get("attempt_count") or 0), 1) - 1.0) / 3.0),
            "status_pressure": _assignment_status_pressure(row.get("status")),
            "recent_score": score,
        }
        composite = 0.65 * signal["score_gap"] + 0.35 * signal["status_pressure"]
        focus_kind = _recommendation_focus_kind(signal, composite)
        reasons = []
        if score is not None:
            reasons.append(t("student_recommendation_reason_low_score", score=int(round(score))))
        if signal["retry_pressure"] >= 0.34:
            reasons.append(t("student_recommendation_reason_retries"))
        reasons.append(t("student_recommendation_reason_active_assignment"))
        fallback_recommendations.append(
            {
                "title": str(row.get("topic") or row.get("title") or t("student_progress_assignments_tab")).strip(),
                "subject_display": str(row.get("subject_display") or "—").strip(),
                "program_title": t("student_progress_assignments_tab"),
                "objective": str(row.get("title") or row.get("topic") or "").strip(),
                "focus_kind": focus_kind,
                "priority_label": _recommendation_priority_label(composite),
                "focus_label": _recommendation_focus_label(focus_kind),
                "score": composite,
                "program_progress": None,
                "recent_score": score,
                "reasons": reasons[:3],
                "actions": _recommendation_actions(focus_kind),
            }
        )
    return fallback_recommendations, overall_signal


def _inject_recommendation_styles() -> None:
    st.markdown(
        """
        <style>
        .classio-reco-hero {
            position: relative;
            overflow: hidden;
            border-radius: 24px;
            padding: 22px 24px;
            margin-bottom: 1rem;
            background:
                radial-gradient(circle at top right, color-mix(in srgb, var(--primary, #2563eb) 22%, transparent), transparent 34%),
                radial-gradient(circle at bottom left, color-mix(in srgb, #10b981 18%, transparent), transparent 38%),
                linear-gradient(135deg, color-mix(in srgb, var(--panel, #ffffff) 76%, var(--primary, #2563eb) 24%), color-mix(in srgb, var(--panel, #ffffff) 88%, #10b981 12%) 48%, var(--panel, #ffffff));
            color: var(--text, #0f172a);
            border: 1px solid color-mix(in srgb, var(--border, rgba(148,163,184,.35)) 78%, var(--primary, #2563eb) 22%);
            box-shadow: 0 18px 48px color-mix(in srgb, var(--primary, #2563eb) 10%, rgba(15,23,42,.08));
        }
        .classio-reco-hero-title {
            font-size: 1.22rem;
            font-weight: 900;
            letter-spacing: -.02em;
        }
        .classio-reco-hero-subtitle {
            margin-top: 0.45rem;
            max-width: 780px;
            color: var(--muted, #475569);
            line-height: 1.45;
        }
        .classio-reco-metric {
            border-radius: 18px;
            padding: 14px 16px;
            background: linear-gradient(180deg, color-mix(in srgb, var(--panel, #ffffff) 95%, white 5%), color-mix(in srgb, var(--panel, #ffffff) 86%, var(--primary, #2563eb) 14%));
            border: 1px solid color-mix(in srgb, var(--border, rgba(148,163,184,.35)) 82%, var(--primary, #2563eb) 18%);
            min-height: 92px;
        }
        .classio-reco-metric-block {
            margin-bottom: 1rem;
        }
        .classio-reco-summary-gap {
            height: 1.1rem;
        }
        .classio-reco-card-row-gap {
            height: 1rem;
        }
        .classio-reco-metric-label {
            font-size: 0.78rem;
            color: var(--muted, #64748b);
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: .06em;
        }
        .classio-reco-metric-value {
            margin-top: 0.35rem;
            font-size: 1.5rem;
            font-weight: 900;
            color: var(--text, #0f172a);
        }
        .classio-reco-card {
            border-radius: 22px;
            padding: 20px 20px 18px;
            background:
                linear-gradient(180deg, color-mix(in srgb, var(--panel, #ffffff) 96%, white 4%), color-mix(in srgb, var(--panel, #ffffff) 90%, var(--primary, #2563eb) 10%));
            border: 1px solid color-mix(in srgb, var(--border, rgba(148,163,184,.35)) 84%, var(--primary, #2563eb) 16%);
            box-shadow: 0 16px 36px rgba(15,23,42,.08);
            min-height: 100%;
        }
        .classio-reco-chip-row {
            display: flex;
            gap: 8px;
            flex-wrap: wrap;
            margin-bottom: 10px;
        }
        .classio-reco-chip {
            display: inline-flex;
            align-items: center;
            border-radius: 999px;
            padding: 5px 10px;
            font-size: 0.75rem;
            font-weight: 800;
        }
        .classio-reco-title {
            font-size: 1.08rem;
            font-weight: 900;
            color: #0f172a;
            line-height: 1.25;
        }
        .classio-reco-meta {
            margin-top: 0.35rem;
            font-size: 0.84rem;
            color: #64748b;
            font-weight: 600;
        }
        .classio-reco-section-label {
            margin-top: 0.95rem;
            font-size: 0.78rem;
            color: #475569;
            font-weight: 800;
            text-transform: uppercase;
            letter-spacing: .04em;
        }
        .classio-reco-body {
            margin-top: 0.3rem;
            color: #0f172a;
            line-height: 1.5;
        }
        .classio-reco-list {
            margin: 0.45rem 0 0 0;
            padding-left: 1.1rem;
            color: #1e293b;
        }
        .classio-reco-list li {
            margin-bottom: 0.28rem;
        }
        .classio-reco-statline {
            display: flex;
            gap: 12px;
            flex-wrap: wrap;
            margin-top: 0.85rem;
        }
        .classio-reco-statpill {
            border-radius: 999px;
            padding: 6px 10px;
            font-size: 0.76rem;
            font-weight: 700;
            color: var(--text, #334155);
            background: color-mix(in srgb, var(--panel-soft, rgba(148,163,184,.12)) 88%, var(--primary, #2563eb) 12%);
            border: 1px solid color-mix(in srgb, var(--border, rgba(148,163,184,.35)) 82%, var(--primary, #2563eb) 18%);
        }
        .classio-reco-resource-tray {
            margin-top: 10px;
            padding: 14px;
            border-radius: 18px;
            border: 1px solid color-mix(in srgb, var(--border, rgba(148,163,184,.35)) 80%, #10b981 20%);
            background:
                linear-gradient(180deg, color-mix(in srgb, var(--panel, #ffffff) 94%, white 6%), color-mix(in srgb, var(--panel, #ffffff) 88%, #10b981 12%));
            box-shadow: 0 12px 26px rgba(15,23,42,.07);
        }
        .classio-reco-resource-head {
            display: flex;
            align-items: flex-start;
            justify-content: space-between;
            gap: 10px;
            margin-bottom: 10px;
        }
        .classio-reco-resource-title {
            font-size: .92rem;
            font-weight: 900;
            color: var(--text, #0f172a);
            line-height: 1.25;
        }
        .classio-reco-resource-subtitle {
            margin-top: 3px;
            color: var(--muted, #64748b);
            font-size: .78rem;
            line-height: 1.35;
        }
        .classio-reco-resource-count {
            flex: 0 0 auto;
            border-radius: 999px;
            padding: 5px 9px;
            font-size: .72rem;
            font-weight: 850;
            color: #047857;
            background: rgba(16,185,129,.12);
            border: 1px solid rgba(16,185,129,.2);
        }
        div[data-testid="stExpander"]:has(.classio-reco-resource-expander-body) {
            border: 1px solid color-mix(in srgb, var(--border, rgba(148,163,184,.35)) 78%, #10b981 22%) !important;
            border-radius: 18px !important;
            background: linear-gradient(180deg, var(--panel, #ffffff), color-mix(in srgb, var(--panel, #ffffff) 92%, #10b981 8%)) !important;
            box-shadow: 0 12px 26px rgba(15,23,42,.07) !important;
            overflow: hidden !important;
            margin-top: 10px !important;
        }
        div[data-testid="stExpander"]:has(.classio-reco-resource-expander-body) summary {
            font-weight: 900 !important;
            color: var(--text, #0f172a) !important;
        }
        .classio-reco-resource-group {
            margin-top: 10px;
        }
        .classio-reco-resource-group-label {
            margin-bottom: 6px;
            font-size: .72rem;
            font-weight: 900;
            color: #475569;
            text-transform: uppercase;
            letter-spacing: .04em;
        }
        .classio-reco-resource-page {
            display: grid;
            grid-template-columns: repeat(2, minmax(0, 1fr));
            gap: 10px;
            overflow-x: auto;
            padding-bottom: 2px;
            scroll-snap-type: x proximity;
        }
        .classio-reco-resource-slot {
            min-width: 0;
            scroll-snap-align: start;
        }
        .classio-reco-resource-card {
            margin-bottom: 8px;
            padding: 11px 12px;
            border-radius: 14px;
            background: rgba(255,255,255,.72);
            border: 1px solid rgba(148,163,184,.22);
            min-height: 132px;
        }
        .classio-reco-resource-card-top {
            display: flex;
            justify-content: space-between;
            gap: 8px;
            align-items: flex-start;
        }
        .classio-reco-resource-card-title {
            font-size: .88rem;
            font-weight: 900;
            color: #0f172a;
            line-height: 1.25;
            min-width: 0;
        }
        .classio-reco-resource-assigned {
            flex: 0 0 auto;
            border-radius: 999px;
            padding: 4px 8px;
            font-size: .68rem;
            font-weight: 900;
            color: #047857;
            background: rgba(16,185,129,.14);
            border: 1px solid rgba(16,185,129,.24);
            white-space: nowrap;
        }
        .classio-reco-resource-preview {
            margin-top: 4px;
            color: #64748b;
            font-size: .78rem;
            line-height: 1.35;
        }
        .classio-reco-resource-chiprow {
            display: flex;
            gap: 6px;
            flex-wrap: wrap;
            margin-top: 8px;
        }
        .classio-reco-resource-chip {
            border-radius: 999px;
            padding: 4px 8px;
            font-size: .7rem;
            font-weight: 800;
            color: #334155;
            background: rgba(248,250,252,.86);
            border: 1px solid rgba(148,163,184,.2);
        }
        .classio-reco-resource-empty {
            margin-top: 8px;
            padding: 10px 12px;
            border-radius: 14px;
            color: #64748b;
            font-size: .8rem;
            background: rgba(248,250,252,.74);
            border: 1px dashed rgba(148,163,184,.34);
        }
        @media (max-width: 768px) {
            .classio-reco-card {
                padding: 16px 16px 14px;
            }
            .classio-reco-hero {
                padding: 18px 18px;
            }
            .classio-reco-resource-page {
                grid-template-columns: repeat(2, minmax(230px, 82vw));
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _render_recommended_resources_for_item(
    item: dict,
    resource_pool: list[dict],
    *,
    key_prefix: str,
    assigned_resource_keys: set[tuple[str, str]] | None = None,
) -> None:
    grouped_resources = _recommended_resources_for_item(item, resource_pool)
    ordered_kinds = _recommended_resource_kind_order(str(item.get("focus_kind") or ""))
    total_matches = sum(len(grouped_resources.get(kind) or []) for kind in ordered_kinds)
    assigned_resource_keys = assigned_resource_keys or set()

    expander_label = f"{t('recommended_resources_title')} · {t('recommended_resources_count', count=total_matches)}"
    with st.expander(expander_label, expanded=False):
        st.markdown(
            f"""
            <div class="classio-reco-resource-expander-body">
                <div class="classio-reco-resource-head">
                    <div>
                        <div class="classio-reco-resource-title">{_html.escape(t('recommended_resources_title'))}</div>
                        <div class="classio-reco-resource-subtitle">{_html.escape(t('recommended_resources_subtitle'))}</div>
                    </div>
                    <div class="classio-reco-resource-count">{_html.escape(t('recommended_resources_count', count=total_matches))}</div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        if total_matches <= 0:
            st.markdown(
                f"<div class='classio-reco-resource-empty'>{_html.escape(t('recommended_resources_empty'))}</div>",
                unsafe_allow_html=True,
            )
            return

        for kind in ordered_kinds:
            resources = grouped_resources.get(kind) or []
            if not resources:
                continue
            group_label = {
                "plan": t("recommended_resources_group_plans"),
                "worksheet": t("recommended_resources_group_practice"),
                "exam": t("recommended_resources_group_assessment"),
                "video": t("recommended_resources_group_videos"),
            }.get(kind, _recommended_resource_kind_label(kind))
            state_key = re.sub(r"[^A-Za-z0-9._-]+", "_", f"{key_prefix}_{kind}_page")
            page_resources, *_ = _slice_teacher_page(resources, state_key, page_size=_RECOMMENDED_RESOURCE_PAGE_SIZE)
            st.markdown(
                f"<div class='classio-reco-resource-group'><div class='classio-reco-resource-group-label'>{_html.escape(group_label)}</div></div>",
                unsafe_allow_html=True,
            )

            resource_cols = st.columns(len(page_resources), gap="small") if page_resources else []
            for resource_idx, (resource_col, resource) in enumerate(zip(resource_cols, page_resources)):
                row = resource.get("row") or {}
                title = str(row.get("title") or _recommended_resource_kind_label(kind)).strip()
                preview = _resource_preview_text(row, kind) or t("no_description_available")
                subject = str(row.get("subject") or "").strip()
                level = str(row.get("level") if kind == "exam" else row.get("level_or_band") or "").strip()
                source_label = _resource_source_label(str(resource.get("source") or ""))
                is_assigned = _recommended_resource_is_assigned(resource, assigned_resource_keys)
                chips = [
                    source_label,
                    _recommended_resource_kind_label(kind),
                    _resource_match_band(float(resource.get("score") or 0.0)),
                ]
                if subject:
                    chips.append(t(f"subject_{subject.lower().replace(' ', '_')}"))
                if level:
                    chips.append(level if level in ("A1", "A2", "B1", "B2", "C1", "C2") else t(level))
                chip_html = "".join(f"<span class='classio-reco-resource-chip'>{_html.escape(str(chip))}</span>" for chip in chips if chip)
                assigned_html = (
                    f"<span class='classio-reco-resource-assigned'>{_html.escape(t('assignment_status_assigned'))}</span>"
                    if is_assigned
                    else ""
                )
                button_key = re.sub(r"[^A-Za-z0-9._-]+", "_", f"{state_key}_{resource.get('source')}_{row.get('id')}_{resource_idx}")
                with resource_col:
                    st.markdown(
                        "<div class='classio-reco-resource-card'>"
                        "<div class='classio-reco-resource-card-top'>"
                        f"<div class='classio-reco-resource-card-title'>{_html.escape(title)}</div>"
                        f"{assigned_html}"
                        "</div>"
                        f"<div class='classio-reco-resource-preview'>{_html.escape(preview[:150])}</div>"
                        f"<div class='classio-reco-resource-chiprow'>{chip_html}</div>"
                        "</div>",
                        unsafe_allow_html=True,
                    )
                    view_col, assign_col = st.columns(2, gap="small")
                    with view_col:
                        if st.button(t("recommended_resource_preview"), key=f"{button_key}_preview", use_container_width=True):
                            _open_recommended_resource(resource, item, assign=False)
                    with assign_col:
                        if st.button(t("recommended_resource_assign"), key=f"{button_key}_assign", use_container_width=True):
                            _open_recommended_resource(resource, item, assign=True)
            _render_teacher_pagination(resources, state_key, page_size=_RECOMMENDED_RESOURCE_PAGE_SIZE)


def _render_recommendations_tab(
    progress_rows: list[dict],
    program_rows: list[dict],
    selected_subject: str,
    selected_student_name: str,
    selected_link: dict,
) -> None:
    subject_groups = _teacher_program_subject_groups(program_rows)
    if selected_subject == "__all__" and len(subject_groups) > 1:
        tabs = st.tabs([f"📚 {label}" for subject_key, label, _rows in subject_groups])
        for tab, (subject_key, _label, rows) in zip(tabs, subject_groups):
            with tab:
                _render_recommendations_tab(
                    progress_rows,
                    rows,
                    subject_key,
                    selected_student_name,
                    selected_link,
                )
        return

    _inject_recommendation_styles()
    recommendations, overall_signal = _build_program_recommendations(
        progress_rows=progress_rows,
        program_rows=program_rows,
        selected_subject=selected_subject,
    )
    resource_pool = _load_recommendation_resource_pool() if recommendations else []
    filtered_program_count = _teacher_program_count(program_rows, selected_subject)

    st.markdown(
        f"""
        <div class="classio-reco-hero">
            <div class="classio-reco-hero-title">{_html.escape(t('student_progress_recommendations_title'))}</div>
            <div class="classio-reco-hero-subtitle">{_html.escape(t('student_progress_recommendations_subtitle'))}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    recent_score_value = overall_signal.get("recent_score")
    recent_score_text = "—" if recent_score_value is None else f"{int(round(recent_score_value))}%"
    summary_cards = [
        (t("student_recommendation_summary_score"), recent_score_text),
        (t("student_recommendation_summary_assignments"), str(int(overall_signal.get("active_assignments") or 0))),
        (t("student_recommendation_summary_programs"), str(filtered_program_count)),
    ]
    summary_cols = st.columns(3, gap="medium")
    for col, (label, value) in zip(summary_cols, summary_cards):
        with col:
            st.markdown(
                f"""
                <div class="classio-reco-metric-block">
                    <div class="classio-reco-metric">
                        <div class="classio-reco-metric-label">{_html.escape(label)}</div>
                        <div class="classio-reco-metric-value">{_html.escape(value)}</div>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    st.markdown("<div class='classio-reco-summary-gap'></div>", unsafe_allow_html=True)

    if not recommendations:
        st.info(t("student_progress_recommendations_empty"))
        return

    assigned_resource_keys = _load_assigned_resource_keys_for_student(selected_link, program_rows)

    for idx in range(0, len(recommendations), 2):
        pair = recommendations[idx: idx + 2]
        cols = st.columns(len(pair), gap="medium")
        for offset, (col, item) in enumerate(zip(cols, pair)):
            with col:
                priority_color = "#dc2626" if item.get("score", 0.0) >= 0.78 else ("#d97706" if item.get("score", 0.0) >= 0.6 else "#2563eb")
                focus_color = {
                    "needs_practice": "#dc2626",
                    "reteach": "#dc2626",
                    "reinforce": "#d97706",
                    "stretch": "#2563eb",
                }.get(item.get("focus_kind"), "#2563eb")
                badge_label = _recommendation_badge_label(item)
                badge_html = (
                    f"<span class='classio-reco-chip' style='background:#dc262618;color:#dc2626;border:1px solid #dc26262a;'>{_html.escape(badge_label)}</span>"
                    if badge_label
                    else ""
                )
                reasons_html = "".join(f"<li>{_html.escape(reason)}</li>" for reason in (item.get("reasons") or []))
                actions_html = "".join(f"<li>{_html.escape(action)}</li>" for action in (item.get("actions") or []))
                objective = str(item.get("objective") or "").strip() or str(item.get("title") or "—")
                program_progress = item.get("program_progress")
                recent_score = item.get("recent_score")
                stat_parts = []
                if recent_score is not None:
                    stat_parts.append(
                        f"<span class='classio-reco-statpill'>{_html.escape(t('student_recommendation_recent_score'))}: {_html.escape(str(int(round(recent_score))) + '%')}</span>"
                    )
                if program_progress is not None:
                    stat_parts.append(
                        f"<span class='classio-reco-statpill'>{_html.escape(t('student_recommendation_program_progress'))}: {_html.escape(str(program_progress) + '%')}</span>"
                    )
                statline_html = "".join(stat_parts)
                card_html = (
                    '<div class="classio-reco-card">'
                    '<div class="classio-reco-chip-row">'
                    f'<span class="classio-reco-chip" style="background:{priority_color}18;color:{priority_color};border:1px solid {priority_color}2a;">{_html.escape(str(item.get("priority_label") or ""))}</span>'
                    f'<span class="classio-reco-chip" style="background:{focus_color}18;color:{focus_color};border:1px solid {focus_color}2a;">{_html.escape(str(item.get("focus_label") or ""))}</span>'
                    f'{badge_html}'
                    '</div>'
                    f'<div class="classio-reco-title">{_html.escape(str(item.get("title") or "-"))}</div>'
                    f'<div class="classio-reco-meta">{_html.escape(str(item.get("program_title") or "-"))} · {_html.escape(str(item.get("subject_display") or "-"))}</div>'
                    f'<div class="classio-reco-section-label">{_html.escape(t("student_recommendation_lesson_objective"))}</div>'
                    f'<div class="classio-reco-body">{_html.escape(objective)}</div>'
                    f'<div class="classio-reco-statline">{statline_html}</div>'
                    f'<div class="classio-reco-section-label">{_html.escape(t("student_recommendation_why"))}</div>'
                    f'<ul class="classio-reco-list">{reasons_html}</ul>'
                    f'<div class="classio-reco-section-label">{_html.escape(t("student_recommendation_actions"))}</div>'
                    f'<ul class="classio-reco-list">{actions_html}</ul>'
                    '</div>'
                )
                st.markdown(card_html, unsafe_allow_html=True)
                student_label = _student_personalization_label(selected_student_name, selected_link)
                recommendation_payload = {
                    **item,
                    "student_label": student_label,
                    "student_id": str((selected_link or {}).get("student_id") or "").strip(),
                }
                _render_recommended_resources_for_item(
                    item,
                    resource_pool,
                    key_prefix=f"reco_resources_{idx}_{offset}_{str(item.get('title') or '')}",
                    assigned_resource_keys=assigned_resource_keys,
                )

                action_cols = st.columns(4, gap="small")
                with action_cols[0]:
                    if st.button(
                        t("student_recommendation_create_lesson_plan"),
                        key=f"reco_plan_{idx}_{offset}_{str(item.get('title') or '')}",
                        use_container_width=True,
                    ):
                        _prefill_smart_tool_from_recommendation(recommendation_payload, "lesson_plan")
                with action_cols[1]:
                    if st.button(
                        t("student_recommendation_create_worksheet"),
                        key=f"reco_ws_{idx}_{offset}_{str(item.get('title') or '')}",
                        use_container_width=True,
                    ):
                        _prefill_smart_tool_from_recommendation(recommendation_payload, "worksheet")
                with action_cols[2]:
                    if st.button(
                        t("student_recommendation_create_exam"),
                        key=f"reco_exam_{idx}_{offset}_{str(item.get('title') or '')}",
                        use_container_width=True,
                    ):
                        _prefill_smart_tool_from_recommendation(recommendation_payload, "exam")
                with action_cols[3]:
                    if st.button(
                        t("mark_done"),
                        key=f"reco_done_{idx}_{offset}_{str(item.get('title') or '')}",
                        use_container_width=True,
                    ):
                        record_recommendation_event(
                            event_type="teacher_marked_done",
                            teacher_id=str(get_current_user_id() or "").strip(),
                            student_id=str(recommendation_payload.get("student_id") or "").strip(),
                            learning_program_assignment_id=int(recommendation_payload.get("learning_program_assignment_id") or 0) or None,
                            learning_program_topic_id=int(recommendation_payload.get("learning_program_topic_id") or 0) or None,
                            program_id=int(recommendation_payload.get("program_id") or 0) or None,
                            recommendation_bucket=str(recommendation_payload.get("recommendation_bucket") or "").strip(),
                            recommendation_focus_kind=str(recommendation_payload.get("focus_kind") or "").strip(),
                            resource_kind="lesson",
                            event_weight=0.42,
                            metadata={"title": str(recommendation_payload.get("title") or "").strip()},
                        )
                        if str(recommendation_payload.get("recommendation_bucket") or "") in {"next_topic", "pending_gap"}:
                            set_assignment_topic_progress(
                                assignment_id=int(recommendation_payload.get("learning_program_assignment_id") or 0),
                                topic_id=int(recommendation_payload.get("learning_program_topic_id") or 0),
                                done_by_teacher=True,
                            )
                        clear_active_recommendation_context()
                        clear_app_caches()
                        st.rerun()
        if idx + 2 < len(recommendations):
            st.markdown("<div class='classio-reco-card-row-gap'></div>", unsafe_allow_html=True)


def _render_teacher_review_requests(
    student_id: str,
    subject_key: str | None = None,
    *,
    status_filter: str | None = None,
    render_title: bool = True,
) -> None:
    review_rows = load_teacher_review_requests(student_id=student_id, subject_key=subject_key)
    if status_filter and status_filter != "__all__":
        review_rows = [row for row in review_rows if str(row.get("status") or "").strip() == status_filter]

    if not review_rows:
        st.info(t("no_review_requests"))
        return

    if render_title:
        st.markdown(f"### {t('teacher_review_requests')}")

    page_rows, *_ = _slice_teacher_page(review_rows, f"teacher_reviews_{student_id}_{subject_key}_{status_filter}")
    for row in page_rows:
        title = _html.escape(str(row.get("title") or "—"))
        student_name = _html.escape(str(row.get("student_name") or "—"))
        status_key = f"teacher_review_status_{row.get('status')}"
        subject_display = _html.escape(_localized_subject_display(row.get("subject_key"), row.get("subject_display") or row.get("subject_label")))
        request_note_html = _review_note_block("teacher_review_note", row.get("request_note"))
        feedback_html = _review_note_block("teacher_review_feedback", row.get("teacher_feedback"), feedback=True)
        card_col, action_col = st.columns([6, 2], gap="medium")
        with card_col:
            st.markdown(
                f"""
                <div class="classio-progress-card">
                    <div style="display:flex;justify-content:space-between;gap:12px;align-items:flex-start;flex-wrap:wrap;">
                        <div>
                            <div class="classio-progress-title">{title}</div>
                            <div class="classio-progress-meta">{student_name} · {subject_display}</div>
                        </div>
                        <div><span class="classio-inline-chip">🧑‍🏫 {_html.escape(t(status_key))}</span></div>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            if request_note_html:
                st.markdown(request_note_html, unsafe_allow_html=True)
            if feedback_html:
                st.markdown(feedback_html, unsafe_allow_html=True)
        with action_col:
            toggle_key = f"teacher_review_panel_open_{row.get('id')}"
            if toggle_key not in st.session_state:
                st.session_state[toggle_key] = str(row.get("status")) == "requested"
            if st.button(
                t("teacher_review_open"),
                key=f"teacher_review_open_btn_{row.get('id')}",
                use_container_width=True,
            ):
                st.session_state[toggle_key] = not st.session_state.get(toggle_key, False)

        if st.session_state.get(toggle_key):
            detail = load_teacher_review_request_detail(int(row.get("id") or 0))
            items = detail.get("items") or []
            if not items:
                st.info(t("no_data"))
                continue

            with st.container():
                overrides: dict[str, str] = {}
                preview_total = 0
                preview_correct = 0
                current_section = None
                for item in items:
                    if item.get("section_title") != current_section:
                        current_section = item.get("section_title")
                        st.markdown(f"#### {_html.escape(str(current_section or '—'))}")
                        source_text = str(item.get("source_text") or "").strip()
                        if source_text:
                            with st.expander(t("reading_passage"), expanded=False):
                                st.write(source_text)
                    prompt = str(item.get("prompt") or "—")
                    student_answer = str(item.get("student_answer") or "").strip() or "—"
                    correct_answer = str(item.get("correct_answer") or "").strip() or "—"
                    auto_result = t("correct") if item.get("auto_correct") else t("incorrect")
                    st.markdown(
                        f"""
                        <div style="padding:14px 16px;border-radius:16px;border:1px solid var(--border);background:rgba(148,163,184,.06);margin:0.45rem 0 0.8rem 0;">
                            <div style="font-weight:800;color:var(--text);">{_html.escape(prompt)}</div>
                            <div style="margin-top:0.45rem;color:var(--muted);"><strong>{_html.escape(t('teacher_review_student_answer'))}:</strong> {_html.escape(student_answer)}</div>
                            <div style="margin-top:0.25rem;color:var(--muted);"><strong>{_html.escape(t('teacher_review_expected_answer'))}:</strong> {_html.escape(correct_answer)}</div>
                            <div style="margin-top:0.25rem;color:var(--muted);"><strong>{_html.escape(t('teacher_review_auto_result'))}:</strong> {_html.escape(auto_result)}</div>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )
                    overrides[item["question_key"]] = st.radio(
                        t("teacher_review_decision"),
                        options=["keep", "correct", "incorrect"],
                        format_func=lambda choice: t(
                            "teacher_review_keep_ai" if choice == "keep" else
                            "teacher_review_mark_correct" if choice == "correct" else
                            "teacher_review_mark_incorrect"
                        ),
                        horizontal=True,
                        key=f"review_override_{row.get('id')}_{item['question_key']}",
                    )
                    preview_total += 1
                    choice = overrides[item["question_key"]]
                    if choice == "correct":
                        preview_correct += 1
                    elif choice == "incorrect":
                        preview_correct += 0
                    elif item.get("auto_correct"):
                        preview_correct += 1

                teacher_feedback = st.text_area(
                    t("teacher_review_feedback"),
                    key=f"teacher_review_feedback_{row.get('id')}",
                    height=100,
                    placeholder=t("teacher_review_feedback_placeholder"),
                )
                preview_score = round((preview_correct / preview_total) * 100, 1) if preview_total else 0.0
                st.caption(
                    f"{t('teacher_review_preview_score')}: {preview_correct}/{preview_total} · {preview_score}%"
                )
                if st.button(t("teacher_review_save"), key=f"teacher_review_save_{row.get('id')}", type="primary"):
                    ok, msg = submit_teacher_review(int(row.get("id") or 0), overrides, teacher_feedback)
                    if ok:
                        st.success(t(msg))
                        st.rerun()
                    st.error(t(msg))
    _render_teacher_pagination(review_rows, f"teacher_reviews_{student_id}_{subject_key}_{status_filter}")


def render_students():
    page_header(t("students"))
    st.caption(t("add_and_manage_students"))

    students = load_students()
    students_df = load_students_df()

    with st.expander(t("home_find_students"), expanded=False):
        st.markdown(
            f"""
            <details style="margin-bottom:14px">
              <summary style="cursor:pointer;font-weight:600;color:#f1f5f9;font-size:14px;
                              padding:8px 12px;background:#1e3a5f;border:1px solid #2d5a9e;
                              border-radius:8px;list-style:none;display:flex;align-items:center;gap:6px">
                💡 {t('find_students_rec_title')}
              </summary>
              <div style="background:#162844;border:1px solid #2d5a9e;border-top:none;
                          border-radius:0 0 8px 8px;padding:10px 14px">
                <ol style="margin:0;padding-left:18px;color:#e2e8f0;font-size:14px;line-height:1.8">
                  <li>{t('find_students_step_1')}</li>
                  <li>{t('find_students_step_2')}</li>
                  <li>{t('find_students_step_3')}</li>
                  <li>{t('find_students_step_4')}</li>
                  <li>{t('find_students_step_5')}</li>
                </ol>
              </div>
            </details>
            <style>
              .platform-grid {{
                display: grid;
                grid-template-columns: repeat(3, 1fr);
                gap: 10px;
                padding: 4px 0 6px 0;
              }}
              .platform-card {{
                display: flex;
                flex-direction: column;
                align-items: center;
                justify-content: center;
                gap: 7px;
                padding: 12px 8px 10px 8px;
                background: var(--platform-card-bg);
                border: 1px solid var(--platform-card-border);
                border-radius: 12px;
                text-decoration: none;
                color: var(--text);
                font-size: 0.78rem;
                font-weight: 600;
                letter-spacing: 0.01em;
                transition: background 0.18s, border-color 0.18s, color 0.18s, transform 0.15s;
                cursor: pointer;
              }}
              .platform-card:hover {{
                background: var(--platform-card-hover-bg);
                border-color: var(--platform-card-hover-border);
                color: var(--text);
                transform: translateY(-2px);
              }}
              .platform-card svg {{
                flex-shrink: 0;
              }}
            </style>
            <div class="platform-grid">
              <a class="platform-card" href="https://www.armut.com" target="_blank" rel="noopener noreferrer">
                <svg xmlns="http://www.w3.org/2000/svg" width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round">
                  <!-- pear shape -->
                  <path d="M12 2 C10 2 8.5 3.5 8.5 5.5 C8.5 7 9.2 8.3 10.3 9.2 C8.2 10.1 6.5 12.3 6.5 15 C6.5 18.6 9 21.5 12 21.5 C15 21.5 17.5 18.6 17.5 15 C17.5 12.3 15.8 10.1 13.7 9.2 C14.8 8.3 15.5 7 15.5 5.5 C15.5 3.5 14 2 12 2 Z"/>
                  <line x1="12" y1="2" x2="13.5" y2="0.5"/>
                </svg>
                Armut
              </a>
              <a class="platform-card" href="https://www.apprentus.com" target="_blank" rel="noopener noreferrer">
                <svg xmlns="http://www.w3.org/2000/svg" width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round">
                  <path d="M22 10v6M2 10l10-5 10 5-10 5z"/>
                  <path d="M6 12v5c3 3 9 3 12 0v-5"/>
                </svg>
                Apprentus
              </a>
              <a class="platform-card" href="https://www.superprof.com" target="_blank" rel="noopener noreferrer">
                <svg xmlns="http://www.w3.org/2000/svg" width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round">
                  <circle cx="12" cy="7" r="3"/>
                  <path d="M5 21v-2a7 7 0 0 1 14 0v2"/>
                  <line x1="9" y1="11" x2="15" y2="11"/>
                  <line x1="12" y1="11" x2="12" y2="17"/>
                </svg>
                Superprof
              </a>
              <a class="platform-card" href="https://www.ozelders.com" target="_blank" rel="noopener noreferrer">
                <svg xmlns="http://www.w3.org/2000/svg" width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round">
                  <path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z"/>
                  <path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z"/>
                </svg>
                ÖzelDers
              </a>
              <a class="platform-card" href="https://preply.com" target="_blank" rel="noopener noreferrer">
                <svg xmlns="http://www.w3.org/2000/svg" width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round">
                  <circle cx="12" cy="12" r="10"/>
                  <line x1="2" y1="12" x2="22" y2="12"/>
                  <path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/>
                </svg>
                Preply
              </a>
              <a class="platform-card" href="https://www.italki.com" target="_blank" rel="noopener noreferrer">
                <svg xmlns="http://www.w3.org/2000/svg" width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round">
                  <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
                  <line x1="9" y1="10" x2="15" y2="10"/>
                  <line x1="12" y1="7" x2="12" y2="13"/>
                </svg>
                italki
              </a>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown(f"### {t('add_new')}")
    new_student = st.text_input(t("new_student_name"), key="new_student_name")

    if st.button(f"{t('add')} {t('student')}", key="add_student"):
        name = new_student.strip()
        if not name:
            st.error(t("no_data"))
        elif any(norm_student(name) == norm_student(s) for s in students):
            st.warning(t("student_name_exists"))
        else:
            ensure_student(name)
            st.success(t("done_ok"))
            st.rerun()

    st.markdown(f"### {t('manage_students')}")
    st.markdown(
        """
        <style>
        .classio-student-link-card {
            position: relative;
            overflow: hidden;
            background:
              radial-gradient(circle at top right, rgba(59,130,246,.08), transparent 34%),
              linear-gradient(180deg, var(--panel), color-mix(in srgb, var(--panel) 82%, white 18%));
            border: 1px solid color-mix(in srgb, var(--border) 78%, rgba(59,130,246,.18) 22%);
            border-radius: 22px;
            padding: 18px 20px;
            box-shadow: 0 14px 32px rgba(15,23,42,.08);
            margin-bottom: 0.5rem;
        }
        .classio-student-link-card::before {
            content: "";
            position: absolute;
            inset: 0 auto 0 0;
            width: 5px;
            background: linear-gradient(180deg, #38bdf8, #6366f1 58%, #14b8a6);
        }
        .classio-student-link-name {
            font-size: 1.08rem;
            font-weight: 800;
            color: var(--text);
            line-height: 1.2;
        }
        .classio-student-link-meta {
            margin-top: 0.65rem;
            color: var(--muted);
            font-size: 0.9rem;
            line-height: 1.45;
        }
        .classio-student-link-note {
            margin-top: 0.75rem;
            padding: 0.75rem 0.9rem;
            border-radius: 14px;
            background: rgba(148,163,184,.08);
            border: 1px solid rgba(148,163,184,.16);
            color: var(--muted);
            font-size: 0.9rem;
        }
        .classio-student-link-action-label {
            font-size: 0.76rem;
            font-weight: 800;
            text-transform: uppercase;
            letter-spacing: 0.06em;
            color: var(--muted);
            margin: 0.25rem 0 0.55rem 0.1rem;
        }
        .classio-inline-chip {
            display: inline-flex;
            align-items: center;
            gap: 0.35rem;
            padding: 0.45rem 0.78rem;
            border-radius: 999px;
            background: rgba(59,130,246,.08);
            border: 1px solid rgba(59,130,246,.14);
            color: #2563eb;
            font-size: 0.78rem;
            font-weight: 700;
            margin: 0 0.45rem 0.45rem 0;
        }
        .classio-progress-card {
            position: relative;
            overflow: hidden;
            background:
              radial-gradient(circle at top right, rgba(139,92,246,.10), transparent 34%),
              linear-gradient(180deg, var(--panel), color-mix(in srgb, var(--panel) 82%, white 18%));
            border: 1px solid color-mix(in srgb, var(--border) 78%, rgba(139,92,246,.18) 22%);
            border-radius: 22px;
            padding: 18px 20px;
            box-shadow: 0 14px 32px rgba(15,23,42,.08);
            margin-bottom: 0.9rem;
        }
        .classio-progress-card::before {
            content: "";
            position: absolute;
            inset: 0 auto 0 0;
            width: 5px;
            background: linear-gradient(180deg, #8b5cf6, #6366f1 52%, #38bdf8);
        }
        .classio-progress-title {
            font-size: 1.08rem;
            font-weight: 800;
            color: var(--text);
            line-height: 1.25;
        }
        .classio-progress-meta {
            margin-top: 0.55rem;
            color: var(--muted);
            font-size: 0.9rem;
            line-height: 1.45;
        }
        .classio-progress-stats {
            display: flex;
            gap: 0.75rem;
            flex-wrap: wrap;
            margin-top: 0.95rem;
        }
        .classio-progress-stat {
            min-width: 110px;
            padding: 0.78rem 0.9rem;
            border-radius: 16px;
            background: rgba(148,163,184,.08);
            border: 1px solid rgba(148,163,184,.16);
        }
        .classio-progress-stat-label {
            font-size: 0.74rem;
            font-weight: 800;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            color: var(--muted);
        }
        .classio-progress-stat-value {
            margin-top: 0.25rem;
            font-size: 1.05rem;
            font-weight: 800;
            color: var(--text);
        }
        div[data-testid="stButton"] > button[kind="primary"] {
            border-radius: 16px;
            min-height: 3rem;
            font-weight: 800;
            box-shadow: 0 14px 28px rgba(37,99,235,.18);
        }
        div[data-testid="stButton"] > button[kind="secondary"] {
            border-radius: 16px;
            min-height: 3rem;
            font-weight: 700;
            border-color: rgba(148,163,184,.28);
            box-shadow: 0 8px 18px rgba(15,23,42,.06);
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
    if students_df.empty:
        render_empty_state(
            title_key="students_empty_title",
            body_key="students_empty_body",
            steps=[
                "students_empty_step_add",
                "students_empty_step_profile",
                "students_empty_step_progress",
            ],
            icon="👩‍🎓",
        )
    else:
        tab_list, tab_profile, tab_history, tab_requests, tab_progress, tab_delete = st.tabs([
            f"👩‍🎓 {t('student_list')}",
            f"📋 {t('student_profile')}",
            f"📊 {t('student_history')}",
            f"🤝 {t('teacher_requests_title')}",
            f"📈 {t('student_progress_title')}",
            f"🗑️ {t('delete_student')}",
        ])

        # ── TAB: Student List ──
        with tab_list:
            s_col1, s_col2 = st.columns([2, 1])
            with s_col1:
                q = st.text_input(
                    t("search"),
                    value="",
                    placeholder=t("search_name_placeholder"),
                    key="students_list_search"
                )
            with s_col2:
                st.caption(f"Total: **{len(students)}**")

            shown = students
            if q.strip():
                shown = [s for s in students if q.strip().lower() in s.lower()]

            if not shown:
                st.info(t("no_students"))
            else:
                shown_page, *_ = _slice_teacher_page(shown, "teacher_student_list_page")
                for name in shown_page:
                    row = students_df.loc[students_df["student"] == name]
                    s_email = str(row.iloc[0].get("email", "")).strip() if not row.empty else ""
                    s_phone = str(row.iloc[0].get("phone", "")).strip() if not row.empty else ""
                    s_zoom  = str(row.iloc[0].get("zoom_link", "")).strip() if not row.empty else ""
                    s_color = str(row.iloc[0].get("color", "#3B82F6")).strip() if not row.empty else "#3B82F6"
                    s_notes = str(row.iloc[0].get("notes", "")).strip() if not row.empty else ""
                    s_address = str(row.iloc[0].get("address", "")).strip() if not row.empty else ""

                    has_profile = bool(s_email or s_phone or s_zoom or s_notes or s_address)

                    if not has_profile:
                        st.markdown(
                            f"""
                            <div style="
                                background:var(--panel, #fff);
                                border:1px solid var(--border-strong, rgba(17,24,39,0.08));
                                border-left:4px solid {s_color};
                                border-radius:12px;
                                padding:14px 16px;
                                margin-bottom:10px;
                                box-shadow:0 1px 4px rgba(0,0,0,0.06);
                            ">
                                <div style="font-weight:700;font-size:1rem;color:var(--text,#0f172a);margin-bottom:4px;">
                                    {name}
                                </div>
                                <div style="font-size:13px;color:var(--muted,#94a3b8);font-style:italic;">
                                    {t("no_profile_data")}
                                </div>
                            </div>
                            """,
                            unsafe_allow_html=True,
                        )
                        continue

                    chips = []
                    email_chip_style = (
                        "display:inline-flex;align-items:center;gap:4px;padding:4px 12px;"
                        "border-radius:20px;background:rgba(59,130,246,0.12);color:var(--text);font-size:13px;"
                        "text-decoration:none;border:1px solid rgba(59,130,246,0.28);"
                    )

                    whatsapp_chip_style = (
                        "display:inline-flex;align-items:center;gap:4px;padding:4px 12px;"
                        "border-radius:20px;background:rgba(16,185,129,0.12);color:var(--text);font-size:13px;"
                        "text-decoration:none;border:1px solid rgba(16,185,129,0.28);"
                    )

                    zoom_chip_style = (
                        "display:inline-flex;align-items:center;gap:4px;padding:4px 12px;"
                        "border-radius:20px;background:rgba(139,92,246,0.12);color:var(--text);font-size:13px;"
                        "text-decoration:none;border:1px solid rgba(139,92,246,0.28);"
                    )

                    if s_email:
                        mail_href = f"mailto:{urllib.parse.quote(s_email)}"
                        chips.append(
                            f'<a href="{mail_href}" target="_blank" rel="noopener noreferrer" '
                            f'style="{email_chip_style}">📧 {t("send_email")}</a>'
                        )
                    if s_phone:
                        wa_phone = normalize_phone_for_whatsapp(s_phone)
                        wa_url = f"https://wa.me/{wa_phone}" if wa_phone else ""
                        if wa_url:
                            chips.append(
                                f'<a href="{wa_url}" target="_blank" rel="noopener noreferrer" '
                                f'style="{whatsapp_chip_style}">💬 {t("send_whatsapp")}</a>'
                            )
                    if s_zoom:
                        chips.append(
                            f'<a href="{s_zoom}" target="_blank" rel="noopener noreferrer" '
                            f'style="{zoom_chip_style}">🎥 {t("open_zoom")}</a>'
                        )
                    if s_address:
                        maps_chip_style = (
                            "display:inline-flex;align-items:center;gap:4px;padding:4px 12px;"
                            "border-radius:20px;background:rgba(234,88,12,0.12);color:var(--text);font-size:13px;"
                            "text-decoration:none;border:1px solid rgba(234,88,12,0.28);"
                        )
                        maps_href = f"https://www.google.com/maps/search/{urllib.parse.quote(s_address)}"
                        chips.append(
                            f'<a href="{maps_href}" target="_blank" rel="noopener noreferrer" '
                            f'style="{maps_chip_style}">📍 {t("open_maps")}</a>'
                        )
                    contact_html = " ".join(chips) if chips else f'<span style="font-size:12px;color:#94a3b8;">{t("no_contact_info")}</span>'

                    info_parts = []
                    if s_email:
                        info_parts.append(f"📧 {s_email}")
                    if s_phone:
                        info_parts.append(f"📱 {s_phone}")
                    info_line = " &nbsp;·&nbsp; ".join(info_parts)

                    notes_html = ""
                    if s_notes:
                        safe_notes = s_notes.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace("\n", "<br>")
                        notes_html = f'<div style="font-size:12px;color:var(--muted,#64748b);margin-top:6px;padding:6px 8px;background:var(--bg-3,#f8fafc);border-radius:6px;">{safe_notes}</div>'

                    st.markdown(
                        f"""
                        <div style="
                            background:var(--panel, #fff);
                            border:1px solid var(--border-strong, rgba(17,24,39,0.08));
                            border-left:4px solid {s_color};
                            border-radius:12px;
                            padding:14px 16px;
                            margin-bottom:10px;
                            box-shadow:0 1px 4px rgba(0,0,0,0.06);
                        ">
                            <div style="font-weight:700;font-size:1rem;color:var(--text,#0f172a);margin-bottom:2px;">
                                {name}
                            </div>
                            <div style="font-size:13px;color:var(--muted,#475569);margin-bottom:8px;">
                                {info_line if info_line else ""}
                            </div>
                            <div style="display:flex;flex-wrap:wrap;gap:6px;margin-bottom:2px;">
                                {contact_html}
                            </div>
                            {notes_html}
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )
                _render_teacher_pagination(shown, "teacher_student_list_page")

        # ── TAB: Student Profile ──
        with tab_profile:
            student_list = sorted(students_df["student"].unique().tolist())
            selected_student = st.selectbox(t("select_student"), student_list, key="edit_student_select")

            student_row = students_df.loc[students_df["student"] == selected_student].iloc[0]
            sid = norm_student(selected_student)

            with st.popover(f"✏️ {t('edit_name')}", use_container_width=False):
                new_name = st.text_input(t("new_name"), value=selected_student, key=f"rename_{sid}")
                if st.button(t("save"), key=f"btn_rename_{sid}"):
                    stripped = new_name.strip()
                    if not stripped:
                        st.error(t("no_data"))
                    elif norm_student(stripped) != norm_student(selected_student) and any(
                        norm_student(stripped) == norm_student(s) for s in student_list
                    ):
                        st.warning(t("student_name_exists"))
                    else:
                        try:
                            rename_student_everywhere(selected_student, stripped)
                            st.success(t("done_ok"))
                            st.rerun()
                        except ValueError as e:
                            st.error(t(str(e)))
                        except Exception as e:
                           st.error(f"{t('rename_student_failed')}\n\n{e}")

            col1, col2 = st.columns(2)
            with col1:
                email = st.text_input(t("email"), value=student_row.get("email", ""), key=f"student_email_{sid}")
                zoom_link = st.text_input(t("zoom_link"), value=student_row.get("zoom_link", ""), key=f"student_zoom_{sid}")
                _raw_phone = st.text_input(t("whatsapp_phone"), value=student_row.get("phone", ""), key=f"student_phone_{sid}")
                import re as _re_phone
                phone = _re_phone.sub(r"[^0-9+]", "", _raw_phone)
                if phone != _raw_phone:
                    st.info(t("examples_phone"))
                st.caption(t("examples_phone"))
            with col2:
                color = st.color_picker(t("calendar_color"), value=student_row.get("color", "#3B82F6"), key=f"student_color_{sid}")
                address = st.text_input(t("address"), value=student_row.get("address", ""), key=f"student_address_{sid}")
                native_language_current = normalize_native_language(student_row.get("native_language", ""))
                native_language = native_language_current
                show_native_language_profile_field = (
                    _current_teacher_teaches_languages()
                    or _student_has_language_subject(selected_student)
                    or bool(native_language_current)
                )
                if show_native_language_profile_field:
                    native_language = st.selectbox(
                        t("student_native_language"),
                        NATIVE_LANGUAGE_OPTIONS,
                        index=NATIVE_LANGUAGE_OPTIONS.index(native_language_current) if native_language_current in NATIVE_LANGUAGE_OPTIONS else 0,
                        format_func=native_language_label,
                        key=f"student_native_language_{sid}",
                        help=t("student_native_language_help"),
                    )
                notes = st.text_area(t("notes"), value=student_row.get("notes", ""), key=f"student_notes_{sid}")

            if phone and not normalize_phone_for_whatsapp(phone) and len(_digits_only(phone)) < 11:
                st.warning(t("examples_phone"))

            if st.button(t("save"), key=f"btn_save_student_profile_{sid}"):
                update_student_profile(selected_student, email, zoom_link, notes, color, phone, address, native_language)
                st.success(t("done_ok"))
                st.rerun()

        # ── TAB: Student History ──
        with tab_history:
            if not students:
                st.info(t("no_students"))
            else:
                hist_student = st.selectbox(t("select_student"), students, key="students_history_student")
                lessons_df, payments_df = show_student_history(hist_student)

                colA, colB = st.columns(2)
                with colA:
                    st.markdown(f"### {t('lessons')}")
                    render_styled_dataframe(translate_df_headers(lessons_df))
                with colB:
                    st.markdown(f"### {t('payments')}")
                    render_styled_dataframe(translate_df_headers(payments_df))

                st.markdown(f"#### {t('report_actions')}")

                _dash = rebuild_dashboard()
                _pkg_df = _dash[_dash["Student"] == hist_student].copy() if not _dash.empty else pd.DataFrame()

                pdf_bytes = build_student_report_pdf(hist_student, lessons_df, payments_df, _pkg_df)
                safe_name = re.sub(r"[^A-Za-z0-9._-]+", "_", hist_student.strip()) or "student"
                file_name = f"report_{safe_name}.pdf"

                _sdf = students_df
                _row = _sdf.loc[_sdf["student"] == hist_student]
                _email = str(_row.iloc[0].get("email", "")).strip() if not _row.empty else ""
                _phone = str(_row.iloc[0].get("phone", "")).strip() if not _row.empty else ""

                from services.permissions_service import can_export_pdf, increment_usage

                btn_cols = st.columns(3)
                with btn_cols[0]:
                    _can_download_pdf = can_export_pdf()
                    if not _can_download_pdf:
                        st.warning(t("ai_limit_reached") if t("ai_limit_reached") != "ai_limit_reached" else "PDF export limit reached.")
                    _downloaded_pdf = st.download_button(
                        label=f"📄 {t('download_pdf')}",
                        data=pdf_bytes,
                        file_name=file_name,
                        mime="application/pdf",
                        key="btn_download_student_report",
                        use_container_width=True,
                        disabled=not _can_download_pdf,
                    )
                    if _downloaded_pdf:
                        increment_usage(None, "pdf_exports")
                with btn_cols[1]:
                    if _phone:
                        wa_url = build_report_whatsapp_url(hist_student, _phone)
                        st.link_button(
                            f"💬 {t('send_whatsapp')}",
                            url=wa_url,
                            use_container_width=True,
                        )
                    else:
                        st.button(
                            f"💬 {t('send_whatsapp')}",
                            disabled=True,
                            help=t("no_phone_on_file"),
                            key="btn_wa_report_disabled",
                            use_container_width=True,
                        )
                with btn_cols[2]:
                    if _email:
                        mail_url = build_report_email_url(hist_student, _email)
                        st.link_button(
                            f"📧 {t('send_email')}",
                            url=mail_url,
                            use_container_width=True,
                        )
                    else:
                        st.button(
                            f"📧 {t('send_email')}",
                            disabled=True,
                            help=t("no_email_on_file"),
                            key="btn_email_report_disabled",
                            use_container_width=True,
                        )
                if _phone or _email:
                    st.caption(t("share_report_hint"))

        # ── TAB: Delete Student ──
        with tab_delete:
            st.caption(t("delete_student_warning"))
            if not students:
                st.info(t("no_students"))
            else:
                del_student = st.selectbox(t("select_student"), students, key="delete_student_select")
                confirm = st.checkbox(t("confirm_delete_student"), key="delete_student_confirm")
                if st.button(t("delete"), type="primary", disabled=not confirm, key="btn_delete_student"):
                    try:
                        get_sb().table("students").delete().eq("student", del_student).eq("user_id", get_current_user_id()).execute()
                        clear_app_caches()
                        st.success(t("done_ok"))
                        st.rerun()
                    except Exception as e:
                        st.error(f"{t('delete_student_failed')}\n\n{e}")

        with tab_requests:
            st.markdown(f"### {t('teacher_requests_title')}")
            incoming = load_incoming_teacher_requests()
            if not incoming:
                st.info(t("no_teacher_requests"))
            else:
                incoming_page, *_ = _slice_teacher_page(incoming, "teacher_incoming_requests_page")
                for row in incoming_page:
                    left_col, right_col = st.columns([6, 2], gap="medium")
                    requested = row.get("requested_subjects") or []
                    requested_labels = [s.get("subject_label", "") for s in requested if s.get("subject_label")]
                    with left_col:
                        chips = "".join(
                            f"<span class='classio-inline-chip'>📚 {str(label)}</span>"
                            for label in requested_labels
                        )
                        note_html = ""
                        if row.get("request_note"):
                            note_html = (
                                f"<div class='classio-student-link-note'><strong>{t('teacher_note')}:</strong> "
                                f"{row.get('request_note')}</div>"
                            )
                        st.markdown(
                            f"""
                            <div class="classio-student-link-card">
                                <div class="classio-student-link-name">{row.get('student_name', '—')}</div>
                                <div class="classio-student-link-meta">{t('requested_subjects')}</div>
                                <div style="margin-top:0.5rem;">{chips or f"<span class='classio-inline-chip'>{t('no_active_subjects')}</span>"}</div>
                                {note_html}
                            </div>
                            """,
                            unsafe_allow_html=True,
                        )

                    req_options = [
                        s.get("subject_label", "")
                        for s in requested
                        if s.get("subject_label")
                    ]
                    with right_col:
                        st.markdown(
                            f"<div class='classio-student-link-action-label'>{t('active_subjects')}</div>",
                            unsafe_allow_html=True,
                        )
                        resolution = get_teacher_request_resolution(int(row.get("id")))
                        selected_record_id = None
                        accept_disabled = not req_options
                        chosen = []
                        if req_options:
                            chosen = st.multiselect(
                                t("active_subjects"),
                                options=req_options,
                                default=req_options,
                                key=f"teacher_request_subjects_{row.get('id')}",
                                label_visibility="collapsed",
                            )
                        else:
                            st.warning(t("select_active_subjects"))
                        if resolution.get("mode") in {"linked_existing", "auto_email"} and resolution.get("selected_row"):
                            st.info(
                                f"{t(resolution.get('summary_key', 'teacher_request_auto_link_existing'))} "
                                f"{_html.escape(str(resolution['selected_row'].get('student') or ''))}"
                            )
                        elif resolution.get("mode") == "review":
                            st.warning(t("teacher_request_review_match"))
                            option_values = ["__choose__", "__create_new__"] + [
                                str(candidate.get("id")) for candidate in resolution.get("candidates", [])
                            ]
                            selected_option = st.selectbox(
                                t("teacher_request_select_student_record"),
                                options=option_values,
                                format_func=lambda value: (
                                    t("teacher_request_choose_resolution")
                                    if value == "__choose__"
                                    else t("teacher_request_create_new_record")
                                    if value == "__create_new__"
                                    else next(
                                        (
                                            f"{candidate.get('student', '—')}"
                                            + (
                                                f" · {candidate.get('email')}"
                                                if str(candidate.get('email') or '').strip()
                                                else ""
                                            )
                                            for candidate in resolution.get("candidates", [])
                                            if str(candidate.get("id")) == str(value)
                                        ),
                                        "—",
                                    )
                                ),
                                key=f"teacher_request_resolution_{row.get('id')}",
                            )
                            if selected_option == "__choose__":
                                accept_disabled = True
                            elif selected_option != "__create_new__":
                                selected_record_id = int(selected_option)
                        else:
                            st.caption(t("teacher_request_new_record_will_be_created"))
                        if st.button(
                            t("accept"),
                            key=f"teacher_request_accept_{row.get('id')}",
                            use_container_width=True,
                            disabled=accept_disabled,
                            type="primary",
                        ):
                            if resolution.get("mode") in {"linked_existing", "auto_email"} and resolution.get("selected_row"):
                                selected_record_id = int(resolution["selected_row"].get("id"))
                            ok, msg = respond_to_teacher_request(
                                int(row.get("id")),
                                True,
                                chosen,
                                selected_record_id,
                            )
                            if ok:
                                st.success(t(msg))
                                st.rerun()
                            st.error(t(msg))
                        st.markdown("<div style='height:0.45rem;'></div>", unsafe_allow_html=True)
                        if st.button(t("reject"), key=f"teacher_request_reject_{row.get('id')}", use_container_width=True):
                            ok, msg = respond_to_teacher_request(int(row.get("id")), False, [])
                            if ok:
                                st.success(t(msg))
                                st.rerun()
                            st.error(t(msg))
                    st.markdown("<div style='height:0.75rem;'></div>", unsafe_allow_html=True)
                _render_teacher_pagination(incoming, "teacher_incoming_requests_page")

            st.markdown(f"### {t('my_linked_students')}")
            linked = load_active_linked_students_for_teacher()
            if not linked:
                st.info(t("no_linked_students"))
            else:
                linked_page, *_ = _slice_teacher_page(linked, "teacher_linked_students_page")
                for row in linked_page:
                    left_col, right_col = st.columns([6, 2], gap="medium")
                    subjects = ", ".join(
                        s.get("subject_label", "")
                        for s in row.get("subjects", [])
                        if s.get("subject_label")
                    )
                    with left_col:
                        chips = "".join(
                            f"<span class='classio-inline-chip'>📚 {label}</span>"
                            for label in [s.strip() for s in subjects.split(",") if s.strip()]
                        )
                        st.markdown(
                            f"""
                            <div class="classio-student-link-card">
                                <div class="classio-student-link-name">{row.get('student_name', '—')}</div>
                                <div class="classio-student-link-meta">{t('active_subjects')}</div>
                                <div style="margin-top:0.55rem;">{chips or f"<span class='classio-inline-chip'>{t('no_active_subjects')}</span>"}</div>
                            </div>
                            """,
                            unsafe_allow_html=True,
                        )
                    with right_col:
                        st.markdown(
                            f"<div class='classio-student-link-action-label'>{t('relationship_end_prompt')}</div>",
                            unsafe_allow_html=True,
                        )
                        _render_end_relationship_action(
                            link_id=int(row.get("id") or 0),
                            key_prefix=f"archive_link_{row.get('id')}",
                        )
                    st.markdown("<div style='height:0.75rem;'></div>", unsafe_allow_html=True)
                _render_teacher_pagination(linked, "teacher_linked_students_page")

        with tab_progress:
            st.markdown(f"### {t('student_progress_title')}")
            linked = load_active_linked_students_for_teacher()
            if not linked:
                st.info(t("no_linked_students"))
            else:
                student_options = {row.get("student_name", "—"): row for row in linked}
                selected_student_name = st.selectbox(
                    t("select_student"),
                    options=list(student_options.keys()),
                    key="assignment_progress_student",
                )
                selected_link = student_options[selected_student_name]
                linked_subjects = [
                    subject
                    for subject in (selected_link.get("subjects", []) or [])
                    if str(subject.get("subject_key") or "").strip()
                ]
                unique_subjects = list(
                    dict.fromkeys(str(subject.get("subject_key") or "").strip() for subject in linked_subjects)
                )
                if len(unique_subjects) > 1:
                    subject_options = ["__all__"] + unique_subjects
                    selected_subject = st.selectbox(
                        t("subject_filter"),
                        options=subject_options,
                        format_func=lambda x: t("all_subjects") if x == "__all__" else next(
                            (
                                s.get("subject_label", x)
                                for s in linked_subjects
                                if s.get("subject_key") == x
                            ),
                            x,
                        ),
                        key="assignment_progress_subject",
                    )
                elif unique_subjects:
                    selected_subject = unique_subjects[0]
                else:
                    selected_subject = "__all__"
                progress_rows = load_teacher_assignment_progress(
                    student_id=str(selected_link.get("student_id") or ""),
                    subject_key=None if selected_subject == "__all__" else selected_subject,
                )
                review_rows = load_teacher_review_requests(
                    student_id=str(selected_link.get("student_id") or ""),
                    subject_key=None if selected_subject == "__all__" else selected_subject,
                )
                program_rows = _load_teacher_program_rows_for_student(selected_link, selected_student_name)
                selected_student_id = str(selected_link.get("student_id") or "").strip() or norm_student(selected_student_name)

                assignments_tab, reviews_tab, programs_tab, recommendations_tab = st.tabs(
                    [
                        f"📝 {t('student_progress_assignments_tab')}",
                        f"🧑‍🏫 {t('student_progress_reviews_tab')}",
                        f"📚 {t('assigned_learning_programs_title')}",
                        f"✨ {t('student_progress_recommendations_tab')}",
                    ]
                )

                with assignments_tab:
                    assignment_status_options = ["__all__"] + list(
                        dict.fromkeys(
                            str(row.get("status") or "").strip()
                            for row in progress_rows
                            if str(row.get("status") or "").strip()
                        )
                    )
                    assignment_status = st.selectbox(
                        t("status"),
                        options=assignment_status_options,
                        format_func=lambda value: t("all") if value == "__all__" else t(f"assignment_status_{value}"),
                        key="assignment_progress_status",
                    )
                    filtered_progress_rows = [
                        row for row in progress_rows
                        if assignment_status == "__all__" or str(row.get("status") or "").strip() == assignment_status
                    ]
                    if not filtered_progress_rows:
                        st.info(t("no_assignments"))
                    else:
                        fpr_page, *_ = _slice_teacher_page(filtered_progress_rows, "teacher_assignment_progress_page")
                        for row in fpr_page:
                            latest = row.get("latest_attempt") or {}
                            score = latest.get("score_pct", row.get("score_pct"))
                            title = _html.escape(str(row.get("title") or "—"))
                            subject_display = _html.escape(_localized_subject_display(row.get("subject_key"), row.get("subject_display")))
                            status_label = _html.escape(t(f"assignment_status_{row.get('status')}"))
                            attempts_value = int(row.get("attempt_count") or 0)
                            score_value = f"{score}%" if score not in (None, "") else "—"
                            student_name_safe = _html.escape(str(row.get("student_name") or selected_student_name or "—"))
                            card_col, action_col = st.columns([6, 2], gap="medium")
                            with card_col:
                                st.markdown(
                                    f"""
                                    <div class="classio-progress-card">
                                        <div style="display:flex;justify-content:space-between;gap:12px;align-items:flex-start;flex-wrap:wrap;">
                                            <div>
                                                <div class="classio-progress-title">{title}</div>
                                                <div class="classio-progress-meta">{student_name_safe} · {subject_display}</div>
                                            </div>
                                            <div><span class="classio-inline-chip">📌 {status_label}</span></div>
                                        </div>
                                        <div class="classio-progress-stats">
                                            <div class="classio-progress-stat">
                                                <div class="classio-progress-stat-label">{_html.escape(t('attempts_label'))}</div>
                                                <div class="classio-progress-stat-value">{attempts_value}</div>
                                            </div>
                                            <div class="classio-progress-stat">
                                                <div class="classio-progress-stat-label">{_html.escape(t('score_label'))}</div>
                                                <div class="classio-progress-stat-value">{_html.escape(score_value)}</div>
                                            </div>
                                            <div class="classio-progress-stat">
                                                <div class="classio-progress-stat-label">{_html.escape(t('created_at_label'))}</div>
                                                <div class="classio-progress-stat-value">{_html.escape(str(row.get('created_at') or '')[:10] or '—')}</div>
                                            </div>
                                        </div>
                                    </div>
                                    """,
                                    unsafe_allow_html=True,
                                )
                            with action_col:
                                if latest.get("practice_session_id") and str(row.get("assignment_type") or "").strip() in {"worksheet", "exam"}:
                                    if st.button(
                                        t("teacher_review_start"),
                                        key=f"teacher_review_start_{row.get('id')}",
                                        use_container_width=True,
                                        help=t("teacher_review_start_help"),
                                    ):
                                        ok, msg, _review_id = ensure_teacher_review_request_for_attempt(
                                            student_id=str(row.get("student_id") or ""),
                                            practice_session_id=int(latest.get("practice_session_id") or 0),
                                            assignment_id=int(row.get("id") or 0),
                                            subject_key=str(row.get("subject_key") or ""),
                                            subject_label_text=str(row.get("subject_display") or ""),
                                            title=str(row.get("title") or ""),
                                            source_type=str(row.get("assignment_type") or ""),
                                            source_id=row.get("source_id"),
                                        )
                                        if ok:
                                            st.success(t(msg))
                                            st.rerun()
                                        st.error(t(msg))
                                if st.button(
                                    t("delete_assignment"),
                                    key=f"archive_assignment_{row.get('id')}",
                                    use_container_width=True,
                                ):
                                    ok, msg = archive_teacher_assignment_for_teacher(int(row.get("id") or 0))
                                    if ok:
                                        st.success(t(msg))
                                        st.rerun()
                                    st.error(t(msg) if msg in {"assignment_archived", "assignment_archive_failed"} else msg)
                        _render_teacher_pagination(filtered_progress_rows, "teacher_assignment_progress_page")

                with recommendations_tab:
                    _render_recommendations_tab(
                        progress_rows,
                        program_rows,
                        selected_subject,
                        selected_student_name,
                        selected_link,
                    )

                with programs_tab:
                    if not program_rows:
                        st.info(t("no_assignments"))
                    else:
                        filtered_rows = [
                            row for row in program_rows
                            if selected_subject == "__all__" or str(row.get("subject_key") or "").strip() == selected_subject
                        ]
                        subject_groups = _teacher_program_subject_groups(filtered_rows)
                        if not subject_groups:
                            st.info(t("no_assignments"))
                        elif len(subject_groups) > 1:
                            tabs = st.tabs([f"📚 {label}" for subject_key, label, _rows in subject_groups])
                            for tab, (subject_key, _label, rows) in zip(tabs, subject_groups):
                                with tab:
                                    _render_teacher_program_assignment_list(
                                        rows,
                                        f"teacher_programs_progress_page_{selected_student_id}_{subject_key}",
                                    )
                        else:
                            subject_key, _label, rows = subject_groups[0]
                            _render_teacher_program_assignment_list(
                                rows,
                                f"teacher_programs_progress_page_{selected_student_id}_{subject_key}",
                            )

                with reviews_tab:
                    review_status_options = ["__all__"] + list(
                        dict.fromkeys(
                            str(row.get("status") or "").strip()
                            for row in review_rows
                            if str(row.get("status") or "").strip()
                        )
                    )
                    review_status = st.selectbox(
                        t("status"),
                        options=review_status_options,
                        format_func=lambda value: t("all") if value == "__all__" else t(f"teacher_review_status_{value}"),
                        key="teacher_review_status_filter",
                    )
                    _render_teacher_review_requests(
                        student_id=str(selected_link.get("student_id") or ""),
                        subject_key=None if selected_subject == "__all__" else selected_subject,
                        status_filter=review_status,
                        render_title=False,
                    )

# =========================
