import html as _html
import json
import math

import streamlit as st

from core.database import get_sb
from core.i18n import t
from core.navigation import go_to
from core.state import get_current_user_id
from helpers.practice_engine import exam_to_exercises, worksheet_to_exercises
from helpers.practice_engine import load_in_progress_practice_session, load_practice_draft_answers, normalize_exercise_data_for_web
from helpers.visual_support import enrich_exam_with_visuals, enrich_worksheet_with_visuals, exam_has_ready_visuals, worksheet_has_ready_visuals
from helpers.teacher_student_integration import (
    _clean_teacher_feedback_text,
    group_assignments_by_teacher_subject,
    has_active_teacher_relationships,
    load_student_assignments,
    load_student_teacher_links,
    mark_assignment_started,
    persist_assignment_content_snapshot,
    update_topic_assignment_status,
)
from helpers.learning_programs import load_enriched_program_assignments_for_current_student, render_student_program_view

_STUDENT_PAGE_SIZE = 4


def _normalize_source_record_id(source_record_id):
    text = str(source_record_id or "").strip()
    if not text:
        return None
    if text.isdigit():
        try:
            return int(text)
        except Exception:
            return text
    return text


def _load_source_worksheet(source_record_id):
    safe_source_id = _normalize_source_record_id(source_record_id)
    if safe_source_id in (None, "", 0, "0"):
        return {}
    try:
        res = (
            get_sb()
            .table("worksheets")
            .select("worksheet_json")
            .eq("id", safe_source_id)
            .limit(1)
            .execute()
        )
        rows = getattr(res, "data", None) or []
        if not rows:
            return {}
        return dict(rows[0].get("worksheet_json") or {})
    except Exception:
        return {}


def _load_source_exam(source_record_id):
    safe_source_id = _normalize_source_record_id(source_record_id)
    if safe_source_id in (None, "", 0, "0"):
        return {}
    try:
        res = (
            get_sb()
            .table("quick_exams")
            .select("exam_data")
            .eq("id", safe_source_id)
            .limit(1)
            .execute()
        )
        rows = getattr(res, "data", None) or []
        if not rows:
            return {}
        return dict(rows[0].get("exam_data") or {})
    except Exception:
        return {}


def _open_assignment_practice(row: dict) -> None:
    assignment_id = row.get("id")
    snapshot = row.get("content_snapshot") or {}
    assignment_type = str(row.get("assignment_type") or "").strip()
    source_record_id = row.get("source_record_id")
    meta = {
        "subject": row.get("subject_key", ""),
        "topic": row.get("topic", ""),
        "learner_stage": (snapshot.get("meta") or {}).get("learner_stage", ""),
        "level": (snapshot.get("meta") or {}).get("level_or_band", ""),
    }

    exercise_data = {}
    if assignment_type == "worksheet":
        worksheet = dict(snapshot.get("worksheet") or {})
        if not worksheet_has_ready_visuals(worksheet):
            source_worksheet = _load_source_worksheet(source_record_id)
            if worksheet_has_ready_visuals(source_worksheet):
                worksheet = source_worksheet
                snapshot["worksheet"] = worksheet
                persist_assignment_content_snapshot(int(assignment_id), snapshot)
        # Visuals are generated once at creation time; no re-enrichment here
        exercise_data = worksheet_to_exercises(worksheet, row_id=assignment_id)
    elif assignment_type == "exam":
        exam_data = dict(snapshot.get("exam_data") or {})
        if not exam_has_ready_visuals(exam_data):
            source_exam = _load_source_exam(source_record_id)
            if exam_has_ready_visuals(source_exam):
                exam_data = source_exam
                snapshot["exam_data"] = exam_data
                persist_assignment_content_snapshot(int(assignment_id), snapshot)
        # Visuals are generated once at creation time; no re-enrichment here
        answer_key = snapshot.get("answer_key") or {}
        exercise_data = exam_to_exercises(exam_data, answer_key, row_id=assignment_id)

    if not exercise_data.get("exercises"):
        st.warning(t("no_exercises_available"))
        return

    draft = load_in_progress_practice_session(assignment_type, assignment_id)
    if draft:
        draft_exercise_data = draft.get("exercise_data") or exercise_data
        if isinstance(draft_exercise_data, str):
            try:
                draft_exercise_data = json.loads(draft_exercise_data)
            except Exception:
                draft_exercise_data = exercise_data
        st.session_state["practice_exercise_data"] = normalize_exercise_data_for_web(draft_exercise_data or exercise_data)
        st.session_state["_practice_resume_session_id"] = draft.get("id")
        st.session_state["_practice_resume_answers"] = load_practice_draft_answers(int(draft.get("id")))
        st.session_state["_practice_resume_notice"] = True
    else:
        st.session_state["practice_exercise_data"] = exercise_data
        st.session_state.pop("_practice_resume_session_id", None)
        st.session_state.pop("_practice_resume_answers", None)
        st.session_state.pop("_practice_resume_notice", None)
    st.session_state["practice_meta"] = meta
    st.session_state["_practice_assignment_id"] = assignment_id
    st.session_state["_practice_assignment_type"] = assignment_type
    mark_assignment_started(assignment_id)
    go_to("student_practice")
    st.rerun()


