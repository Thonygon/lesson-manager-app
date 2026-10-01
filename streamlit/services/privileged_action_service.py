from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import streamlit as st

from core.database import get_sb, json_safe
from core.state import get_current_user_id, get_current_user_role
from services.authorization_service import get_authorization_context


AUDIT_TABLE = "privileged_action_audit_log"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _clean_text(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def _request_context() -> dict[str, Any]:
    return {
        "page": str(st.session_state.get("page") or "").strip(),
        "active_mode": str(get_current_user_role() or "").strip(),
        "recorded_at": _utc_now_iso(),
    }


def record_privileged_action(
    *,
    action_type: str,
    entity_type: str,
    entity_id: str,
    before_json: dict[str, Any] | None = None,
    after_json: dict[str, Any] | None = None,
    reason: str = "",
    actor_user_id: str | None = None,
    actor_roles: list[str] | None = None,
    request_context: dict[str, Any] | None = None,
) -> bool:
    try:
        safe_actor_user_id = _clean_text(actor_user_id or get_current_user_id())
        context = get_authorization_context(user_id=safe_actor_user_id) if safe_actor_user_id else None
        roles = actor_roles or list((context.product_roles if context else ())) + list((context.staff_roles if context else ()))
        payload = {
            "actor_user_id": safe_actor_user_id or None,
            "actor_roles": sorted({role for role in roles if _clean_text(role)}),
            "action_type": _clean_text(action_type),
            "entity_type": _clean_text(entity_type),
            "entity_id": _clean_text(entity_id),
            "before_json": json_safe(before_json or {}),
            "after_json": json_safe(after_json or {}),
            "reason": _clean_text(reason),
            "request_context": json_safe(request_context or _request_context()),
        }
        get_sb().table(AUDIT_TABLE).insert(payload).execute()
        list_privileged_actions.clear()
        return True
    except Exception:
        return False


@st.cache_data(ttl=30, show_spinner=False)
def list_privileged_actions(limit: int = 100, cache_bust: str = "") -> list[dict[str, Any]]:
    try:
        rows = (
            get_sb()
            .table(AUDIT_TABLE)
            .select("id,actor_user_id,actor_roles,action_type,entity_type,entity_id,before_json,after_json,reason,request_context,created_at")
            .order("created_at", desc=True)
            .limit(max(1, min(int(limit), 500)))
            .execute()
        ).data or []
        return [dict(row) for row in rows]
    except Exception:
        return []
