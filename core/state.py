import streamlit as st
import pycountry
from zoneinfo import available_timezones


def _user_to_dict(user):
    if user is None:
        return None
    if isinstance(user, dict):
        return user
    if hasattr(user, "model_dump"):
        return user.model_dump()
    try:
        return dict(user)
    except Exception:
        return None


def get_current_user_id() -> str:
    uid = str(st.session_state.get("user_id") or "").strip()
    return uid


def with_owner(payload: dict) -> dict:
    out = dict(payload or {})
    uid = get_current_user_id()
    if uid:
        out["user_id"] = uid
    return out


def _set_logged_in_user(
    user,
    profile_name: str = "",
    profile_username: str = "",
    user_id: str = "",
) -> None:
    user_dict = _user_to_dict(user) or {}
    st.session_state["auth_user"] = user_dict

    resolved_user_id = (
        str(user_id or "").strip()
        or str(user_dict.get("id") or "").strip()
        or str(st.session_state.get("user_id") or "").strip()
    )
    st.session_state["user_id"] = resolved_user_id or None

    resolved_email = (
        str(user_dict.get("email") or "").strip()
        or str(st.session_state.get("user_email") or "").strip()
    )
    st.session_state["user_email"] = resolved_email or None

    metadata = user_dict.get("user_metadata") or {}

    st.session_state["user_name"] = (
        str(profile_name or "").strip()
        or str(metadata.get("full_name") or "").strip()
        or str(metadata.get("name") or "").strip()
        or str(metadata.get("display_name") or "").strip()
        or resolved_email
        or "User"
    )

    st.session_state["user_username"] = (
        str(profile_username or "").strip()
        or str(metadata.get("username") or "").strip()
        or str(st.session_state.get("user_username") or "").strip()
    )


def _clear_logged_in_user() -> None:
    st.session_state["auth_user"] = None
    st.session_state["user_id"] = None
    st.session_state["user_email"] = None
    st.session_state["user_name"] = None
    st.session_state["user_username"] = None
    st.session_state["avatar_url"] = None
    st.session_state["_email_synced_to_profile"] = False


# ---- Profile option constants ----
PROFILE_SUBJECT_OPTIONS = [
    "english",
    "spanish",
    "mathematics",
    "science",
    "music",
    "study_skills",
    "other",
]

PROFILE_STAGE_OPTIONS = [
    "early_primary",
    "upper_primary",
    "lower_secondary",
    "upper_secondary",
    "adult_stage",
]

PROFILE_TEACH_LANG_OPTIONS = ["en", "es", "tr"]
PROFILE_DURATION_OPTIONS = [30, 45, 60, 90]
PROFILE_TIMEZONE_OPTIONS = sorted(available_timezones())
PROFILE_COUNTRY_OPTIONS = ["Select..."] + sorted([c.name for c in pycountry.countries])