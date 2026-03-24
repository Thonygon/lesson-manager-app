import streamlit as st
import os
from streamlit_option_menu import option_menu

from core.i18n import t
from core.state import (
    get_current_user_id, _set_logged_in_user, _clear_logged_in_user,
    PROFILE_SUBJECT_OPTIONS, PROFILE_STAGE_OPTIONS, PROFILE_TEACH_LANG_OPTIONS,
    PROFILE_DURATION_OPTIONS, PROFILE_TIMEZONE_OPTIONS, PROFILE_COUNTRY_OPTIONS,
)
from core.timezone import DEFAULT_TZ_NAME
from core.navigation import _set_query
from core.database import (
    get_sb, clear_app_caches, apply_auth_session, get_user_display_name,
    load_profile_row, upsert_profile_row, is_username_taken, get_user_username,
)
from helpers.currency import CURRENCIES, CURRENCY_CODES
from core.database import (
    get_profile_avatar_url, save_profile_avatar_url,
)

def _has_tokens() -> bool:
    return bool(st.session_state.get("sb_access_token"))

def _set_auth_session(resp) -> None:
    """
    Robustly store Supabase session tokens + user id into st.session_state
    Works with supabase-py v1/v2 response shapes.
    """
    session = None
    user = None

    # supabase-py v2: resp.session / resp.user
    if hasattr(resp, "session"):
        session = resp.session
    if hasattr(resp, "user"):
        user = resp.user

    # Sometimes resp is dict-like
    if session is None and isinstance(resp, dict):
        session = resp.get("session") or resp.get("data") or resp

    if user is None:
        # Try multiple places for user
        if isinstance(resp, dict):
            user = resp.get("user") or (resp.get("session", {}) if isinstance(resp.get("session"), dict) else None)
        if user is None and hasattr(session, "user"):
            user = session.user

    # Extract tokens
    access_token = None
    refresh_token = None

    if isinstance(session, dict):
        access_token = session.get("access_token") or session.get("accessToken")
        refresh_token = session.get("refresh_token") or session.get("refreshToken")
    else:
        access_token = getattr(session, "access_token", None) or getattr(session, "accessToken", None)
        refresh_token = getattr(session, "refresh_token", None) or getattr(session, "refreshToken", None)

    if not access_token:
        raise Exception("Login succeeded but no access_token was returned (cannot persist session).")

    st.session_state["sb_access_token"] = str(access_token)
    st.session_state["sb_refresh_token"] = str(refresh_token or "")

    # Extract user if needed from session
    if user is None:
        if isinstance(session, dict):
            user = session.get("user")
        else:
            user = getattr(session, "user", None)

    # Store standardized session user
    _set_logged_in_user(user)

def _apply_auth_to_client():
    at = st.session_state.get("sb_access_token")
    rt = st.session_state.get("sb_refresh_token")
    if not at:
        return
    try:
        get_sb().auth.set_session(at, rt)
    except Exception as e:
        st.warning(f"Could not apply auth session (RLS may fail): {e}")


@st.cache_data(show_spinner=False)
def load_logo_bytes() -> bytes:
    logo_path = os.path.join("static", "logo_classio_light.png")
    with open(logo_path, "rb") as f:
        return f.read()


