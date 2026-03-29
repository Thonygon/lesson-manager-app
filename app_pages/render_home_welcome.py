import streamlit as st
from core.i18n import t
from core.navigation import go_to, home_go
from core.database import load_students
from core.state import get_current_user_id
from helpers.planner_storage import load_my_lesson_plans
from helpers.worksheet_storage import load_my_worksheets


def _safe_count(obj) -> int:
    try:
        return 0 if obj is None else len(obj)
    except Exception:
        return 0

def _welcome_skip_key() -> str:
    uid = str(get_current_user_id() or "").strip()
    return f"home_welcome_skipped::{uid}" if uid else "home_welcome_skipped::anon"


def _is_welcome_skipped() -> bool:
    return bool(st.session_state.get(_welcome_skip_key(), False))


def _set_welcome_skipped(value: bool) -> None:
    st.session_state[_welcome_skip_key()] = bool(value)


def _clear_welcome_skipped_for_current_user() -> None:
    st.session_state.pop(_welcome_skip_key(), None)

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

    if _is_welcome_skipped():
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
          <span>🤖 {t("greeting")}</span>
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
            <div style="font-size: 1rem; color: var(--muted, #64748b); margin-bottom: 16px; align-items: center; display: flex; gap: 12px;">
                {t("welcome_home_subtitle")}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown(
        f"""
        <div class="home-section-line">
          <span>{t("choose_where_to_go")}</span>
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
            go_to("analytics")
            st.session_state["welcome_focus_tool"] = "goal"
            st.rerun()

    st.markdown(
        f"""
        <div class="home-section-line">
          <span>{t("welcome_slogan")}</span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # ---------- Welcome Progress ----------
    total_steps = 3
    done_steps = sum([
        progress["students_done"],
        progress["lesson_plans_done"],
        progress["worksheets_done"],
    ])

    progress_percent = int((done_steps / total_steps) * 100)

    if progress_percent == 0:
        progress_text = t("welcome_progress_start")
    elif progress_percent < 100:
        progress_text = t("welcome_progress_almost")
    else:
        progress_text = t("welcome_progress_done")

    bottom_left, bottom_right = st.columns([6, 1], vertical_alignment="center")

    with bottom_left:
        st.markdown(
            f"""
            <div style="font-weight:700;margin-bottom:8px;color:var(--text);">
                🚀 {t("setup_progress")}
            </div>

            <div style="
                width:100%;
                background:var(--panel-2, rgba(148,163,184,0.15));
                border-radius:14px;
                overflow:hidden;
                height:14px;
                margin-bottom:8px;
                border:1px solid var(--border-strong, rgba(148,163,184,0.25));
            ">
                <div style="
                    width:{progress_percent}%;
                    height:14px;
                    background:linear-gradient(90deg,#22c55e,#3b82f6,#8b5cf6);
                    box-shadow:0 0 10px rgba(59,130,246,0.6),
                               0 0 18px rgba(139,92,246,0.4);
                    transition:width 0.4s ease;
                "></div>
            </div>

            <div style="
                font-size:0.85rem;
                color:var(--muted);
                font-weight:600;
            ">
                {progress_percent}% — {progress_text}
            </div>
            <div style="
                display:flex;
                gap:14px;
                font-size:0.85rem;
                color:var(--muted);
                padding:12px 0;
                justify-content:center;
                align-items:center; 
                flex-wrap:wrap;
                text-align:center;
            ">
                <span>{"✅" if progress["students_done"] else "👤"} {t("add_student_done")}</span>
                <span>{"✅" if progress["lesson_plans_done"] else "📚"} {t("create_lesson_plan_done")}</span>
                <span>{"✅" if progress["worksheets_done"] else "🧩"} {t("create_worksheet_done")}</span>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with bottom_right:
        if allow_skip:
            if st.button(t("skip"), key="welcome_skip_btn", use_container_width=True):
                _set_welcome_skipped(True)
                st.session_state["home_action_menu_prev"] = t("home")
                st.session_state["home_action_menu_nonce"] = st.session_state.get("home_action_menu_nonce", 0) + 1

                # clear transient welcome helpers
                st.session_state.pop("welcome_focus_tool", None)

                # force actual navigation to Home
                go_to("home")
                home_go("home", panel="home")

                st.rerun()

    st.markdown(
        """
        <div class="home-section-line"> 
          <span>🤖</span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    return True