import streamlit as st
import os
from core.i18n import t
from core.state import (
    get_current_user_id,
    get_current_user_role,
    _set_logged_in_user,
    _clear_logged_in_user,
    PROFILE_SUBJECT_OPTIONS,
    PROFILE_STAGE_OPTIONS,
    PROFILE_TEACH_LANG_OPTIONS,
    PROFILE_DURATION_OPTIONS,
    PROFILE_TIMEZONE_OPTIONS,
    PROFILE_COUNTRY_OPTIONS,
)
from helpers.lesson_planner import subject_label as _profile_subject_label
from core.timezone import DEFAULT_TZ_NAME
from core.navigation import _set_query
from core.database import (
    get_sb,
    load_profile_row,
    upsert_profile_row,
    is_username_taken,
    get_user_username,
    get_profile_by_email,
    apply_auth_session,
    get_profile_avatar_url,
    save_profile_avatar_url,
    resolve_active_mode,
)
from helpers.currency import CURRENCIES, CURRENCY_CODES


@st.cache_data(show_spinner=False)
def load_logo_bytes() -> bytes:
    logo_path = os.path.join("static", "logo_classio_light.png")
    with open(logo_path, "rb") as f:
        return f.read()


def _get_logged_in_email() -> str:
    if getattr(st.user, "is_logged_in", False):
        return str(getattr(st.user, "email", "") or "").strip().lower()
    return ""


def _ensure_profile_for_oidc_user() -> str:
    """
    Ensure a profile row exists for the currently logged-in OIDC user.
    Also ensures a matching row in auth.users (required by FK constraints).
    Returns user_id if a profile exists or is created, else "".
    """
    email = _get_logged_in_email()
    if not email:
        return ""

    existing = get_profile_by_email(email)
    if existing:
        return str(existing.get("user_id") or "").strip()

    try:
        import secrets
        sb = get_sb()

        # Create an auth.users entry so FK constraints on worksheets etc. are satisfied.
        # email_confirm=True auto-confirms (no email sent) — correct for Google OAuth.
        random_password = secrets.token_urlsafe(32)
        user_id = ""
        try:
            auth_resp = sb.auth.admin.create_user({
                "email": email,
                "password": random_password,
                "email_confirm": True,
            })
            user_id = str(auth_resp.user.id)
        except Exception:
            # User likely already exists in auth.users (e.g. from a previous attempt).
            # Search through paginated list_users to find them.
            user_id = _find_auth_user_by_email(sb, email)

        if not user_id:
            return ""

        display_name = str(getattr(st.user, "name", "") or "").strip()

        ok = upsert_profile_row(
            user_id,
            {
                "email": email,
                "display_name": display_name,
                "preferred_ui_language": st.session_state.get("ui_lang", "en"),
                "timezone": DEFAULT_TZ_NAME,
                "default_lesson_duration": 45,
                "role": "teacher",
                "primary_role": "teacher",
                "can_teach": True,
                "can_study": False,
                "last_active_mode": "teacher",
                "primary_subjects": [],
                "teaching_stages": [],
                "teaching_languages": [],
                "onboarding_completed": False,
                "login_count": 0,
                "active_student_count": 0,
                "account_status": "active",
            },
        )
        return user_id if ok else ""
    except Exception:
        return ""


def _find_auth_user_by_email(sb, email: str) -> str:
    """
    Search Supabase auth.users for a user by email, handling pagination.
    Returns the user's id as a string, or "" if not found.
    """
    try:
        page = 1
        per_page = 1000
        while True:
            users = sb.auth.admin.list_users(page=page, per_page=per_page)
            if not users:
                break
            for u in users:
                if getattr(u, "email", "") == email:
                    return str(u.id)
            if len(users) < per_page:
                break
            page += 1
    except Exception:
        pass
    return ""


