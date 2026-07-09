import streamlit as st
import streamlit.components.v1 as components
import os
from urllib.parse import quote
from streamlit.errors import StreamlitAuthError
from core.i18n import t
from core.state import (
    get_current_user_id,
    get_current_user_role,
    resolve_active_face,
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
from helpers.ui_components import trigger_book_rain
from helpers.native_language import native_language_label, normalize_native_language
from core.timezone import DEFAULT_TZ_NAME, _get_qp
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


_SUPPORTED_UI_LANGS = ("en", "es", "tr")
_EXPLORER_CLAIM_COOKIE = "classio_explorer_claims"


def _normalize_explorer_claim_ids(values) -> list[str]:
    if isinstance(values, str):
        items = [part.strip() for part in values.split(",")]
    elif isinstance(values, (list, tuple, set)):
        items = [str(part or "").strip() for part in values]
    else:
        items = []
    out: list[str] = []
    for item in items:
        if item and item not in out:
            out.append(item)
    return out


def _pending_explorer_claim_ids_from_session() -> list[str]:
    ids = _normalize_explorer_claim_ids(st.session_state.get("_explorer_claim_move_ids") or [])
    for key in (
        "_pending_plan_after_signup",
        "_pending_worksheet_after_signup",
        "_pending_exam_after_signup",
    ):
        payload = st.session_state.get(key)
        if isinstance(payload, dict) and payload.get("move_id"):
            ids = _normalize_explorer_claim_ids(ids + [payload.get("move_id")])
    return ids


def _sync_explorer_claim_cookie(move_ids: list[str]) -> None:
    move_ids = _normalize_explorer_claim_ids(move_ids)
    cookie_value = ",".join(move_ids)
    max_age = 1800 if cookie_value else 0
    components.html(
        f"""
        <script>
        (function () {{
          const value = {cookie_value!r};
          const cookie = `{_EXPLORER_CLAIM_COOKIE}=${{value}}; path=/; max-age={max_age}; SameSite=Lax`;
          try {{ document.cookie = cookie; }} catch (e) {{}}
          try {{ window.parent.document.cookie = cookie; }} catch (e) {{}}
        }})();
        </script>
        """,
        height=0,
    )


def _sync_explorer_claim_cookie_from_session() -> None:
    move_ids = _pending_explorer_claim_ids_from_session()
    if move_ids:
        st.session_state["_explorer_claim_move_ids"] = move_ids
        _sync_explorer_claim_cookie(move_ids)


def _clear_explorer_claim_state() -> None:
    st.session_state.pop("_explorer_claim_move_ids", None)
    _sync_explorer_claim_cookie([])


def _read_explorer_claim_ids() -> list[str]:
    cookie_ids = []
    try:
        cookie_ids = _normalize_explorer_claim_ids(st.context.cookies.get(_EXPLORER_CLAIM_COOKIE, ""))
    except Exception:
        cookie_ids = []
    session_ids = _normalize_explorer_claim_ids(st.session_state.get("_explorer_claim_move_ids") or [])
    return _normalize_explorer_claim_ids(cookie_ids + session_ids)


def _consume_pending_explorer_saves() -> None:
    user_id = str(get_current_user_id() or "").strip()
    if not user_id:
        return

    library_saved = False
    consumed_move_ids: list[str] = []

    def _load_move_payload(move_id):
        if not move_id:
            return {}, {}
        try:
            from helpers.explorer_moves import load_explorer_move

            row = load_explorer_move(move_id) or {}
            payload = row.get("payload_json") if isinstance(row.get("payload_json"), dict) else {}
            meta = row.get("meta_json") if isinstance(row.get("meta_json"), dict) else {}
            return payload, meta
        except Exception:
            return {}, {}

    pending_plan = st.session_state.pop("_pending_plan_after_signup", None)
    if isinstance(pending_plan, dict):
        plan = pending_plan.get("plan") if isinstance(pending_plan.get("plan"), dict) else {}
        meta = pending_plan.get("meta") if isinstance(pending_plan.get("meta"), dict) else {}
        if (not plan) and pending_plan.get("move_id"):
            plan, fallback_meta = _load_move_payload(pending_plan.get("move_id"))
            meta = meta or fallback_meta
        if plan:
            try:
                from helpers.planner_storage import save_lesson_plan_record

                ok = save_lesson_plan_record(
                    subject=str(meta.get("subject") or "").strip(),
                    learner_stage=str(meta.get("learner_stage") or "").strip(),
                    level_or_band=str(meta.get("level_or_band") or "").strip(),
                    lesson_purpose=str(meta.get("lesson_purpose") or "").strip(),
                    topic=str(meta.get("topic") or "").strip(),
                    mode=str(meta.get("mode") or "ai").strip() or "ai",
                    plan=plan,
                )
                library_saved = library_saved or bool(ok)
                if ok and pending_plan.get("move_id"):
                    consumed_move_ids.append(str(pending_plan.get("move_id")))
            except Exception:
                pass

    pending_worksheet = st.session_state.pop("_pending_worksheet_after_signup", None)
    if isinstance(pending_worksheet, dict):
        worksheet = pending_worksheet.get("worksheet") if isinstance(pending_worksheet.get("worksheet"), dict) else {}
        meta = pending_worksheet.get("meta") if isinstance(pending_worksheet.get("meta"), dict) else {}
        if (not worksheet) and pending_worksheet.get("move_id"):
            worksheet, fallback_meta = _load_move_payload(pending_worksheet.get("move_id"))
            meta = meta or fallback_meta
        if worksheet:
            try:
                from helpers.worksheet_storage import save_worksheet_record

                ok = save_worksheet_record(
                    subject=str(meta.get("subject") or "").strip(),
                    learner_stage=str(meta.get("learner_stage") or "").strip(),
                    level_or_band=str(meta.get("level_or_band") or "").strip(),
                    worksheet_type=str(meta.get("worksheet_type") or "").strip(),
                    topic=str(meta.get("topic") or "").strip(),
                    worksheet=worksheet,
                )
                library_saved = library_saved or bool(ok)
                if ok and pending_worksheet.get("move_id"):
                    consumed_move_ids.append(str(pending_worksheet.get("move_id")))
            except Exception:
                pass

    pending_cv = st.session_state.pop("_pending_cv_after_signup", None)
    if isinstance(pending_cv, dict):
        cv = pending_cv.get("cv") if isinstance(pending_cv.get("cv"), dict) else {}
        if cv:
            try:
                from helpers.cv_storage import save_cv_record

                ok = save_cv_record(
                    cv_dict=cv,
                    source_type="ai",
                    title=str(cv.get("title") or cv.get("full_name") or t("my_cv")).strip(),
                    ai_prompt="",
                )
                library_saved = library_saved or bool(ok)
            except Exception:
                pass

    pending_exam = st.session_state.pop("_pending_exam_after_signup", None)
    if isinstance(pending_exam, dict):
        exam_data = pending_exam.get("exam_data") if isinstance(pending_exam.get("exam_data"), dict) else {}
        answer_key = pending_exam.get("answer_key") if isinstance(pending_exam.get("answer_key"), dict) else {}
        meta = pending_exam.get("meta") if isinstance(pending_exam.get("meta"), dict) else {}
        if ((not exam_data) or (not answer_key)) and pending_exam.get("move_id"):
            payload, fallback_meta = _load_move_payload(pending_exam.get("move_id"))
            exam_data = payload.get("exam_data") if isinstance(payload.get("exam_data"), dict) else exam_data
            answer_key = payload.get("answer_key") if isinstance(payload.get("answer_key"), dict) else answer_key
            meta = meta or fallback_meta
        if exam_data and answer_key:
            try:
                from helpers.quick_exam_storage import save_exam_record

                ok = save_exam_record(
                    subject=str(meta.get("subject") or "").strip(),
                    learner_stage=str(meta.get("learner_stage") or "").strip(),
                    level_or_band=str(meta.get("level_or_band") or "").strip(),
                    topic=str(meta.get("topic") or "").strip(),
                    exam_length=str(meta.get("exam_length") or "").strip(),
                    exercise_types=list(meta.get("exercise_types") or []),
                    exam_data=exam_data,
                    answer_key=answer_key,
                )
                library_saved = library_saved or bool(ok)
                if ok and pending_exam.get("move_id"):
                    consumed_move_ids.append(str(pending_exam.get("move_id")))
            except Exception:
                pass

    claim_ids = [move_id for move_id in _read_explorer_claim_ids() if move_id not in consumed_move_ids]
    if claim_ids:
        try:
            from helpers.explorer_moves import assign_explorer_move_to_profile, load_explorer_move

            owner_name = str(st.session_state.get("user_name") or "").strip() or t("unknown")
            for move_id in claim_ids:
                move = load_explorer_move(move_id) or {}
                if not move:
                    continue
                ok, _record_id, _msg = assign_explorer_move_to_profile(move, user_id, owner_name)
                library_saved = library_saved or bool(ok)
        except Exception:
            pass

    if library_saved:
        st.session_state["_explore_saved_after_signup"] = True
    _clear_explorer_claim_state()


def _normalize_ui_lang(value, default: str = "") -> str:
    lang = str(value or "").strip().lower()
    if lang in _SUPPORTED_UI_LANGS:
        return lang
    if "-" in lang:
        lang = lang.split("-", 1)[0]
    if "_" in lang:
        lang = lang.split("_", 1)[0]
    return lang if lang in _SUPPORTED_UI_LANGS else default


def _get_cookie_ui_lang() -> str:
    try:
        return _normalize_ui_lang(st.context.cookies.get("classio_ui_lang", ""))
    except Exception:
        return ""


def _get_locale_ui_lang() -> str:
    try:
        return _normalize_ui_lang(getattr(st.context, "locale", ""))
    except Exception:
        return ""


def _resolve_pre_auth_ui_lang() -> str:
    for candidate in (
        st.session_state.get("_pre_auth_ui_lang", ""),
        _get_qp("lang", ""),
        _get_cookie_ui_lang(),
        st.session_state.get("ui_lang", ""),
        _get_locale_ui_lang(),
    ):
        lang = _normalize_ui_lang(candidate)
        if lang:
            return lang
    return "en"


def _sync_ui_lang_cookie(lang: str) -> None:
    lang = _normalize_ui_lang(lang, "en")
    components.html(
        f"""
        <script>
        (function () {{
          const lang = {lang!r};
          const cookie = `classio_ui_lang=${{lang}}; path=/; max-age=31536000; SameSite=Lax`;
          try {{ document.cookie = cookie; }} catch (e) {{}}
          try {{ window.parent.document.cookie = cookie; }} catch (e) {{}}
        }})();
        </script>
        """,
        height=0,
    )


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
                "preferred_ui_language": _resolve_pre_auth_ui_lang(),
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

        preferred_ui_language = _normalize_ui_lang(
            row.get("preferred_ui_language") or _resolve_pre_auth_ui_lang(),
            "en",
        )
        st.session_state["ui_lang"] = preferred_ui_language
        st.session_state["_pre_auth_ui_lang"] = preferred_ui_language

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
            user_role=resolve_active_face(
                str(row.get("role") or ""),
                resolve_active_mode(row),
            ),
        )

        return user_id
    except Exception:
        return ""


