from __future__ import annotations

import secrets
import html as _html
import math
from datetime import timedelta
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

from app_pages.pricing import render_plan_preview_cards
from core.database import clear_app_caches, get_sb, upsert_profile_row
from core.i18n import t
from core.state import get_current_user_id
from core.timezone import DEFAULT_TZ_NAME, today_local
from helpers.currency import CURRENCIES, CURRENCY_CODES, get_exchange_rate, get_preferred_currency
from helpers.lesson_planner import normalize_subject
from helpers.recommendation_models import (
    humanize_ai_feature_name,
    humanize_assignment_status,
    humanize_recommendation_event,
    humanize_review_status,
    normalized_subject_label,
)
from helpers.ui_components import chart_series
from services.account_reset_service import (
    RESET_SCOPE_FULL,
    RESET_SCOPE_STUDENT,
    RESET_SCOPE_TEACHER,
    build_user_reset_preview,
    execute_user_reset,
)
from services.auth_service import require_admin
from services.subscription_service import list_active_plans, list_plan_catalog, reset_usage, update_user_plan


ADMIN_ROLE_OPTIONS = ["teacher", "student", "school_admin", "admin"]
SUBSCRIPTION_STATUS_OPTIONS = ["active", "trialing", "past_due", "cancelled", "free"]
ACCOUNT_STATUS_OPTIONS = ["active", "suspended", "deleted"]
ADMIN_SECTIONS = [
    ("overview", "grid-1x2-fill", "admin_overview"),
    ("operations", "people-fill", "admin_operations"),
    ("pricing", "cash-coin", "admin_pricing"),
    ("subscriptions", "credit-card-2-front-fill", "admin_plans_subscriptions"),
    ("intelligence", "cpu-fill", "admin_ai_intelligence"),
    ("business", "graph-up-arrow", "admin_business_analytics"),
    ("audit", "clock-history", "admin_audit_log"),
]

OPERATIONS_TABS = [
    ("accounts", "person-plus-fill", "admin_accounts"),
    ("users", "people-fill", "admin_users"),
]
_ADMIN_USERS_PAGE_SIZE = 4
_DEFAULT_PLAN_LABEL_KEYS = {
    "free": "admin_plan_value_free",
    "teacher_pro": "admin_plan_value_teacher_pro",
    "school": "admin_plan_value_school",
    "beta_lifetime": "admin_plan_value_beta_lifetime",
}
_ROLE_LABEL_KEYS = {
    "teacher": "admin_role_value_teacher",
    "student": "admin_role_value_student",
    "school_admin": "admin_role_value_school_admin",
    "admin": "admin_role_value_admin",
}
_ACCOUNT_STATUS_LABEL_KEYS = {
    "active": "admin_account_status_value_active",
    "suspended": "admin_account_status_value_suspended",
    "deleted": "admin_account_status_value_deleted",
}
_SUBSCRIPTION_STATUS_LABEL_KEYS = {
    "active": "admin_subscription_status_value_active",
    "trialing": "admin_subscription_status_value_trialing",
    "past_due": "admin_subscription_status_value_past_due",
    "cancelled": "admin_subscription_status_value_cancelled",
    "free": "admin_subscription_status_value_free",
}
_OVERRIDE_TYPE_LABEL_KEYS = {
    "account_create": "admin_override_type_account_create",
    "plan_update": "admin_override_type_plan_update",
    "plan_assignment": "admin_override_type_plan_assignment",
    "reset_usage": "admin_override_type_reset_usage",
    "suspend_user": "admin_override_type_suspend_user",
    "unsuspend_user": "admin_override_type_unsuspend_user",
    "role_access": "admin_override_type_role_access",
    "user_row_update": "admin_override_type_user_row_update",
    "restart_account": "admin_override_type_restart_account",
}
_PROFILE_FIELD_LABEL_KEYS = {
    "user_id": "admin_profile_field_user_id",
    "email": "admin_email_label",
    "display_name": "admin_display_name_label",
    "role": "admin_role_label",
    "primary_role": "admin_primary_role_label",
    "current_plan": "admin_current_plan_label",
    "subscription_status": "admin_subscription_status_label",
    "customer_id": "admin_customer_id_label",
    "manual_override": "admin_manual_override_label",
    "expires_at": "admin_expires_at_label",
    "account_status": "admin_account_status_label",
    "created_at": "admin_created_at_label",
    "admin_notes": "admin_notes_label",
    "login_count": "admin_logins_label",
    "last_active_mode": "admin_last_active_mode_label",
    "active_student_count": "admin_students_label",
    "can_teach": "admin_can_teach_label",
    "can_study": "admin_can_study_label",
    "last_used_at": "admin_last_logged_in_label",
}

PLAN_FEATURE_GROUPS = [
    (
        "teacher_workspace",
        "admin_feature_group_teacher_workspace",
        [
            ("dashboard_access", "admin_feature_dashboard_access"),
            ("dashboard_insights", "admin_feature_dashboard_insights"),
            ("dashboard_reports", "admin_feature_dashboard_reports"),
            ("students_access", "admin_feature_students_access"),
            ("students_profile_tools", "admin_feature_students_profile_tools"),
            ("students_progress_tools", "admin_feature_students_progress_tools"),
            ("students_recommendations", "admin_feature_students_recommendations"),
            ("lessons_access", "admin_feature_lessons_access"),
            ("payments_access", "admin_feature_payments_access"),
            ("calendar_access", "admin_feature_calendar_access"),
            ("analytics_access", "admin_feature_analytics_access"),
            ("resources_access", "admin_feature_resources_access"),
            ("community_access", "admin_feature_community_access"),
            ("videos_access", "admin_feature_videos_access"),
        ],
    ),
    (
        "smart_tools",
        "admin_feature_group_smart_tools",
        [
            ("ai_tools", "admin_ai_tools_label"),
            ("smart_tools_access", "admin_feature_smart_tools_access"),
            ("smart_tools_worksheets", "admin_feature_smart_tools_worksheets"),
            ("smart_tools_exams", "admin_feature_smart_tools_exams"),
            ("smart_tools_lesson_plans", "admin_feature_smart_tools_lesson_plans"),
            ("smart_tools_learning_programs", "admin_feature_smart_tools_learning_programs"),
            ("smart_tools_goal_explorer", "admin_feature_smart_tools_goal_explorer"),
            ("smart_tools_student_personalization", "admin_feature_smart_tools_student_personalization"),
        ],
    ),
    (
        "student_experience",
        "admin_feature_group_student_experience",
        [
            ("student_home_access", "admin_feature_student_home_access"),
            ("student_home_recommendations", "admin_feature_student_home_recommendations"),
            ("student_practice_access", "admin_feature_student_practice_access"),
            ("student_practice_history", "admin_feature_student_practice_history"),
            ("student_practice_progress", "admin_feature_student_practice_progress"),
            ("student_study_plan_access", "admin_feature_student_study_plan_access"),
            ("student_assignments_access", "admin_feature_student_assignments_access"),
            ("student_find_teacher_access", "admin_feature_student_find_teacher_access"),
        ],
    ),
    (
        "billing_and_access",
        "admin_feature_group_billing_access",
        [
            ("pdf_export", "admin_pdf_export_label"),
            ("word_export", "admin_word_export_label"),
            ("premium_tools", "admin_premium_tools_label"),
            ("pricing_access", "admin_feature_pricing_access"),
            ("account_access", "admin_feature_account_access"),
            ("school_admin", "admin_school_admin_label"),
            ("admin_console_access", "admin_feature_admin_console_access"),
            ("subscription_controls", "admin_feature_subscription_controls"),
        ],
    ),
]
PREMIUM_TOOL_CANDIDATES = [
    "dashboard_insights",
    "dashboard_reports",
    "students_progress_tools",
    "students_recommendations",
    "analytics_access",
    "smart_tools_access",
    "smart_tools_worksheets",
    "smart_tools_exams",
    "videos_access",
    "smart_tools_lesson_plans",
    "smart_tools_learning_programs",
    "smart_tools_goal_explorer",
    "smart_tools_student_personalization",
    "pdf_export",
    "word_export",
]


def _admin_nav_styles() -> dict:
    return {
        "container": {
            "padding": "0 !important",
            "margin": "0 0 1rem 0 !important",
            "background": "var(--panel)",
            "border": "1px solid var(--border)",
            "border-radius": "14px",
        },
        "nav-link": {
            "font-size": "14px",
            "text-align": "center",
            "padding": "6px 8px",
            "color": "var(--muted)",
            "--hover-color": "var(--panel-soft)",
        },
        "nav-link-selected": {
            "background": "var(--primary)",
            "color": "#f1f5f9",
        },
        "icon": {
            "font-size": "16px",
            "color": "var(--primary-light)",
        },
    }


def _active_mode_options(role: str, can_teach: bool, can_study: bool) -> list[str]:
    return ["teacher", "student", "admin"]


def _plan_feature_label_map() -> dict[str, str]:
    label_map: dict[str, str] = {}
    for _group_key, _group_label_key, items in PLAN_FEATURE_GROUPS:
        for feature_key, label_key in items:
            label_map[feature_key] = label_key
    return label_map


def _infer_plan_feature_default(feature_key: str, features: dict) -> bool:
    premium = bool((features or {}).get("premium_tools", False))
    ai = bool((features or {}).get("ai_tools", False))
    pdf = bool((features or {}).get("pdf_export", False))
    school = bool((features or {}).get("school_admin", False))
    defaults = {
        "dashboard_access": True,
        "dashboard_insights": True,
        "dashboard_reports": pdf,
        "students_access": True,
        "students_profile_tools": True,
        "students_progress_tools": premium or ai,
        "students_recommendations": ai,
        "lessons_access": True,
        "payments_access": True,
        "calendar_access": True,
        "analytics_access": premium,
        "resources_access": True,
        "community_access": True,
        "videos_access": True,
        "smart_tools_access": ai,
        "smart_tools_worksheets": ai,
        "smart_tools_exams": ai,
        "smart_tools_lesson_plans": ai,
        "smart_tools_learning_programs": ai and premium,
        "smart_tools_goal_explorer": ai,
        "smart_tools_student_personalization": ai and premium,
        "student_home_access": True,
        "student_home_recommendations": ai or premium,
        "student_practice_access": True,
        "student_practice_history": True,
        "student_practice_progress": True,
        "student_study_plan_access": True,
        "student_assignments_access": True,
        "student_find_teacher_access": True,
        "pricing_access": True,
        "account_access": True,
        "admin_console_access": school,
        "subscription_controls": school,
        "word_export": pdf,
    }
    return bool(defaults.get(feature_key, False))


def _collect_plan_feature_flags(features: dict) -> dict[str, bool]:
    collected: dict[str, bool] = {}
    for _group_key, _group_label_key, items in PLAN_FEATURE_GROUPS:
        for feature_key, _label_key in items:
            if feature_key in (features or {}):
                collected[feature_key] = bool((features or {}).get(feature_key, False))
            else:
                collected[feature_key] = _infer_plan_feature_default(feature_key, features or {})
    return collected


def _collect_premium_tool_highlights(features: dict) -> dict[str, bool]:
    stored = list((features or {}).get("premium_tool_highlights") or [])
    if stored:
        return {key: key in stored for key in PREMIUM_TOOL_CANDIDATES}
    return {
        key: bool((features or {}).get(key, False) or (key in {"pdf_export", "word_export"} and (features or {}).get(key, False))
        or ((features or {}).get("premium_tools", False) and key in {
            "dashboard_insights",
            "students_progress_tools",
            "students_recommendations",
            "analytics_access",
            "smart_tools_access",
            "smart_tools_worksheets",
            "smart_tools_exams",
            "smart_tools_lesson_plans",
            "smart_tools_learning_programs",
            "smart_tools_goal_explorer",
            "smart_tools_student_personalization",
        }))
        for key in PREMIUM_TOOL_CANDIDATES
    }


@st.cache_data(ttl=45, show_spinner=False)
def _fetch_profiles(search: str = "") -> list[dict]:
    try:
        q = get_sb().table("profiles").select(
            "user_id,email,display_name,role,primary_role,current_plan,subscription_status,"
            "created_at,account_status,admin_notes,login_count,last_active_mode,active_student_count,can_teach,can_study"
        ).order("created_at", desc=True).limit(500)
        if search:
            q = q.or_(f"email.ilike.%{search}%,display_name.ilike.%{search}%")
        return getattr(q.execute(), "data", None) or []
    except Exception as exc:
        st.warning(t("admin_profiles_load_failed", error=str(exc)))
        return []


@st.cache_data(ttl=45, show_spinner=False)
def _fetch_subscriptions() -> list[dict]:
    try:
        return getattr(get_sb().table("user_subscriptions").select("*").limit(500).execute(), "data", None) or []
    except Exception:
        return []


@st.cache_data(ttl=45, show_spinner=False)
def _fetch_events() -> list[dict]:
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
def _fetch_overrides() -> list[dict]:
    try:
        return getattr(
            get_sb()
            .table("admin_overrides")
            .select("*")
            .order("created_at", desc=True)
            .limit(100)
            .execute(),
            "data",
            None,
        ) or []
    except Exception:
        return []


@st.cache_data(ttl=60, show_spinner=False)
def _fetch_auth_user_activity() -> dict[str, dict[str, str]]:
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
def _fetch_recent_app_activity() -> dict[str, str]:
    usage: dict[str, str] = {}

    def _remember(user_id: Any, *timestamps: Any) -> None:
        safe_user_id = str(user_id or "").strip()
        if not safe_user_id:
            return
        usage[safe_user_id] = _latest_timestamp(usage.get(safe_user_id, ""), *timestamps)

    try:
        profile_rows = getattr(
            get_sb().table("profiles").select("user_id,last_used_at").limit(500).execute(),
            "data",
            None,
        ) or []
        for row in profile_rows:
            _remember(row.get("user_id"), row.get("last_used_at"))
    except Exception:
        pass

    table_specs = [
        ("user_activity_log", "user_id", ["created_at"]),
        ("practice_sessions", "user_id", ["updated_at", "completed_at", "created_at"]),
        ("practice_progress", "user_id", ["last_practiced", "created_at"]),
        ("teacher_review_requests", "student_id", ["created_at"]),
    ]
    for table_name, user_column, timestamp_columns in table_specs:
        select_columns = ",".join([user_column, *timestamp_columns])
        try:
            rows = getattr(
                get_sb().table(table_name).select(select_columns).limit(5000).execute(),
                "data",
                None,
            ) or []
        except Exception:
            continue
        for row in rows:
            _remember(row.get(user_column), *[row.get(column_name) for column_name in timestamp_columns])

    return usage