def _restore_user_from_email() -> str:
    """
    Map Streamlit OIDC user -> your app user/profile row.
    Returns user_id if found, else "".
    """
    email = _get_logged_in_email()
    if not email:
        return ""

    try:
        row = get_profile_by_email(email)
        if not row:
            user_id = _ensure_profile_for_oidc_user()
            if not user_id:
                return ""
            row = get_profile_by_email(email)

        if not row:
            return ""

        user_id = str(row.get("user_id") or "").strip()
        if not user_id:
            return ""

        preferred_ui_language = str(
            row.get("preferred_ui_language") or st.session_state.get("ui_lang", "en")
        ).strip().lower()
        if preferred_ui_language not in ("en", "es", "tr"):
            preferred_ui_language = "en"
        st.session_state["ui_lang"] = preferred_ui_language

        # Sync Google display name to profile if missing
        google_name = str(getattr(st.user, "name", "") or "").strip()
        profile_name = str(row.get("display_name") or "").strip()
        if google_name and not profile_name:
            upsert_profile_row(user_id, {"display_name": google_name})
            profile_name = google_name

        oidc_user = {
            "email": email,
            "user_metadata": {
                "display_name": google_name or profile_name,
            },
        }

        _set_logged_in_user(
            oidc_user,
            profile_name=profile_name or google_name,
            profile_username=str(row.get("username") or "").strip(),
            user_id=user_id,
            user_role=resolve_active_mode(row),
        )

        return user_id
    except Exception:
        return ""

def render_google_auth_card(
    title_key,
    body_key=None,
    button_key=None,
    button_widget_key=None,
    show_signup_note=False
):

    google_svg = """
    <svg width="24" height="24" viewBox="0 0 48 48">
    <path fill="#EA4335" d="M24 9.5c3.3 0 6.3 1.1 8.6 3.3l6.4-6.4C34.9 2.6 29.8 0 24 0 14.7 0 6.7 5.4 2.7 13.3l7.9 6.1C12.7 13.2 17.9 9.5 24 9.5z"/>
    <path fill="#4285F4" d="M46.1 24.5c0-1.6-.1-3.2-.4-4.7H24v9h12.5c-.5 2.7-2.1 5-4.5 6.6l7 5.4c4.1-3.8 6.5-9.3 6.5-16.3z"/>
    <path fill="#FBBC05" d="M10.6 28.4c-.6-1.7-.9-3.5-.9-5.4s.3-3.7.9-5.4l-7.9-6.1C1 15.1 0 19.4 0 24s1 8.9 2.7 12.5l7.9-6.1z"/>
    <path fill="#34A853" d="M24 48c6.5 0 11.9-2.1 15.8-5.7l-7-5.4c-2 1.4-4.6 2.2-8.8 2.2-6.1 0-11.3-3.7-13.2-9l-7.9 6.1C6.7 42.6 14.7 48 24 48z"/>
    </svg>
    """

    body_html = ""
    if body_key:
        body_html = f'<div class="classio-auth-body">{t(body_key)}</div>'

    html = f"""
    <style>
    .classio-auth-card {{
        border-radius:18px;
        padding:18px;
        border:1px solid rgba(127,127,127,0.18);
    }}

    .classio-auth-head {{
        display:flex;
        align-items:center;
        gap:12px;
    }}

    .classio-auth-icon {{
        width:42px;
        height:42px;
    }}

    .classio-auth-title {{
        font-weight:700;
        font-size:1rem;
    }}

    .classio-auth-body {{
        margin-top:6px;
        opacity:0.85;
    }}
    </style>

    <div class="classio-auth-card">
        <div class="classio-auth-head">
            <div class="classio-auth-icon">{google_svg}</div>
            <div class="classio-auth-title">{t(title_key)}</div>
        </div>
        {body_html}
    </div>
    """

    st.markdown(html, unsafe_allow_html=True)

    st.button(
        t(button_key),
        on_click=st.login,
        use_container_width=True,
        key=button_widget_key,
    )

    if show_signup_note:
        st.caption(t("google_auth_signup_note"))

    st.markdown(
        """
        <div class="home-section-line"> 
          <span>🤖</span>
        </div>
        """,
        unsafe_allow_html=True,
    )

