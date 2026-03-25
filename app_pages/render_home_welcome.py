import streamlit as st
from core.i18n import t
from core.navigation import go_to, home_go
from core.database import load_students
from helpers.planner_storage import load_my_lesson_plans
from helpers.worksheet_storage import load_my_worksheets


def _safe_count(obj) -> int:
    try:
        return 0 if obj is None else len(obj)
    except Exception:
        return 0


def get_welcome_progress() -> dict:
    students_df = load_students()
    plans_df = load_my_lesson_plans()
    worksheets_df = load_my_worksheets()

    students_count = _safe_count(students_df)
    lesson_plans_count = _safe_count(plans_df)
    worksheets_count = _safe_count(worksheets_df)

    all_empty = (
        students_count == 0
        and lesson_plans_count == 0
        and worksheets_count == 0
    )

    all_done = (
        students_count > 0
        and lesson_plans_count > 0
        and worksheets_count > 0
    )

    incomplete = not all_done

    return {
        "students_count": students_count,
        "lesson_plans_count": lesson_plans_count,
        "worksheets_count": worksheets_count,
        "all_empty": all_empty,
        "all_done": all_done,
        "incomplete": incomplete,
        "students_done": students_count > 0,
        "lesson_plans_done": lesson_plans_count > 0,
        "worksheets_done": worksheets_count > 0,
    }


def should_show_welcome() -> tuple[bool, bool, dict]:
    """
    Returns:
      show_welcome, allow_skip, progress
    """
    progress = get_welcome_progress()

    if progress["all_done"]:
        return False, False, progress

    if progress["all_empty"]:
        return True, False, progress

    if st.session_state.get("home_welcome_skipped", False):
        return False, True, progress

    return True, True, progress


def render_home_welcome(user_name: str) -> bool:
    """
    Returns True if the welcome screen was rendered and Home should stop.
    Returns False if normal Home should continue.
    """
    show_welcome, allow_skip, progress = should_show_welcome()

    if not show_welcome:
        return False

    st.markdown(
        f"""
        <div class="home-section-line">
          <span>{t("welcome")}</span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown(
        f"""
        <div style="
            background: linear-gradient(180deg, var(--panel, rgba(255,255,255,0.92)), var(--panel-2, rgba(248,250,255,0.85)));
            border: 1px solid var(--border-strong, rgba(17,24,39,0.08));
            border-radius: 20px;
            padding: 24px 20px;
            box-shadow: 0 8px 26px rgba(59,130,246,0.18);
            margin-bottom: 18px;
        ">
            <div style="font-size: 1.6rem; font-weight: 800; margin-bottom: 8px; color: var(--text, #0f172a);">
                {t("welcome_home_title").format(name=user_name)}
            </div>
            <div style="font-size: 1rem; color: var(--muted, #64748b); margin-bottom: 16px;">
                {t("welcome_home_subtitle")}
            </div>
            <div style="font-size: 0.95rem; font-weight: 700; color: var(--text, #0f172a); margin-bottom: 12px;">
                {t("choose_where_to_go")}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    done_student = "✅" if progress["students_done"] else "⬜"
    done_plan = "✅" if progress["lesson_plans_done"] else "⬜"
    done_ws = "✅" if progress["worksheets_done"] else "⬜"

    st.markdown(
        f"""
        <div style="
            background: var(--panel-soft, rgba(255,255,255,0.55));
            border: 1px solid var(--border, rgba(148,163,184,0.22));
            border-radius: 16px;
            padding: 16px 18px;
            margin-bottom: 14px;
        ">
            <div style="font-weight: 700; margin-bottom: 10px; color: var(--text, #0f172a);">
                {t("getting_started")}
            </div>
            <div style="display:grid; gap:8px; color: var(--text, #0f172a);">
                <div>{done_student} {t("students")}</div>
                <div>{done_plan} {t("create_lesson_plan_cta")}</div>
                <div>{done_ws} {t("create_worksheet_cta")}</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    c1, c2 = st.columns(2)
    with c1:
        if st.button(t("add_student"), key="welcome_add_student", use_container_width=True):
            go_to("students")
            st.rerun()
    with c2:
        if st.button(t("create_lesson_plan_cta"), key="welcome_create_plan", use_container_width=True):
            go_to("add_lesson")
            st.rerun()

    c3, c4 = st.columns(2)
    with c3:
        if st.button(t("create_worksheet_cta"), key="welcome_create_ws", use_container_width=True):
            home_go("home", panel="ai_tools")
            st.session_state["welcome_focus_tool"] = "worksheet"
            st.rerun()
    with c4:
        if st.button(t("set_income_goal"), key="welcome_goal", use_container_width=True):
            home_go("home", panel="ai_tools")
            st.session_state["welcome_focus_tool"] = "goal"
            st.rerun()

    st.caption(t("welcome_slogan"))

    if allow_skip:
        if st.button(t("skip"), key="welcome_skip_btn"):
            st.session_state["home_welcome_skipped"] = True
            st.rerun()

    return True