def require_login():
    """
    Blocks the app unless a user is logged in.
    """
    # If already logged in -> restore full session and continue
    if _has_tokens():
        apply_auth_session()

        if get_current_user_id():
            # Check for pending post-signup redirect
            after_page = st.session_state.pop("_after_signup_page", None)
            if after_page:
                st.session_state["page"] = after_page
            return

        st.error("Could not restore the logged-in user. Please sign in again.")
        _clear_logged_in_user()
        st.session_state["sb_access_token"] = None
        st.session_state["sb_refresh_token"] = None
        st.stop()

    # Inject theme CSS for the login page
    _theme_mode = st.session_state.get("ui_theme_mode", "auto")
    _dark_login = _theme_mode == "dark"
    from styles.theme import _root_vars, _dark_widget_css
    st.markdown(f"<style>{_root_vars()}</style>", unsafe_allow_html=True)
    _dw = _dark_widget_css()
    if _dw:
        st.markdown(f"<style>{_dw}</style>", unsafe_allow_html=True)

    # Always use the light logo
    logo_bytes = load_logo_bytes()

    st.markdown(
        """
        <style>
        .login-topbar {
            margin-bottom: 0px;
        }

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
        </style>
        """,
        unsafe_allow_html=True,
    )

    # Logo
    col_logo_left, col_logo_center, col_logo_right = st.columns([1, 2, 1])
    with col_logo_center:
        st.markdown('<div class="login-logo-wrap">', unsafe_allow_html=True)
        st.image(logo_bytes, width=500)
        st.markdown("</div>", unsafe_allow_html=True)

    st.markdown('<div class="login-topbar">', unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

    # After explorer CTA, show signup tab first so it's the active tab
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

    with tab_explore:
        from helpers.goal_explorer import render_goal_explorer
        wants_signup = render_goal_explorer()
        if wants_signup:
            # Switch to Create Account tab on next rerun
            st.session_state["_explore_go_signup"] = True
            st.rerun()

    if _from_explore:
        with tab_signup:
            pending_page = st.session_state.get("_after_signup_page")
            if pending_page:
                st.info(t("explore_signup_prompt_feature", feature=t(pending_page.replace("add_", ""))))
            else:
                st.info(t("explore_signup_prompt"))

    with tab_login:
        email = st.text_input(t("email"), key="login_email")
        password = st.text_input(t("password"), type="password", key="login_password")

        if st.button(t("sign_in"), key="btn_login"):
            try:
                resp = get_sb().auth.sign_in_with_password(
                    {"email": email, "password": password}
                )
                _set_auth_session(resp)
                apply_auth_session()

                if not get_current_user_id():
                    raise Exception("Login succeeded but user_id was not restored.")

                st.success(t("logged_in_ok"))
                st.rerun()
            except Exception as e:
                st.error(f"{t('login_failed')}: {e}")

        with st.expander(t("forgot_password")):
            reset_email = st.text_input(t("email_reset_link"), key="reset_email")
            if st.button(t("send_reset_email"), key="btn_reset"):
                try:
                    get_sb().auth.reset_password_for_email(reset_email)
                    st.success(t("reset_email_sent"))
                except Exception as e:
                    st.error(f"{t('reset_failed')}: {e}")

    with tab_signup:
        username = st.text_input(t("user_name"), key="signup_username", help=t("username_hint"))

        if username.strip():
            if is_username_taken(username.strip().lower()):
                st.error(t("username_taken"))
            else:
                st.success(t("username_available"))

        full_name = st.text_input(t("full_name_label"), key="signup_full_name")
        email2 = st.text_input(t("email"), key="signup_email")
        password2 = st.text_input(t("password"), type="password", key="signup_password")

        if st.button(t("create_account"), key="btn_signup"):
            if not username.strip():
                st.error(t("username_required"))
            elif not full_name.strip():
                st.error(t("full_name_required"))
            elif is_username_taken(username.strip().lower()):
                st.error(t("username_taken"))
            else:
                try:
                    resp = get_sb().auth.sign_up({"email": email2, "password": password2})

                    user = resp.user
                    if user:
                        get_sb().table("profiles").upsert(
                            {
                                "user_id": user.id,
                                "email": email2.strip(),
                                "username": username.strip().lower(),
                                "display_name": full_name.strip(),
                                "preferred_ui_language": st.session_state.get("ui_lang", "en"),
                                "timezone": DEFAULT_TZ_NAME,
                                "default_lesson_duration": 45,
                                "role": "teacher",
                                "primary_subjects": [],
                                "teaching_stages": [],
                                "teaching_languages": [],
                                "onboarding_completed": False,
                            },
                            on_conflict="user_id",
                        ).execute()

                        # Auto-save pending lesson plan from explore page
                        _save_pending_explore_plan(user.id, full_name.strip())

                        # Auto-save pending worksheet from explore page
                        _save_pending_explore_worksheet(user.id, full_name.strip())

                        # Auto-save pending CV from explore page
                        _save_pending_explore_cv(user.id, full_name.strip())

                    st.success(t("account_created_check_email"))

                except Exception as e:
                    _err_str = str(e).lower()
                    if any(w in _err_str for w in ("already registered", "already been registered", "user already")):
                        # Check if there's a deleted account with this email
                        try:
                            _check = get_sb().table("profiles").select("account_status").eq(
                                "email", email2.strip()
                            ).limit(1).execute()
                            _rows = getattr(_check, "data", None) or []
                            if _rows and _rows[0].get("account_status") == "deleted":
                                st.warning(t("account_deleted_signup_hint"))
                            else:
                                st.error(f"{t('signup_failed')}: {e}")
                        except Exception:
                            st.error(f"{t('signup_failed')}: {e}")
                    else:
                        st.error(f"{t('signup_failed')}: {e}")

    st.stop()


def _save_pending_explore_plan(user_id: str, display_name: str) -> None:
    """If the user generated a lesson plan on the explore page, save it to their account."""
    pending = st.session_state.pop("_pending_plan_after_signup", None)
    if not pending:
        return
    plan = pending.get("plan")
    meta = pending.get("meta", {})
    if not plan:
        return
    try:
        from datetime import datetime as _dt, timezone
        get_sb().table("lesson_plans").insert({
            "user_id": user_id,
            "subject": str(meta.get("subject", "")).strip(),
            "topic": str(meta.get("topic", "")).strip(),
            "learner_stage": str(meta.get("learner_stage", "")).strip(),
            "level_or_band": str(meta.get("level_or_band", "")).strip(),
            "lesson_purpose": str(meta.get("lesson_purpose", "")).strip(),
            "plan_language": st.session_state.get("ui_lang", "en"),
            "student_material_language": "",
            "source_type": "template",
            "planner_mode": "template",
            "plan_json": plan,
            "title": str(plan.get("title", "")).strip(),
            "author_name": display_name or "Unknown",
            "subject_display": str(meta.get("subject", "")).strip(),
            "is_public": True,
            "created_at": _dt.now(timezone.utc).isoformat(),
        }).execute()
        st.success(t("explore_plan_auto_saved"))
    except Exception:
        pass  # Non-critical; user can re-create the plan after login


def _save_pending_explore_worksheet(user_id: str, display_name: str) -> None:
    """If the user generated a worksheet on the explore page, save it to their account."""
    pending = st.session_state.pop("_pending_worksheet_after_signup", None)
    if not pending:
        return
    ws = pending.get("worksheet")
    meta = pending.get("meta", {})
    if not ws:
        return
    try:
        from datetime import datetime as _dt, timezone
        get_sb().table("worksheets").insert({
            "user_id": user_id,
            "subject": str(meta.get("subject", "")).strip(),
            "topic": str(meta.get("topic", "")).strip(),
            "learner_stage": str(meta.get("learner_stage", "")).strip(),
            "level_or_band": str(meta.get("level_or_band", "")).strip(),
            "worksheet_type": str(meta.get("worksheet_type", "")).strip(),
            "plan_language": st.session_state.get("ui_lang", "en"),
            "student_material_language": "",
            "source_type": "ai",
            "worksheet_json": ws,
            "title": str(ws.get("title", "")).strip(),
            "author_name": display_name or "Unknown",
            "subject_display": str(meta.get("subject", "")).strip(),
            "is_public": True,
            "created_at": _dt.now(timezone.utc).isoformat(),
        }).execute()
        st.success(t("explore_ws_auto_saved"))
    except Exception:
        pass  # Non-critical; user can re-create the worksheet after login


def _save_pending_explore_cv(user_id: str, display_name: str) -> None:
    """If the user generated a CV on the explore page, save it to their account."""
    pending = st.session_state.pop("_pending_cv_after_signup", None)
    if not pending:
        return
    cv = pending.get("cv")
    meta = pending.get("meta", {})
    if not cv:
        return
    try:
        from datetime import datetime as _dt, timezone
        full_name = str(meta.get("full_name") or display_name or "").strip()
        title = f"{full_name} CV" if full_name else "My CV"
        get_sb().table("professional_profiles").insert({
            "user_id": user_id,
            "doc_type": "cv",
            "title": title,
            "source_type": "ai",
            "cv_json": cv,
            "ai_prompt": "",
            "created_at": _dt.now(timezone.utc).isoformat(),
        }).execute()
        st.success(t("explore_cv_auto_saved"))
    except Exception:
        pass  # Non-critical; user can regenerate the CV after login


def _profile_subject_label(subject: str) -> str:
    mapping = {
        "English": t("subject_english"),
        "Spanish": t("subject_spanish"),
        "Mathematics": t("subject_mathematics"),
        "Science": t("subject_science"),
        "Music": t("subject_music"),
        "Study Skills": t("subject_study_skills"),
    }
    return mapping.get(subject, subject)


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

            # Username (non-editable)
            _current_username = str(profile.get("username") or st.session_state.get("user_username") or "")
            st.text_input(
                t("user_name"),
                value=_current_username,
                disabled=True,
                key="profile_username_display",
                help=t("username_not_editable"),
            )

            # Full name (editable)
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

                # Preferred currency
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
                role = st.selectbox(
                    t("role_label"),
                    ["teacher", "tutor"],
                    index=0 if role_value == "teacher" else 1,
                    format_func=lambda x: t("teacher_role") if x == "teacher" else t("tutor_role"),
                    key="profile_role",
                )

                duration_value = int(profile.get("default_lesson_duration") or 45)
                duration_index = PROFILE_DURATION_OPTIONS.index(duration_value) if duration_value in PROFILE_DURATION_OPTIONS else 1
                default_lesson_duration = st.selectbox(
                    t("default_lesson_duration_label"),
                    PROFILE_DURATION_OPTIONS,
                    index=duration_index,
                    format_func=_profile_duration_label,
                    key="profile_default_lesson_duration",
                )

            primary_subjects = st.multiselect(
                t("primary_subjects_label"),
                PROFILE_SUBJECT_OPTIONS,
                default=[x for x in (profile.get("primary_subjects") or []) if x in PROFILE_SUBJECT_OPTIONS],
                format_func=_profile_subject_label,
                key="profile_primary_subjects",
            )

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
                    }
                )

                if ok:
                    from core.database import update_active_student_count
                    update_active_student_count(user_id)
                    st.session_state["user_name"] = display_name.strip() or st.session_state.get("user_name", "User")
                    st.session_state["avatar_url"] = new_avatar_url
                    st.session_state["ui_lang"] = preferred_ui_language
                    st.session_state["preferred_currency"] = preferred_currency
                    _set_query(lang=preferred_ui_language)

                    st.session_state["home_action_menu_prev"] = t("files")
                    st.success(t("profile_updated"))
                    st.rerun()
                else:
                    st.error(t("save_failed"))

            # ── Change email & password ──────────────────────────────────────
            st.divider()
            with st.expander(t("change_email_password")):
                st.caption(t("change_email_password_hint"))
                new_email_val = st.text_input(t("new_email"), key="profile_new_email")
                current_pwd_val = st.text_input(
                    t("current_password"), type="password", key="profile_current_pwd"
                )
                new_pwd_val = st.text_input(
                    t("new_password"), type="password", key="profile_new_pwd"
                )
                confirm_pwd_val = st.text_input(
                    t("confirm_new_password"), type="password", key="profile_confirm_pwd"
                )

                if st.button(
                    t("update_email_password"), key="btn_update_email_pwd", use_container_width=True
                ):
                    if not new_email_val.strip():
                        st.error(t("new_email_required"))
                    elif not current_pwd_val:
                        st.error(t("current_password_required"))
                    elif not new_pwd_val:
                        st.error(t("new_password_required"))
                    elif new_pwd_val != confirm_pwd_val:
                        st.error(t("passwords_do_not_match"))
                    elif len(new_pwd_val) < 6:
                        st.error(t("password_too_short"))
                    else:
                        try:
                            # Verify current password before making any changes
                            get_sb().auth.sign_in_with_password(
                                {"email": current_auth_email, "password": current_pwd_val}
                            )
                            # Update password immediately
                            get_sb().auth.update_user({"password": new_pwd_val})
                            # Request email change — confirmation sent to new address
                            get_sb().auth.update_user({"email": new_email_val.strip()})
                            st.success(t("email_change_confirmation_sent"))
                        except Exception as _e:
                            _err = str(_e).lower()
                            if any(w in _err for w in ("invalid", "credentials", "wrong", "incorrect")):
                                st.error(t("wrong_current_password"))
                            else:
                                st.error(f"{t('update_failed')}: {_e}")

            # ── Delete account ───────────────────────────────────────────
            st.divider()
            with st.expander(f"⚠️ {t('delete_account')}"):
                st.warning(t("delete_account_warning"))
                st.caption(t("supabase_retention_note"))
                _del_confirm = st.checkbox(
                    t("delete_account_confirm"), key="profile_delete_confirm"
                )
                _del_pwd = st.text_input(
                    t("delete_account_password"),
                    type="password",
                    key="profile_delete_pwd",
                )
                if st.button(
                    t("delete_account_btn"),
                    key="btn_delete_account",
                    use_container_width=True,
                    type="primary",
                    disabled=not _del_confirm,
                ):
                    if not _del_pwd:
                        st.error(t("delete_account_password"))
                    else:
                        try:
                            # Verify password
                            get_sb().auth.sign_in_with_password(
                                {"email": current_auth_email, "password": _del_pwd}
                            )
                            # Delete all user data
                            from core.database import delete_user_data
                            delete_user_data(user_id)
                            st.success(t("delete_account_success"))
                            import time; time.sleep(2)
                            # Sign out
                            sign_out_user()
                        except Exception as _e:
                            _err = str(_e).lower()
                            if any(w in _err for w in ("invalid", "credentials", "wrong", "incorrect")):
                                st.error(t("wrong_password"))
                            else:
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

            if st.button(t("set_username_btn"), key="btn_set_username", use_container_width=True, type="primary"):
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


def sign_out_user() -> None:
    try:
        get_sb().auth.sign_out()
    except Exception:
        pass

    _clear_logged_in_user()

    st.session_state["sb_access_token"] = None
    st.session_state["sb_refresh_token"] = None

    st.rerun()

def render_logout_button():
    if st.button(t("sign_out"), key="btn_logout"):
        try:
            get_sb().auth.sign_out()
        except Exception:
            pass

        # clear auth session
        st.session_state["sb_access_token"] = None
        st.session_state["sb_refresh_token"] = None
        st.session_state["show_profile_dialog"] = False

        # clear user info
        _clear_logged_in_user()

        st.rerun()