def require_login():
    """
    Blocks the app unless a user is logged in with Streamlit OIDC.
    """
    if getattr(st.user, "is_logged_in", False):
        user_id = _restore_user_from_email()
        if user_id:
            apply_auth_session()
            after_page = st.session_state.pop("_after_signup_page", None)
            if after_page:
                st.session_state["page"] = after_page
            return

    _theme_mode = st.session_state.get("ui_theme_mode", "auto")
    _dark_login = _theme_mode == "dark"
    from styles.theme import _root_vars, _dark_widget_css

    st.markdown(f"<style>{_root_vars()}</style>", unsafe_allow_html=True)
    _dw = _dark_widget_css()
    if _dw:
        st.markdown(f"<style>{_dw}</style>", unsafe_allow_html=True)

    logo_bytes = load_logo_bytes()

    st.markdown(
        """
        <style>
        .login-topbar { margin-bottom: 0px; }
        .login-logo-wrap {
            display: flex;
            justify-content: center;
            align-items: center;
            margin-top: 0 !important;
            margin-bottom: -18px !important;
            padding: 0 !important;
        }
        div[data-testid="stImage"] {
            margin-top: -40px !important;
            margin-bottom: -24px !important;
            padding: 0 !important;
            text-align: center;
        }
        div[data-testid="stImage"] img {
            display: block;
            margin: 0 auto !important;
            padding: 0 !important;
        }
        /* Remove extra space under tabs */
        [data-baseweb="tab-panel"] {
            padding-top: 0 !important;
            margin-top: 0 !important;
        }

        [data-baseweb="tab-list"] {
            margin-bottom: 0 !important;
        }

        [data-baseweb="tab-panel"] > div {
            padding-top: 0 !important;
            margin-top: 0 !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    col_logo_left, col_logo_center, col_logo_right = st.columns([1, 2, 1])
    with col_logo_center:
        st.markdown('<div class="login-logo-wrap">', unsafe_allow_html=True)
        st.image(logo_bytes, width=500)
        st.markdown("</div>", unsafe_allow_html=True)

    _from_explore = st.session_state.pop("_explore_go_signup", False)
    _lang_tab_label = "🌐"
    _theme_tab_label = "🌙" if not _dark_login else "☀️"

    if _from_explore:
        tab_signup, tab_login, tab_explore, tab_lang, tab_theme = st.tabs(
            [t("sign_up"), t("sign_in"), t("explore_tab"), _lang_tab_label, _theme_tab_label]
        )
    else:
        tab_explore, tab_login, tab_signup, tab_lang, tab_theme = st.tabs(
            [t("explore_tab"), t("sign_in"), t("sign_up"), _lang_tab_label, _theme_tab_label]
        )

    with tab_theme:
        _current_theme_mode = st.session_state.get("ui_theme_mode", "auto")
        st.markdown(f"#### 🎨 {t('theme')}")
        _theme_options = ["auto", "light", "dark"]
        _new_theme_mode = st.radio(
            t("select_theme"),
            _theme_options,
            index=_theme_options.index(_current_theme_mode) if _current_theme_mode in _theme_options else 0,
            format_func=lambda x: {
                "auto": f"🖥️ {t('theme_auto')}",
                "light": f"☀️ {t('theme_light')}",
                "dark": f"🌙 {t('theme_dark')}",
            }[x],
            key="login_theme_radio",
            horizontal=True,
        )
        if _new_theme_mode != _current_theme_mode:
            st.session_state["ui_theme_mode"] = _new_theme_mode
            st.rerun()

    with tab_lang:
        _cur = st.session_state.get("ui_lang", "en")
        _lang_options = {"en": "🇬🇧 English", "es": "🇪🇸 Español", "tr": "🇹🇷 Türkçe"}
        _selected = st.radio(
            t("language_ui"),
            list(_lang_options.keys()),
            index=list(_lang_options.keys()).index(_cur) if _cur in _lang_options else 0,
            format_func=lambda x: _lang_options[x],
            key="login_lang_radio",
            horizontal=True,
        )
        if _selected != _cur:
            st.session_state["ui_lang"] = _selected
            _set_query(lang=_selected)
            st.rerun()

    with tab_login:
        render_google_auth_card(
            title_key="google_signin_title",
            body_key="google_signin_body",
            button_key="continue_with_google",
            button_widget_key="btn_google_signin",
        )

    with tab_signup:
        render_google_auth_card(
            title_key="google_signup_title",
            body_key="account_managed_by_provider",
            button_key="create_account_google",
            button_widget_key="btn_google_signup",
            show_signup_note=True,
        )

    with tab_explore:
        from helpers.goal_explorer import render_goal_explorer
        wants_signup = render_goal_explorer()
        if wants_signup:
            st.session_state["_explore_go_signup"] = True
            st.rerun()

    st.stop()


def sign_out_user() -> None:
    uid = str(get_current_user_id() or "").strip()

    _clear_logged_in_user()
    st.session_state.pop("user_id", None)
    st.session_state.pop("user_email", None)
    st.session_state.pop("user_name", None)
    st.session_state.pop("user_username", None)
    st.session_state.pop("user_role", None)

    if uid:
        st.session_state.pop(f"home_welcome_skipped::{uid}", None)

    st.session_state.pop("_login_redirect_done", None)
    st.session_state.pop("_post_login_action", None)
    st.session_state.pop("_email_synced_to_profile", None)

    st.logout()


def render_logout_button():
    st.button(t("sign_out"), key="btn_logout", on_click=sign_out_user)




def _profile_stage_label(stage: str) -> str:
    mapping = {
        "early_primary": t("stage_early_primary"),
        "upper_primary": t("stage_upper_primary"),
        "lower_secondary": t("stage_lower_secondary"),
        "upper_secondary": t("stage_upper_secondary"),
        "adult_stage": t("stage_adult"),
    }
    return mapping.get(stage, stage)


def _profile_lang_label(lang_code: str) -> str:
    mapping = {
        "en": t("english"),
        "es": t("spanish"),
        "tr": t("turkish"),
    }
    return mapping.get(lang_code, lang_code)


def _profile_duration_label(minutes: int) -> str:
    mapping = {
        30: t("duration_30"),
        45: t("duration_45"),
        60: t("duration_60"),
        90: t("duration_90"),
    }
    return mapping.get(int(minutes), f"{minutes} min")


def render_profile_dialog(user_id: str) -> None:
    profile = load_profile_row(user_id)

    try:
        @st.dialog(t("edit_profile"))
        def _profile_dialog():
            st.markdown(f"### {t('edit_profile')}")

            current_avatar = str(profile.get("avatar_url") or st.session_state.get("avatar_url") or "").strip()
            if current_avatar:
                st.image(current_avatar, width=96)

            up = st.file_uploader(
                t("choose_photo"),
                type=["png", "jpg", "jpeg", "webp"],
                key="profile_avatar_uploader",
                label_visibility="collapsed",
            )

            _current_username = str(profile.get("username") or st.session_state.get("user_username") or "")
            st.text_input(
                t("user_name"),
                value=_current_username,
                disabled=True,
                key="profile_username_display",
                help=t("username_not_editable"),
            )

            display_name = st.text_input(
                t("full_name_label"),
                value=str(profile.get("display_name") or st.session_state.get("user_name") or ""),
                key="profile_display_name",
            )

            current_auth_email = str(
                st.session_state.get("user_email")
                or profile.get("email")
                or ""
            )
            st.text_input(
                t("current_email"),
                value=current_auth_email,
                disabled=True,
                key="profile_current_email_display",
            )

            p1, p2, p3 = st.columns(3)
            with p1:
                import datetime as _dt_mod
                _dob_raw = str(profile.get("date_of_birth") or "").strip()
                _dob_default = None
                if _dob_raw:
                    try:
                        _dob_default = _dt_mod.datetime.strptime(_dob_raw[:10], "%Y-%m-%d").date()
                    except Exception:
                        pass
                date_of_birth_val = st.date_input(
                    t("date_of_birth"),
                    value=_dob_default,
                    min_value=_dt_mod.date(1940, 1, 1),
                    max_value=_dt_mod.date.today(),
                    format="YYYY-MM-DD",
                    key="profile_dob",
                )
            with p2:
                _sex_options = ["", "Male", "Female", "Other", "Prefer not to say"]
                _sex_default_val = str(profile.get("sex") or "")
                _sex_default_idx = _sex_options.index(_sex_default_val) if _sex_default_val in _sex_options else 0
                sex_val = st.selectbox(
                    t("sex"),
                    _sex_options,
                    index=_sex_default_idx,
                    format_func=lambda x: t(f"sex_{x.lower().replace(' ', '_')}") if x else "—",
                    key="profile_sex",
                )
            with p3:
                import re as _re
                _raw_phone = st.text_input(
                    t("phone"),
                    value=_re.sub(r"[^\d+]", "", str(profile.get("phone_number") or "")),
                    placeholder="+1234567890",
                    key="profile_phone_number",
                    help=t("phone_format_hint"),
                )
                phone_number_val = _re.sub(r"[^\d+]", "", _raw_phone)

            c1, c2 = st.columns(2)

            with c1:
                _lang_options = ["en", "es", "tr"]
                _lang_labels = {"en": "english", "es": "spanish", "tr": "turkish"}
                _lang_flags = {"en": "🇬🇧 ", "es": "🇪🇸 ", "tr": "🇹🇷 "}
                _cur_lang = str(profile.get("preferred_ui_language") or st.session_state.get("ui_lang", "en"))
                preferred_ui_language = st.selectbox(
                    t("preferred_ui_language"),
                    _lang_options,
                    index=_lang_options.index(_cur_lang) if _cur_lang in _lang_options else 0,
                    format_func=lambda x: _lang_flags.get(x, "") + t(_lang_labels.get(x, "english")),
                    key="profile_preferred_ui_language",
                )

                timezone_value = str(profile.get("timezone") or DEFAULT_TZ_NAME)
                timezone_index = PROFILE_TIMEZONE_OPTIONS.index(timezone_value) if timezone_value in PROFILE_TIMEZONE_OPTIONS else 0
                timezone_name = st.selectbox(
                    t("timezone_label"),
                    PROFILE_TIMEZONE_OPTIONS,
                    index=timezone_index,
                    key="profile_timezone",
                )

                country_value = str(profile.get("country") or "")

                if country_value and country_value in PROFILE_COUNTRY_OPTIONS:
                    country_options = [country_value] + [c for c in PROFILE_COUNTRY_OPTIONS if c != country_value]
                else:
                    country_options = PROFILE_COUNTRY_OPTIONS

                country = st.selectbox(
                    t("country_label"),
                    country_options,
                    index=0,
                    key="profile_country",
                )

                _cur_value = str(profile.get("preferred_currency") or st.session_state.get("preferred_currency", "TRY"))
                _cur_idx = CURRENCY_CODES.index(_cur_value) if _cur_value in CURRENCY_CODES else 0
                preferred_currency = st.selectbox(
                    t("preferred_currency"),
                    CURRENCY_CODES,
                    index=_cur_idx,
                    format_func=lambda c: f"{CURRENCIES[c]['symbol']}  {c} — {CURRENCIES[c]['name']}",
                    key="profile_preferred_currency",
                )

            with c2:
                role_value = str(profile.get("role") or "teacher")
                _role_options = ["teacher", "student"]
                _role_idx = _role_options.index(role_value) if role_value in _role_options else 0
                role = st.selectbox(
                    t("role_label"),
                    _role_options,
                    index=_role_idx,
                    format_func=lambda x: t(f"{x}_role"),
                    key="profile_role",
                )

                _is_teacher = role in ("teacher", "tutor")

                if _is_teacher:
                    duration_value = int(profile.get("default_lesson_duration") or 45)
                    duration_index = PROFILE_DURATION_OPTIONS.index(duration_value) if duration_value in PROFILE_DURATION_OPTIONS else 1
                    default_lesson_duration = st.selectbox(
                        t("default_lesson_duration_label"),
                        PROFILE_DURATION_OPTIONS,
                        index=duration_index,
                        format_func=_profile_duration_label,
                        key="profile_default_lesson_duration",
                    )
                else:
                    default_lesson_duration = int(profile.get("default_lesson_duration") or 45)


            if _is_teacher:
                primary_subjects = st.multiselect(
                    t("primary_subjects_label"),
                    PROFILE_SUBJECT_OPTIONS,
                    default=[x for x in (profile.get("primary_subjects") or []) if x in PROFILE_SUBJECT_OPTIONS],
                    format_func=_profile_subject_label,
                    key="profile_primary_subjects",
                )

                custom_subjects_text = ""
                if "other" in primary_subjects:
                    custom_subjects_text = st.text_input(
                        t("other_subject_label"),
                        value=", ".join(profile.get("custom_subjects") or []),
                        key="profile_custom_subjects",
                        help=t("custom_subjects_hint"),
                    ).strip()

                teaching_stages = st.multiselect(
                    t("teaching_stages_label"),
                    PROFILE_STAGE_OPTIONS,
                    default=[x for x in (profile.get("teaching_stages") or []) if x in PROFILE_STAGE_OPTIONS],
                    format_func=_profile_stage_label,
                    key="profile_teaching_stages",
                )

                teaching_languages = st.multiselect(
                    t("teaching_languages_label"),
                    PROFILE_TEACH_LANG_OPTIONS,
                    default=[x for x in (profile.get("teaching_languages") or []) if x in PROFILE_TEACH_LANG_OPTIONS],
                    format_func=_profile_lang_label,
                    key="profile_teaching_languages",
                )

                _edu_options = ["", "edu_student", "edu_bachelors", "edu_masters", "edu_doctorate"]
                _edu_default = str(profile.get("education_level") or "")
                _edu_idx = _edu_options.index(_edu_default) if _edu_default in _edu_options else 0
                education_level = st.selectbox(
                    t("education_level"),
                    _edu_options,
                    index=_edu_idx,
                    format_func=lambda x: t(x) if x else "—",
                    key="profile_education_level",
                )
            else:
                primary_subjects = profile.get("primary_subjects") or []
                teaching_stages = profile.get("teaching_stages") or []
                teaching_languages = profile.get("teaching_languages") or []
                education_level = profile.get("education_level") or ""
                custom_subjects_text = ""

            st.divider()
            st.markdown(f"**🎨 {t('appearance')}**")
            _cur_theme_mode = st.session_state.get("ui_theme_mode", "auto")
            _theme_options = ["auto", "light", "dark"]

            _theme_choice = st.radio(
                t("select_theme"),
                _theme_options,
                index=_theme_options.index(_cur_theme_mode) if _cur_theme_mode in _theme_options else 0,
                format_func=lambda x: {
                    "auto": f"🖥️ {t('theme_auto')}",
                    "light": f"☀️ {t('theme_light')}",
                    "dark": f"🌙 {t('theme_dark')}",
                }[x],
                key="profile_theme_radio",
                horizontal=True,
            )
            if _theme_choice != _cur_theme_mode:
                st.session_state["ui_theme_mode"] = _theme_choice

            st.divider()
            st.markdown(f"**🌐 {t('show_community_profile')}**")
            show_community_profile = st.toggle(
                t("show_community_profile"),
                value=bool(profile.get("show_community_profile", False)),
                key="profile_show_community",
                label_visibility="collapsed",
                help=t("community_profile_hint"),
            )
            if show_community_profile:
                show_community_contact = st.toggle(
                    t("show_community_contact"),
                    value=bool(profile.get("show_community_contact", False)),
                    key="profile_show_community_contact",
                    help=t("community_contact_hint"),
                )
            else:
                show_community_contact = False

            # ── Branding settings (teacher only) ──
            if _is_teacher:
                st.divider()
                from helpers.branding import render_branding_settings
                render_branding_settings()

            save_profile = st.button(t("save_profile"), key="profile_save_btn", use_container_width=True)

            if save_profile:
                new_avatar_url = current_avatar

                if up is not None:
                    try:
                        from helpers.goals import upload_avatar_to_supabase
                        new_avatar_url = upload_avatar_to_supabase(up, user_id=user_id)
                    except Exception as e:
                        st.error(f"{t('upload_failed')}: {e}")
                        return

                ok = upsert_profile_row(
                    user_id,
                    {
                        "display_name": display_name.strip(),
                        "avatar_url": new_avatar_url,
                        "preferred_ui_language": preferred_ui_language,
                        "preferred_currency": preferred_currency,
                        "timezone": timezone_name,
                        "country": None if country == "Select..." else country,
                        "role": role,
                        "primary_subjects": primary_subjects,
                        "custom_subjects": [
                            s.strip().lower()
                            for s in custom_subjects_text.split(",")
                            if s.strip()
                        ] if custom_subjects_text else [],
                        "teaching_stages": teaching_stages,
                        "teaching_languages": teaching_languages,
                        "default_lesson_duration": int(default_lesson_duration),
                        "onboarding_completed": True,
                        "date_of_birth": str(date_of_birth_val) if date_of_birth_val else None,
                        "sex": sex_val if sex_val else None,
                        "phone_number": phone_number_val.strip() or None,
                        "education_level": education_level if education_level else None,
                        "show_community_profile": show_community_profile,
                        "show_community_contact": show_community_contact,
                    },
                )

                if ok:
                    from core.database import update_active_student_count
                    update_active_student_count(user_id)
                    st.session_state["user_name"] = display_name.strip() or st.session_state.get("user_name", "User")
                    st.session_state["avatar_url"] = new_avatar_url
                    st.session_state["ui_lang"] = preferred_ui_language
                    st.session_state["preferred_currency"] = preferred_currency
                    st.session_state["user_role"] = role
                    _set_query(lang=preferred_ui_language)

                    st.session_state["home_action_menu_prev"] = t("files")
                    st.success(t("profile_updated"))
                    st.rerun()
                else:
                    st.error(t("save_failed"))

            st.divider()
            with st.expander(t("change_email_password")):
                st.caption(t("change_email_password_hint"))
                st.info(t("email_managed_by_provider"))
                st.info(t("password_managed_by_provider"))

            st.divider()
            with st.expander(f"⚠️ {t('delete_account')}"):
                st.warning(t("delete_account_warning"))
                st.caption(t("supabase_retention_note"))
                _del_confirm = st.checkbox(
                    t("delete_account_confirm"),
                    key="profile_delete_confirm",
                )
                if st.button(
                    t("delete_account_btn"),
                    key="btn_delete_account",
                    use_container_width=True,
                    type="primary",
                    disabled=not _del_confirm,
                ):
                    try:
                        from core.database import delete_user_data
                        delete_user_data(user_id)
                        st.success(t("delete_account_success"))
                        sign_out_user()
                    except Exception as _e:
                        st.error(f"{t('delete_failed')}: {_e}")

        _profile_dialog()

    except Exception:
        st.warning(t("edit_profile"))


def render_choose_username_dialog(user_id: str) -> None:
    """Show a dialog forcing existing users to pick a unique username."""
    try:
        @st.dialog(t("choose_username_title"))
        def _choose_username_dlg():
            st.info(t("choose_username_msg"))

            username = st.text_input(
                t("user_name"),
                key="choose_username_input",
                help=t("username_hint"),
            )

            if username.strip():
                if is_username_taken(username.strip().lower()):
                    st.error(t("username_taken"))
                else:
                    st.success(t("username_available"))

            if st.button(
                t("set_username_btn"),
                key="btn_set_username",
                use_container_width=True,
                type="primary",
            ):
                if not username.strip():
                    st.error(t("username_required"))
                elif is_username_taken(username.strip().lower()):
                    st.error(t("username_taken"))
                else:
                    ok = upsert_profile_row(user_id, {"username": username.strip().lower()})
                    if ok:
                        st.session_state["user_username"] = username.strip().lower()
                        st.session_state["show_choose_username_dialog"] = False
                        st.success(t("profile_updated"))
                        st.rerun()
                    else:
                        st.error(t("save_failed"))

        _choose_username_dlg()

    except Exception:
        st.warning(t("choose_username_title"))


def render_choose_role_dialog(user_id: str) -> None:
    """Premium welcome dialog for new users to pick Teacher or Student role."""
    try:
        @st.dialog(t("welcome_choose_role_title"), width="large")
        def _choose_role_dlg():
            st.markdown(
                f"""
                <div style="text-align:center; padding: 8px 0 16px;">
                    <div style="font-size:2.4rem; margin-bottom:6px;">🍎</div>
                    <h2 style="margin:0 0 4px;">{t("welcome_choose_role_heading")}</h2>
                    <p style="opacity:0.75; margin:0; font-size:1.05rem;">{t("welcome_choose_role_subtitle")}</p>
                </div>
                """,
                unsafe_allow_html=True,
            )

            col_teacher, col_student = st.columns(2, gap="large")

            with col_teacher:
                st.markdown(
                    f"""
                    <div style="
                        background: linear-gradient(135deg, rgba(59,130,246,0.12), rgba(59,130,246,0.04));
                        border-radius: 18px; padding: 28px 20px; text-align: center;
                        border: 1px solid var(--border); min-height: 220px;
                    ">
                        <div style="font-size:2.8rem; margin-bottom:10px;">👩‍🏫</div>
                        <h3 style="margin:0 0 8px;">{t("teacher_role")}</h3>
                        <p style="opacity:0.7; font-size:0.92rem; margin:0;">{t("welcome_teacher_desc")}</p>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
                if st.button(
                    t("welcome_i_am_teacher"),
                    key="btn_role_teacher",
                    use_container_width=True,
                    type="primary",
                ):
                    upsert_profile_row(
                        user_id,
                        {
                            "role": "teacher",
                            "primary_role": "teacher",
                            "can_teach": True,
                            "last_active_mode": "teacher",
                        },
                    )
                    st.session_state["user_role"] = "teacher"
                    st.session_state["show_choose_role_dialog"] = False
                    st.session_state["_post_login_action"] = "page:home"
                    st.rerun()

            with col_student:
                st.markdown(
                    f"""
                    <div style="
                        background: linear-gradient(135deg, rgba(16,185,129,0.12), rgba(16,185,129,0.04));
                        border-radius: 18px; padding: 28px 20px; text-align: center;
                        border: 1px solid var(--border); min-height: 220px;
                    ">
                        <div style="font-size:2.8rem; margin-bottom:10px;">🎓</div>
                        <h3 style="margin:0 0 8px;">{t("student_role")}</h3>
                        <p style="opacity:0.7; font-size:0.92rem; margin:0;">{t("welcome_student_desc")}</p>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
                if st.button(
                    t("welcome_i_am_student"),
                    key="btn_role_student",
                    use_container_width=True,
                    type="primary",
                ):
                    upsert_profile_row(
                        user_id,
                        {
                            "role": "student",
                            "primary_role": "student",
                            "can_study": True,
                            "last_active_mode": "student",
                        },
                    )
                    st.session_state["user_role"] = "student"
                    st.session_state["show_choose_role_dialog"] = False
                    st.session_state["_post_login_action"] = "page:student_home"
                    st.rerun()

            st.caption(t("welcome_role_change_hint"))

        _choose_role_dlg()

    except Exception:
        st.warning(t("welcome_choose_role_title"))