def _safe_secret_get(key: str, default=None):
    try:
        return st.secrets.get(key, default)
    except Exception:
        return default


def _has_configured_auth_provider() -> bool:
    auth_config = _safe_secret_get("auth", None)

    if not auth_config:
        return False

    try:
        required_default_keys = ("client_id", "client_secret", "server_metadata_url")
        if all(auth_config.get(key) for key in required_default_keys):
            return True
    except Exception:
        pass

    try:
        for provider_name in ("google", "microsoft", "github", "auth0", "okta"):
            if auth_config.get(provider_name):
                return True
    except Exception:
        return False

    return False


def _get_dev_login_email() -> str:
    for candidate in (
        _safe_secret_get("DEV_LOGIN_EMAIL", ""),
        os.getenv("CLASSIO_DEV_LOGIN_EMAIL", ""),
        os.getenv("DEV_LOGIN_EMAIL", ""),
    ):
        email = str(candidate or "").strip().lower()
        if email:
            return email
    return ""


def _try_local_dev_login() -> bool:
    email = _get_dev_login_email()
    if not email:
        return False

    row = get_profile_by_email(email)
    if not row:
        st.error(
            f"Local dev login failed: no profile was found for {email}. Update DEV_LOGIN_EMAIL to an existing profile email."
        )
        return False

    st.session_state["user_email"] = email
    apply_auth_session()

    if st.session_state.get("user_id"):
        _consume_pending_explorer_saves()
        after_page = st.session_state.pop("_after_signup_page", None)
        if after_page:
            st.session_state["page"] = after_page
        st.session_state["_dev_login_email"] = email
        return True

    st.error(
        f"Local dev login failed for {email}. Check Supabase connectivity and try again."
    )
    return False


