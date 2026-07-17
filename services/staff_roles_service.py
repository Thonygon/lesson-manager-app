from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import streamlit as st

from core.database import clear_app_caches, get_sb, json_safe
from core.state import get_current_user_id
from services.authorization_service import (
    CAPABILITY_MANAGE_STAFF_ROLES,
    STAFF_ROLE_KEYS,
    clear_authorization_cache,
    get_authorization_context,
    require_capability,
)
from services.privileged_action_service import record_privileged_action


STAFF_ROLE_TABLE = "user_staff_roles"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _clean_text(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def _safe_metadata(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


@st.cache_data(ttl=30, show_spinner=False)
def search_profiles_for_staff_access(search_text: str = "", limit: int = 25, cache_bust: str = "") -> list[dict[str, Any]]:
    query = (
        get_sb()
        .table("profiles")
        .select("user_id,email,display_name,role,primary_role,can_teach,can_study,last_active_mode,created_at")
        .order("created_at", desc=True)
        .limit(max(1, min(int(limit), 100)))
    )
    rows = getattr(query.execute(), "data", None) or []
    safe_search = _clean_text(search_text).lower()
    if safe_search:
        filtered = []
        for row in rows:
            haystack = " ".join(
                [
                    _clean_text(row.get("display_name")),
                    _clean_text(row.get("email")),
                    _clean_text(row.get("user_id")),
                    _clean_text(row.get("role")),
                ]
            ).lower()
            if safe_search in haystack:
                filtered.append(dict(row))
        rows = filtered
    return [dict(row) for row in rows]


@st.cache_data(ttl=30, show_spinner=False)
def list_staff_role_assignments(
    *,
    user_id: str = "",
    active_only: bool = False,
    limit: int = 200,
    cache_bust: str = "",
) -> list[dict[str, Any]]:
    query = (
        get_sb()
        .table(STAFF_ROLE_TABLE)
        .select("id,user_id,role_key,is_active,assigned_by,assigned_at,revoked_by,revoked_at,assignment_reason,metadata,created_at,updated_at")
        .order("assigned_at", desc=True)
        .limit(max(1, min(int(limit), 500)))
    )
    safe_user_id = _clean_text(user_id)
    if safe_user_id:
        query = query.eq("user_id", safe_user_id)
    if active_only:
        query = query.eq("is_active", True)
    try:
        return [dict(row) for row in (query.execute().data or [])]
    except Exception:
        return []


def _clear_staff_role_caches() -> None:
    list_staff_role_assignments.clear()
    search_profiles_for_staff_access.clear()
    clear_authorization_cache()
    clear_app_caches()


def assign_staff_role(
    *,
    target_user_id: str,
    role_key: str,
    assignment_reason: str = "",
    metadata: dict[str, Any] | None = None,
) -> tuple[bool, str]:
    require_capability(CAPABILITY_MANAGE_STAFF_ROLES, message="Admin staff-role permission required.")
    safe_target_user_id = _clean_text(target_user_id)
    safe_role_key = _clean_text(role_key).lower()
    if not safe_target_user_id:
        return False, "Target user is required."
    if safe_role_key not in STAFF_ROLE_KEYS:
        return False, "Unsupported staff role."

    existing = [
        row
        for row in list_staff_role_assignments(user_id=safe_target_user_id, active_only=True, cache_bust="assign")
        if _clean_text(row.get("role_key")).lower() == safe_role_key
    ]
    if existing:
        return False, "This active staff role is already assigned."

    profile_rows = (
        get_sb()
        .table("profiles")
        .select("user_id,email,display_name,role")
        .eq("user_id", safe_target_user_id)
        .limit(1)
        .execute()
    ).data or []
    if not profile_rows:
        return False, "Target user does not exist."

    actor_id = _clean_text(get_current_user_id())
    payload = {
        "user_id": safe_target_user_id,
        "role_key": safe_role_key,
        "is_active": True,
        "assigned_by": actor_id or None,
        "assigned_at": _utc_now_iso(),
        "assignment_reason": _clean_text(assignment_reason),
        "metadata": json_safe(_safe_metadata(metadata)),
    }
    try:
        get_sb().table(STAFF_ROLE_TABLE).insert(payload).execute()
        _clear_staff_role_caches()
        record_privileged_action(
            action_type="staff_role_assigned",
            entity_type="user_staff_role",
            entity_id=f"{safe_target_user_id}:{safe_role_key}",
            before_json={},
            after_json=payload,
            reason=assignment_reason,
        )
        return True, "Staff role assigned."
    except Exception as exc:
        return False, str(exc)


def revoke_staff_role(
    *,
    assignment_id: int | str | None = None,
    target_user_id: str = "",
    role_key: str = "",
    revoke_reason: str = "",
) -> tuple[bool, str]:
    require_capability(CAPABILITY_MANAGE_STAFF_ROLES, message="Admin staff-role permission required.")
    safe_role_key = _clean_text(role_key).lower()
    safe_target_user_id = _clean_text(target_user_id)
    rows = list_staff_role_assignments(user_id=safe_target_user_id, active_only=True, cache_bust="revoke")
    target_row: dict[str, Any] = {}
    for row in rows:
        if assignment_id not in (None, "") and str(row.get("id")) == str(assignment_id):
            target_row = row
            break
        if safe_role_key and _clean_text(row.get("role_key")).lower() == safe_role_key:
            target_row = row
            break
    if not target_row:
        return False, "Active staff role assignment not found."

    actor_id = _clean_text(get_current_user_id())
    before_json = dict(target_row)
    update_payload = {
        "is_active": False,
        "revoked_by": actor_id or None,
        "revoked_at": _utc_now_iso(),
        "assignment_reason": _clean_text(revoke_reason) or _clean_text(target_row.get("assignment_reason")),
        "updated_at": _utc_now_iso(),
    }
    try:
        get_sb().table(STAFF_ROLE_TABLE).update(update_payload).eq("id", target_row["id"]).execute()
        _clear_staff_role_caches()
        after_json = dict(before_json)
        after_json.update(update_payload)
        record_privileged_action(
            action_type="staff_role_revoked",
            entity_type="user_staff_role",
            entity_id=f"{target_row.get('user_id')}:{target_row.get('role_key')}",
            before_json=before_json,
            after_json=after_json,
            reason=revoke_reason,
        )
        return True, "Staff role revoked."
    except Exception as exc:
        return False, str(exc)


def recent_staff_role_changes(limit: int = 25) -> list[dict[str, Any]]:
    rows = list_staff_role_assignments(limit=limit, cache_bust="recent")
    return rows
