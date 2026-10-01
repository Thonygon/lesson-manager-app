from __future__ import annotations

import secrets
from typing import Any
from uuid import UUID

import pandas as pd
import streamlit as st

from core.database import clear_app_caches, get_sb, upsert_profile_row
from core.state import get_current_user_id
from core.timezone import DEFAULT_TZ_NAME
from core.i18n import t
from services.authorization_service import clear_authorization_cache
from services.staff_roles_service import assign_staff_role
from services.subscription_service import list_active_plans, list_plan_catalog, reset_usage, update_user_plan


ADMIN_ROLE_OPTIONS = ["teacher", "student", "school_admin", "admin"]
SUBSCRIPTION_STATUS_OPTIONS = ["active", "trialing", "past_due", "cancelled", "free"]
ACCOUNT_STATUS_OPTIONS = ["active", "suspended", "deleted"]
STAFF_ROLE_OPTIONS = ["developer", "data_scientist"]
ADMIN_OVERRIDE_COLUMNS = "id,user_id,override_type,reason,created_by,expires_at,created_at"


def _latest_timestamp(*values: Any) -> str:
    best_value = ""
    best_dt = None
    for value in values:
        dt = pd.to_datetime(value, errors="coerce", utc=True)
        if pd.isna(dt):
            continue
        if best_dt is None or dt > best_dt:
            best_dt = dt
            best_value = str(value or "")
    return best_value


def _active_mode_options(role: str, can_teach: bool, can_study: bool, *, developer_workspace_allowed: bool = False) -> list[str]:
    options: list[str] = []
    if can_teach:
        options.append("teacher")
    if can_study:
        options.append("student")
    if developer_workspace_allowed:
        options.append("developer_workspace")
    if str(role or "").strip().lower() == "admin":
        options.append("admin")
    return options or ["teacher"]


@st.cache_data(ttl=45, show_spinner=False)
def fetch_profiles(search: str = "") -> list[dict]:
    try:
        query = (
            get_sb()
            .table("profiles")
            .select(
                "user_id,email,display_name,role,primary_role,current_plan,subscription_status,"
                "created_at,account_status,admin_notes,login_count,last_active_mode,active_student_count,can_teach,can_study"
            )
            .order("created_at", desc=True)
            .limit(500)
        )
        if search:
            query = query.or_(f"email.ilike.%{search}%,display_name.ilike.%{search}%")
        return getattr(query.execute(), "data", None) or []
    except Exception as exc:
        st.warning(t("admin_profiles_load_failed", error=str(exc)))
        return []


@st.cache_data(ttl=45, show_spinner=False)
def fetch_subscriptions(user_ids: tuple[str, ...] = ()) -> list[dict]:
    try:
        query = get_sb().table("user_subscriptions").select(
            "user_id,plan_id,subscription_status,provider_customer_id,manual_override,updated_at"
        )
        safe_user_ids = [str(user_id or "").strip() for user_id in user_ids if str(user_id or "").strip()]
        if safe_user_ids:
            query = query.in_("user_id", safe_user_ids)
        limit = max(500, len(safe_user_ids)) if safe_user_ids else 500
        return getattr(query.limit(limit).execute(), "data", None) or []
    except Exception:
        return []


@st.cache_data(ttl=45, show_spinner=False)
def fetch_events() -> list[dict]:
    try:
        return getattr(
            get_sb()
            .table("payment_events")
            .select("id,provider,event_type,processed,created_at")
            .order("created_at", desc=True)
            .limit(100)
            .execute(),
            "data",
            None,
        ) or []
    except Exception:
        return []


@st.cache_data(ttl=45, show_spinner=False)
def fetch_overrides(columns: str = ADMIN_OVERRIDE_COLUMNS) -> list[dict]:
    try:
        return getattr(
            get_sb()
            .table("admin_overrides")
            .select(columns)
            .order("created_at", desc=True)
            .limit(100)
            .execute(),
            "data",
            None,
        ) or []
    except Exception:
        return []


@st.cache_data(ttl=60, show_spinner=False)
def fetch_auth_user_activity() -> dict[str, dict[str, str]]:
    activity: dict[str, dict[str, str]] = {}
    try:
        page = 1
        per_page = 500
        while True:
            users = get_sb().auth.admin.list_users(page=page, per_page=per_page)
            if not users:
                break
            for user in users:
                user_id = str(getattr(user, "id", "") or "").strip()
                if not user_id:
                    continue
                activity[user_id] = {
                    "last_sign_in_at": str(getattr(user, "last_sign_in_at", "") or "").strip(),
                }
            if len(users) < per_page:
                break
            page += 1
    except Exception:
        return {}
    return activity


