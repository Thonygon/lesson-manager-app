from __future__ import annotations

import streamlit as st
from core.database import get_sb
from core.state import get_current_user_id

ADMIN_ROLES = {"admin"}
APP_ROLES = {"admin", "teacher", "student", "school_admin"}


def get_current_profile() -> dict:
    """Load the current user's profile row from Supabase."""
    uid = get_current_user_id()
    if not uid:
        return {}

    try:
        res = (
            get_sb()
            .table("profiles")
            .select("*")
            .eq("user_id", str(uid))
            .limit(1)
            .execute()
        )
        rows = getattr(res, "data", None) or []
        return rows[0] if rows else {}
    except Exception:
        return {}


def get_profile_role(profile: dict | None = None) -> str:
    profile = profile if profile is not None else get_current_profile()
    role = str((profile or {}).get("role") or "teacher").strip().lower()
    return role if role in APP_ROLES else "teacher"


def current_user_is_admin() -> bool:
    return get_profile_role() in ADMIN_ROLES


def require_admin() -> dict:
    """
    Server-side admin guard for Streamlit pages.

    The page is stopped unless the logged-in user's profiles.role is admin.
    """
    profile = get_current_profile()
    if get_profile_role(profile) not in ADMIN_ROLES:
        st.error("Admin access required.")
        st.stop()
    return profile
