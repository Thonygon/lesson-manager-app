import logging

import streamlit as st
from streamlit_option_menu import option_menu
from typing import Callable

from core.i18n import t
from core.navigation import go_to, PAGE_KEYS, _set_query
from core.state import get_current_user_role, get_current_user_id
from core.database import enable_profile_mode
from auth.auth import render_profile_dialog, sign_out_user
from helpers.ui_components import trigger_book_rain
from services.auth_service import current_user_is_admin

logger = logging.getLogger(__name__)


def _inject_scrollable_top_nav_styles() -> None:
    st.markdown(
        """
        <style>
        .classio-top-nav-scroll-anchor,
        .classio-student-top-nav-scroll-anchor,
        .classio-admin-top-nav-scroll-anchor {
            display: none;
        }
        div[data-testid="stVerticalBlock"]:has(.classio-top-nav-scroll-anchor) ul,
        div[data-testid="stVerticalBlock"]:has(.classio-student-top-nav-scroll-anchor) ul,
        div[data-testid="stVerticalBlock"]:has(.classio-admin-top-nav-scroll-anchor) ul {
            display: flex !important;
            flex-wrap: nowrap !important;
            overflow-x: auto !important;
            overflow-y: hidden !important;
            scrollbar-width: thin;
            -webkit-overflow-scrolling: touch;
            gap: 0.2rem;
        }
        div[data-testid="stVerticalBlock"]:has(.classio-top-nav-scroll-anchor) ul::-webkit-scrollbar,
        div[data-testid="stVerticalBlock"]:has(.classio-student-top-nav-scroll-anchor) ul::-webkit-scrollbar,
        div[data-testid="stVerticalBlock"]:has(.classio-admin-top-nav-scroll-anchor) ul::-webkit-scrollbar {
            height: 6px;
        }
        div[data-testid="stVerticalBlock"]:has(.classio-top-nav-scroll-anchor) li,
        div[data-testid="stVerticalBlock"]:has(.classio-student-top-nav-scroll-anchor) li,
        div[data-testid="stVerticalBlock"]:has(.classio-admin-top-nav-scroll-anchor) li {
            flex: 0 0 auto !important;
            width: auto !important;
        }
        div[data-testid="stVerticalBlock"]:has(.classio-top-nav-scroll-anchor) a,
        div[data-testid="stVerticalBlock"]:has(.classio-student-top-nav-scroll-anchor) a,
        div[data-testid="stVerticalBlock"]:has(.classio-admin-top-nav-scroll-anchor) a {
            white-space: nowrap !important;
            min-width: max-content !important;
        }
        @media (max-width: 768px) {
            div[data-testid="stVerticalBlock"]:has(.classio-top-nav-scroll-anchor) a,
            div[data-testid="stVerticalBlock"]:has(.classio-student-top-nav-scroll-anchor) a,
            div[data-testid="stVerticalBlock"]:has(.classio-admin-top-nav-scroll-anchor) a {
                padding: 8px 10px !important;
                font-size: 13px !important;
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _render_profile_dialog_if_requested() -> None:
    if not st.session_state.get("show_profile_dialog"):
        return
    st.session_state["show_profile_dialog"] = False
    uid = get_current_user_id()
    if uid:
        render_profile_dialog(uid)


def _render_global_page_divider() -> None:
    st.markdown(
        """
        <div class="home-section-line">
          <span>🤖</span>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _page_loading_label(page_key: str) -> str:
    label_keys = {
        "home": "home",
        "resources": "files",
        "community": "community",
        "dashboard": "dashboard",
        "students": "students",
        "add_lesson": "lessons",
        "add_payment": "payment",
        "calendar": "calendar",
        "smart_tools": "ai_tools",
        "analytics": "analytics",
        "pricing": "pricing",
        "account": "account",
        "admin": "admin",
        "student_home": "student_home_title",
        "student_practice": "smart_practice",
        "student_study_plan": "smart_study_plan",
        "student_assignments": "student_assignments_title",
        "student_find_teacher": "find_my_teacher",
    }
    label_key = label_keys.get(page_key, page_key)
    label = t(label_key)
    return label if label != label_key else page_key.replace("_", " ").title()


def _page_render_error_copy() -> tuple[str, str, str]:
    lang = str(st.session_state.get("ui_lang") or "en").strip().lower()
    if lang == "es":
        return (
            "No pudimos abrir esta sección ahora.",
            "Inténtalo de nuevo en un momento. Si el problema continúa, vuelve al inicio y entra otra vez.",
            "Reintentar",
        )
    if lang == "tr":
        return (
            "Bu bolumu simdi acamadik.",
            "Lutfen biraz sonra tekrar deneyin. Sorun devam ederse ana sayfaya donup yeniden girin.",
            "Tekrar dene",
        )
    return (
        "We couldn't open this section right now.",
        "Please try again in a moment. If the issue continues, return to the home page and open it again.",
        "Try again",
    )


def _render_page_error_fallback(page_key: str) -> None:
    title, body, retry_label = _page_render_error_copy()
    st.error(title)
    st.caption(body)
    if st.button(retry_label, key=f"{page_key}_render_retry", use_container_width=False):
        st.rerun()


def _render_page_with_loading(page_key: str, render_fn: Callable[[], None]) -> None:
    label = _page_loading_label(page_key)
    loading_slot = st.empty()
    progress = loading_slot.progress(0.12, text=t("section_loading_start", section=label))
    progress.progress(0.42, text=t("section_loading_data", section=label))
    try:
        render_fn()
        progress.progress(1.0, text=t("section_loading_ready", section=label))
    except Exception:
        logger.exception(
            "Page render failed",
            extra={
                "page_key": page_key,
                "role": str(get_current_user_role() or ""),
                "user_id": str(get_current_user_id() or ""),
            },
        )
        _render_page_error_fallback(page_key)
    finally:
        loading_slot.empty()


def render_top_nav(active_page: str):
    _inject_scrollable_top_nav_styles()
    current_lang = st.session_state.get("ui_lang", "en")
    if current_lang not in ("en", "es", "tr"):
        current_lang = "en"
    primary_items = [
        ("dashboard",   t("dashboard"), "bar-chart"),
        ("students",    t("students"),  "people"),
        ("add_lesson",  t("lessons"),   "calendar-event"),
        ("add_payment", t("payment"),   "credit-card"),
        ("calendar",    t("calendar"),  "calendar3"),
        ("smart_tools", t("ai_tools"),  "robot"),
        ("resources",   t("files"),     "folder2-open"),
    ]
    more_items = [
        ("home",      t("home"),      "house"),
        ("community", t("community"), "globe"),
        ("profile",   t("profile"),   "person-circle"),
        ("analytics", t("analytics"), "graph-up"),
    ]
    if current_user_is_admin():
        more_items.append(("pricing", t("pricing"), "gem"))
        more_items.append(("account", t("account"), "person-badge"))
        more_items.append(("admin", t("admin"), "shield-lock"))
    more_items.append(("sign_out", t("sign_out"), "box-arrow-right"))

    keys   = [k for k, _, _ in primary_items]
    labels = [label for _, label, _ in primary_items]
    icons  = [icon for _, _, icon in primary_items]

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
                .teacher-more-floating-anchor{display:none;}
                div[data-testid="stVerticalBlockBorderWrapper"]:has(.teacher-more-floating-anchor){
                    position:fixed;
                    top:78px;
                    right:0.95rem;
                    width:min(280px, 92vw);
                    margin:0;
                    padding:12px;
                    border-radius:20px;
                    border:1px solid color-mix(in srgb, var(--border) 72%, var(--primary) 28%);
                    background:linear-gradient(180deg, color-mix(in srgb, var(--panel) 97%, white 3%), color-mix(in srgb, var(--panel-soft) 94%, var(--primary) 6%));
                    box-shadow:0 20px 44px rgba(15,23,42,.14);
                    backdrop-filter:blur(18px);
                    z-index:50;
                }
                div[data-testid="stVerticalBlockBorderWrapper"]:has(.teacher-more-floating-anchor) button[kind="secondary"]{
                    justify-content:flex-start;
                    border-radius:16px;
                    border:1px solid color-mix(in srgb, var(--border) 78%, transparent);
                    background:linear-gradient(180deg, rgba(255,255,255,.86), rgba(255,255,255,.64));
                    box-shadow:0 10px 22px rgba(15,23,42,.06);
                    font-weight:700;
                }
                div[data-testid="stVerticalBlockBorderWrapper"]:has(.teacher-more-floating-anchor) button[kind="secondary"]:hover{
                    border-color:color-mix(in srgb, var(--primary) 26%, var(--border));
                    background:linear-gradient(180deg, rgba(255,255,255,.96), rgba(255,255,255,.78));
                }
                @media (max-width: 768px){
                    div[data-testid="stVerticalBlockBorderWrapper"]:has(.teacher-more-floating-anchor){
                        top:72px;
                        right:0.75rem;
                        width:min(260px, calc(100vw - 1.5rem));
                    }
                }
        </style>
        """,
        unsafe_allow_html=True,
    )

    nav_col, more_col = st.columns([12, 1.75], vertical_alignment="center")
    with nav_col:
        st.markdown("<div class='classio-top-nav-scroll-anchor'></div>", unsafe_allow_html=True)
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
    with more_col:
        if "top_nav_more_open" not in st.session_state:
            st.session_state["top_nav_more_open"] = False
        more_label = t("more") if t("more") != "more" else "More"
        more_active = active_page in {key for key, _, _ in more_items}
        if st.session_state.get("top_nav_more_open", False):
            if st.button(t("close"), key="top_nav_more_toggle_close", use_container_width=True):
                st.session_state["top_nav_more_open"] = False
                st.rerun()
        else:
            menu_label = f"⋯ {more_label}" + (" •" if more_active else "")
            if st.button(menu_label, key="top_nav_more_toggle_open", use_container_width=True):
                st.session_state["top_nav_more_open"] = True
                st.rerun()

    if st.session_state.get("top_nav_more_open", False):
        menu_box = st.container(border=True)
        with menu_box:
            st.markdown("<div class='teacher-more-floating-anchor'></div>", unsafe_allow_html=True)
            for idx, (key, label, _icon) in enumerate(more_items):
                if st.button(label, key=f"more_nav_{key}", use_container_width=True):
                    st.session_state["top_nav_more_open"] = False
                    if key == "sign_out":
                        sign_out_user()
                    elif key == "profile":
                        st.session_state["show_profile_dialog"] = True
                        st.rerun()
                    else:
                        go_to(key)
                        st.rerun()
                if idx == len(more_items) - 2:
                    st.markdown("---")

    selected_key = active_page
    for key, label, _ in primary_items:
        if label == selected_label:
            selected_key = key
            break

    previous_key = st.session_state.get("top_nav_prev", active_page)

    if selected_key != previous_key:
        st.session_state["top_nav_prev"] = selected_key
        if selected_key != active_page:
            st.session_state["top_nav_more_open"] = False
            go_to(selected_key)
            st.rerun()


def render_student_top_nav(active_page: str):
    _inject_scrollable_top_nav_styles()
    current_lang = st.session_state.get("ui_lang", "en")
    if current_lang not in ("en", "es", "tr"):
        current_lang = "en"
    if "student_assignments_book_nonce" not in st.session_state:
        st.session_state["student_assignments_book_nonce"] = 0

    items = [
        ("student_home",         t("student_home_title"), "house"),
        ("student_practice",     t("smart_practice"),     "lightbulb"),
        ("student_study_plan",   t("smart_study_plan"),   "book"),
        ("student_assignments",  t("student_assignments_title"), "journal-text"),
        ("student_find_teacher", t("find_my_teacher"),    "search"),
        ("profile",              t("profile"),            "person-circle"),
        ("switch_teacher",       t("switch_to_teacher"),  "arrow-repeat"),
        ("sign_out",             t("sign_out"),           "box-arrow-right"),
    ]
    if current_user_is_admin():
        items.insert(-1, ("switch_admin", t("admin"), "shield-lock"))

    keys   = [k for k, _, _ in items]
    labels = [label for _, label, _ in items]
    icons  = [icon for _, _, icon in items]

    try:
        default_index = keys.index(active_page)
    except ValueError:
        default_index = 0

    st.markdown("<div class='classio-student-top-nav-scroll-anchor'></div>", unsafe_allow_html=True)
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
                "overflow-x": "auto",
                "overflow-y": "hidden",
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

    if int(st.session_state.get("student_assignments_book_nonce", 0) or 0) > 0:
        trigger_book_rain(
            nonce=f"student-assignments-{st.session_state.get('student_assignments_book_nonce', 0)}",
            total_books=18,
            min_font_px=36,
            max_font_px=56,
            min_duration_s=2.8,
            max_duration_s=4.8,
        )

    if selected_key != previous_key:
        st.session_state["student_top_nav_prev"] = selected_key
        if selected_key == "sign_out":
            sign_out_user()
        elif selected_key == "profile":
            st.session_state["show_profile_dialog"] = True
        elif selected_key == "switch_teacher":
            st.session_state["student_top_nav_prev"] = active_page
            _switch_role("teacher")
        elif selected_key == "switch_admin":
            st.session_state["student_top_nav_prev"] = active_page
            _switch_role("admin")
        elif selected_key != active_page:
            if selected_key == "student_assignments":
                st.session_state["student_assignments_book_nonce"] = int(st.session_state.get("student_assignments_book_nonce", 0) or 0) + 1
            go_to(selected_key)
            st.rerun()


def render_admin_top_nav(active_page: str):
    _inject_scrollable_top_nav_styles()
    items = [
        ("admin", t("admin"), "shield-lock"),
        ("switch_teacher", t("switch_to_teacher"), "arrow-left-right"),
        ("switch_student", t("switch_to_student"), "arrow-left-right"),
        ("profile", t("profile"), "person-circle"),
        ("sign_out", t("sign_out"), "box-arrow-right"),
    ]

    keys = [k for k, _, _ in items]
    labels = [label for _, label, _ in items]
    icons = [icon for _, _, icon in items]

    try:
        default_index = keys.index(active_page)
    except ValueError:
        default_index = 0

    st.markdown("<div class='classio-admin-top-nav-scroll-anchor'></div>", unsafe_allow_html=True)
    selected_label = option_menu(
        menu_title=None,
        options=labels,
        icons=icons,
        orientation="horizontal",
        default_index=default_index,
        key="admin_top_nav_option_menu",
        styles={
            "container": {
                "padding": "0 !important",
                "margin": "0 0 1rem 0 !important",
                "background": "var(--panel)",
                "border": "1px solid var(--border)",
                "border-radius": "14px",
                "overflow-x": "auto",
                "overflow-y": "hidden",
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

    previous_key = st.session_state.get("admin_top_nav_prev", active_page)
    if selected_key != previous_key:
        st.session_state["admin_top_nav_prev"] = selected_key
        if selected_key == "sign_out":
            sign_out_user()
        elif selected_key == "profile":
            st.session_state["show_profile_dialog"] = True
        elif selected_key == "switch_teacher":
            _switch_role("teacher")
        elif selected_key == "switch_student":
            _switch_role("student")
        elif selected_key != active_page:
            go_to(selected_key)
            st.rerun()


def _switch_role(target_role: str):
    """Switch the user's active app mode without rewriting the saved profile role."""
    uid = get_current_user_id()
    if uid:
        enable_profile_mode(uid, target_role)
    st.session_state["user_role"] = target_role
    if target_role == "student":
        st.session_state["page"] = "student_home"
        _set_query(page="student_home", lang=st.session_state.get("ui_lang", "en"))
    elif target_role == "admin":
        st.session_state["page"] = "admin"
        _set_query(page="admin", lang=st.session_state.get("ui_lang", "en"))
    else:
        st.session_state["page"] = "home"
        _set_query(page="home", lang=st.session_state.get("ui_lang", "en"))
    st.rerun()


def route_app_pages(page: str):
    role = get_current_user_role()

    if role == "admin" or page == "admin":
        _route_admin_pages(page)
        return

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
    from app_pages.pricing import render_pricing
    from app_pages.account import render_account
    from app_pages.admin import render_admin
    from styles.theme import load_css_home, load_css_app

    if page == "home":
        load_css_home()
        _render_page_with_loading("home", render_home)
        _render_global_page_divider()
        st.stop()

    if page == "resources":
        load_css_home()
        render_top_nav("resources")
        _render_profile_dialog_if_requested()
        _render_page_with_loading(
            "resources",
            lambda: render_home(panel_override="files", show_home_actions=False),
        )
        _render_global_page_divider()
        st.stop()

    if page == "smart_tools":
        load_css_home()
        render_top_nav("smart_tools")
        _render_profile_dialog_if_requested()
        _render_page_with_loading(
            "smart_tools",
            lambda: render_home(panel_override="ai_tools", show_home_actions=False),
        )
        _render_global_page_divider()
        st.stop()

    if page == "community":
        load_css_home()
        render_top_nav("community")
        _render_profile_dialog_if_requested()
        _render_page_with_loading(
            "community",
            lambda: render_home(panel_override="community", show_home_actions=False),
        )
        _render_global_page_divider()
        st.stop()

    load_css_app(compact=bool(st.session_state.get("compact_mode", False)))
    render_top_nav(page)
    _render_profile_dialog_if_requested()

    if page == "dashboard":
        render_dashboard()
    elif page == "students":
        _render_page_with_loading("students", render_students)
    elif page == "add_lesson":
        _render_page_with_loading("add_lesson", render_add_lesson)
    elif page == "add_payment":
        _render_page_with_loading("add_payment", render_add_payment)
    elif page == "calendar":
        _render_page_with_loading("calendar", render_calendar)
    elif page == "smart_tools":
        load_css_home()
        _render_page_with_loading(
            "smart_tools",
            lambda: render_home(panel_override="ai_tools", show_home_actions=False),
        )
    elif page == "analytics":
        _render_page_with_loading("analytics", render_analytics)
    elif page == "pricing":
        _render_page_with_loading("pricing", render_pricing)
    elif page == "account":
        _render_page_with_loading("account", render_account)
    elif page == "admin":
        _render_page_with_loading("admin", render_admin)
    else:
        go_to("home")
        st.rerun()

    _render_global_page_divider()


def _route_student_pages(page: str):
    from app_pages.student_home import render_student_home
    from app_pages.student_practice import render_student_practice
    from app_pages.student_study_plan import render_student_study_plan
    from app_pages.student_assignments import render_student_assignments
    from app_pages.student_find_teacher import render_student_find_teacher
    from styles.theme import load_css_app

    if page in ("home", "student_home"):
        page = "student_home"

    load_css_app(compact=bool(st.session_state.get("compact_mode", False)))
    render_student_top_nav(page)

    _render_profile_dialog_if_requested()

    if page == "student_home":
        _render_page_with_loading("student_home", render_student_home)
    elif page == "student_practice":
        _render_page_with_loading("student_practice", render_student_practice)
    elif page == "student_study_plan":
        _render_page_with_loading("student_study_plan", render_student_study_plan)
    elif page == "student_assignments":
        _render_page_with_loading("student_assignments", render_student_assignments)
    elif page == "student_find_teacher":
        _render_page_with_loading("student_find_teacher", render_student_find_teacher)
    else:
        go_to("student_home")
        st.rerun()

    _render_global_page_divider()


def _route_admin_pages(page: str):
    from app_pages.admin import render_admin
    from styles.theme import load_css_app

    if page != "admin":
        page = "admin"

    load_css_app(compact=bool(st.session_state.get("compact_mode", False)))
    render_admin_top_nav(page)
    _render_profile_dialog_if_requested()
    _render_page_with_loading("admin", render_admin)
    _render_global_page_divider()