@st.cache_data(ttl=60, show_spinner=False)
def fetch_recent_app_activity(user_ids: tuple[str, ...] = ()) -> dict[str, str]:
    usage: dict[str, str] = {}
    safe_user_ids = [str(user_id or "").strip() for user_id in user_ids if str(user_id or "").strip()]
    if not safe_user_ids:
        return usage

    uuid_user_ids: list[str] = []
    for user_id in safe_user_ids:
        try:
            uuid_user_ids.append(str(UUID(user_id)))
        except (TypeError, ValueError, AttributeError):
            continue
    if not uuid_user_ids:
        return usage

    def _remember(user_id: Any, *timestamps: Any) -> None:
        safe_user_id = str(user_id or "").strip()
        if not safe_user_id:
            return
        usage[safe_user_id] = _latest_timestamp(usage.get(safe_user_id, ""), *timestamps)

    table_specs = [
        ("user_activity_log", "user_id", ["created_at"]),
        ("practice_sessions", "user_id", ["completed_at", "created_at"]),
        ("practice_progress", "user_id", ["last_practiced", "created_at"]),
        ("teacher_review_requests", "student_id", ["created_at"]),
    ]
    for table_name, user_column, timestamp_columns in table_specs:
        select_columns = ",".join([user_column, *timestamp_columns])
        try:
            rows = getattr(
                get_sb().table(table_name).select(select_columns).in_(user_column, uuid_user_ids).limit(5000).execute(),
                "data",
                None,
            ) or []
        except Exception:
            continue
        for row in rows:
            _remember(row.get(user_column), *[row.get(column_name) for column_name in timestamp_columns])

    return usage


def clear_admin_console_caches() -> None:
    clear_app_caches()
    clear_authorization_cache()
    for cached_fn in (
        fetch_profiles,
        fetch_subscriptions,
        fetch_events,
        fetch_overrides,
        fetch_auth_user_activity,
        fetch_recent_app_activity,
        list_plan_catalog,
        list_active_plans,
    ):
        try:
            cached_fn.clear()
        except Exception:
            pass


def log_admin_override(target_user_id: str, override_type: str, reason: str) -> None:
    try:
        get_sb().table("admin_overrides").insert(
            {
                "user_id": str(target_user_id or "").strip(),
                "override_type": str(override_type or "").strip(),
                "reason": str(reason or "").strip(),
                "created_by": str(get_current_user_id() or ""),
            }
        ).execute()
    except Exception:
        pass


def _find_auth_user_by_email(email: str) -> str:
    try:
        sb = get_sb()
        page = 1
        per_page = 500
        while True:
            users = sb.auth.admin.list_users(page=page, per_page=per_page)
            if not users:
                break
            for user in users:
                if str(getattr(user, "email", "") or "").strip().lower() == str(email or "").strip().lower():
                    return str(user.id)
            if len(users) < per_page:
                break
            page += 1
    except Exception:
        pass
    return ""


