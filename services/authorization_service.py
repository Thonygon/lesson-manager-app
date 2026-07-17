from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import streamlit as st

from core.database import get_sb
from core.state import get_current_user_id


STAFF_ROLE_KEYS = ("developer", "data_scientist")
CAPABILITY_MANAGE_STAFF_ROLES = "manage_staff_roles"
CAPABILITY_VIEW_DEVELOPER_WORKSPACE = "view_developer_workspace"
CAPABILITY_VIEW_ML_LAB = "view_ml_lab"
CAPABILITY_RUN_APPROVED_EXPERIMENTS = "run_approved_experiments"
CAPABILITY_RERUN_INTEGRITY_REVIEW = "rerun_integrity_review"
CAPABILITY_VIEW_TECHNICAL_ARTIFACTS = "view_technical_artifacts"
CAPABILITY_VIEW_TELEMETRY_DIAGNOSTICS = "view_telemetry_diagnostics"
CAPABILITY_VIEW_JOB_DIAGNOSTICS = "view_job_diagnostics"
CAPABILITY_COMPARE_EXPERIMENT_RUNS = "compare_experiment_runs"
CAPABILITY_VIEW_AUDIT_LOG = "view_audit_log"

STAFF_CAPABILITY_MAP = {
    "developer": {
        CAPABILITY_VIEW_DEVELOPER_WORKSPACE,
        CAPABILITY_VIEW_ML_LAB,
        CAPABILITY_RUN_APPROVED_EXPERIMENTS,
        CAPABILITY_RERUN_INTEGRITY_REVIEW,
        CAPABILITY_VIEW_TECHNICAL_ARTIFACTS,
        CAPABILITY_VIEW_TELEMETRY_DIAGNOSTICS,
        CAPABILITY_VIEW_JOB_DIAGNOSTICS,
        CAPABILITY_COMPARE_EXPERIMENT_RUNS,
        CAPABILITY_VIEW_AUDIT_LOG,
    },
    "data_scientist": {
        CAPABILITY_VIEW_DEVELOPER_WORKSPACE,
        CAPABILITY_VIEW_ML_LAB,
        CAPABILITY_RUN_APPROVED_EXPERIMENTS,
        CAPABILITY_RERUN_INTEGRITY_REVIEW,
        CAPABILITY_VIEW_TECHNICAL_ARTIFACTS,
        CAPABILITY_VIEW_TELEMETRY_DIAGNOSTICS,
        CAPABILITY_COMPARE_EXPERIMENT_RUNS,
        CAPABILITY_VIEW_AUDIT_LOG,
    },
}
PRODUCT_ROLE_CAPABILITY_MAP = {
    "admin": {CAPABILITY_MANAGE_STAFF_ROLES},
}


@dataclass(frozen=True)
class AuthorizationContext:
    user_id: str
    product_roles: tuple[str, ...]
    staff_roles: tuple[str, ...]
    capabilities: tuple[str, ...]
    profile: dict[str, Any]


def _clean_text(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


@st.cache_data(ttl=60, show_spinner=False)
def _load_authorization_context(user_id: str, cache_bust: str = "") -> dict[str, Any]:
    safe_user_id = _clean_text(user_id)
    if not safe_user_id:
        return {
            "user_id": "",
            "product_roles": [],
            "staff_roles": [],
            "capabilities": [],
            "profile": {},
        }

    sb = get_sb()
    profile_rows = (
        sb.table("profiles")
        .select("user_id,role,primary_role,can_teach,can_study,last_active_mode,email,display_name")
        .eq("user_id", safe_user_id)
        .limit(1)
        .execute()
    ).data or []
    profile = dict(profile_rows[0]) if profile_rows else {}

    product_roles: list[str] = []
    role = _clean_text(profile.get("role")).lower()
    if role:
        product_roles.append(role)
    primary_role = _clean_text(profile.get("primary_role")).lower()
    if primary_role and primary_role not in product_roles:
        product_roles.append(primary_role)
    if bool(profile.get("can_teach")) and "teacher" not in product_roles:
        product_roles.append("teacher")
    if bool(profile.get("can_study")) and "student" not in product_roles:
        product_roles.append("student")

    staff_rows: list[dict[str, Any]] = []
    try:
        staff_rows = (
            sb.table("user_staff_roles")
            .select("role_key,is_active")
            .eq("user_id", safe_user_id)
            .eq("is_active", True)
            .execute()
        ).data or []
    except Exception:
        staff_rows = []

    staff_roles = sorted(
        {
            _clean_text(row.get("role_key")).lower()
            for row in staff_rows
            if _clean_text(row.get("role_key")).lower() in STAFF_ROLE_KEYS and bool(row.get("is_active", True))
        }
    )

    capabilities: set[str] = set()
    for product_role in product_roles:
        capabilities.update(PRODUCT_ROLE_CAPABILITY_MAP.get(product_role, set()))
    for staff_role in staff_roles:
        capabilities.update(STAFF_CAPABILITY_MAP.get(staff_role, set()))

    return {
        "user_id": safe_user_id,
        "product_roles": sorted(set(product_roles)),
        "staff_roles": staff_roles,
        "capabilities": sorted(capabilities),
        "profile": profile,
    }


def clear_authorization_cache() -> None:
    _load_authorization_context.clear()


def get_authorization_context(*, user_id: str | None = None, refresh: bool = False) -> AuthorizationContext:
    safe_user_id = _clean_text(user_id or get_current_user_id())
    if refresh:
        clear_authorization_cache()
    payload = _load_authorization_context(safe_user_id, cache_bust="1" if refresh else "")
    return AuthorizationContext(
        user_id=str(payload.get("user_id") or ""),
        product_roles=tuple(payload.get("product_roles") or ()),
        staff_roles=tuple(payload.get("staff_roles") or ()),
        capabilities=tuple(payload.get("capabilities") or ()),
        profile=dict(payload.get("profile") or {}),
    )


def get_user_capabilities(*, user_id: str | None = None, refresh: bool = False) -> set[str]:
    return set(get_authorization_context(user_id=user_id, refresh=refresh).capabilities)


def has_staff_role(role_key: str, *, user_id: str | None = None, refresh: bool = False) -> bool:
    safe_role_key = _clean_text(role_key).lower()
    return safe_role_key in set(get_authorization_context(user_id=user_id, refresh=refresh).staff_roles)


def has_capability(capability: str, *, user_id: str | None = None, refresh: bool = False) -> bool:
    safe_capability = _clean_text(capability)
    return safe_capability in get_user_capabilities(user_id=user_id, refresh=refresh)


def require_capability(capability: str, *, message: str | None = None) -> AuthorizationContext:
    context = get_authorization_context()
    if capability not in set(context.capabilities):
        st.error(message or "You do not have permission to access this workspace.")
        st.stop()
    return context


def current_user_can_access_developer_workspace(*, refresh: bool = False) -> bool:
    return has_capability(CAPABILITY_VIEW_DEVELOPER_WORKSPACE, refresh=refresh)
