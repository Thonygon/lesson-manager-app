import html as _html

import streamlit as st

from core.i18n import t
from core.navigation import go_to
from helpers.practice_engine import exam_to_exercises, worksheet_to_exercises
from helpers.practice_engine import load_in_progress_practice_session
from helpers.teacher_student_integration import (
    group_assignments_by_teacher_subject,
    has_active_teacher_relationships,
    load_student_assignments,
    load_student_teacher_links,
    mark_assignment_started,
    update_topic_assignment_status,
)


def _open_assignment_practice(row: dict) -> None:
    assignment_id = row.get("id")
    snapshot = row.get("content_snapshot") or {}
    assignment_type = str(row.get("assignment_type") or "").strip()
    meta = {
        "subject": row.get("subject_key", ""),
        "topic": row.get("topic", ""),
        "learner_stage": (snapshot.get("meta") or {}).get("learner_stage", ""),
        "level": (snapshot.get("meta") or {}).get("level_or_band", ""),
    }

    exercise_data = {}
    if assignment_type == "worksheet":
        worksheet = snapshot.get("worksheet") or {}
        exercise_data = worksheet_to_exercises(worksheet, row_id=assignment_id)
    elif assignment_type == "exam":
        exam_data = dict(snapshot.get("exam_data") or {})
        exam_data.setdefault("subject", row.get("subject_key", ""))
        exam_data.setdefault("topic", row.get("topic", ""))
        exam_data.setdefault("learner_stage", (snapshot.get("meta") or {}).get("learner_stage", ""))
        answer_key = snapshot.get("answer_key") or {}
        exercise_data = exam_to_exercises(exam_data, answer_key, row_id=assignment_id)

    if not exercise_data.get("exercises"):
        st.warning(t("no_exercises_available"))
        return

    st.session_state["practice_exercise_data"] = exercise_data
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


def _assignment_card(row: dict, key_prefix: str) -> None:
    title = _html.escape(str(row.get("title") or "—"))
    status = str(row.get("status") or "").strip()
    due_at = str(row.get("due_at") or "").strip()
    created_at = str(row.get("created_at") or "").strip()
    teacher_note = str(row.get("teacher_note") or "").strip()
    assignment_type = str(row.get("assignment_type") or "").strip()
    teacher_name = _html.escape(str(row.get("teacher_name") or "—"))
    subject_name = _html.escape(str(row.get("subject_display") or "—"))

    meta_bits = [teacher_name, subject_name]
    if due_at:
        meta_bits.append(f"{_html.escape(_safe_ui_label('due_date', 'assignment_set_due_date'))}: {_html.escape(due_at[:10])}")
    elif created_at:
        meta_bits.append(f"{_html.escape(t('created_at_label'))}: {_html.escape(created_at[:10])}")

    left_col, right_col = st.columns([6, 2], gap="medium")
    with left_col:
        st.markdown(
            f"""
            <div class="classio-assign-card">
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
            action_text = (
                t("assignment_done")
                if is_finalized
                else (t("continue_practice") if is_continue else t("open_assignment"))
            )
            if is_finalized:
                st.markdown(
                    f"<div class='classio-assign-action-done'>{_html.escape(t('assignment_done'))}</div>",
                    unsafe_allow_html=True,
                )
            elif st.button(action_text, key=f"{key_prefix}_open", use_container_width=True, type="primary"):
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

    grouped = group_assignments_by_teacher_subject(rows)
    for teacher_name, subject_groups in grouped:
        st.markdown(f"<div class='classio-assign-teacher'>{_html.escape(teacher_name)}</div>", unsafe_allow_html=True)
        for subject_name, items in subject_groups:
            st.markdown(f"<div class='classio-assign-subject'>{_html.escape(subject_name)}</div>", unsafe_allow_html=True)
            for idx, row in enumerate(items):
                _assignment_card(row, f"{group_prefix}_{teacher_name}_{subject_name}_{idx}")


def render_student_assignments() -> None:
    _inject_assignment_page_styles()
    st.markdown(f"## 🗂️ {t('student_assignments_title')}")
    st.caption(t("student_assignments_desc"))

    _render_teacher_relationships()

    assignments = load_student_assignments()
    if not assignments and not has_active_teacher_relationships():
        st.info(t("no_assignments_or_teachers"))
        return

    worksheets = [row for row in assignments if row.get("assignment_type") == "worksheet"]
    exams = [row for row in assignments if row.get("assignment_type") == "exam"]
    topics = [row for row in assignments if row.get("assignment_type") == "lesson_plan_topic"]

    tab_ws, tab_exams, tab_topics = st.tabs(
        [
            f"📋 {t('worksheet_assignments')}",
            f"📝 {t('exam_assignments')}",
            f"🧭 {t('assigned_topics')}",
        ]
    )

    with tab_ws:
        _render_assignment_group(t("worksheet_assignments"), worksheets, "student_assignments_ws")
    with tab_exams:
        _render_assignment_group(t("exam_assignments"), exams, "student_assignments_exam")
    with tab_topics:
        _render_assignment_group(t("assigned_topics"), topics, "student_assignments_topic")