def _clear_admin_page_caches() -> None:
    clear_app_caches()
    for cached_fn in (
        _fetch_profiles,
        _fetch_subscriptions,
        _fetch_events,
        _fetch_overrides,
        _fetch_auth_user_activity,
        _fetch_recent_app_activity,
        list_plan_catalog,
        list_active_plans,
    ):
        try:
            cached_fn.clear()
        except Exception:
            pass


def _minimal_rows(table: str, columns: str = "id,created_at", limit: int = 5000) -> list[dict]:
    try:
        return getattr(get_sb().table(table).select(columns).limit(limit).execute(), "data", None) or []
    except Exception:
        return []


def _fallback_label(value: str) -> str:
    parts = [part for part in str(value or "").strip().replace("-", "_").split("_") if part]
    return " ".join(part.capitalize() for part in parts) if parts else "—"


def _translate_from_map(value: str, mapping: dict[str, str]) -> str:
    raw = str(value or "").strip()
    key = mapping.get(raw)
    if not key:
        return _fallback_label(raw)
    translated = t(key)
    return translated if translated != key else _fallback_label(raw)


def _plan_display_label(plan_id: str, plan_lookup: dict[str, dict] | None = None) -> str:
    raw = str(plan_id or "").strip()
    if not raw:
        return "—"
    if raw in _DEFAULT_PLAN_LABEL_KEYS:
        translated = t(_DEFAULT_PLAN_LABEL_KEYS[raw])
        if translated != _DEFAULT_PLAN_LABEL_KEYS[raw]:
            return translated
    if plan_lookup:
        plan = dict(plan_lookup.get(raw) or {})
        plan_name = str(plan.get("name") or "").strip()
        if plan_name:
            return plan_name
    return _fallback_label(raw)


def _role_display_label(role: str) -> str:
    return _translate_from_map(role, _ROLE_LABEL_KEYS)


def _account_status_display_label(status: str) -> str:
    return _translate_from_map(status, _ACCOUNT_STATUS_LABEL_KEYS)


def _subscription_status_display_label(status: str) -> str:
    return _translate_from_map(status, _SUBSCRIPTION_STATUS_LABEL_KEYS)


def _override_type_display_label(value: str) -> str:
    return _translate_from_map(value, _OVERRIDE_TYPE_LABEL_KEYS)


def _mode_display_label(mode: str) -> str:
    raw = str(mode or "").strip()
    if not raw:
        return "—"
    translated = t(raw)
    return translated if translated != raw else _fallback_label(raw)


def _bool_display_label(value: Any) -> str:
    return t("yes_label") if bool(value) else t("no_label")


def _format_admin_datetime(value: Any) -> str:
    try:
        dt = pd.to_datetime(value, errors="coerce", utc=True)
        if pd.isna(dt):
            return "—"
        return dt.strftime("%Y-%m-%d %H:%M UTC")
    except Exception:
        return "—"


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


def _translated_profile_field_label(field_name: str) -> str:
    key = _PROFILE_FIELD_LABEL_KEYS.get(str(field_name or "").strip(), "")
    if not key:
        return _fallback_label(str(field_name or ""))
    translated = t(key)
    return translated if translated != key else _fallback_label(str(field_name or ""))


def _user_option_label(row: dict) -> str:
    name = str(row.get("display_name") or row.get("email") or t("admin_user_fallback_name")).strip()
    email = str(row.get("email") or t("admin_no_email")).strip()
    user_id = str(row.get("user_id") or "").strip()
    return f"{name} | {email} | {user_id}"


def _selected_user_row(df: pd.DataFrame, state_key: str, *, label_key: str) -> dict:
    if df.empty:
        return {}
    rows = df.to_dict("records")
    option_map = {_user_option_label(row): row for row in rows}
    selected_label = st.selectbox(
        t(label_key),
        list(option_map.keys()),
        key=state_key,
    )
    return dict(option_map.get(selected_label) or {})


def _reset_scope_label(scope: str) -> str:
    key_map = {
        RESET_SCOPE_STUDENT: "admin_restart_scope_student",
        RESET_SCOPE_TEACHER: "admin_restart_scope_teacher",
        RESET_SCOPE_FULL: "admin_restart_scope_full",
    }
    key = key_map.get(str(scope or "").strip(), "")
    return t(key) if key else str(scope or "")


def _reset_scope_success_message(scope: str) -> str:
    key_map = {
        RESET_SCOPE_STUDENT: "admin_restart_account_success_student",
        RESET_SCOPE_TEACHER: "admin_restart_account_success_teacher",
        RESET_SCOPE_FULL: "admin_restart_account_success_full",
    }
    key = key_map.get(str(scope or "").strip(), "admin_restart_account_success_full")
    return t(key)


def _render_reset_preview(preview: dict) -> None:
    rows = list(preview.get("rows") or [])
    if not rows:
        st.info(t("admin_restart_preview_empty"))
        return

    summary = preview.get("summary") or {}
    metric_cols = st.columns(3)
    metric_cols[0].metric(t("admin_reset_summary_delete"), int(summary.get("delete") or 0))
    metric_cols[1].metric(t("admin_reset_summary_archive"), int(summary.get("archive") or 0))
    metric_cols[2].metric(t("admin_reset_summary_reset"), int(summary.get("reset") or 0))

    preview_df = pd.DataFrame(
        [
            {
                t("admin_reset_preview_area"): t(str(item.get("label_key") or "")),
                t("admin_reset_preview_action"): t(f"admin_reset_action_{str(item.get('action') or '').strip().lower()}"),
                t("admin_reset_preview_count"): int(item.get("count") or 0),
                t("admin_reset_preview_note"): t(str(item.get("note_key") or "")) if item.get("note_key") else "—",
            }
            for item in rows
        ]
    )
    st.dataframe(preview_df, use_container_width=True, hide_index=True)


def _merge_profiles_subscriptions(
    profiles: list[dict],
    subscriptions: list[dict],
    auth_activity: dict[str, dict[str, str]] | None = None,
    app_activity: dict[str, str] | None = None,
) -> pd.DataFrame:
    sub_by_user = {str(row.get("user_id")): row for row in subscriptions}
    auth_activity = auth_activity or {}
    app_activity = app_activity or {}
    rows = []
    for profile in profiles:
        uid = str(profile.get("user_id") or "")
        sub = sub_by_user.get(uid, {})
        auth_row = auth_activity.get(uid, {})
        last_used_at = _latest_timestamp(
            profile.get("last_used_at"),
            app_activity.get(uid),
            auth_row.get("last_sign_in_at"),
        )
        rows.append(
            {
                "user_id": uid,
                "email": profile.get("email"),
                "display_name": profile.get("display_name"),
                "role": profile.get("role"),
                "primary_role": profile.get("primary_role"),
                "current_plan": profile.get("current_plan") or sub.get("plan_id") or "free",
                "subscription_status": profile.get("subscription_status") or sub.get("subscription_status") or "free",
                "customer_id": sub.get("provider_customer_id"),
                "manual_override": sub.get("manual_override"),
                "account_status": profile.get("account_status") or "active",
                "created_at": profile.get("created_at"),
                "admin_notes": profile.get("admin_notes"),
                "login_count": int(profile.get("login_count") or 0),
                "last_active_mode": profile.get("last_active_mode") or "",
                "active_student_count": int(profile.get("active_student_count") or 0),
                "can_teach": bool(profile.get("can_teach")),
                "can_study": bool(profile.get("can_study")),
                "last_used_at": last_used_at,
            }
        )
    return pd.DataFrame(rows)


def _is_paid_user_row(row: dict | pd.Series) -> bool:
    plan_id = str((row.get("current_plan") if hasattr(row, "get") else "") or "").strip().lower()
    subscription_status = str((row.get("subscription_status") if hasattr(row, "get") else "") or "").strip().lower()
    if plan_id in {"", "free", "beta_lifetime"}:
        return False
    return subscription_status in {"active", "trialing", "past_due"}


def _log_admin_override(target_user_id: str, override_type: str, reason: str) -> None:
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