def _status_badge(status: str) -> str:
    colors = {
        "assigned": "#2563EB",
        "started": "#F59E0B",
        "submitted": "#8B5CF6",
        "graded": "#10B981",
        "completed": "#059669",
        "overdue": "#DC2626",
        "cancelled": "#64748B",
        "archived": "#64748B",
    }
    color = colors.get(str(status or "").strip(), "#64748B")
    return (
        f"<span style='display:inline-flex;align-items:center;padding:7px 12px;border-radius:999px;"
        f"background:linear-gradient(135deg,{color}20,{color}10);color:{color};font-size:0.78rem;font-weight:800;border:1px solid {color}4D;"
        f"box-shadow:0 6px 18px {color}14;'>"
        f"{t(f'assignment_status_{status}') if status else '—'}</span>"
    )


def _safe_ui_label(key: str, fallback: str | None = None) -> str:
    value = t(key)
    if value != key:
        return value
    if fallback:
        fallback_value = t(fallback)
        if fallback_value != fallback:
            return fallback_value
    return key.replace("_", " ").strip().title()


def _slice_student_page(rows: list[dict], state_key: str, *, page_size: int = _STUDENT_PAGE_SIZE):
    total_items = len(rows or [])
    total_pages = max(1, math.ceil(total_items / page_size)) if total_items else 1
    current_page = int(st.session_state.get(state_key, 1) or 1)
    current_page = max(1, min(current_page, total_pages))
    st.session_state[state_key] = current_page
    start_idx = (current_page - 1) * page_size
    end_idx = min(start_idx + page_size, total_items)
    return list((rows or [])[start_idx:end_idx]), current_page, total_pages, start_idx, end_idx, total_items


