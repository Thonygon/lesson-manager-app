# ============================================================
# CLASSIO — Streamlit App Entrypoint
# ============================================================
import streamlit as st

st.set_page_config(
    page_title="Classio",
    page_icon="🍎",
    layout="wide",
    initial_sidebar_state="collapsed",
)

from styles.theme import remove_streamlit_top_spacing
from helpers.ui_components import inject_pwa_head
from core.navigation import PAGE_KEYS, _set_query, init_navigation_defaults
from auth.auth import require_login

# ── Chrome cleanup ──
remove_streamlit_top_spacing()

# ── Session-state defaults ──
if "ui_lang" not in st.session_state:
    st.session_state.ui_lang = "en"
if "compact_mode" not in st.session_state:
    st.session_state.compact_mode = False
if "show_profile_dialog" not in st.session_state:
    st.session_state["show_profile_dialog"] = False
if "home_action_menu_nonce" not in st.session_state:
    st.session_state["home_action_menu_nonce"] = 0

init_navigation_defaults()

# ── PWA ──
inject_pwa_head()

# ── Auth gate ──
require_login()

# ── Route ──
from pages.router import route_pages

page = st.session_state.get("page", "home")
if page not in PAGE_KEYS:
    page = "home"
    st.session_state["page"] = "home"
    _set_query(page="home", lang=st.session_state.get("ui_lang", "en"))

route_pages(page)