def _create_account(
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
    primary_role = "teacher" if can_teach else "student"
    active_mode_options = _active_mode_options(role, can_teach, can_study)
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

    update_user_plan(user_id, str(plan_id or "free"), status=subscription_status, manual_override=True)
    _log_admin_override(user_id, "account_create", f"Created account with role={role}, plan={plan_id}. {notes}".strip())
    _clear_admin_page_caches()
    return True, user_id


def _update_profile_fields(user_id: str, payload: dict, note: str, action_type: str) -> tuple[bool, str]:
    user_id = str(user_id or "").strip()
    if not user_id:
        return False, t("admin_user_id_required")
    try:
        get_sb().table("profiles").update(payload).eq("user_id", user_id).execute()
        _log_admin_override(user_id, action_type, note)
        _clear_admin_page_caches()
        return True, t("admin_saved")
    except Exception as exc:
        return False, str(exc)


def _upsert_plan(payload: dict) -> tuple[bool, str]:
    try:
        get_sb().table("plans").upsert(payload, on_conflict="id").execute()
        _clear_admin_page_caches()
        return True, t("admin_plan_saved")
    except Exception as exc:
        return False, str(exc)


def _business_metrics(df: pd.DataFrame) -> dict[str, int]:
    today = today_local()
    last_30 = pd.Timestamp(today - timedelta(days=30))
    created_at = pd.to_datetime(df.get("created_at"), errors="coerce", utc=True) if not df.empty and "created_at" in df.columns else pd.Series(dtype="datetime64[ns, UTC]")
    paid_users = int(sum(_is_paid_user_row(row) for row in df.to_dict("records"))) if not df.empty else 0
    return {
        "total_users": int(len(df)),
        "teachers": int((df.get("role", pd.Series(dtype=str)).astype(str) == "teacher").sum()) if not df.empty else 0,
        "students": int((df.get("role", pd.Series(dtype=str)).astype(str) == "student").sum()) if not df.empty else 0,
        "admins": int((df.get("role", pd.Series(dtype=str)).astype(str) == "admin").sum()) if not df.empty else 0,
        "paid_users": paid_users,
        "suspended_users": int((df.get("account_status", pd.Series(dtype=str)).astype(str) == "suspended").sum()) if not df.empty else 0,
        "new_last_30": int((created_at >= last_30.tz_localize("UTC")).sum()) if not created_at.empty else 0,
    }


def _content_metrics() -> dict[str, int]:
    worksheet_rows = _minimal_rows("worksheets")
    exam_rows = _minimal_rows("quick_exams")
    plan_rows = _minimal_rows("lesson_plans")
    program_rows = _minimal_rows("learning_programs")
    ai_rows = _minimal_rows("ai_usage_logs")
    return {
        "worksheets": len(worksheet_rows),
        "exams": len(exam_rows),
        "lesson_plans": len(plan_rows),
        "learning_programs": len(program_rows),
        "ai_events": len(ai_rows),
    }


@st.cache_data(ttl=60, show_spinner=False)
def _fetch_admin_dataset_rows(
    table: str,
    columns: str,
    cache_bust: str = "",
    *,
    limit: int = 5000,
    order_column: str = "created_at",
) -> list[dict]:
    try:
        query = get_sb().table(table).select(columns).limit(limit)
        if order_column:
            query = query.order(order_column, desc=True)
        return getattr(query.execute(), "data", None) or []
    except Exception:
        return []


def _table_frame(
    table: str,
    columns: str,
    cache_bust: str = "",
    *,
    limit: int = 5000,
    order_column: str = "created_at",
) -> pd.DataFrame:
    rows = _fetch_admin_dataset_rows(table, columns, cache_bust, limit=limit, order_column=order_column)
    return pd.DataFrame(rows) if rows else pd.DataFrame()


def _normalize_datetime_columns(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    if df.empty:
        return df
    out = df.copy()
    for column in columns:
        if column in out.columns:
            out[column] = pd.to_datetime(out[column], errors="coerce", utc=True)
    return out


def _safe_ratio(numerator: float, denominator: float) -> float:
    denominator = float(denominator or 0.0)
    if denominator <= 0:
        return 0.0
    return float(numerator or 0.0) / denominator


def _pct_text(value: float) -> str:
    safe_value = max(0.0, min(1.0, float(value or 0.0)))
    return f"{int(round(safe_value * 100))}%"


def _latest_frame_timestamp(df: pd.DataFrame, candidates: list[str]) -> pd.Timestamp | None:
    if df.empty:
        return None
    latest: pd.Timestamp | None = None
    for column in candidates:
        if column not in df.columns:
            continue
        series = pd.to_datetime(df[column], errors="coerce", utc=True)
        if series.dropna().empty:
            continue
        current = series.max()
        if pd.isna(current):
            continue
        if latest is None or current > latest:
            latest = current
    return latest


def _freshness_label(value: pd.Timestamp | None) -> str:
    if value is None or pd.isna(value):
        return t("admin_ai_freshness_unknown")
    now_utc = pd.Timestamp.now(tz="UTC")
    delta_hours = max(0.0, (now_utc - value).total_seconds() / 3600.0)
    if delta_hours < 24:
        return t("admin_ai_freshness_hours", count=int(round(delta_hours)))
    return t("admin_ai_freshness_days", count=int(round(delta_hours / 24.0)))


def _readiness_label(score: float) -> str:
    if score >= 0.8:
        return t("admin_ai_readiness_high")
    if score >= 0.45:
        return t("admin_ai_readiness_medium")
    return t("admin_ai_readiness_low")


def _render_section_callout(title: str, subtitle: str) -> None:
    st.markdown(
        f"<div class='admin-section-card'><div class='admin-card-title'>{_html.escape(title)}</div><div class='admin-card-subtitle'>{_html.escape(subtitle)}</div></div>",
        unsafe_allow_html=True,
    )


def _current_ai_code_signal() -> dict[str, Any]:
    project_root = Path(__file__).resolve().parents[1]
    candidates: list[Path] = []
    for folder in ("app_pages", "helpers", "services"):
        root = project_root / folder
        if not root.exists():
            continue
        candidates.extend(root.rglob("*.py"))
    if not candidates:
        return {"latest_change": None, "file_count": 0}
    latest_change = max((path.stat().st_mtime for path in candidates), default=0.0)
    latest_ts = pd.to_datetime(latest_change, unit="s", utc=True, errors="coerce")
    return {
        "latest_change": latest_ts if not pd.isna(latest_ts) else None,
        "file_count": len(candidates),
    }


def _admin_ai_decision_rows(metrics: dict[str, Any], code_signal: dict[str, Any]) -> list[tuple[str, str]]:
    rows: list[tuple[str, str]] = []

    if metrics["topic_linkage_score"] >= 0.6:
        rows.append(
            (
                t("admin_ai_decision_good"),
                t("admin_ai_decision_topic_linkage_good", pct=_pct_text(metrics["topic_linkage_score"])),
            )
        )
    else:
        rows.append(
            (
                t("admin_ai_decision_gap"),
                t("admin_ai_decision_topic_linkage_gap", pct=_pct_text(metrics["topic_linkage_score"])),
            )
        )

    if metrics["recommendation_acceptance_score"] >= 0.22 and metrics["recommendation_outcome_score"] >= 0.18:
        rows.append(
            (
                t("admin_ai_decision_good"),
                t(
                    "admin_ai_decision_acceptance_good",
                    acceptance=_pct_text(metrics["recommendation_acceptance_score"]),
                    outcome=_pct_text(metrics["recommendation_outcome_score"]),
                ),
            )
        )
    else:
        rows.append(
            (
                t("admin_ai_decision_gap"),
                t(
                    "admin_ai_decision_acceptance_gap",
                    acceptance=_pct_text(metrics["recommendation_acceptance_score"]),
                    outcome=_pct_text(metrics["recommendation_outcome_score"]),
                ),
            )
        )

    if metrics["review_closure_score"] >= 0.65:
        rows.append((t("admin_ai_decision_good"), t("admin_ai_decision_reviews_good")))
    else:
        rows.append((t("admin_ai_decision_risk"), t("admin_ai_decision_reviews_risk")))

    if metrics["ai_success_score"] >= 0.8:
        rows.append((t("admin_ai_decision_good"), t("admin_ai_decision_ai_good")))
    else:
        rows.append((t("admin_ai_decision_risk"), t("admin_ai_decision_ai_risk")))

    latest_code_change = code_signal.get("latest_change")
    if latest_code_change is not None and not pd.isna(latest_code_change):
        rows.append(
            (
                t("admin_ai_decision_good"),
                t(
                    "admin_ai_decision_runtime_live",
                    freshness=_freshness_label(latest_code_change),
                    file_count=int(code_signal.get("file_count") or 0),
                ),
            )
        )

    weakest = min(
        [
            ("topic_linkage", float(metrics.get("topic_linkage_score") or 0.0)),
            ("acceptance", float(metrics.get("recommendation_acceptance_score") or 0.0)),
            ("reviews", float(metrics.get("review_closure_score") or 0.0)),
            ("ai", float(metrics.get("ai_success_score") or 0.0)),
            ("progress", float(metrics.get("progress_tracking_score") or 0.0)),
        ],
        key=lambda item: item[1],
    )[0]
    next_key = {
        "topic_linkage": "admin_ai_decision_next_topic_linkage",
        "acceptance": "admin_ai_decision_next_acceptance",
        "reviews": "admin_ai_decision_next_reviews",
        "ai": "admin_ai_decision_next_ai",
        "progress": "admin_ai_decision_next_progress",
    }.get(weakest, "admin_ai_decision_next_action")
    rows.append((t("admin_ai_decision_next"), t(next_key)))
    return rows


def _load_admin_ai_frames() -> dict[str, pd.DataFrame]:
    code_signal = _current_ai_code_signal()
    latest_change = code_signal.get("latest_change")
    cache_bust = str(int(latest_change.timestamp())) if latest_change is not None and not pd.isna(latest_change) else ""
    frames = {
        "profiles": _table_frame(
            "profiles",
            "user_id,role,current_plan,subscription_status,created_at,last_used_at,can_teach,can_study",
            cache_bust,
            limit=5000,
            order_column="created_at",
        ),
        "teacher_student_links": _table_frame(
            "teacher_student_links",
            "id,teacher_id,student_id,status,created_at,updated_at",
            cache_bust,
            limit=5000,
            order_column="updated_at",
        ),
        "teacher_student_subjects": _table_frame(
            "teacher_student_subjects",
            "id,link_id,teacher_id,student_id,subject_key,subject_label,status,created_at,updated_at",
            cache_bust,
            limit=5000,
            order_column="updated_at",
        ),
        "learning_programs": _table_frame(
            "learning_programs",
            "id,user_id,subject,learner_stage,level_or_band,status,created_at,updated_at",
            cache_bust,
            limit=5000,
            order_column="updated_at",
        ),
        "learning_program_topics": _table_frame(
            "learning_program_topics",
            "id,program_id,unit_id,title,topic_number,created_at,updated_at",
            cache_bust,
            limit=12000,
            order_column="updated_at",
        ),
        "learning_program_assignments": _table_frame(
            "learning_program_assignments",
            "id,program_id,teacher_id,student_user_id,status,assigned_at,updated_at",
            cache_bust,
            limit=12000,
            order_column="updated_at",
        ),
        "videos": _table_frame(
            "videos",
            "id,user_id,subject,learner_stage,level_or_band,is_public,status,created_at,updated_at",
            cache_bust,
            limit=12000,
            order_column="updated_at",
        ),
        "learning_program_progress": _table_frame(
            "learning_program_progress",
            "id,assignment_id,topic_id,teacher_done,student_done,is_done,completed_at,created_at,updated_at",
            cache_bust,
            limit=25000,
            order_column="updated_at",
        ),
        "teacher_assignments": _table_frame(
            "teacher_assignments",
            "id,teacher_id,student_id,assignment_type,status,score_pct,assigned_at,created_at,updated_at,learning_program_assignment_id,learning_program_topic_id,recommendation_bucket,recommendation_focus_kind",
            cache_bust,
            limit=20000,
            order_column="updated_at",
        ),
        "teacher_assignment_attempts": _table_frame(
            "teacher_assignment_attempts",
            "id,assignment_id,teacher_id,student_id,status,score_pct,created_at,submitted_at,graded_at,completed_at,updated_at,learning_program_assignment_id,learning_program_topic_id,recommendation_bucket,recommendation_focus_kind",
            cache_bust,
            limit=20000,
            order_column="updated_at",
        ),
        "learning_program_recommendation_events": _table_frame(
            "learning_program_recommendation_events",
            "id,teacher_id,student_id,learning_program_assignment_id,learning_program_topic_id,recommendation_bucket,recommendation_focus_kind,event_type,resource_kind,teacher_assignment_id,assignment_attempt_id,created_at,updated_at",
            cache_bust,
            limit=25000,
            order_column="updated_at",
        ),
        "teacher_review_requests": _table_frame(
            "teacher_review_requests",
            "id,teacher_id,student_id,status,requested_at,reviewed_at,created_at",
            cache_bust,
            limit=12000,
            order_column="created_at",
        ),
        "practice_sessions": _table_frame(
            "practice_sessions",
            "id,user_id,source_type,subject,topic,level,score_pct,status,created_at,completed_at",
            cache_bust,
            limit=25000,
            order_column="created_at",
        ),
        "practice_progress": _table_frame(
            "practice_progress",
            "id,user_id,subject,topic,exercise_type,level,accuracy_pct,last_practiced,created_at",
            cache_bust,
            limit=25000,
            order_column="last_practiced",
        ),
        "ai_usage_logs": _table_frame(
            "ai_usage_logs",
            "id,user_id,feature_name,status,created_at",
            cache_bust,
            limit=25000,
            order_column="created_at",
        ),
        "user_activity_log": _table_frame(
            "user_activity_log",
            "id,user_id,activity_type,feature_name,created_at",
            cache_bust,
            limit=25000,
            order_column="created_at",
        ),
    }
    datetime_map = {
        "profiles": ["created_at", "last_used_at"],
        "teacher_student_links": ["created_at", "updated_at"],
        "teacher_student_subjects": ["created_at", "updated_at"],
        "learning_programs": ["created_at", "updated_at"],
        "learning_program_topics": ["created_at", "updated_at"],
        "learning_program_assignments": ["assigned_at", "updated_at"],
        "learning_program_progress": ["completed_at", "created_at", "updated_at"],
        "teacher_assignments": ["assigned_at", "created_at", "updated_at"],
        "teacher_assignment_attempts": ["created_at", "submitted_at", "graded_at", "completed_at", "updated_at"],
        "learning_program_recommendation_events": ["created_at", "updated_at"],
        "teacher_review_requests": ["requested_at", "reviewed_at", "created_at"],
        "practice_sessions": ["created_at", "completed_at"],
        "practice_progress": ["last_practiced", "created_at"],
        "ai_usage_logs": ["created_at"],
        "user_activity_log": ["created_at"],
        "videos": ["created_at", "updated_at"],
    }
    for key, cols in datetime_map.items():
        frames[key] = _normalize_datetime_columns(frames[key], cols)
    return frames


def _build_admin_ai_snapshot() -> dict[str, Any]:
    frames = _load_admin_ai_frames()
    code_signal = _current_ai_code_signal()
    links_df = frames["teacher_student_links"]
    subjects_df = frames["teacher_student_subjects"]
    programs_df = frames["learning_programs"]
    videos_df = frames["videos"]
    topics_df = frames["learning_program_topics"]
    program_assign_df = frames["learning_program_assignments"]
    progress_df = frames["learning_program_progress"]
    assignments_df = frames["teacher_assignments"]
    attempts_df = frames["teacher_assignment_attempts"]
    recommendation_df = frames["learning_program_recommendation_events"]
    reviews_df = frames["teacher_review_requests"]
    practice_df = frames["practice_sessions"]
    ai_usage_df = frames["ai_usage_logs"]
    activity_df = frames["user_activity_log"]

    active_links = int((links_df.get("status", pd.Series(dtype=str)).astype(str) == "active").sum()) if not links_df.empty else 0
    active_subjects = int((subjects_df.get("status", pd.Series(dtype=str)).astype(str) == "active").sum()) if not subjects_df.empty else 0
    active_program_assignments = int((program_assign_df.get("status", pd.Series(dtype=str)).astype(str) != "archived").sum()) if not program_assign_df.empty else 0

    if not assignments_df.empty:
        assignments_df = assignments_df.copy()
        assignments_df["linked_to_program"] = (
            assignments_df.get("learning_program_assignment_id", pd.Series(dtype=float)).notna()
            & assignments_df.get("learning_program_topic_id", pd.Series(dtype=float)).notna()
        )
    if not attempts_df.empty:
        attempts_df = attempts_df.copy()
        attempts_df["linked_to_program"] = (
            attempts_df.get("learning_program_assignment_id", pd.Series(dtype=float)).notna()
            & attempts_df.get("learning_program_topic_id", pd.Series(dtype=float)).notna()
        )

    program_alignment_score = _safe_ratio(
        float(assignments_df.get("linked_to_program", pd.Series(dtype=bool)).sum()) if not assignments_df.empty else 0.0,
        float(len(assignments_df)),
    )
    review_closure_score = _safe_ratio(
        float((reviews_df.get("status", pd.Series(dtype=str)).astype(str) == "reviewed").sum()) if not reviews_df.empty else 0.0,
        float(len(reviews_df)),
    )
    ai_success_score = _safe_ratio(
        float((ai_usage_df.get("status", pd.Series(dtype=str)).astype(str).str.lower() == "success").sum()) if not ai_usage_df.empty else 0.0,
        float(len(ai_usage_df)),
    )

    recommendation_event_counts = (
        recommendation_df.groupby("event_type", as_index=False).size().rename(columns={"size": "count"})
        if not recommendation_df.empty and "event_type" in recommendation_df.columns
        else pd.DataFrame(columns=["event_type", "count"])
    )
    recommendation_surface = int(
        recommendation_event_counts.loc[
            recommendation_event_counts["event_type"].astype(str).isin(["prefill", "resource_opened", "resource_assigned"]),
            "count",
        ].sum()
    ) if not recommendation_event_counts.empty else 0
    recommendation_actions = int(
        recommendation_event_counts.loc[
            recommendation_event_counts["event_type"].astype(str).isin(["assignment_created", "teacher_marked_done"]),
            "count",
        ].sum()
    ) if not recommendation_event_counts.empty else 0
    recommendation_learning = int(
        recommendation_event_counts.loc[
            recommendation_event_counts["event_type"].astype(str).isin(["student_started", "student_completed", "student_improved"]),
            "count",
        ].sum()
    ) if not recommendation_event_counts.empty else 0
    feedback_loop_score = _safe_ratio(recommendation_learning, recommendation_actions or recommendation_surface)
    recommendation_acceptance_score = _safe_ratio(recommendation_actions, recommendation_surface)
    recommendation_outcome_score = _safe_ratio(recommendation_learning, recommendation_actions)
    topic_linked_assignments = int(
        assignments_df.get("learning_program_topic_id", pd.Series(dtype=float)).notna().sum()
    ) if not assignments_df.empty else 0
    topic_linked_attempts = int(
        attempts_df.get("learning_program_topic_id", pd.Series(dtype=float)).notna().sum()
    ) if not attempts_df.empty else 0
    topic_linked_events = int(
        recommendation_df.get("learning_program_topic_id", pd.Series(dtype=float)).notna().sum()
    ) if not recommendation_df.empty else 0
    topic_linkage_score = _safe_ratio(
        float(topic_linked_assignments + topic_linked_attempts + topic_linked_events),
        float(len(assignments_df) + len(attempts_df) + len(recommendation_df)),
    )

    program_topic_counts = (
        topics_df.groupby("program_id", as_index=False).size().rename(columns={"size": "topic_count"})
        if not topics_df.empty and "program_id" in topics_df.columns
        else pd.DataFrame(columns=["program_id", "topic_count"])
    )
    potential_progress_rows = 0
    if not program_assign_df.empty and not program_topic_counts.empty:
        topic_lookup = {int(row["program_id"]): int(row["topic_count"]) for row in program_topic_counts.to_dict("records") if row.get("program_id") is not None}
        potential_progress_rows = int(
            sum(topic_lookup.get(int(row.get("program_id") or 0), 0) for row in program_assign_df.to_dict("records"))
        )
    progress_tracking_score = _safe_ratio(len(progress_df), potential_progress_rows) if potential_progress_rows else 0.0

    latest_timestamps = [
        _latest_frame_timestamp(links_df, ["updated_at", "created_at"]),
        _latest_frame_timestamp(subjects_df, ["updated_at", "created_at"]),
        _latest_frame_timestamp(program_assign_df, ["updated_at", "assigned_at"]),
        _latest_frame_timestamp(videos_df, ["updated_at", "created_at"]),
        _latest_frame_timestamp(progress_df, ["updated_at", "completed_at", "created_at"]),
        _latest_frame_timestamp(assignments_df, ["updated_at", "assigned_at", "created_at"]),
        _latest_frame_timestamp(attempts_df, ["updated_at", "completed_at", "graded_at", "submitted_at", "created_at"]),
        _latest_frame_timestamp(recommendation_df, ["updated_at", "created_at"]),
        _latest_frame_timestamp(reviews_df, ["reviewed_at", "requested_at", "created_at"]),
        _latest_frame_timestamp(practice_df, ["completed_at", "created_at"]),
        _latest_frame_timestamp(ai_usage_df, ["created_at"]),
        _latest_frame_timestamp(activity_df, ["created_at"]),
    ]
    latest_timestamps = [stamp for stamp in latest_timestamps if stamp is not None]
    overall_freshness = max(latest_timestamps) if latest_timestamps else None

    multi_subject_links = 0
    if not subjects_df.empty and "link_id" in subjects_df.columns:
        active_subjects_df = subjects_df[subjects_df.get("status", pd.Series(dtype=str)).astype(str) == "active"].copy()
        if not active_subjects_df.empty:
            multi_subject_links = int((active_subjects_df.groupby("link_id").size() > 1).sum())

    return {
        "frames": frames,
        "metrics": {
            "active_links": active_links,
            "active_subjects": active_subjects,
            "multi_subject_links": multi_subject_links,
            "program_assignments": active_program_assignments,
            "videos": int(len(videos_df)),
            "recommendation_events": int(len(recommendation_df)),
            "program_alignment_score": program_alignment_score,
            "topic_linkage_score": topic_linkage_score,
            "review_closure_score": review_closure_score,
            "ai_success_score": ai_success_score,
            "feedback_loop_score": feedback_loop_score,
            "recommendation_acceptance_score": recommendation_acceptance_score,
            "recommendation_outcome_score": recommendation_outcome_score,
            "progress_tracking_score": progress_tracking_score,
            "freshness": overall_freshness,
        },
        "recommendation_counts": recommendation_event_counts,
        "code_signal": code_signal,
    }


def _render_admin_ai_intelligence() -> None:
    card_col, refresh_col = st.columns([0.76, 0.24], vertical_alignment="center")
    with card_col:
        _render_section_callout(t("admin_ai_intelligence_title"), t("admin_ai_intelligence_subtitle"))
    with refresh_col:
        st.markdown("<div style='height:10px;'></div>", unsafe_allow_html=True)
        if st.button(t("admin_ai_refresh_now"), key="admin_ai_refresh_now", use_container_width=True):
            clear_app_caches()
            st.rerun()
    st.markdown("<div class='admin-kpi-stack-gap'></div>", unsafe_allow_html=True)
    snapshot = _build_admin_ai_snapshot()
    frames = snapshot["frames"]
    metrics = snapshot["metrics"]
    code_signal = snapshot.get("code_signal") or {}

    top_metrics = [
        (t("admin_ai_metric_active_links"), str(metrics["active_links"])),
        (t("admin_ai_metric_program_assignments"), str(metrics["program_assignments"])),
        (t("admin_ai_metric_videos"), str(metrics["videos"])),
        (t("admin_ai_metric_recommendation_events"), str(metrics["recommendation_events"])),
        (t("admin_ai_metric_freshness"), _freshness_label(metrics["freshness"])),
    ]
    _render_kpi_row(top_metrics)
    st.markdown("<div class='admin-kpi-stack-gap'></div>", unsafe_allow_html=True)
    _render_kpi_row(
        [
            (t("admin_ai_metric_program_alignment"), _pct_text(metrics["program_alignment_score"])),
            (t("admin_ai_metric_review_closure"), _pct_text(metrics["review_closure_score"])),
            (t("admin_ai_metric_feedback_loop"), _pct_text(metrics["feedback_loop_score"])),
            (t("admin_ai_metric_ai_success"), _pct_text(metrics["ai_success_score"])),
        ]
    )
    st.markdown("<div class='admin-kpi-stack-gap'></div>", unsafe_allow_html=True)

    map_cols = st.columns(4, gap="medium")
    map_items = [
        (t("admin_ai_map_signals_title"), t("admin_ai_map_signals_body")),
        (t("admin_ai_map_features_title"), t("admin_ai_map_features_body")),
        (t("admin_ai_map_decisions_title"), t("admin_ai_map_decisions_body")),
        (t("admin_ai_map_outcomes_title"), t("admin_ai_map_outcomes_body")),
    ]
    for col, (title, body) in zip(map_cols, map_items):
        with col:
            st.markdown(
                f"""
                <div class="admin-kpi-card">
                    <div class="admin-kpi-label">{_html.escape(title)}</div>
                    <div style="margin-top:8px;font-size:.86rem;line-height:1.45;color:var(--text);">{_html.escape(body)}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    graph_tab, model_tab, data_tab, decision_tab = st.tabs(
        [
            f"📈 {t('admin_ai_tab_graphs')}",
            f"🧠 {t('admin_ai_tab_models')}",
            f"🗂️ {t('admin_ai_tab_datasets')}",
            f"🧭 {t('admin_ai_tab_decisions')}",
        ]
    )

    with graph_tab:
        recommendation_df = frames["learning_program_recommendation_events"]
        assignments_df = frames["teacher_assignments"]
        reviews_df = frames["teacher_review_requests"]
        ai_usage_df = frames["ai_usage_logs"]
        practice_df = frames["practice_sessions"]
        progress_df = frames["learning_program_progress"]

        left, right = st.columns(2, gap="large")
        with left:
            st.markdown(f"### {t('admin_ai_graph_recommendation_funnel')}")
            if recommendation_df.empty or "event_type" not in recommendation_df.columns:
                st.info(t("admin_ai_empty_data"))
            else:
                funnel = (
                    recommendation_df.groupby("event_type", as_index=False)
                    .size()
                    .rename(columns={"size": "count"})
                    .sort_values("count", ascending=False)
                )
                funnel["event_type"] = funnel["event_type"].astype(str).map(humanize_recommendation_event)
                funnel_series = chart_series(funnel, "event_type", "count", "admin_chart_index_action", "admin_chart_value_count")
                if funnel_series is not None:
                    st.bar_chart(funnel_series)
        with right:
            st.markdown(f"### {t('admin_ai_graph_assignment_lifecycle')}")
            if assignments_df.empty or "status" not in assignments_df.columns:
                st.info(t("admin_ai_empty_data"))
            else:
                status_df = (
                    assignments_df.groupby("status", as_index=False)
                    .size()
                    .rename(columns={"size": "count"})
                    .sort_values("count", ascending=False)
                )
                status_df["status"] = status_df["status"].astype(str).map(humanize_assignment_status)
                status_series = chart_series(status_df, "status", "count", "admin_chart_index_status", "admin_chart_value_count")
                if status_series is not None:
                    st.bar_chart(status_series)

        left, right = st.columns(2, gap="large")
        with left:
            st.markdown(f"### {t('admin_ai_graph_review_lifecycle')}")
            if reviews_df.empty or "status" not in reviews_df.columns:
                st.info(t("admin_ai_empty_data"))
            else:
                review_mix = (
                    reviews_df.groupby("status", as_index=False)
                    .size()
                    .rename(columns={"size": "count"})
                    .sort_values("count", ascending=False)
                )
                review_mix["status"] = review_mix["status"].astype(str).map(humanize_review_status)
                review_series = chart_series(review_mix, "status", "count", "admin_chart_index_status", "admin_chart_value_count")
                if review_series is not None:
                    st.bar_chart(review_series)
        with right:
            st.markdown(f"### {t('admin_ai_graph_ai_usage_by_feature')}")
            if ai_usage_df.empty or "feature_name" not in ai_usage_df.columns:
                st.info(t("admin_ai_empty_data"))
            else:
                success_df = ai_usage_df[ai_usage_df.get("status", pd.Series(dtype=str)).astype(str).str.lower() == "success"].copy()
                usage_mix = (
                    success_df.groupby("feature_name", as_index=False)
                    .size()
                    .rename(columns={"size": "count"})
                    .sort_values("count", ascending=False)
                    .head(10)
                )
                usage_mix["feature_name"] = usage_mix["feature_name"].astype(str).map(humanize_ai_feature_name)
                usage_series = chart_series(usage_mix, "feature_name", "count", "admin_chart_index_metric", "admin_chart_value_count")
                if usage_series is not None:
                    st.bar_chart(usage_series)

        left, right = st.columns(2, gap="large")
        with left:
            st.markdown(f"### {t('admin_ai_graph_practice_subjects')}")
            if practice_df.empty or "subject" not in practice_df.columns:
                st.info(t("admin_ai_empty_data"))
            else:
                practice_subjects = (
                    practice_df.assign(
                        score_pct=pd.to_numeric(practice_df.get("score_pct"), errors="coerce"),
                        subject_norm=practice_df.get("subject", pd.Series(dtype=str)).astype(str).map(lambda value: str(value or "")),
                    )
                    .assign(subject_norm=lambda df: df["subject_norm"].map(lambda value: normalize_subject(str(value or "").strip()) or "other"))
                    .groupby("subject_norm", as_index=False)
                    .agg(sessions=("id", "size"), avg_score=("score_pct", "mean"))
                    .sort_values("sessions", ascending=False)
                    .head(10)
                )
                practice_subjects["label"] = practice_subjects["subject_norm"].astype(str).map(normalized_subject_label)
                practice_series = chart_series(practice_subjects, "label", "sessions", "admin_chart_index_metric", "admin_chart_value_count")
                if practice_series is not None:
                    st.bar_chart(practice_series)
        with right:
            st.markdown(f"### {t('admin_ai_graph_program_progress')}")
            if progress_df.empty:
                st.info(t("admin_ai_empty_data"))
            else:
                summary_df = pd.DataFrame(
                    [
                        {"metric": t("admin_ai_progress_teacher_done"), "count": int(progress_df.get("teacher_done", pd.Series(dtype=bool)).fillna(False).sum())},
                        {"metric": t("admin_ai_progress_student_done"), "count": int(progress_df.get("student_done", pd.Series(dtype=bool)).fillna(False).sum())},
                        {"metric": t("admin_ai_progress_fully_done"), "count": int(progress_df.get("is_done", pd.Series(dtype=bool)).fillna(False).sum())},
                    ]
                )
                progress_series = chart_series(summary_df, "metric", "count", "admin_chart_index_metric", "admin_chart_value_count")
                if progress_series is not None:
                    st.bar_chart(progress_series)

    with model_tab:
        st.markdown(f"### {t('admin_ai_models_live_title')}")
        live_models = [
            {
                "name": t("admin_ai_model_teacher_recommendations"),
                "stage": t("admin_ai_model_stage_live"),
                "goal": t("admin_ai_model_teacher_recommendations_goal"),
                "signals": t("admin_ai_model_teacher_recommendations_signals"),
                "output": t("admin_ai_model_teacher_recommendations_output"),
            },
            {
                "name": t("admin_ai_model_student_recommendations"),
                "stage": t("admin_ai_model_stage_live"),
                "goal": t("admin_ai_model_student_recommendations_goal"),
                "signals": t("admin_ai_model_student_recommendations_signals"),
                "output": t("admin_ai_model_student_recommendations_output"),
            },
            {
                "name": t("admin_ai_model_practice_progress"),
                "stage": t("admin_ai_model_stage_live"),
                "goal": t("admin_ai_model_practice_progress_goal"),
                "signals": t("admin_ai_model_practice_progress_signals"),
                "output": t("admin_ai_model_practice_progress_output"),
            },
            {
                "name": t("admin_ai_model_review_sync"),
                "stage": t("admin_ai_model_stage_live"),
                "goal": t("admin_ai_model_review_sync_goal"),
                "signals": t("admin_ai_model_review_sync_signals"),
                "output": t("admin_ai_model_review_sync_output"),
            },
            {
                "name": t("admin_ai_model_recommendation_acceptance"),
                "stage": t("admin_ai_model_stage_live"),
                "goal": t("admin_ai_model_recommendation_acceptance_goal"),
                "signals": t("admin_ai_model_recommendation_acceptance_signals"),
                "output": t("admin_ai_model_recommendation_acceptance_output"),
            },
            {
                "name": t("admin_ai_model_resource_matching"),
                "stage": t("admin_ai_model_stage_live"),
                "goal": t("admin_ai_model_resource_matching_goal"),
                "signals": t("admin_ai_model_resource_matching_signals"),
                "output": t("admin_ai_model_resource_matching_output"),
            },
        ]
        live_df = pd.DataFrame(live_models).rename(
            columns={
                "name": t("admin_ai_model_name"),
                "stage": t("admin_ai_model_stage"),
                "goal": t("admin_ai_model_goal"),
                "signals": t("admin_ai_model_signals"),
                "output": t("admin_ai_model_output"),
            }
        )
        st.dataframe(live_df, use_container_width=True, hide_index=True)

        st.markdown(f"### {t('admin_ai_models_next_title')}")
        next_models = [
            {
                "name": t("admin_ai_model_next_best_action"),
                "stage": t("admin_ai_model_stage_next"),
                "goal": t("admin_ai_model_next_best_action_goal"),
                "signals": t("admin_ai_model_next_best_action_signals"),
                "output": t("admin_ai_model_next_best_action_output"),
            },
            {
                "name": t("admin_ai_model_student_mastery"),
                "stage": t("admin_ai_model_stage_next"),
                "goal": t("admin_ai_model_student_mastery_goal"),
                "signals": t("admin_ai_model_student_mastery_signals"),
                "output": t("admin_ai_model_student_mastery_output"),
            },
        ]
        next_df = pd.DataFrame(next_models).rename(
            columns={
                "name": t("admin_ai_model_name"),
                "stage": t("admin_ai_model_stage"),
                "goal": t("admin_ai_model_goal"),
                "signals": t("admin_ai_model_signals"),
                "output": t("admin_ai_model_output"),
            }
        )
        st.dataframe(next_df, use_container_width=True, hide_index=True)

    with data_tab:
        dataset_rows = []
        dataset_specs = [
            ("admin_ai_dataset_accounts", "profiles", t("admin_ai_dataset_accounts_purpose"), t("admin_ai_grain_user"), ["created_at", "last_used_at"], 0.95),
            ("admin_ai_dataset_links", "teacher_student_links", t("admin_ai_dataset_links_purpose"), t("admin_ai_grain_teacher_student"), ["updated_at", "created_at"], 0.85),
            ("admin_ai_dataset_program_catalog", "learning_program_topics", t("admin_ai_dataset_program_catalog_purpose"), t("admin_ai_grain_program_topic"), ["updated_at", "created_at"], metrics["topic_linkage_score"]),
            ("admin_ai_dataset_videos", "videos", t("admin_ai_dataset_videos_purpose"), t("admin_ai_grain_video"), ["updated_at", "created_at"], 0.88),
            ("admin_ai_dataset_program_progress", "learning_program_progress", t("admin_ai_dataset_program_progress_purpose"), t("admin_ai_grain_assignment_topic"), ["updated_at", "completed_at", "created_at"], metrics["progress_tracking_score"]),
            ("admin_ai_dataset_assignments", "teacher_assignments", t("admin_ai_dataset_assignments_purpose"), t("admin_ai_grain_assignment"), ["updated_at", "assigned_at", "created_at"], max(metrics["program_alignment_score"], metrics["topic_linkage_score"])),
            ("admin_ai_dataset_attempts", "teacher_assignment_attempts", t("admin_ai_dataset_attempts_purpose"), t("admin_ai_grain_attempt"), ["updated_at", "graded_at", "submitted_at", "created_at"], 0.82),
            ("admin_ai_dataset_recommendations", "learning_program_recommendation_events", t("admin_ai_dataset_recommendations_purpose"), t("admin_ai_grain_event"), ["updated_at", "created_at"], max(metrics["feedback_loop_score"], metrics["recommendation_acceptance_score"])),
            ("admin_ai_dataset_reviews", "teacher_review_requests", t("admin_ai_dataset_reviews_purpose"), t("admin_ai_grain_request"), ["reviewed_at", "requested_at", "created_at"], metrics["review_closure_score"]),
            ("admin_ai_dataset_practice", "practice_sessions", t("admin_ai_dataset_practice_purpose"), t("admin_ai_grain_session"), ["completed_at", "created_at"], 0.9),
            ("admin_ai_dataset_ai_usage", "ai_usage_logs", t("admin_ai_dataset_ai_usage_purpose"), t("admin_ai_grain_activity"), ["created_at"], metrics["ai_success_score"]),
        ]
        for name_key, frame_key, purpose, grain, freshness_cols, readiness_score in dataset_specs:
            frame = frames[frame_key]
            latest = _latest_frame_timestamp(frame, freshness_cols)
            dataset_rows.append(
                {
                    t("admin_ai_dataset_label"): t(name_key),
                    t("admin_ai_dataset_purpose"): purpose,
                    t("admin_ai_dataset_grain"): grain,
                    t("admin_ai_dataset_rows"): int(len(frame)),
                    t("admin_ai_dataset_freshness"): _freshness_label(latest),
                    t("admin_ai_dataset_readiness"): _readiness_label(readiness_score),
                }
            )
        st.dataframe(pd.DataFrame(dataset_rows), use_container_width=True, hide_index=True)

        show_tables = st.toggle(t("admin_ai_show_raw_tables"), key="admin_ai_show_raw_tables")
        if show_tables:
            raw_choice = st.selectbox(
                t("admin_ai_select_dataset"),
                list(frames.keys()),
                format_func=lambda value: t({
                    "profiles": "admin_ai_dataset_accounts",
                    "teacher_student_links": "admin_ai_dataset_links",
                    "learning_program_topics": "admin_ai_dataset_program_catalog",
                    "videos": "admin_ai_dataset_videos",
                    "learning_program_progress": "admin_ai_dataset_program_progress",
                    "teacher_assignments": "admin_ai_dataset_assignments",
                    "teacher_assignment_attempts": "admin_ai_dataset_attempts",
                    "learning_program_recommendation_events": "admin_ai_dataset_recommendations",
                    "teacher_review_requests": "admin_ai_dataset_reviews",
                    "practice_sessions": "admin_ai_dataset_practice",
                    "ai_usage_logs": "admin_ai_dataset_ai_usage",
                    "teacher_student_subjects": "admin_ai_dataset_subject_scopes",
                    "learning_program_assignments": "admin_ai_dataset_program_assignments",
                    "learning_programs": "admin_ai_dataset_programs",
                    "practice_progress": "admin_ai_dataset_progress_aggregates",
                    "user_activity_log": "admin_ai_dataset_activity_log",
                }.get(value, value)),
            )
            st.dataframe(frames.get(raw_choice, pd.DataFrame()), use_container_width=True, hide_index=True)

    with decision_tab:
        decision_rows = _admin_ai_decision_rows(metrics, code_signal)
        for title, body in decision_rows:
            st.markdown(
                f"""
                <div class="admin-kpi-card" style="margin-bottom:10px;">
                    <div class="admin-kpi-label">{_html.escape(title)}</div>
                    <div style="margin-top:8px;font-size:.9rem;line-height:1.5;color:var(--text);">{_html.escape(body)}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )


def _series_from_rows(rows: list[dict], *, period: str = "M", date_key: str = "created_at") -> pd.DataFrame:
    if not rows:
        return pd.DataFrame(columns=["period", "count"])
    df = pd.DataFrame(rows)
    if date_key not in df.columns:
        return pd.DataFrame(columns=["period", "count"])
    df[date_key] = pd.to_datetime(df[date_key], errors="coerce", utc=True)
    df = df.dropna(subset=[date_key]).copy()
    if df.empty:
        return pd.DataFrame(columns=["period", "count"])
    df["period"] = df[date_key].dt.to_period(period).astype(str)
    return df.groupby("period", as_index=False).size().rename(columns={"size": "count"})


def _render_kpi_row(items: list[tuple[str, str]]) -> None:
    cols = st.columns(len(items), gap="medium")
    for col, (label, value) in zip(cols, items):
        with col:
            st.markdown(
                f"""
                <div class="admin-kpi-card">
                    <div class="admin-kpi-label">{_html.escape(label)}</div>
                    <div class="admin-kpi-value">{_html.escape(value)}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )


def _inject_admin_styles() -> None:
    st.markdown(
        """
        <style>
        .admin-hero{
            position:relative;overflow:hidden;border-radius:26px;padding:24px 26px;margin:0 0 1rem 0;
            background:
              radial-gradient(circle at top right, color-mix(in srgb, var(--primary) 22%, transparent), transparent 34%),
              radial-gradient(circle at bottom left, rgba(16,185,129,.18), transparent 36%),
              linear-gradient(135deg, color-mix(in srgb, var(--panel) 94%, white 6%), color-mix(in srgb, var(--panel-soft) 90%, var(--primary) 10%));
            border:1px solid color-mix(in srgb, var(--border) 82%, var(--primary) 18%);
            box-shadow:0 18px 42px rgba(15,23,42,.08);
        }
        .admin-hero-title{font-size:1.5rem;font-weight:900;color:var(--text);letter-spacing:-.02em;}
        .admin-hero-subtitle{margin-top:.45rem;max-width:920px;color:var(--muted);line-height:1.5;}
        .admin-chiprow{display:flex;gap:8px;flex-wrap:wrap;margin-top:14px;}
        .admin-chip{display:inline-flex;align-items:center;border-radius:999px;padding:6px 10px;font-size:.76rem;font-weight:800;background:var(--panel);color:var(--text);border:1px solid var(--border);}
        .admin-kpi-card{
            padding:14px 16px;border-radius:18px;min-height:92px;
            background:linear-gradient(180deg, color-mix(in srgb, var(--panel) 96%, white 4%), color-mix(in srgb, var(--panel-soft) 94%, var(--primary) 6%));
            border:1px solid var(--border);box-shadow:0 10px 24px rgba(15,23,42,.06);
        }
        .admin-kpi-stack-gap{height:1rem;}
        .admin-kpi-label{font-size:.78rem;font-weight:900;color:var(--muted);text-transform:uppercase;letter-spacing:.04em;}
        .admin-kpi-value{margin-top:8px;font-size:1.55rem;font-weight:950;color:var(--text);}
        .admin-section-card{
            border-radius:22px;padding:18px 18px 16px;margin-top:10px;
            background:linear-gradient(180deg, color-mix(in srgb, var(--panel) 96%, white 4%), var(--panel-soft));
            border:1px solid var(--border);box-shadow:0 10px 24px rgba(15,23,42,.05);
        }
        .admin-card-title{font-size:1rem;font-weight:900;color:var(--text);}
        .admin-card-subtitle{margin-top:4px;color:var(--muted);font-size:.84rem;line-height:1.45;}
        .admin-plan-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(230px,1fr));gap:12px;margin-top:12px;}
        .admin-plan-card{
            border-radius:18px;padding:14px;background:var(--panel);border:1px solid var(--border);
        }
        .admin-plan-name{font-size:.98rem;font-weight:900;color:var(--text);}
        .admin-plan-meta{margin-top:4px;color:var(--muted);font-size:.8rem;}
        .admin-plan-price{margin-top:8px;font-size:1.2rem;font-weight:900;color:var(--primary);}
        .admin-user-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:14px;margin-top:12px;}
        .admin-user-card{
            border-radius:20px;padding:16px;background:linear-gradient(180deg, color-mix(in srgb, var(--panel) 96%, white 4%), var(--panel-soft));
            border:1px solid var(--border);box-shadow:0 10px 24px rgba(15,23,42,.05);
        }
        .admin-user-top{display:flex;justify-content:space-between;gap:10px;align-items:flex-start;}
        .admin-user-name{font-size:1rem;font-weight:900;color:var(--text);line-height:1.25;}
        .admin-user-email{margin-top:2px;color:var(--muted);font-size:.82rem;word-break:break-word;}
        .admin-pill-row{display:flex;gap:6px;flex-wrap:wrap;margin-top:10px;}
        .admin-pill{display:inline-flex;align-items:center;border-radius:999px;padding:5px 9px;font-size:.72rem;font-weight:800;background:color-mix(in srgb, var(--primary) 12%, var(--panel));color:var(--primary);border:1px solid color-mix(in srgb, var(--primary) 26%, var(--border));}
        .admin-user-stats{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px;margin-top:12px;}
        .admin-user-stat{border-radius:14px;padding:10px 11px;background:var(--panel);border:1px solid var(--border);}
        .admin-user-stat-label{font-size:.7rem;text-transform:uppercase;letter-spacing:.05em;color:var(--muted);font-weight:800;}
        .admin-user-stat-value{margin-top:4px;font-size:.92rem;font-weight:900;color:var(--text);}
        </style>
        """,
        unsafe_allow_html=True,
    )


def _render_admin_hero(df: pd.DataFrame) -> None:
    metrics = _business_metrics(df)
    chips = [
        t("admin_hero_users_chip", count=metrics["total_users"]),
        t("admin_hero_paid_chip", count=metrics["paid_users"]),
        t("admin_hero_admins_chip", count=metrics["admins"]),
        t("admin_hero_new_30d_chip", count=metrics["new_last_30"]),
    ]
    chip_html = "".join(f"<span class='admin-chip'>{_html.escape(chip)}</span>" for chip in chips)
    st.markdown(
        f"""
        <div class="admin-hero">
            <div class="admin-hero-title">{_html.escape(t('admin'))}</div>
            <div class="admin-hero-subtitle">{_html.escape(t('admin_control_center_caption'))}</div>
            <div class="admin-chiprow">{chip_html}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_overview(df: pd.DataFrame, subscriptions: list[dict]) -> None:
    metrics = _business_metrics(df)
    content = _content_metrics()
    plan_lookup = {str(plan.get("id")): plan for plan in list_plan_catalog()}
    _render_kpi_row(
        [
            (t("admin_metric_users"), str(metrics["total_users"])),
            (t("admin_metric_paid_users"), str(metrics["paid_users"])),
            (t("admin_metric_new_30d"), str(metrics["new_last_30"])),
            (t("admin_metric_suspended"), str(metrics["suspended_users"])),
        ]
    )
    st.markdown("")
    _render_kpi_row(
        [
            (t("admin_metric_worksheets"), str(content["worksheets"])),
            (t("admin_metric_exams"), str(content["exams"])),
            (t("admin_metric_lesson_plans"), str(content["lesson_plans"])),
            (t("admin_metric_ai_events"), str(content["ai_events"])),
        ]
    )

    left, right = st.columns([1.1, 0.9], gap="large")
    with left:
        st.markdown(f"### {t('admin_recent_accounts')}")
        preview = df[["email", "role", "current_plan", "subscription_status", "created_at"]].head(12) if not df.empty else pd.DataFrame()
        if preview.empty:
            st.info(t("admin_no_profiles_found"))
        else:
            plan_lookup = {str(plan.get("id")): plan for plan in list_plan_catalog()}
            preview = preview.copy()
            preview["role"] = preview["role"].astype(str).map(_role_display_label)
            preview["current_plan"] = preview["current_plan"].astype(str).map(lambda value: _plan_display_label(value, plan_lookup))
            preview["subscription_status"] = preview["subscription_status"].astype(str).map(_subscription_status_display_label)
            preview["created_at"] = preview["created_at"].apply(_format_admin_datetime)
            preview = preview.rename(
                columns={
                    "email": t("admin_email_label"),
                    "role": t("admin_role_label"),
                    "current_plan": t("admin_current_plan_label"),
                    "subscription_status": t("admin_subscription_status_label"),
                    "created_at": t("admin_created_at_label"),
                }
            )
            st.dataframe(preview, use_container_width=True, hide_index=True)
    with right:
        st.markdown(f"### {t('admin_plan_mix')}")
        if df.empty:
            st.info(t("admin_no_plan_data"))
        else:
            plan_mix = (
                df.groupby("current_plan", as_index=False)
                .size()
                .rename(columns={"size": "users"})
                .sort_values("users", ascending=False)
            )
            plan_mix["current_plan"] = plan_mix["current_plan"].astype(str).map(lambda value: _plan_display_label(value, plan_lookup))
            overview_series = chart_series(plan_mix, "current_plan", "users", "admin_chart_index_plan", "admin_chart_value_users")
            if overview_series is not None:
                st.bar_chart(overview_series)


