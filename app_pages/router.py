import streamlit as st
from streamlit_option_menu import option_menu

from core.i18n import t
from core.navigation import go_to, PAGE_KEYS, _set_query
from core.state import get_current_user_role, get_current_user_id
from core.database import upsert_profile_row
from auth.auth import sign_out_user


def render_top_nav(active_page: str):
    current_lang = st.session_state.get("ui_lang", "en")
    if current_lang not in ("en", "es", "tr"):
        current_lang = "en"

    items = [
        ("home",        t("home"),      "house"),
        ("dashboard",   t("dashboard"), "bar-chart"),
        ("students",    t("students"),  "people"),
        ("add_lesson",  t("lesson"),    "calendar-event"),
        ("add_payment", t("payment"),   "credit-card"),
        ("calendar",    t("calendar"),  "calendar3"),
        ("analytics",   t("analytics"), "graph-up"),
        ("switch_student", t("switch_to_student"), "arrow-repeat"),
        ("sign_out",    t("sign_out"),  "box-arrow-right"),
    ]

    keys   = [k for k, _, _ in items]
    labels = [label for _, label, _ in items]
    icons  = [icon for _, _, icon in items]

    try:
        default_index = keys.index(active_page)
    except ValueError:
        default_index = 0

    st.markdown(
        """
        <style>
        @media (max-width: 768px){
          .block-container{
            padding-left: 0.85rem !important;
            padding-right: 0.85rem !important;
          }
          .home-topbar{ padding: 8px 10px; }
          .home-hero{ padding: 18px 14px; }
          .home-menu-wrap{ padding: 12px; }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    selected_label = option_menu(
        menu_title=None,
        options=labels,
        icons=icons,
        orientation="horizontal",
        default_index=default_index,
        key="top_nav_option_menu",
        styles={
            "container": {
                "padding": "0 !important",
                "margin": "0 0 1rem 0 !important",
                "background": "var(--panel)",
                "border": "1px solid var(--border)",
                "border-radius": "14px",
                "overflow-x": "auto",
                "white-space": "nowrap",
            },
            "nav-link": {
                "font-size": "14px",
                "text-align": "center",
                "padding": "6px 8px",
                "color": "var(--muted)",
                "--hover-color": "var(--panel-soft)",
            },
            "nav-link-selected": {
                "background": "var(--primary)",
                "color": "#f1f5f9",
            },
            "icon": {
                "font-size": "16px",
                "color": "var(--primary-light)",
            },
        },
    )

    selected_key = active_page
    for key, label, _ in items:
        if label == selected_label:
            selected_key = key
            break

    previous_key = st.session_state.get("top_nav_prev", active_page)

    if selected_key != previous_key:
        st.session_state["top_nav_prev"] = selected_key
        if selected_key == "sign_out":
            sign_out_user()
        elif selected_key == "switch_student":
            st.session_state["top_nav_prev"] = active_page
            _switch_role("student")
        elif selected_key != active_page:
            go_to(selected_key)
            st.rerun()


def render_student_top_nav(active_page: str):
    current_lang = st.session_state.get("ui_lang", "en")
    if current_lang not in ("en", "es", "tr"):
        current_lang = "en"

    items = [
        ("student_home",         t("student_home_title"), "house"),
        ("student_practice",     t("smart_practice"),     "lightbulb"),
        ("student_study_plan",   t("smart_study_plan"),   "book"),
        ("student_find_teacher", t("find_my_teacher"),    "search"),
        ("profile",              t("profile"),            "person-circle"),
        ("switch_teacher",       t("switch_to_teacher"),  "arrow-repeat"),
        ("sign_out",             t("sign_out"),           "box-arrow-right"),
    ]

    keys   = [k for k, _, _ in items]
    labels = [label for _, label, _ in items]
    icons  = [icon for _, _, icon in items]

    try:
        default_index = keys.index(active_page)
    except ValueError:
        default_index = 0

    selected_label = option_menu(
        menu_title=None,
        options=labels,
        icons=icons,
        orientation="horizontal",
        default_index=default_index,
        key="student_top_nav_option_menu",
        styles={
            "container": {
                "padding": "0 !important",
                "margin": "0 0 1rem 0 !important",
                "background": "var(--panel)",
                "border": "1px solid var(--border)",
                "border-radius": "14px",
            },
            "nav-link": {
                "font-size": "14px",
                "text-align": "center",
                "padding": "6px 8px",
                "color": "var(--muted)",
                "--hover-color": "var(--panel-soft)",
            },
            "nav-link-selected": {
                "background": "var(--primary)",
                "color": "#f1f5f9",
            },
            "icon": {
                "font-size": "16px",
                "color": "var(--primary-light)",
            },
        },
    )

    selected_key = active_page
    for key, label, _ in items:
        if label == selected_label:
            selected_key = key
            break

    previous_key = st.session_state.get("student_top_nav_prev", active_page)

    if selected_key != previous_key:
        st.session_state["student_top_nav_prev"] = selected_key
        if selected_key == "sign_out":
            sign_out_user()
        elif selected_key == "profile":
            st.session_state["show_profile_dialog"] = True
        elif selected_key == "switch_teacher":
            st.session_state["student_top_nav_prev"] = active_page
            _switch_role("teacher")
        elif selected_key != active_page:
            go_to(selected_key)
            st.rerun()


def _switch_role(target_role: str):
    """Switch the user's active role and navigate to the appropriate home."""
    uid = get_current_user_id()
    if uid:
        upsert_profile_row(uid, {"role": target_role})
    st.session_state["user_role"] = target_role
    if target_role == "student":
        st.session_state["page"] = "student_home"
        _set_query(page="student_home", lang=st.session_state.get("ui_lang", "en"))
    else:
        st.session_state["page"] = "home"
        _set_query(page="home", lang=st.session_state.get("ui_lang", "en"))
    st.rerun()


def route_app_pages(page: str):
    role = get_current_user_role()

    # Student role routing
    if role == "student" or page.startswith("student_"):
        _route_student_pages(page)
        return

    from app_pages.home import render_home
    from app_pages.app_page_dashboard import render_dashboard
    from app_pages.app_page_students import render_students
    from app_pages.app_page_add_lesson import render_add_lesson
    from app_pages.app_page_add_payment import render_add_payment
    from app_pages.app_page_calendar import render_calendar
    from app_pages.app_page_analytics import render_analytics
    from styles.theme import load_css_home, load_css_app

    if page == "home":
        load_css_home()
        render_home()
        st.stop()

    load_css_app(compact=bool(st.session_state.get("compact_mode", False)))
    render_top_nav(page)

    if page == "dashboard":
        render_dashboard()
    elif page == "students":
        render_students()
    elif page == "add_lesson":
        render_add_lesson()
    elif page == "add_payment":
        render_add_payment()
    elif page == "calendar":
        render_calendar()
    elif page == "analytics":
        render_analytics()
    else:
        go_to("home")
        st.rerun()


def _route_student_pages(page: str):
    from app_pages.student_home import render_student_home
    from app_pages.student_practice import render_student_practice
    from app_pages.student_study_plan import render_student_study_plan
    from app_pages.student_find_teacher import render_student_find_teacher
    from styles.theme import load_css_app

    if page in ("home", "student_home"):
        page = "student_home"

    load_css_app(compact=bool(st.session_state.get("compact_mode", False)))
    render_student_top_nav(page)

    # Profile dialog for student pages
    if st.session_state.get("show_profile_dialog"):
        st.session_state["show_profile_dialog"] = False
        from auth.auth import render_profile_dialog
        uid = get_current_user_id()
        if uid:
            render_profile_dialog(uid)

    if page == "student_home":
        render_student_home()
    elif page == "student_practice":
        render_student_practice()
    elif page == "student_study_plan":
        render_student_study_plan()
    elif page == "student_find_teacher":
        render_student_find_teacher()
    else:
        go_to("student_home")
        st.rerun()