def _missing_auth_config_message() -> str:
    return (
        "Google sign-in is not configured for this environment. "
        "Add an authentication provider to .streamlit/secrets.toml, or set DEV_LOGIN_EMAIL "
        "to an existing profile email for local development."
    )


def _render_signup_invite_dialog() -> None:
    @st.dialog(t("explore_signup_dialog_title"))
    def _signup_dlg():
        st.write(t("explore_signup_dialog_body"))
        render_google_auth_card(
            title_key="google_signup_title",
            body_key="account_managed_by_provider",
            button_key="create_account_google",
            button_widget_key="btn_google_signup_dialog",
            show_signup_note=True,
        )
        if st.button(t("explore_signup_dialog_keep_exploring"), key="btn_signup_dialog_keep_exploring", use_container_width=True):
            st.rerun()

    _signup_dlg()

def render_google_auth_card(
    title_key,
    body_key=None,
    button_key=None,
    button_widget_key=None,
    show_signup_note=False
):

    google_svg = """
    <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 48 48">
    <path fill="#EA4335" d="M24 9.5c3.3 0 6.3 1.1 8.6 3.3l6.4-6.4C34.9 2.6 29.8 0 24 0 14.7 0 6.7 5.4 2.7 13.3l7.9 6.1C12.7 13.2 17.9 9.5 24 9.5z"/>
    <path fill="#4285F4" d="M46.1 24.5c0-1.6-.1-3.2-.4-4.7H24v9h12.5c-.5 2.7-2.1 5-4.5 6.6l7 5.4c4.1-3.8 6.5-9.3 6.5-16.3z"/>
    <path fill="#FBBC05" d="M10.6 28.4c-.6-1.7-.9-3.5-.9-5.4s.3-3.7.9-5.4l-7.9-6.1C1 15.1 0 19.4 0 24s1 8.9 2.7 12.5l7.9-6.1z"/>
    <path fill="#34A853" d="M24 48c6.5 0 11.9-2.1 15.8-5.7l-7-5.4c-2 1.4-4.6 2.2-8.8 2.2-6.1 0-11.3-3.7-13.2-9l-7.9 6.1C6.7 42.6 14.7 48 24 48z"/>
    </svg>
    """

    auth_provider_configured = _has_configured_auth_provider()
    wrapper_class = f"st-key-{button_widget_key}"
    google_svg_data = quote(google_svg.strip())
    button_cta = t(button_key)
    body_text = t(body_key) if body_key else ""
    eyebrow_text = t("sign_in") if not show_signup_note else t("sign_up")
    st.markdown(
        f"""
        <style>
        .{wrapper_class} {{
            --auth-google-border: color-mix(in srgb, var(--border-strong, rgba(17,24,39,.12)) 74%, rgba(66,133,244,.26) 26%);
            --auth-google-shadow: 0 22px 52px rgba(15,23,42,.10), inset 0 1px 0 rgba(255,255,255,.82);
        }}
        .{wrapper_class} div[data-testid="stButton"] {{
            margin-top: 0 !important;
            margin-bottom: 0.35rem !important;
        }}
        .{wrapper_class} div[data-testid="stButton"] > button {{
            position: relative;
            overflow: hidden;
            min-height: 224px;
            margin: 0 !important;
            padding: 24px 24px 78px !important;
            border-radius: 24px !important;
            border: 1px solid var(--auth-google-border) !important;
            background:
                radial-gradient(circle at 100% 2%, rgba(66,133,244,.08), transparent 28%),
                linear-gradient(135deg, color-mix(in srgb, rgba(66,133,244,.12) 72%, transparent 28%), rgba(20,184,166,.05)),
                linear-gradient(180deg, color-mix(in srgb, var(--panel, #fff) 94%, white 6%), color-mix(in srgb, var(--panel-2, #f8fafc) 88%, rgba(66,133,244,.08) 12%)) !important;
            box-shadow: var(--auth-google-shadow) !important;
            color: var(--text, #0f172a) !important;
            text-align: left !important;
            white-space: normal !important;
            transition: transform .18s ease, box-shadow .18s ease, border-color .18s ease !important;
        }}
        .{wrapper_class} div[data-testid="stButton"] > button:hover,
        .{wrapper_class} div[data-testid="stButton"] > button:focus {{
            transform: translateY(-2px);
            border-color: color-mix(in srgb, rgba(66,133,244,.48) 42%, var(--border-strong, rgba(17,24,39,.12)) 58%) !important;
            box-shadow: 0 26px 58px rgba(15,23,42,.12), inset 0 1px 0 rgba(255,255,255,.88) !important;
        }}
        .{wrapper_class} div[data-testid="stButton"] > button:disabled {{
            opacity: .72;
            cursor: not-allowed;
            transform: none !important;
            box-shadow: 0 12px 30px rgba(15,23,42,.06), inset 0 1px 0 rgba(255,255,255,.72) !important;
        }}
        .{wrapper_class} div[data-testid="stButton"] > button::before {{
            content: {eyebrow_text.upper()!r};
            position: absolute;
            top: 20px;
            left: 24px;
            font-size: .74rem;
            font-weight: 900;
            color: #4285F4;
            letter-spacing: 0;
            z-index: 2;
            pointer-events: none;
        }}
        .{wrapper_class} div[data-testid="stButton"] > button::after {{
            content: {button_cta!r};
            position: absolute;
            left: 24px;
            bottom: 22px;
            display: inline-flex;
            align-items: center;
            justify-content: center;
            min-height: 40px;
            padding: 0 16px;
            border-radius: 999px;
            background: linear-gradient(180deg, rgba(255,255,255,.86), rgba(255,255,255,.62));
            border: 1px solid color-mix(in srgb, rgba(66,133,244,.28) 34%, var(--border-strong, rgba(17,24,39,.12)) 66%);
            color: var(--text, #0f172a);
            font-size: .92rem;
            font-weight: 820;
            box-shadow: 0 10px 24px rgba(15,23,42,.08);
            pointer-events: none;
        }}
        .{wrapper_class} div[data-testid="stButton"] > button > div {{
            position: relative;
            z-index: 1;
            display: block !important;
            width: 100% !important;
            text-align: left !important;
        }}
        .{wrapper_class} div[data-testid="stButton"] > button > div::before {{
            content: "";
            position: absolute;
            top: 20px;
            right: 0;
            width: 62px;
            height: 62px;
            border-radius: 20px;
            background:
                linear-gradient(180deg, rgba(255,255,255,.92), rgba(255,255,255,.72));
            background-image: url("data:image/svg+xml;utf8,{google_svg_data}");
            background-repeat: no-repeat;
            background-position: center;
            background-size: 38px 38px;
            border: 1px solid color-mix(in srgb, var(--border-strong, rgba(17,24,39,.12)) 78%, rgba(66,133,244,.22) 22%);
            box-shadow: 0 14px 28px rgba(15,23,42,.10);
            pointer-events: none;
        }}
        .{wrapper_class} div[data-testid="stButton"] > button > div::after {{
            content: "";
            position: absolute;
            left: 18px;
            right: 18px;
            top: 0;
            height: 4px;
            border-radius: 0 0 999px 999px;
            background: linear-gradient(90deg, transparent, rgba(66,133,244,.72), transparent);
            opacity: .8;
            pointer-events: none;
        }}
        .{wrapper_class} div[data-testid="stButton"] > button p {{
            position: relative;
            z-index: 1;
            display: block;
            width: min(760px, calc(100% - 96px));
            max-width: min(760px, calc(100% - 96px));
            margin: 78px 0 0;
            white-space: pre-line !important;
            text-align: left !important;
            color: var(--muted, #475569) !important;
            font-size: 1rem;
            line-height: 1.52;
            font-weight: 620;
        }}
        .{wrapper_class} div[data-testid="stButton"] > button p strong {{
            display: block;
            margin: 0 0 10px;
            color: var(--text, #0f172a) !important;
            font-size: 1.45rem;
            line-height: 1.16;
            font-weight: 950;
        }}
        @media (max-width: 768px) {{
            .{wrapper_class} div[data-testid="stButton"] > button {{
                min-height: 204px;
                padding: 22px 20px 72px !important;
                border-radius: 22px !important;
            }}
            .{wrapper_class} div[data-testid="stButton"] > button::before {{
                top: 18px;
                left: 20px;
            }}
            .{wrapper_class} div[data-testid="stButton"] > button > div::before {{
                top: 18px;
                right: 0;
                width: 56px;
                height: 56px;
                border-radius: 18px;
                background-size: 34px 34px;
            }}
            .{wrapper_class} div[data-testid="stButton"] > button::after {{
                left: 20px;
                bottom: 18px;
                min-height: 38px;
                padding: 0 14px;
                font-size: .88rem;
            }}
            .{wrapper_class} div[data-testid="stButton"] > button p {{
                width: calc(100% - 84px);
                max-width: calc(100% - 84px);
                margin-top: 70px;
                font-size: .96rem;
                line-height: 1.48;
            }}
            .{wrapper_class} div[data-testid="stButton"] > button p strong {{
                margin-bottom: 10px;
                font-size: 1.32rem;
            }}
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )
    if st.button(
        f"**{t(title_key)}**  \n{body_text}",
        use_container_width=True,
        key=button_widget_key,
        disabled=not auth_provider_configured,
        help=None if auth_provider_configured else _missing_auth_config_message(),
    ):
        try:
            st.login()
        except StreamlitAuthError:
            st.error(_missing_auth_config_message())

    if show_signup_note:
        st.caption(t("google_auth_signup_note"))

def require_login():
    """
    Blocks the app unless a user is logged in with Streamlit OIDC.
    """
    resolved_ui_lang = _resolve_pre_auth_ui_lang()
    st.session_state["ui_lang"] = resolved_ui_lang
    st.session_state["_pre_auth_ui_lang"] = resolved_ui_lang

    if getattr(st.user, "is_logged_in", False):
        user_id = _restore_user_from_email()
        if user_id:
            apply_auth_session()
            _consume_pending_explorer_saves()
            after_page = st.session_state.pop("_after_signup_page", None)
            if after_page:
                st.session_state["page"] = after_page
            return

    auth_provider_configured = _has_configured_auth_provider()
    if not auth_provider_configured and _try_local_dev_login():
        return

    _theme_mode = st.session_state.get("ui_theme_mode", "auto")
    _dark_login = _theme_mode == "dark"
    from styles.theme import _root_vars, _dark_widget_css

    _sync_ui_lang_cookie(resolved_ui_lang)
    _sync_explorer_claim_cookie_from_session()

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

    if not auth_provider_configured:
        dev_login_email = _get_dev_login_email()
        if dev_login_email:
            st.info(
                f"Google sign-in is not configured for this environment. The app will try DEV_LOGIN_EMAIL={dev_login_email} for local development."
            )
        else:
            st.info(
                _missing_auth_config_message()
            )

    _focus_signup_tab = bool(st.session_state.pop("_explore_go_signup", False))
    _focus_login_tab = bool(st.session_state.pop("_auth_focus_login", False))
    _lang_tab_label = "🌐"
    _theme_tab_label = "🌙" if not _dark_login else "☀️"

    _tab_specs = [
        ("explore", t("explore_tab")),
        ("income_goal", t("set_income_goal")),
        ("login", t("sign_in")),
        ("signup", t("sign_up")),
        ("lang", _lang_tab_label),
        ("theme", _theme_tab_label),
    ]
    if _focus_signup_tab:
        _tab_specs = [spec for spec in _tab_specs if spec[0] == "signup"] + [spec for spec in _tab_specs if spec[0] != "signup"]
    elif _focus_login_tab:
        _tab_specs = [spec for spec in _tab_specs if spec[0] == "login"] + [spec for spec in _tab_specs if spec[0] != "login"]

    st.markdown(
        """
        <style>
        div[data-testid="stTabs"] > div:first-child {
            margin-bottom: 0.25rem !important;
        }
        div[data-testid="stTabs"] div[role="tabpanel"] {
            padding-top: 0.15rem !important;
            margin-top: 0 !important;
        }
        div[data-testid="stTabs"] div[role="tabpanel"] > div[data-testid="stVerticalBlock"] {
            gap: 0.45rem !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    _tabs = st.tabs([label for _, label in _tab_specs])
    _tab_by_key = {key: tab for (key, _), tab in zip(_tab_specs, _tabs)}
    tab_explore = _tab_by_key["explore"]
    tab_income_goal = _tab_by_key["income_goal"]
    tab_login = _tab_by_key["login"]
    tab_signup = _tab_by_key["signup"]
    tab_lang = _tab_by_key["lang"]
    tab_theme = _tab_by_key["theme"]

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
            _sync_ui_lang_cookie(_selected)
            st.session_state["ui_lang"] = _selected
            st.session_state["_pre_auth_ui_lang"] = _selected
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
        st.markdown(f"#### {t('already_have_account')}")
        st.caption(t("already_have_account_hint"))
        if st.button(t("sign_in"), key="btn_signup_go_login", use_container_width=True):
            st.session_state["_auth_focus_login"] = True
            st.rerun()
        st.markdown(
            """
            <div class="home-section-line"> 
              <span>🤖</span>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with tab_explore:
        from helpers.goal_explorer import render_goal_explorer
        wants_signup = render_goal_explorer()
        if wants_signup:
            st.session_state["_explore_go_signup"] = True
            st.session_state["_show_signup_invite_dialog"] = True
            st.rerun()

    with tab_income_goal:
        from helpers.goal_explorer import render_income_goal_explorer
        wants_signup = render_income_goal_explorer()
        if wants_signup:
            st.session_state["_explore_go_signup"] = True
            st.session_state["_show_signup_invite_dialog"] = True
            st.rerun()

    if st.session_state.pop("_show_signup_invite_dialog", False):
        _render_signup_invite_dialog()

    if not st.session_state.get("_prelogin_book_rain_seen", False):
        trigger_book_rain(nonce="prelogin-landing")
        st.session_state["_prelogin_book_rain_seen"] = True

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
    return native_language_label(lang_code)


def _normalized_profile_languages(values) -> list[str]:
    normalized: list[str] = []
    for value in values or []:
        lang_code = normalize_native_language(value)
        if lang_code and lang_code in PROFILE_TEACH_LANG_OPTIONS and lang_code not in normalized:
            normalized.append(lang_code)
    return normalized


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

            profile_role_value = str(profile.get("role") or "teacher").strip().lower()
            _is_admin_profile = profile_role_value == "admin"
            role_value = (
                str(profile.get("primary_role") or profile.get("last_active_mode") or "teacher").strip().lower()
                if _is_admin_profile
                else profile_role_value
            )
            _role_options = ["teacher", "student"]
            _role_idx = _role_options.index(role_value) if role_value in _role_options else 0

            c1, c2 = st.columns(2)

            with c2:
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

                if _is_teacher:
                    _cur_value = str(profile.get("preferred_currency") or st.session_state.get("preferred_currency", "TRY"))
                    _cur_idx = CURRENCY_CODES.index(_cur_value) if _cur_value in CURRENCY_CODES else 0
                    preferred_currency = st.selectbox(
                        t("preferred_currency"),
                        CURRENCY_CODES,
                        index=_cur_idx,
                        format_func=lambda c: f"{CURRENCIES[c]['symbol']}  {c} — {CURRENCIES[c]['name']}",
                        key="profile_preferred_currency",
                    )


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
                    default=_normalized_profile_languages(profile.get("teaching_languages") or []),
                    format_func=_profile_lang_label,
                    key="profile_teaching_languages",
                    help=t("teaching_languages_help"),
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

                profile_payload = {
                    "display_name": display_name.strip(),
                    "avatar_url": new_avatar_url,
                    "preferred_ui_language": preferred_ui_language,
                    "timezone": timezone_name,
                    "country": None if country == "Select..." else country,
                    "role": "admin" if _is_admin_profile else role,
                    "primary_role": role,
                    "can_teach": bool(_is_admin_profile or role == "teacher"),
                    "can_study": bool(role == "student"),
                    "last_active_mode": role,
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
                }
                if _is_teacher:
                    profile_payload["preferred_currency"] = preferred_currency

                ok = upsert_profile_row(user_id, profile_payload)

                if ok:
                    from core.database import update_active_student_count
                    update_active_student_count(user_id)
                    st.session_state["user_name"] = display_name.strip() or st.session_state.get("user_name", "User")
                    st.session_state["avatar_url"] = new_avatar_url
                    st.session_state["ui_lang"] = preferred_ui_language
                    st.session_state["_pre_auth_ui_lang"] = preferred_ui_language
                    if _is_teacher:
                        st.session_state["preferred_currency"] = preferred_currency
                    st.session_state["user_role"] = role
                    _sync_ui_lang_cookie(preferred_ui_language)
                    _set_query(lang=preferred_ui_language)

                    st.session_state["home_action_menu_prev"] = t("home")
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
            # ── Language selector (persists choice to profile + cookie) ──
            _lang_options = {"en": "🇬🇧 English", "es": "🇪🇸 Español", "tr": "🇹🇷 Türkçe"}
            _cur_lang = st.session_state.get("ui_lang", "en")
            _pick = st.radio(
                t("language_ui"),
                list(_lang_options.keys()),
                index=list(_lang_options.keys()).index(_cur_lang) if _cur_lang in _lang_options else 0,
                format_func=lambda x: _lang_options[x],
                key="role_dlg_lang_radio",
                horizontal=True,
            )
            if _pick != _cur_lang:
                st.session_state["ui_lang"] = _pick
                st.session_state["_pre_auth_ui_lang"] = _pick
                _sync_ui_lang_cookie(_pick)
                # Persist to profile so subsequent pages read the correct language
                try:
                    upsert_profile_row(user_id, {"preferred_ui_language": _pick})
                except Exception:
                    pass
                st.rerun()

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
                    _chosen_lang = st.session_state.get("ui_lang", "en")
                    upsert_profile_row(
                        user_id,
                        {
                            "role": "teacher",
                            "primary_role": "teacher",
                            "can_teach": True,
                            "last_active_mode": "teacher",
                            "preferred_ui_language": _chosen_lang,
                        },
                    )
                    _sync_ui_lang_cookie(_chosen_lang)
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
                    _chosen_lang = st.session_state.get("ui_lang", "en")
                    upsert_profile_row(
                        user_id,
                        {
                            "role": "student",
                            "primary_role": "student",
                            "can_study": True,
                            "last_active_mode": "student",
                            "preferred_ui_language": _chosen_lang,
                        },
                    )
                    _sync_ui_lang_cookie(_chosen_lang)
                    st.session_state["user_role"] = "student"
                    st.session_state["show_choose_role_dialog"] = False
                    st.session_state["_post_login_action"] = "page:student_home"
                    st.rerun()

            st.caption(t("welcome_role_change_hint"))

        _choose_role_dlg()

    except Exception:
        st.warning(t("welcome_choose_role_title"))