def create_account(
    email: str,
    display_name: str,
    role: str,
    plan_id: str,
    account_status: str,
    notes: str,
    *,
    can_teach: bool,
    can_study: bool,
    active_mode: str,
    subscription_status: str,
    staff_role_key: str = "",
) -> tuple[bool, str]:
    email = str(email or "").strip().lower()
    role = str(role or "teacher").strip().lower()
    if not email:
        return False, t("admin_error_email_required")
    if role not in ADMIN_ROLE_OPTIONS:
        return False, t("admin_error_invalid_role")

    sb = get_sb()
    user_id = ""
    try:
        auth_resp = sb.auth.admin.create_user(
            {
                "email": email,
                "password": secrets.token_urlsafe(24),
                "email_confirm": True,
            }
        )
        user_id = str(auth_resp.user.id)
    except Exception:
        user_id = _find_auth_user_by_email(email)

    if not user_id:
        return False, t("admin_error_auth_user_missing")

    can_teach = bool(can_teach)
    can_study = bool(can_study)
    staff_role_key = str(staff_role_key or "").strip().lower()
    if staff_role_key not in {"", *STAFF_ROLE_OPTIONS}:
        staff_role_key = ""
    primary_role = "teacher" if can_teach else "student"
    active_mode_options = _active_mode_options(
        role,
        can_teach,
        can_study,
        developer_workspace_allowed=bool(role == "admin" or staff_role_key in STAFF_ROLE_OPTIONS),
    )
    active_mode = str(active_mode or "").strip().lower()
    if active_mode not in active_mode_options:
        active_mode = active_mode_options[0]
    subscription_status = str(subscription_status or "free").strip().lower()
    if subscription_status not in SUBSCRIPTION_STATUS_OPTIONS:
        subscription_status = "free"

    ok = upsert_profile_row(
        user_id,
        {
            "email": email,
            "display_name": str(display_name or "").strip() or email.split("@")[0],
            "preferred_ui_language": "en",
            "timezone": DEFAULT_TZ_NAME,
            "default_lesson_duration": 45,
            "role": role,
            "primary_role": primary_role,
            "can_teach": can_teach,
            "can_study": can_study,
            "last_active_mode": active_mode,
            "current_plan": str(plan_id or "free"),
            "subscription_status": subscription_status,
            "primary_subjects": [],
            "teaching_stages": [],
            "teaching_languages": [],
            "onboarding_completed": False,
            "login_count": 0,
            "active_student_count": 0,
            "account_status": account_status,
            "admin_notes": notes,
        },
    )
    if not ok:
        return False, t("admin_error_profile_save_failed")

    if staff_role_key:
        staff_role_ok, staff_role_msg = assign_staff_role(
            target_user_id=user_id,
            role_key=staff_role_key,
            assignment_reason=t("admin_create_account_staff_access_reason"),
        )
        if not staff_role_ok:
            return False, f"{t('admin_account_created_staff_role_failed_prefix', user_id=user_id)} {staff_role_msg}"

    update_user_plan(user_id, str(plan_id or "free"), status=subscription_status, manual_override=True)
    log_admin_override(user_id, "account_create", f"Created account with role={role}, plan={plan_id}. {notes}".strip())
    clear_admin_console_caches()
    return True, user_id


def update_profile_fields(user_id: str, payload: dict, note: str, action_type: str) -> tuple[bool, str]:
    safe_user_id = str(user_id or "").strip()
    if not safe_user_id:
        return False, t("admin_user_id_required")
    try:
        get_sb().table("profiles").update(payload).eq("user_id", safe_user_id).execute()
        log_admin_override(safe_user_id, action_type, note)
        clear_admin_console_caches()
        return True, t("admin_saved")
    except Exception as exc:
        return False, str(exc)


def upsert_plan(payload: dict) -> tuple[bool, str]:
    try:
        get_sb().table("plans").upsert(payload, on_conflict="id").execute()
        clear_admin_console_caches()
        return True, t("admin_plan_saved")
    except Exception as exc:
        return False, str(exc)


def apply_subscription_action(
    user_id: str,
    *,
    plan_id: str | None = None,
    status: str | None = None,
    reason: str = "",
    action: str | None = None,
    notes: str = "",
) -> tuple[bool, str]:
    safe_user_id = str(user_id or "").strip()
    if not safe_user_id:
        return False, t("admin_target_user_id_required")
    try:
        if plan_id is not None and status is not None:
            update_user_plan(safe_user_id, str(plan_id or "free"), status=str(status or "free"), manual_override=True)
            log_admin_override(
                safe_user_id,
                "plan_assignment",
                reason or f"Assigned {plan_id} with status {status}",
            )
        elif action == "reset_usage":
            reset_usage(safe_user_id)
            log_admin_override(safe_user_id, action, notes or action)
        elif action == "suspend_user":
            get_sb().table("profiles").update({"account_status": "suspended", "admin_notes": notes}).eq("user_id", safe_user_id).execute()
            log_admin_override(safe_user_id, action, notes or action)
        elif action == "unsuspend_user":
            get_sb().table("profiles").update({"account_status": "active", "admin_notes": notes}).eq("user_id", safe_user_id).execute()
            log_admin_override(safe_user_id, action, notes or action)
        else:
            return False, t("admin_action_invalid")
        clear_admin_console_caches()
        return True, t("admin_action_applied")
    except Exception as exc:
        return False, str(exc)