def _filter_admin_users(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    search_col, role_col, status_col, plan_col = st.columns([1.5, 1, 1, 1], gap="medium")
    with search_col:
        user_options = [t("admin_all_users")] + [_user_option_label(row) for row in df.to_dict("records")]
        picked_user = st.selectbox(t("admin_quick_pick_user"), user_options, key="admin_ops_user_pick")
    with role_col:
        role_filter = st.multiselect(
            t("admin_role_label"),
            sorted(df["role"].dropna().astype(str).unique().tolist()),
            key="admin_ops_role_filter",
            format_func=_role_display_label,
        )
    with status_col:
        status_filter = st.multiselect(
            t("admin_status_label"),
            sorted(df["account_status"].dropna().astype(str).unique().tolist()),
            key="admin_ops_status_filter",
            format_func=_account_status_display_label,
        )
    with plan_col:
        plan_filter = st.multiselect(
            t("admin_plan_label"),
            sorted(df["current_plan"].dropna().astype(str).unique().tolist()),
            key="admin_ops_plan_filter",
            format_func=_plan_display_label,
        )

    filtered = df.copy()
    if picked_user and picked_user != t("admin_all_users"):
        picked_id = picked_user.rsplit("|", 1)[-1].strip().lower()
        filtered = filtered[filtered.get("user_id", pd.Series(dtype=str)).fillna("").astype(str).str.lower() == picked_id]
    if role_filter:
        filtered = filtered[filtered["role"].astype(str).isin(role_filter)]
    if status_filter:
        filtered = filtered[filtered["account_status"].astype(str).isin(status_filter)]
    if plan_filter:
        filtered = filtered[filtered["current_plan"].astype(str).isin(plan_filter)]
    st.caption(t("admin_matching_users_caption", count=len(filtered)))
    return filtered


def _slice_admin_users_page(df: pd.DataFrame, state_key: str, *, page_size: int = _ADMIN_USERS_PAGE_SIZE):
    if df is None:
        return df, 1, 1, 0, 0, 0
    total_items = len(df)
    total_pages = max(1, math.ceil(total_items / page_size)) if total_items else 1
    current_page = int(st.session_state.get(state_key, 1) or 1)
    current_page = max(1, min(current_page, total_pages))
    st.session_state[state_key] = current_page
    start_idx = (current_page - 1) * page_size
    end_idx = min(start_idx + page_size, total_items)
    page_df = df.iloc[start_idx:end_idx].copy() if total_items else df
    return page_df, current_page, total_pages, start_idx, end_idx, total_items


def _render_admin_users_pagination(df: pd.DataFrame, state_key: str, *, page_size: int = _ADMIN_USERS_PAGE_SIZE) -> None:
    _, current_page, total_pages, start_idx, end_idx, total_items = _slice_admin_users_page(
        df,
        state_key,
        page_size=page_size,
    )
    if total_items <= page_size:
        return

    prev_col, info_col, next_col = st.columns([1, 3, 1])
    with prev_col:
        if st.button("←", key=f"{state_key}_prev", use_container_width=True, disabled=current_page <= 1):
            st.session_state[state_key] = max(1, current_page - 1)
            st.rerun()
    with info_col:
        st.caption(f"{start_idx + 1}-{end_idx} / {total_items} · {current_page}/{total_pages}")
    with next_col:
        if st.button("→", key=f"{state_key}_next", use_container_width=True, disabled=current_page >= total_pages):
            st.session_state[state_key] = min(total_pages, current_page + 1)
            st.rerun()
def _render_users(df: pd.DataFrame) -> None:
    st.markdown(
        f"<div class='admin-section-card'><div class='admin-card-title'>{_html.escape(t('admin_users_directory_title'))}</div><div class='admin-card-subtitle'>{_html.escape(t('admin_users_directory_subtitle'))}</div></div>",
        unsafe_allow_html=True,
    )
    df = _filter_admin_users(df)
    if df.empty:
        st.info(t("admin_no_users_found"))
        return
    plan_lookup = {str(plan.get("id")): plan for plan in list_plan_catalog()}

    preview_df = df.sort_values("created_at", ascending=False, na_position="last").copy()
    preview_df, *_ = _slice_admin_users_page(preview_df, "admin_users_cards_page")
    cards_html = ["<div class='admin-user-grid'>"]
    for idx, (_, row) in enumerate(preview_df.iterrows()):
        name = str(row.get("display_name") or row.get("email") or t("admin_user_fallback_name"))
        email = str(row.get("email") or t("admin_no_email"))
        role = _role_display_label(str(row.get("role") or ""))
        plan = _plan_display_label(str(row.get("current_plan") or "free"), plan_lookup)
        status = _account_status_display_label(str(row.get("account_status") or "active"))
        last_login = _format_admin_datetime(row.get("last_used_at"))
        cards_html.append(
            "<div class='admin-user-card'>"
            f"<div class='admin-user-top'><div><div class='admin-user-name'>{_html.escape(name)}</div><div class='admin-user-email'>{_html.escape(email)}</div></div></div>"
            f"<div class='admin-pill-row'><span class='admin-pill'>{_html.escape(role)}</span><span class='admin-pill'>{_html.escape(plan)}</span><span class='admin-pill'>{_html.escape(status)}</span></div>"
            f"<div class='admin-user-stats'><div class='admin-user-stat'><div class='admin-user-stat-label'>{_html.escape(t('admin_logins_label'))}</div><div class='admin-user-stat-value'>{int(row.get('login_count') or 0)}</div></div><div class='admin-user-stat'><div class='admin-user-stat-label'>{_html.escape(t('admin_students_label'))}</div><div class='admin-user-stat-value'>{int(row.get('active_student_count') or 0)}</div></div><div class='admin-user-stat'><div class='admin-user-stat-label'>{_html.escape(t('admin_last_logged_in_label'))}</div><div class='admin-user-stat-value'>{_html.escape(last_login)}</div></div></div>"
            "</div>"
        )
    cards_html.append("</div>")
    st.markdown("".join(cards_html), unsafe_allow_html=True)
    _render_admin_users_pagination(df.sort_values("created_at", ascending=False, na_position="last").copy(), "admin_users_cards_page")

    show_table = st.toggle(t("admin_open_full_row_data_table"), key="admin_users_show_table")
    if show_table:
        st.dataframe(df, use_container_width=True, hide_index=True)

    row = _selected_user_row(df, "admin_users_select", label_key="admin_select_user_to_edit")
    if not row:
        return
    left, right = st.columns([1.05, 0.95], gap="large")
    with left:
        st.markdown(f"### {t('admin_user_details')}")
        detail_rows = []
        for col in df.columns:
            raw_value = row.get(col)
            if col == "role":
                value = _role_display_label(str(raw_value or ""))
            elif col == "primary_role":
                value = _role_display_label(str(raw_value or ""))
            elif col == "current_plan":
                value = _plan_display_label(str(raw_value or ""), plan_lookup)
            elif col == "subscription_status":
                value = _subscription_status_display_label(str(raw_value or ""))
            elif col == "account_status":
                value = _account_status_display_label(str(raw_value or ""))
            elif col == "last_active_mode":
                value = _mode_display_label(str(raw_value or ""))
            elif col in {"can_teach", "can_study", "manual_override"}:
                value = _bool_display_label(raw_value)
            elif col in {"created_at", "last_used_at"}:
                value = _format_admin_datetime(raw_value)
            else:
                value = raw_value if raw_value not in (None, "") else "—"
            detail_rows.append({"field": _translated_profile_field_label(col), "value": value})
        detail_df = pd.DataFrame(detail_rows).rename(columns={"field": t("admin_field_label"), "value": t("admin_value_label")})
        st.dataframe(detail_df, use_container_width=True, hide_index=True)
    with right:
        st.markdown(f"### {t('admin_edit_user_row')}")
        with st.form("admin_user_inline_edit_form"):
            display_name = st.text_input(t("admin_display_name_label"), value=str(row.get("display_name") or ""))
            email = st.text_input(t("admin_email_label"), value=str(row.get("email") or ""))
            role = st.selectbox(t("admin_role_label"), ADMIN_ROLE_OPTIONS, index=ADMIN_ROLE_OPTIONS.index(str(row.get("role") or "teacher")) if str(row.get("role") or "teacher") in ADMIN_ROLE_OPTIONS else 0, format_func=_role_display_label)
            can_teach = st.checkbox(t("admin_can_teach_label"), value=bool(row.get("can_teach", role in {"teacher", "school_admin", "admin"})))
            can_study = st.checkbox(t("admin_can_study_label"), value=bool(row.get("can_study", role == "student")))
            active_mode_options = _active_mode_options(role, can_teach, can_study)
            current_active_mode = str(row.get("last_active_mode") or active_mode_options[0])
            active_mode = st.selectbox(
                t("admin_default_active_mode_label"),
                active_mode_options,
                index=active_mode_options.index(current_active_mode) if current_active_mode in active_mode_options else 0,
                format_func=_mode_display_label,
            )
            account_status = st.selectbox(t("admin_account_status_label"), ACCOUNT_STATUS_OPTIONS, index=ACCOUNT_STATUS_OPTIONS.index(str(row.get("account_status") or "active")) if str(row.get("account_status") or "active") in ACCOUNT_STATUS_OPTIONS else 0, format_func=_account_status_display_label)
            plan_options = [str(plan.get("id")) for plan in list_plan_catalog()]
            current_plan = str(row.get("current_plan") or "free")
            plan_id = st.selectbox(t("admin_plan_label"), plan_options, index=plan_options.index(current_plan) if current_plan in plan_options else 0, format_func=lambda value: _plan_display_label(value, plan_lookup))
            subscription_status = st.selectbox(t("admin_subscription_status_label"), SUBSCRIPTION_STATUS_OPTIONS, index=SUBSCRIPTION_STATUS_OPTIONS.index(str(row.get("subscription_status") or "free")) if str(row.get("subscription_status") or "free") in SUBSCRIPTION_STATUS_OPTIONS else 0, format_func=_subscription_status_display_label)
            notes = st.text_area(t("admin_notes_label"), value=str(row.get("admin_notes") or ""))
            submitted = st.form_submit_button(t("admin_save_user_row"), type="primary")
            if submitted:
                primary_role = "teacher" if can_teach else "student"
                ok, msg = _update_profile_fields(
                    str(row.get("user_id") or ""),
                    {
                        "display_name": display_name.strip(),
                        "email": email.strip().lower(),
                        "role": role,
                        "primary_role": primary_role,
                        "can_teach": bool(can_teach),
                        "can_study": bool(can_study),
                        "last_active_mode": active_mode,
                        "account_status": account_status,
                        "current_plan": plan_id,
                        "subscription_status": subscription_status,
                        "admin_notes": notes,
                    },
                    f"Updated full user row for {row.get('user_id')}",
                    "user_row_update",
                )
                if ok:
                    try:
                        update_user_plan(str(row.get("user_id") or ""), plan_id, status=subscription_status, manual_override=True)
                    except Exception:
                        pass
                    st.success(msg)
                else:
                    st.error(msg)

        st.markdown("---")
        st.markdown(f"### {t('admin_restart_account_title')}")
        st.caption(t("admin_restart_account_caption"))
        selected_user_id = str(row.get("user_id") or "").strip()
        scope_key = f"admin_restart_scope_{selected_user_id}"
        remove_links_key = f"admin_restart_remove_links_{selected_user_id}"
        archive_shared_key = f"admin_restart_archive_shared_{selected_user_id}"

        restart_scope = st.selectbox(
            t("admin_restart_scope_label"),
            [RESET_SCOPE_STUDENT, RESET_SCOPE_TEACHER, RESET_SCOPE_FULL],
            key=scope_key,
            format_func=_reset_scope_label,
            help=t("admin_restart_scope_help"),
        )
        archive_shared_resources = st.checkbox(
            t("admin_restart_archive_shared_label"),
            value=bool(st.session_state.get(archive_shared_key, True)),
            key=archive_shared_key,
            help=t("admin_restart_archive_shared_help"),
            disabled=restart_scope == RESET_SCOPE_STUDENT,
        )
        remove_relationships = st.checkbox(
            t("admin_restart_remove_relationships_label"),
            value=bool(st.session_state.get(remove_links_key, True)),
            key=remove_links_key,
            help=t("admin_restart_remove_relationships_help"),
        )

        st.markdown(f"#### {t('admin_restart_preview_title')}")
        st.caption(t("admin_restart_preview_caption"))
        preview = build_user_reset_preview(
            selected_user_id,
            restart_scope,
            archive_shared_resources=archive_shared_resources,
            remove_relationships=remove_relationships,
        )
        _render_reset_preview(preview)

        expected_phrase = {
            RESET_SCOPE_STUDENT: "RESTART STUDENT",
            RESET_SCOPE_TEACHER: "RESTART TEACHER",
            RESET_SCOPE_FULL: "RESTART FULL",
        }.get(restart_scope, "RESTART")

        with st.form("admin_restart_user_form"):
            restart_notes = st.text_area(t("admin_restart_account_notes_label"), value=str(row.get("admin_notes") or ""), help=t("admin_restart_account_notes_help"))
            confirm_restart = st.checkbox(t("admin_restart_account_confirm_label"))
            confirmation_text = st.text_input(
                t("admin_restart_account_phrase_label", phrase=expected_phrase),
                help=t("admin_restart_account_phrase_help"),
            )
            restart_submitted = st.form_submit_button(t("admin_restart_account_button"), type="secondary")
            if restart_submitted:
                if not confirm_restart:
                    st.error(t("admin_restart_account_confirm_error"))
                elif confirmation_text.strip().upper() != expected_phrase:
                    st.error(t("admin_restart_account_phrase_error", phrase=expected_phrase))
                else:
                    ok, msg, counters = execute_user_reset(
                        selected_user_id,
                        restart_scope,
                        notes=restart_notes,
                        archive_shared_resources=archive_shared_resources,
                        remove_relationships=remove_relationships,
                    )
                    if ok:
                        audit_reason = (
                            f"{_reset_scope_label(restart_scope)} | "
                            f"{restart_notes or t('admin_restart_account_title')}"
                        )
                        _log_admin_override(selected_user_id, "restart_account", audit_reason)
                        st.success(_reset_scope_success_message(restart_scope))
                        if counters:
                            st.caption(t("admin_restart_account_done_counts", count=sum(int(value or 0) for value in counters.values())))
                        st.rerun()
                    else:
                        st.error(msg)


def _render_accounts(df: pd.DataFrame) -> None:
    st.markdown(
        f"<div class='admin-section-card'><div class='admin-card-title'>{_html.escape(t('admin_create_account_title'))}</div><div class='admin-card-subtitle'>{_html.escape(t('admin_create_account_subtitle'))}</div></div>",
        unsafe_allow_html=True,
    )
    plans = list_plan_catalog()
    plan_ids = [str(plan.get("id")) for plan in plans]
    plan_lookup = {str(plan.get("id")): plan for plan in plans}
    with st.form("admin_create_account_form"):
        display_name = st.text_input(t("admin_display_name_label"))
        email = st.text_input(t("admin_email_label"))
        role = st.selectbox(t("admin_role_label"), ADMIN_ROLE_OPTIONS, index=0, format_func=_role_display_label)
        default_can_teach = role in {"teacher", "school_admin", "admin"}
        default_can_study = role == "student"
        can_teach = st.checkbox(t("admin_can_teach_label"), value=default_can_teach)
        can_study = st.checkbox(t("admin_can_study_label"), value=default_can_study)
        active_mode_options = _active_mode_options(role, can_teach, can_study)
        active_mode = st.selectbox(t("admin_default_active_mode_label"), active_mode_options, index=0, format_func=_mode_display_label)
        subscription_status_default = "free"
        plan_id = st.selectbox(t("admin_initial_plan_label"), plan_ids, index=0 if "free" not in plan_ids else plan_ids.index("free"), format_func=lambda value: _plan_display_label(value, plan_lookup))
        subscription_status = st.selectbox(t("admin_subscription_status_label"), SUBSCRIPTION_STATUS_OPTIONS, index=SUBSCRIPTION_STATUS_OPTIONS.index(subscription_status_default), format_func=_subscription_status_display_label)
        account_status = st.selectbox(t("admin_account_status_label"), ACCOUNT_STATUS_OPTIONS, index=0, format_func=_account_status_display_label)
        notes = st.text_area(t("admin_notes_label"), placeholder=t("admin_notes_placeholder"))
        submitted = st.form_submit_button(t("admin_create_account_button"), type="primary")
        if submitted:
            ok, msg = _create_account(
                email,
                display_name,
                role,
                plan_id,
                account_status,
                notes,
                can_teach=can_teach,
                can_study=can_study,
                active_mode=active_mode,
                subscription_status=subscription_status,
            )
            if ok:
                st.success(t("admin_account_created_success", user_id=msg))
            else:
                st.error(msg)


def _render_roles_and_access(df: pd.DataFrame) -> None:
    if df.empty:
        st.info(t("admin_no_users_available"))
        return
    st.markdown(
        f"<div class='admin-section-card'><div class='admin-card-title'>{_html.escape(t('admin_roles_access_status_title'))}</div><div class='admin-card-subtitle'>{_html.escape(t('admin_roles_access_status_subtitle'))}</div></div>",
        unsafe_allow_html=True,
    )
    row = _selected_user_row(df, "admin_roles_select", label_key="admin_select_user")
    if not row:
        return
    current_role = str(row.get("role") or "teacher")
    plan_options = [str(plan.get("id")) for plan in list_plan_catalog()]
    plan_lookup = {str(plan.get("id")): plan for plan in list_plan_catalog()}
    current_plan = str(row.get("current_plan") or "free")
    with st.form("admin_role_access_form"):
        role = st.selectbox(t("admin_role_label"), ADMIN_ROLE_OPTIONS, index=ADMIN_ROLE_OPTIONS.index(current_role) if current_role in ADMIN_ROLE_OPTIONS else 0, format_func=_role_display_label)
        can_teach = st.checkbox(t("admin_can_teach_label"), value=(role in {"teacher", "school_admin", "admin"}))
        can_study = st.checkbox(t("admin_can_study_label"), value=(role == "student"))
        active_mode_options = ["teacher", "student", "admin"]
        current_active_mode = str(row.get("last_active_mode") or "teacher")
        active_mode = st.selectbox(
            t("admin_default_active_mode_label"),
            active_mode_options,
            index=active_mode_options.index(current_active_mode) if current_active_mode in active_mode_options else 0,
            format_func=_mode_display_label,
        )
        account_status = st.selectbox(t("admin_account_status_label"), ACCOUNT_STATUS_OPTIONS, index=ACCOUNT_STATUS_OPTIONS.index(str(row.get("account_status") or "active")) if str(row.get("account_status") or "active") in ACCOUNT_STATUS_OPTIONS else 0, format_func=_account_status_display_label)
        plan_id = st.selectbox(t("admin_assigned_plan_label"), plan_options, index=plan_options.index(current_plan) if current_plan in plan_options else 0, format_func=lambda value: _plan_display_label(value, plan_lookup))
        subscription_status = st.selectbox(t("admin_subscription_status_label"), SUBSCRIPTION_STATUS_OPTIONS, index=SUBSCRIPTION_STATUS_OPTIONS.index(str(row.get("subscription_status") or "free")) if str(row.get("subscription_status") or "free") in SUBSCRIPTION_STATUS_OPTIONS else 0, format_func=_subscription_status_display_label)
        notes = st.text_area(t("admin_notes_label"), value=str(row.get("admin_notes") or ""))
        submitted = st.form_submit_button(t("admin_save_access_settings"), type="primary")
        if submitted:
            primary_role = "teacher" if can_teach else "student"
            ok, msg = _update_profile_fields(
                str(row.get("user_id") or ""),
                {
                    "role": role,
                    "primary_role": primary_role,
                    "can_teach": bool(can_teach),
                    "can_study": bool(can_study),
                    "last_active_mode": active_mode,
                    "account_status": account_status,
                    "current_plan": plan_id,
                    "subscription_status": subscription_status,
                    "admin_notes": notes,
                },
                f"Role/access updated to role={role}, can_teach={can_teach}, can_study={can_study}, active_mode={active_mode}, account_status={account_status}, plan={plan_id}. {notes}".strip(),
                "role_access",
            )
            if ok:
                try:
                    update_user_plan(str(row.get("user_id") or ""), plan_id, status=subscription_status, manual_override=True)
                except Exception:
                    pass
                st.success(msg)
            else:
                st.error(msg)


def _render_pricing_and_plans() -> None:
    plans = list_plan_catalog()
    plan_lookup = {str(plan.get("id")): plan for plan in plans}
    st.markdown(
        f"<div class='admin-section-card'><div class='admin-card-title'>{_html.escape(t('admin_classio_packages_title'))}</div><div class='admin-card-subtitle'>{_html.escape(t('admin_classio_packages_subtitle'))}</div></div>",
        unsafe_allow_html=True,
    )
    if not plans:
        st.info(t("admin_no_plans_found"))
        return

    control_left, control_right = st.columns([1.1, 0.9], gap="medium")
    with control_left:
        selected_plan_id = st.selectbox(
            t("admin_select_plan"),
            list(plan_lookup.keys()) or ["free"],
            key="admin_plan_select",
            format_func=lambda value: _plan_display_label(value, plan_lookup),
        )
    with control_right:
        default_currency = str(st.session_state.get("admin_plan_preview_currency") or get_preferred_currency() or "USD")
        default_currency = default_currency if default_currency in CURRENCY_CODES else "USD"
        preview_currency = st.selectbox(
            t("payment_currency"),
            CURRENCY_CODES,
            index=CURRENCY_CODES.index(default_currency),
            format_func=lambda c: f"{CURRENCIES[c]['symbol']} {c}",
            key="admin_plan_preview_currency",
        )

    selected_plan = dict(plan_lookup.get(selected_plan_id) or {})
    features = dict(selected_plan.get("features_json") or {})
    feature_flags = _collect_plan_feature_flags(features)
    premium_highlights = _collect_premium_tool_highlights(features)
    feature_label_map = _plan_feature_label_map()
    limits = dict(selected_plan.get("limits_json") or {})
    usd_to_preview = get_exchange_rate("USD", preview_currency) or 1.0
    stored_price_cents = selected_plan.get("price")
    stored_display_amount = 0.0 if stored_price_cents is None else round((int(stored_price_cents or 0) / 100) * usd_to_preview, 2)

    editor_col, preview_col = st.columns([1.05, 1.25], gap="large")
    with editor_col:
        st.markdown(f"### {t('admin_plan_editor_title')}")
        plan_id = st.text_input(t("admin_plan_id_label"), value=str(selected_plan.get("id") or selected_plan_id))
        name = st.text_input(t("admin_plan_name_label"), value=str(selected_plan.get("name") or ""))
        custom_pricing = st.checkbox(t("admin_custom_pricing_label"), value=selected_plan.get("price") is None)
        price_display = st.number_input(
            t("admin_plan_price_label", currency=preview_currency),
            min_value=0.0,
            value=float(stored_display_amount),
            step=1.0,
            disabled=custom_pricing,
            key="admin_plan_price_display",
        )
        billing_options = ["month", "year", "lifetime", "custom"]
        billing_interval = st.selectbox(
            t("admin_billing_interval_label"),
            billing_options,
            index=billing_options.index(str(selected_plan.get("billing_interval") or "month")) if str(selected_plan.get("billing_interval") or "month") in billing_options else 0,
            format_func=lambda value: t(value) if t(value) != value else _fallback_label(value),
        )
        active = st.checkbox(t("admin_active_label"), value=bool(selected_plan.get("active", True)))

        st.markdown(f"#### {t('admin_feature_flags_title')}")
        updated_feature_flags: dict[str, bool] = {}
        for group_key, group_label_key, items in PLAN_FEATURE_GROUPS:
            with st.expander(t(group_label_key), expanded=(group_key == "teacher_workspace")):
                for feature_key, label_key in items:
                    updated_feature_flags[feature_key] = st.checkbox(
                        t(label_key),
                        value=bool(feature_flags.get(feature_key, False)),
                        key=f"admin_plan_feature_{selected_plan_id}_{feature_key}",
                    )
        with st.expander(t("admin_premium_tools_customizer_title"), expanded=False):
            st.caption(t("admin_premium_tools_customizer_caption"))
            updated_premium_highlights: dict[str, bool] = {}
            for feature_key in PREMIUM_TOOL_CANDIDATES:
                updated_premium_highlights[feature_key] = st.checkbox(
                    t(feature_label_map.get(feature_key, feature_key)),
                    value=bool(premium_highlights.get(feature_key, False)),
                    key=f"admin_plan_premium_highlight_{selected_plan_id}_{feature_key}",
                )

        st.markdown(f"#### {t('admin_limits_title')}")
        ai_generations = st.number_input(t("admin_ai_generations_label"), min_value=0, value=int(limits.get("ai_generations") or 0), step=10)
        pdf_exports = st.number_input(t("admin_pdf_exports_label"), min_value=0, value=int(limits.get("pdf_exports") or 0), step=10)
        word_exports = st.number_input(t("admin_word_exports_limit_label"), min_value=0, value=int(limits.get("word_exports") or 0), step=10)
        students_count = st.number_input(t("admin_students_limit_label"), min_value=0, value=int(limits.get("students_count") or 0), step=5)
        classes_count = st.number_input(t("admin_classes_limit_label"), min_value=0, value=int(limits.get("classes_count") or 0), step=10)

        raw_usd_amount = 0.0 if custom_pricing else (float(price_display) / usd_to_preview if usd_to_preview else float(price_display))
        computed_price_cents = None if custom_pricing else int(round(raw_usd_amount * 100))
        if st.button(t("admin_save_plan_button"), type="primary", use_container_width=True):
            ok, msg = _upsert_plan(
                {
                    "id": plan_id.strip(),
                    "name": name.strip(),
                    "price": computed_price_cents,
                    "billing_interval": billing_interval,
                    "active": bool(active),
                    "features_json": {
                        **updated_feature_flags,
                        "premium_tool_highlights": [key for key, enabled in updated_premium_highlights.items() if enabled],
                    },
                    "limits_json": {
                        "ai_generations": int(ai_generations),
                        "pdf_exports": int(pdf_exports),
                        "word_exports": int(word_exports),
                        "students_count": int(students_count),
                        "classes_count": int(classes_count),
                    },
                }
            )
            if ok:
                _log_admin_override("", "plan_update", f"Updated plan {plan_id.strip()}")
                st.success(msg)
                st.rerun()
            else:
                st.error(msg)

    preview_plan = {
        **selected_plan,
        "id": plan_id.strip() or selected_plan_id,
        "name": name.strip() or selected_plan.get("name") or selected_plan_id,
        "price": computed_price_cents,
        "billing_interval": billing_interval,
        "active": bool(active),
        "features_json": {
            **updated_feature_flags,
            "premium_tool_highlights": [key for key, enabled in updated_premium_highlights.items() if enabled],
        },
        "limits_json": {
            "ai_generations": int(ai_generations),
            "pdf_exports": int(pdf_exports),
            "word_exports": int(word_exports),
            "students_count": int(students_count),
            "classes_count": int(classes_count),
        },
    }
    preview_plans = [preview_plan if str(plan.get("id")) == selected_plan_id else plan for plan in plans]

    with preview_col:
        st.markdown(f"### {t('admin_live_preview_title')}")
        st.caption(t("admin_live_preview_caption"))
        render_plan_preview_cards(
            preview_plans,
            preview_currency=preview_currency,
            interactive=False,
            key_prefix="admin_plan_preview",
            show_comparison=False,
        )


def _render_operations(df: pd.DataFrame) -> None:
    st.markdown(
        f"<div class='admin-section-card'><div class='admin-card-title'>{_html.escape(t('admin_operations'))}</div><div class='admin-card-subtitle'>{_html.escape(t('admin_operations_subtitle'))}</div></div>",
        unsafe_allow_html=True,
    )
    tab_accounts, tab_users = st.tabs([
        f"🆕 {t('admin_accounts')}",
        f"👥 {t('admin_users')}",
    ])
    with tab_accounts:
        _render_accounts(df)
    with tab_users:
        _render_users(df)


def _render_subscriptions(df: pd.DataFrame, events: list[dict]) -> None:
    st.markdown(
        f"<div class='admin-section-card'><div class='admin-card-title'>{_html.escape(t('admin_subscription_control_title'))}</div><div class='admin-card-subtitle'>{_html.escape(t('admin_subscription_control_subtitle'))}</div></div>",
        unsafe_allow_html=True,
    )
    plans = list_active_plans()
    plan_ids = [str(plan.get("id")) for plan in plans]
    plan_lookup = {str(plan.get("id")): plan for plan in list_plan_catalog()}
    selected_user_row = _selected_user_row(df, "admin_subscription_selected_user", label_key="admin_user_label") if not df.empty else {}
    selected_user_id = str(selected_user_row.get("user_id") or "").strip()
    if selected_user_row:
        st.caption(
            t(
                "admin_selected_user_summary",
                email=str(selected_user_row.get("email") or t("admin_no_email")),
                plan=_plan_display_label(str(selected_user_row.get("current_plan") or "free"), plan_lookup),
                subscription=_subscription_status_display_label(str(selected_user_row.get("subscription_status") or "free")),
                last_login=_format_admin_datetime(selected_user_row.get("last_used_at")),
            )
        )
    with st.form("admin_plan_form"):
        plan_id = st.selectbox(t("admin_plan_label"), plan_ids, index=0 if plan_ids else None, format_func=lambda value: _plan_display_label(value, plan_lookup))
        status = st.selectbox(t("admin_status_label"), SUBSCRIPTION_STATUS_OPTIONS, index=0, format_func=_subscription_status_display_label)
        reason = st.text_input(t("admin_reason_note_label"), placeholder=t("admin_reason_note_placeholder"))
        submitted = st.form_submit_button(t("admin_assign_plan_grant_access"), type="primary")
        if submitted:
            if not selected_user_id:
                st.error(t("admin_user_id_required"))
            else:
                try:
                    update_user_plan(selected_user_id, plan_id, status=status, manual_override=True)
                    _log_admin_override(selected_user_id, "plan_assignment", reason or f"Assigned {plan_id} with status {status}")
                    _clear_admin_page_caches()
                    st.success(t("admin_plan_updated"))
                except Exception as exc:
                    st.error(str(exc))

    with st.form("admin_user_actions"):
        action_label_map = {
            "reset_usage": t("admin_action_reset_usage"),
            "suspend_user": t("admin_action_suspend_user"),
            "unsuspend_user": t("admin_action_unsuspend_user"),
        }
        action = st.selectbox(
            t("admin_action_label"),
            list(action_label_map.keys()),
            format_func=lambda value: action_label_map.get(str(value), str(value)),
        )
        notes = st.text_area(t("admin_notes_label"))
        submitted = st.form_submit_button(t("admin_apply_action"))
        if submitted:
            if not selected_user_id:
                st.error(t("admin_target_user_id_required"))
            else:
                try:
                    if action == "reset_usage":
                        reset_usage(selected_user_id)
                    elif action == "suspend_user":
                        get_sb().table("profiles").update({"account_status": "suspended", "admin_notes": notes}).eq("user_id", selected_user_id).execute()
                    elif action == "unsuspend_user":
                        get_sb().table("profiles").update({"account_status": "active", "admin_notes": notes}).eq("user_id", selected_user_id).execute()
                    _log_admin_override(selected_user_id, action, notes or action)
                    _clear_admin_page_caches()
                    st.success(t("admin_action_applied"))
                except Exception as exc:
                    st.error(str(exc))

    st.markdown(f"### {t('admin_recent_payment_events')}")
    if events:
        events_df = pd.DataFrame(events).rename(
            columns={
                "provider": t("admin_provider_label"),
                "event_type": t("admin_event_type_label"),
                "processed": t("admin_processed_label"),
                "created_at": t("admin_created_at_label"),
            }
        )
        if t("admin_created_at_label") in events_df.columns:
            events_df[t("admin_created_at_label")] = events_df[t("admin_created_at_label")].apply(_format_admin_datetime)
        if t("admin_processed_label") in events_df.columns:
            events_df[t("admin_processed_label")] = events_df[t("admin_processed_label")].apply(_bool_display_label)
        st.dataframe(events_df, use_container_width=True, hide_index=True)
    else:
        st.info(t("admin_no_payment_events"))


def _render_business_analytics(df: pd.DataFrame, subscriptions: list[dict]) -> None:
    st.markdown(
        f"<div class='admin-section-card'><div class='admin-card-title'>{_html.escape(t('admin_business_analytics_title'))}</div><div class='admin-card-subtitle'>{_html.escape(t('admin_business_analytics_subtitle'))}</div></div>",
        unsafe_allow_html=True,
    )
    signup_rows = _series_from_rows(df.to_dict("records") if not df.empty else [], period="M", date_key="created_at")
    if signup_rows.empty:
        st.info(t("admin_not_enough_profile_data"))
    else:
        st.markdown(f"### {t('admin_signup_trend_title')}")
        signup_series = chart_series(signup_rows, "period", "count", "admin_chart_index_period", "admin_chart_value_signups")
        if signup_series is not None:
            st.line_chart(signup_series)

    if not df.empty:
        plan_lookup = {str(plan.get("id")): plan for plan in list_plan_catalog()}
        plan_mix = (
            df.groupby("current_plan", as_index=False)
            .size()
            .rename(columns={"size": "users"})
            .sort_values("users", ascending=False)
        )
        plan_mix["current_plan"] = plan_mix["current_plan"].astype(str).map(lambda value: _plan_display_label(value, plan_lookup))
        left, right = st.columns(2, gap="large")
        with left:
            st.markdown(f"### {t('admin_accounts_by_plan')}")
            plan_series = chart_series(plan_mix, "current_plan", "users", "admin_chart_index_plan", "admin_chart_value_users")
            if plan_series is not None:
                st.bar_chart(plan_series)
        with right:
            st.markdown(f"### {t('admin_subscription_states')}")
            status_mix = (
                df.groupby("subscription_status", as_index=False)
                .size()
                .rename(columns={"size": "users"})
                .sort_values("users", ascending=False)
            )
            status_mix["subscription_status"] = status_mix["subscription_status"].astype(str).map(_subscription_status_display_label)
            status_series = chart_series(status_mix, "subscription_status", "users", "admin_chart_index_status", "admin_chart_value_users")
            if status_series is not None:
                st.bar_chart(status_series)

    content = _content_metrics()
    st.markdown(f"### {t('admin_product_volume')}")
    volume_df = pd.DataFrame(
        [
            {"metric": t("admin_metric_worksheets"), "count": content["worksheets"]},
            {"metric": t("admin_metric_exams"), "count": content["exams"]},
            {"metric": t("admin_metric_lesson_plans"), "count": content["lesson_plans"]},
            {"metric": t("admin_metric_learning_programs"), "count": content["learning_programs"]},
            {"metric": t("admin_metric_ai_usage_logs"), "count": content["ai_events"]},
        ]
    )
    volume_series = chart_series(volume_df, "metric", "count", "admin_chart_index_metric", "admin_chart_value_count")
    if volume_series is not None:
        st.bar_chart(volume_series)


def _render_audit_log(overrides: list[dict], events: list[dict]) -> None:
    st.markdown(
        f"<div class='admin-section-card'><div class='admin-card-title'>{_html.escape(t('admin_audit_trail_title'))}</div><div class='admin-card-subtitle'>{_html.escape(t('admin_audit_trail_subtitle'))}</div></div>",
        unsafe_allow_html=True,
    )
    if overrides:
        override_df = pd.DataFrame(overrides)
        if "override_type" in override_df.columns:
            override_df["override_type"] = override_df["override_type"].astype(str).map(_override_type_display_label)
            override_mix = (
                override_df.groupby("override_type", as_index=False)
                .size()
                .rename(columns={"size": "count"})
                .sort_values("count", ascending=False)
            )
            st.markdown(f"### {t('admin_override_activity_title')}")
            override_series = chart_series(override_mix, "override_type", "count", "admin_chart_index_action", "admin_chart_value_count")
            if override_series is not None:
                st.bar_chart(override_series)
        renamed_override_df = override_df.rename(
            columns={
                "user_id": t("admin_profile_field_user_id"),
                "override_type": t("admin_action_label"),
                "reason": t("admin_reason_note_label"),
                "created_by": t("admin_created_by_label"),
                "expires_at": t("admin_expires_at_label"),
                "created_at": t("admin_created_at_label"),
            }
        )
        if t("admin_created_at_label") in renamed_override_df.columns:
            renamed_override_df[t("admin_created_at_label")] = renamed_override_df[t("admin_created_at_label")].apply(_format_admin_datetime)
        if t("admin_expires_at_label") in renamed_override_df.columns:
            renamed_override_df[t("admin_expires_at_label")] = renamed_override_df[t("admin_expires_at_label")].apply(_format_admin_datetime)
        st.dataframe(renamed_override_df, use_container_width=True, hide_index=True)
    else:
        st.info(t("admin_no_override_history"))

    st.markdown(f"### {t('admin_payment_event_trail')}")
    if events:
        events_df = pd.DataFrame(events).rename(
            columns={
                "provider": t("admin_provider_label"),
                "event_type": t("admin_event_type_label"),
                "processed": t("admin_processed_label"),
                "created_at": t("admin_created_at_label"),
            }
        )
        if t("admin_created_at_label") in events_df.columns:
            events_df[t("admin_created_at_label")] = events_df[t("admin_created_at_label")].apply(_format_admin_datetime)
        if t("admin_processed_label") in events_df.columns:
            events_df[t("admin_processed_label")] = events_df[t("admin_processed_label")].apply(_bool_display_label)
        st.dataframe(events_df, use_container_width=True, hide_index=True)
    else:
        st.info(t("admin_no_payment_events"))


def render_admin() -> None:
    require_admin()
    _inject_admin_styles()

    profiles = _fetch_profiles("")
    subscriptions = _fetch_subscriptions()
    events = _fetch_events()
    overrides = _fetch_overrides()
    auth_activity = _fetch_auth_user_activity()
    app_activity = _fetch_recent_app_activity()
    df = _merge_profiles_subscriptions(profiles, subscriptions, auth_activity, app_activity)
    _render_admin_hero(df)

    (
        tab_overview,
        tab_operations,
        tab_pricing,
        tab_subscriptions,
        tab_intelligence,
        tab_business,
        tab_audit,
    ) = st.tabs([
        f"📊 {t('admin_overview')}",
        f"🛠️ {t('admin_operations')}",
        f"💳 {t('admin_pricing')}",
        f"🧾 {t('admin_plans_subscriptions')}",
        f"🧠 {t('admin_ai_intelligence')}",
        f"📈 {t('admin_business_analytics')}",
        f"🕒 {t('admin_audit_log')}",
    ])

    with tab_overview:
        _render_overview(df, subscriptions)
    with tab_operations:
        _render_operations(df)
    with tab_pricing:
        _render_pricing_and_plans()
    with tab_subscriptions:
        _render_subscriptions(df, events)
    with tab_intelligence:
        _render_admin_ai_intelligence()
    with tab_business:
        _render_business_analytics(df, subscriptions)
    with tab_audit:
        _render_audit_log(overrides, events)
