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
if "ui_theme" not in st.session_state:
    st.session_state.ui_theme = "light"
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

# ── Post-login redirect (runs once per session, set by apply_auth_session) ──
_post_login_action = st.session_state.pop("_post_login_action", None)
if _post_login_action:
    from core.database import get_current_user_id as _gcuid
    if _post_login_action == "profile_dialog":
        st.session_state["show_profile_dialog"] = True
        st.session_state["page"] = "home"
    elif _post_login_action == "dashboard":
        st.session_state["page"] = "dashboard"
        _set_query(page="dashboard", lang=st.session_state.get("ui_lang", "en"))
    elif _post_login_action.startswith("page:"):
        _target = _post_login_action[5:]
        if _target in PAGE_KEYS:
            st.session_state["page"] = _target
            _set_query(page=_target, lang=st.session_state.get("ui_lang", "en"))

# ── Persist last_page so next login can restore it ──
_current_page_for_last = st.session_state.get("page", "home")
if _current_page_for_last not in ("home",) and st.session_state.get("user_id"):
    if st.session_state.get(f"_last_page_saved_{_current_page_for_last}") != _current_page_for_last:
        try:
            from core.database import get_sb as _get_sb
            _get_sb().table("profiles").update(
                {"last_page": _current_page_for_last}
            ).eq("user_id", str(st.session_state["user_id"])).execute()
            st.session_state[f"_last_page_saved_{_current_page_for_last}"] = _current_page_for_last
        except Exception:
            pass

# ── Route ──
from pages.router import route_pages

page = st.session_state.get("page", "home")
if page not in PAGE_KEYS:
    page = "home"
    st.session_state["page"] = "home"
    _set_query(page="home", lang=st.session_state.get("ui_lang", "en"))

route_pages(page)