def _render_student_pagination(rows: list[dict], state_key: str, *, page_size: int = _STUDENT_PAGE_SIZE) -> None:
    _, current_page, total_pages, start_idx, end_idx, total_items = _slice_student_page(
        rows,
        state_key,
        page_size=page_size,
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


def _inject_assignment_page_styles() -> None:
    st.markdown(
        """
        <style>
        .classio-assign-teacher {
            margin-top: 1.8rem;
            margin-bottom: 0.9rem;
            font-size: 1.85rem;
            font-weight: 800;
            letter-spacing: -0.02em;
        }
        .classio-assign-subject {
            margin: 0 0 0.95rem 0.15rem;
            font-size: 1rem;
            font-weight: 700;
            color: var(--muted);
        }
        .classio-assign-card {
            position: relative;
            overflow: hidden;
            background:
              radial-gradient(circle at top right, rgba(59,130,246,.08), transparent 38%),
              linear-gradient(180deg, var(--panel), color-mix(in srgb, var(--panel) 84%, white 16%));
            border: 1px solid color-mix(in srgb, var(--border) 78%, rgba(59,130,246,.22) 22%);
            border-radius: 22px;
            padding: 20px 22px 18px;
            box-shadow: 0 12px 34px rgba(15,23,42,.08);
            margin-bottom: 0.65rem;
        }
        .classio-assign-card::before {
            content: "";
            position: absolute;
            inset: 0 auto 0 0;
            width: 5px;
            background: linear-gradient(180deg, #38bdf8, #6366f1 55%, #14b8a6);
        }
        .classio-assign-card--worksheet {
            background:
              radial-gradient(circle at top right, rgba(167,139,250,.12), transparent 38%),
              linear-gradient(180deg, var(--panel), color-mix(in srgb, var(--panel) 84%, white 16%));
            border-color: color-mix(in srgb, var(--border) 76%, rgba(167,139,250,.28) 24%);
        }
        .classio-assign-card--worksheet::before {
            background: linear-gradient(180deg, #a78bfa, #8b5cf6 58%, #6366f1);
        }
        .classio-assign-card--exam {
            background:
              radial-gradient(circle at top right, rgba(248,113,113,.12), transparent 38%),
              linear-gradient(180deg, var(--panel), color-mix(in srgb, var(--panel) 84%, white 16%));
            border-color: color-mix(in srgb, var(--border) 76%, rgba(248,113,113,.26) 24%);
        }
        .classio-assign-card--exam::before {
            background: linear-gradient(180deg, #f87171, #ef4444 58%, #f59e0b);
        }
        .classio-assign-card--topic {
            background:
              radial-gradient(circle at top right, rgba(96,165,250,.12), transparent 38%),
              linear-gradient(180deg, var(--panel), color-mix(in srgb, var(--panel) 84%, white 16%));
            border-color: color-mix(in srgb, var(--border) 76%, rgba(96,165,250,.24) 24%);
        }
        .classio-assign-card--topic::before {
            background: linear-gradient(180deg, #60a5fa, #3b82f6 58%, #38bdf8);
        }
        .classio-assign-title {
            font-size: 1.18rem;
            font-weight: 800;
            line-height: 1.25;
            color: var(--text);
        }
        .classio-assign-meta {
            margin-top: 0.7rem;
            color: var(--muted);
            font-size: 0.92rem;
            line-height: 1.45;
        }
        .classio-assign-note {
            margin: 0.55rem 0 1.2rem 0.15rem;
            padding: 0.72rem 0.9rem;
            border-radius: 14px;
            background: rgba(148,163,184,.08);
            border: 1px solid rgba(148,163,184,.16);
            color: var(--muted);
            font-size: 0.9rem;
        }
        .classio-assign-action-label {
            font-size: 0.76rem;
            font-weight: 800;
            text-transform: uppercase;
            letter-spacing: 0.06em;
            color: var(--muted);
            margin: 0.2rem 0 0.55rem 0.1rem;
        }
        .classio-assign-action-done {
            border-radius: 16px;
            min-height: 3rem;
            display: flex;
            align-items: center;
            justify-content: center;
            font-weight: 800;
            color: #0f766e;
            background: linear-gradient(135deg, rgba(16,185,129,.16), rgba(45,212,191,.12));
            border: 1px solid rgba(16,185,129,.26);
            box-shadow: 0 12px 24px rgba(16,185,129,.12);
        }
        .classio-assign-action-archived {
            border-radius: 16px;
            min-height: 3rem;
            display: flex;
            align-items: center;
            justify-content: center;
            font-weight: 800;
            color: #475569;
            background: linear-gradient(135deg, rgba(148,163,184,.20), rgba(148,163,184,.10));
            border: 1px solid rgba(148,163,184,.28);
            box-shadow: 0 12px 24px rgba(148,163,184,.10);
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
        .classio-assigned-program-head {
            margin-top: 1rem;
            margin-bottom: .9rem;
            font-size: 1.55rem;
            font-weight: 900;
            letter-spacing: -0.03em;
        }
        .classio-assigned-program-meta {
            color: var(--muted);
            font-size: .92rem;
            margin-top: .4rem;
        }
        .classio-assigned-program-wrap {
            position: relative;
            overflow: hidden;
            border-radius: 28px;
            padding: 1.15rem 1.15rem 1rem;
            background:
              radial-gradient(circle at top left, rgba(59,130,246,.18), transparent 35%),
              radial-gradient(circle at top right, rgba(251,191,36,.16), transparent 30%),
              linear-gradient(180deg, var(--panel), color-mix(in srgb, var(--panel) 82%, white 18%));
            border: 1px solid color-mix(in srgb, var(--border) 74%, rgba(59,130,246,.24) 26%);
            box-shadow: 0 18px 40px rgba(15,23,42,.10);
            margin-bottom: 1rem;
        }
        .classio-assigned-program-title {
            font-size: 1.22rem;
            line-height: 1.2;
            font-weight: 900;
            color: var(--text);
        }
        .classio-assigned-program-subtitle {
            margin-top: .45rem;
            color: var(--muted);
            font-size: .93rem;
            line-height: 1.45;
        }
        .classio-assigned-program-progress {
            margin-top: .8rem;
            display: flex;
            flex-wrap: wrap;
            gap: .45rem;
        }
        .classio-assigned-pill {
            display: inline-flex;
            align-items: center;
            padding: .42rem .78rem;
            border-radius: 999px;
            background: color-mix(in srgb, var(--panel-soft) 82%, var(--panel) 18%);
            border: 1px solid color-mix(in srgb, var(--border-strong) 70%, var(--text) 12%);
            font-size: .8rem;
            font-weight: 800;
            color: var(--text);
            box-shadow: inset 0 1px 0 color-mix(in srgb, var(--text) 10%, transparent);
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _assignment_card(row: dict, key_prefix: str) -> None:
    title = _html.escape(str(row.get("title") or "—"))
    status = str(row.get("status") or "").strip()
    due_at = str(row.get("due_at") or "").strip()
    created_at = str(row.get("created_at") or "").strip()
    teacher_note = _clean_teacher_feedback_text(row.get("teacher_note"))
    assignment_type = str(row.get("assignment_type") or "").strip()
    source_archived = bool(row.get("source_archived"))
    teacher_name = _html.escape(str(row.get("teacher_name") or "—"))
    subject_name = _html.escape(str(row.get("subject_display") or "—"))
    type_class = {
        "worksheet": "classio-assign-card--worksheet",
        "exam": "classio-assign-card--exam",
        "lesson_plan_topic": "classio-assign-card--topic",
    }.get(assignment_type, "")

    meta_bits = [teacher_name, subject_name]
    if due_at:
        meta_bits.append(f"{_html.escape(_safe_ui_label('due_date', 'assignment_set_due_date'))}: {_html.escape(due_at[:10])}")
    elif created_at:
        meta_bits.append(f"{_html.escape(t('created_at_label'))}: {_html.escape(created_at[:10])}")

    left_col, right_col = st.columns([6, 2], gap="medium")
    with left_col:
        st.markdown(
            f"""
            <div class="classio-assign-card {type_class}">
                <div style="display:flex;justify-content:space-between;gap:12px;align-items:flex-start;flex-wrap:wrap;">
                    <div>
                        <div class="classio-assign-title">{title}</div>
                        <div class="classio-assign-meta">{' · '.join(meta_bits)}</div>
                    </div>
                    <div>{_status_badge(status)}</div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        if teacher_note:
            st.markdown(
                f"<div class='classio-assign-note'><strong>{_html.escape(t('teacher_note'))}:</strong> {_html.escape(teacher_note)}</div>",
                unsafe_allow_html=True,
            )
        else:
            st.markdown("<div style='height:0.8rem;'></div>", unsafe_allow_html=True)

    with right_col:
        draft = load_in_progress_practice_session(assignment_type, row.get("id"))
        if assignment_type in {"worksheet", "exam"}:
            is_finalized = status in {"submitted", "graded", "completed", "cancelled"}
            is_continue = bool(draft) or status == "started"
            if source_archived:
                if st.button(t("archived_label"), key=f"{key_prefix}_archived", use_container_width=True):
                    st.info(t("assignment_source_archived_notice"))
            elif is_finalized:
                st.markdown(
                    f"<div class='classio-assign-action-done'>{_html.escape(t('assignment_done'))}</div>",
                    unsafe_allow_html=True,
                )
            else:
                action_text = t("continue_practice") if is_continue else t("open_assignment")
                if st.button(action_text, key=f"{key_prefix}_open", use_container_width=True, type="primary"):
                    _open_assignment_practice(row)
        elif assignment_type == "lesson_plan_topic":
            st.markdown(
                f"<div class='classio-assign-action-label'>{_html.escape(t('assigned_topics'))}</div>",
                unsafe_allow_html=True,
            )
            if st.button(t("mark_in_progress"), key=f"{key_prefix}_start", use_container_width=True):
                update_topic_assignment_status(row.get("id"), "started")
                st.rerun()
            st.markdown("<div style='height:0.45rem;'></div>", unsafe_allow_html=True)
            if st.button(t("mark_completed"), key=f"{key_prefix}_complete", use_container_width=True, type="primary"):
                update_topic_assignment_status(row.get("id"), "completed")
                st.rerun()
        st.markdown("<div style='height:0.7rem;'></div>", unsafe_allow_html=True)


def _render_teacher_relationships() -> None:
    relationships = load_student_teacher_links()
    if not relationships:
        st.info(t("no_linked_teachers"))
        return

    active = [row for row in relationships if str(row.get("status") or "") == "active"]
    pending = [row for row in relationships if str(row.get("status") or "") == "pending"]

    if active:
        st.markdown(f"### {t('my_teachers')}")
        for row in active:
            subjects = ", ".join(s.get("subject_label", "") for s in row.get("active_subjects", []) if s.get("subject_label"))
            st.markdown(f"**{row.get('teacher_name', '—')}**")
            if subjects:
                st.caption(f"{t('active_subjects')}: {subjects}")

    if pending:
        st.markdown(f"### {t('teacher_requests_pending')}")
        for row in pending:
            requested = ", ".join(s.get("subject_label", "") for s in row.get("requested_subjects", []) if s.get("subject_label"))
            st.markdown(f"**{row.get('teacher_name', '—')}**")
            if requested:
                st.caption(f"{t('requested_subjects')}: {requested}")


def _render_assignment_group(title: str, rows: list[dict], group_prefix: str) -> None:
    if not rows:
        st.info(t("no_assignments"))
        return

    page_rows, *_ = _slice_student_page(rows, f"{group_prefix}_page")
    grouped = group_assignments_by_teacher_subject(page_rows)
    for teacher_name, subject_groups in grouped:
        st.markdown(f"<div class='classio-assign-teacher'>{_html.escape(teacher_name)}</div>", unsafe_allow_html=True)
        for subject_name, items in subject_groups:
            st.markdown(f"<div class='classio-assign-subject'>{_html.escape(subject_name)}</div>", unsafe_allow_html=True)
            for idx, row in enumerate(items):
                _assignment_card(row, f"{group_prefix}_{teacher_name}_{subject_name}_{idx}")
    _render_student_pagination(rows, f"{group_prefix}_page")


def render_assigned_learning_programs_section(program_assignments: list[dict], legacy_topics: list[dict]) -> None:
    if not program_assignments and not legacy_topics:
        st.info(t("no_assignments"))
        return

    if program_assignments:
        for idx, item in enumerate(program_assignments):
            program = item.get("program") or {}
            title = _html.escape(str(program.get("title") or "Learning program"))
            teacher_name = _html.escape(str(item.get("teacher_name") or "Teacher"))
            subject_display = _html.escape(str(item.get("subject_display") or "—"))
            completed_topics = int(item.get("completed_topics") or 0)
            total_topics = int(item.get("total_topics") or 0)
            progress_pct = int(item.get("progress_pct") or 0)
            start_on = str(item.get("start_on") or "").strip()
            target_completion_on = str(item.get("target_completion_on") or "").strip()
            teacher_note = _clean_teacher_feedback_text(item.get("teacher_note"))

            st.markdown(
                f"""
                <div class="classio-assigned-program-wrap">
                    <div class="classio-assigned-program-title">{title}</div>
                    <div class="classio-assigned-program-subtitle">{teacher_name} · {subject_display}</div>
                    <div class="classio-assigned-program-progress">
                        <span class="classio-assigned-pill">{completed_topics}/{total_topics} topics done</span>
                        <span class="classio-assigned-pill">{progress_pct}% complete</span>
                        <span class="classio-assigned-pill">{'Target: ' + _html.escape(target_completion_on[:10]) if target_completion_on else 'Start from lesson 1'}</span>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            if start_on or teacher_note:
                meta_parts = []
                if start_on:
                    meta_parts.append(f"{t('day')}: {start_on[:10]}")
                if teacher_note:
                    meta_parts.append(f"{t('teacher_note')}: {teacher_note}")
                st.caption(" · ".join(meta_parts))

            render_student_program_view(program, assignment_id=int(item.get("id") or 0), interactive=True)
            if idx < len(program_assignments) - 1:
                st.markdown("<div style='height:.6rem;'></div>", unsafe_allow_html=True)

    if legacy_topics:
        st.markdown(f"<div class='classio-assigned-program-head'>{t('legacy_topic_tasks')}</div>", unsafe_allow_html=True)
        _render_assignment_group(t("assigned_topics"), legacy_topics, "student_assignments_topic_legacy")


def _student_smart_plan_state() -> dict:
    uid = str(get_current_user_id() or "").strip() or "anon"
    return dict(st.session_state.get(f"student_smart_plan_data_{uid}", {}) or {})


def _render_program_assigned_topics(program_assignments: list[dict]) -> bool:
    if not program_assignments:
        return False

    smart_state = _student_smart_plan_state()
    tasks = list(smart_state.get("tasks") or [])
    if tasks and smart_state.get("program_anchor_signature"):
        st.caption(t("smart_plan_program_anchor_setup_hint"))
        for idx, task in enumerate(tasks, 1):
            title = _html.escape(str(task.get("title") or "—"))
            subtitle = _html.escape(str(task.get("subtitle") or ""))
            category = _html.escape(str(t(f"smart_plan_category_{task.get('category')}")))
            minutes = int(task.get("minutes") or 0)
            done = bool(task.get("done"))
            st.markdown(
                f"""
                <div class="classio-assign-card">
                    <div style="display:flex;justify-content:space-between;gap:12px;align-items:flex-start;flex-wrap:wrap;">
                        <div>
                            <div class="classio-assign-title">{title}</div>
                            <div class="classio-assign-meta">{subtitle}</div>
                        </div>
                        <div>{_status_badge('completed' if done else 'assigned')}</div>
                    </div>
                    <div class="classio-assign-meta" style="margin-top:.8rem;">{category} · {minutes} min</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
        return True

    first_program = program_assignments[0]
    program = first_program.get("program") or {}
    progress_map = first_program.get("progress_map") or {}
    next_topics: list[dict] = []
    global_number = 0
    for unit in program.get("units") or []:
        for topic in unit.get("topics") or []:
            global_number += 1
            topic_id = int(topic.get("topic_id") or 0)
            if bool(progress_map.get(topic_id, {}).get("is_done")):
                continue
            next_topics.append(
                {
                    "global_number": global_number,
                    "unit_number": int(unit.get("unit_number") or 0),
                    "title": str(topic.get("title") or "").strip(),
                    "summary": str(topic.get("student_summary") or topic.get("lesson_focus") or topic.get("subtopic") or "").strip(),
                }
            )
            if len(next_topics) >= 5:
                break
        if len(next_topics) >= 5:
            break

    if not next_topics:
        st.info(t("smart_plan_program_anchor_all_done"))
        return True

    st.caption(t("smart_plan_program_anchor_setup_hint"))
    for item in next_topics:
        title = t("smart_plan_program_task_title", number=item["global_number"], title=item["title"] or "—")
        subtitle = t("smart_plan_program_task_subtitle", unit=item["unit_number"] or 1, summary=item["summary"] or t("smart_plan_program_anchor_default_summary"))
        st.markdown(
            f"""
            <div class="classio-assign-card">
                <div class="classio-assign-title">{_html.escape(title)}</div>
                <div class="classio-assign-meta" style="margin-top:.6rem;">{_html.escape(subtitle)}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    return True


def render_student_assignments() -> None:
    _inject_assignment_page_styles()
    st.markdown(f"## 🗂️ {t('student_assignments_title')}")
    st.caption(t("student_assignments_desc"))

    _render_teacher_relationships()

    assignments = load_student_assignments()
    program_assignments = load_enriched_program_assignments_for_current_student()
    if not assignments and not program_assignments and not has_active_teacher_relationships():
        st.info(t("no_assignments_or_teachers"))
        return

    worksheets = [row for row in assignments if row.get("assignment_type") == "worksheet"]
    exams = [row for row in assignments if row.get("assignment_type") == "exam"]
    topics = [row for row in assignments if row.get("assignment_type") == "lesson_plan_topic"]

    tab_ws, tab_exams, tab_topics = st.tabs(
        [
            f"📋 {t('worksheet_assignments')}",
            f"📝 {t('exam_assignments')}",
            f"🧠 {t('assigned_topics')}",
        ]
    )

    with tab_ws:
        _render_assignment_group(t("worksheet_assignments"), worksheets, "student_assignments_ws")
    with tab_exams:
        _render_assignment_group(t("exam_assignments"), exams, "student_assignments_exam")
    with tab_topics:
        if not _render_program_assigned_topics(program_assignments):
            _render_assignment_group(t("assigned_topics"), topics, "student_assignments_topics")
