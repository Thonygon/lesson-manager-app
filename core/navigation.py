import streamlit as st
from typing import Optional
from core.i18n import t
from core.timezone import _get_qp, detect_browser_timezone

PAGES = [
    ("dashboard", "dashboard", "📊"),
    ("students", "students", "👥"),
    ("add_lesson", "lesson", "🗓️"),
    ("add_payment", "payment", "💳"),
    ("calendar", "calendar", "📅"),
    ("analytics", "analytics", "📈"),
]

PAGE_KEYS = {"home"} | {key for key, _, _ in PAGES}


def _set_query(page: Optional[str] = None, lang: Optional[str] = None, panel: Optional[str] = None) -> None:
    new_page = page if page is not None else st.session_state.get("page", "home")
    new_lang = lang if lang is not None else st.session_state.get("ui_lang", "en")
    params = {"page": new_page, "lang": new_lang}
    if panel is not None:
        params["panel"] = panel
    try:
        st.query_params.clear()
        for k, v in params.items():
            st.query_params[k] = v
    except Exception:
        st.experimental_set_query_params(**params)


def go_to(page_name: str):
    if page_name not in PAGE_KEYS:
        page_name = "home"
    st.session_state["page"] = page_name
    _set_query(page=page_name, lang=st.session_state.get("ui_lang", "en"))


def home_go(page_name: str = "home", panel: Optional[str] = None):
    if page_name not in PAGE_KEYS:
        page_name = "home"
    st.session_state["page"] = page_name
    _set_query(page=page_name, lang=st.session_state.get("ui_lang", "en"), panel=panel)


def page_header(title: str):
    st.markdown(f"## {title}")


def init_navigation_defaults():
    """Initialize all navigation-related session state and sync from URL."""
    if "page" not in st.session_state:
        st.session_state["page"] = "home"
    if "ui_lang" not in st.session_state:
        st.session_state["ui_lang"] = "en"
    if "show_profile_dialog" not in st.session_state:
        st.session_state["show_profile_dialog"] = False
    if "home_action_menu_prev" not in st.session_state:
        st.session_state["home_action_menu_prev"] = t("profile")
    if "home_action_menu_nonce" not in st.session_state:
        st.session_state["home_action_menu_nonce"] = 0
    if "top_nav_prev" not in st.session_state:
        st.session_state["top_nav_prev"] = "home"

    # Sync from URL
    lang_qp = _get_qp("lang", None)
    if lang_qp in ("en", "es"):
        st.session_state["ui_lang"] = lang_qp

    qp_page = str(_get_qp("page", "home") or "home")
    if qp_page in PAGE_KEYS:
        st.session_state["page"] = qp_page
    else:
        st.session_state["page"] = "home"
        _set_query(page="home", lang=st.session_state["ui_lang"])

    detect_browser_timezone()
