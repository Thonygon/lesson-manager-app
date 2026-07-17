from __future__ import annotations

import json
import secrets
import html as _html
import math
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

from app_pages.pricing import render_plan_preview_cards
from core.database import clear_app_caches, get_sb, load_profile_row, upsert_profile_row
from core.i18n import t
from core.navigation import go_to
from core.state import get_current_user_id
from core.timezone import DEFAULT_TZ_NAME, today_local
from helpers.explorer_moves import (
    EXPLORER_MOVE_STATUS_ARCHIVED,
    EXPLORER_MOVE_STATUS_PENDING,
    EXPLORER_MOVE_STATUS_PUBLISHED,
    EXPLORER_MOVE_STATUS_SOLVED,
    assign_explorer_move_to_profile,
    archive_explorer_move,
    explorer_moves_table_available,
    load_explorer_moves_admin,
    persist_explorer_move_payload,
    publish_explorer_move,
)
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
from services.authorization_service import (
    CAPABILITY_VIEW_TECHNICAL_ARTIFACTS,
    current_user_can_access_developer_workspace,
    has_capability,
)
from services import eic_service
from services.eic_display_service import (
    get_business_action_display,
    get_component_display_name,
    get_component_type_display,
    get_evidence_display,
    get_experiment_display_name,
    get_integrity_status_display,
    get_legacy_report_status_display,
    get_model_comparison_column_display,
    get_model_comparison_value_display,
    get_maturity_display,
    get_run_status_display,
    get_staff_role_display,
)
from services.eic_report_service import get_or_create_validated_report, list_available_eic_reports
from services.account_reset_service import (
    RESET_SCOPE_FULL,
    RESET_SCOPE_STUDENT,
    RESET_SCOPE_TEACHER,
    build_user_reset_preview,
    execute_user_reset,
)
from services.auth_service import require_admin
from services.ml_experiment_service import get_latest_validated_run_summary, list_experiment_catalog
from services.staff_roles_service import (
    assign_staff_role,
    list_staff_role_assignments,
    recent_staff_role_changes,
    revoke_staff_role,
    search_profiles_for_staff_access,
)
from services.subscription_service import list_active_plans, list_plan_catalog, reset_usage, update_user_plan


ADMIN_ROLE_OPTIONS = ["teacher", "student", "school_admin", "admin"]
SUBSCRIPTION_STATUS_OPTIONS = ["active", "trialing", "past_due", "cancelled", "free"]
ACCOUNT_STATUS_OPTIONS = ["active", "suspended", "deleted"]
ADMIN_SECTIONS = [
    ("overview", "grid-1x2-fill", "admin_overview"),
    ("operations", "people-fill", "admin_operations"),
    ("pricing", "cash-coin", "admin_pricing"),
    ("subscriptions", "credit-card-2-front-fill", "admin_plans_subscriptions"),
    ("ai_intelligence", "cpu-fill", "admin_ai_intelligence"),
    ("explorer_moves", "compass-fill", "admin_explorer_moves"),
    ("business", "graph-up-arrow", "admin_business_analytics"),
    ("audit", "clock-history", "admin_audit_log"),
]

OPERATIONS_TABS = [
    ("accounts", "person-plus-fill", "admin_accounts"),
    ("users", "people-fill", "admin_users"),
    ("staff_access", "person-lock", "admin_staff_access_title"),
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
_ADMIN_OVERRIDE_COLUMNS = (
    "id,user_id,override_type,old_value,new_value,note,admin_user_id,admin_email,created_at"
)
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
    "explorer_move_preview_open": "admin_override_type_explorer_move_preview_open",
    "explorer_move_preview_close": "admin_override_type_explorer_move_preview_close",
    "explorer_move_publish": "admin_override_type_explorer_move_publish",
    "explorer_move_archive": "admin_override_type_explorer_move_archive",
    "explorer_move_assign": "admin_override_type_explorer_move_assign",
    "explorer_move_assign_duplicate": "admin_override_type_explorer_move_assign_duplicate",
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

MODEL_REPORT_SPECS = [
    {
        "key": "student_recommendations",
        "label_key": "admin_model_reports_student_label",
        "description_key": "admin_model_reports_student_description",
        "status": "live",
        "report_dir": "student_recommendation_project",
    },
    {
        "key": "teacher_recommendations",
        "label_key": "admin_model_reports_teacher_label",
        "description_key": "admin_model_reports_teacher_description",
        "status": "live",
        "report_dir": "teacher_recommendation_project",
    },
    {
        "key": "practice_progress",
        "label_key": "admin_model_reports_practice_label",
        "description_key": "admin_model_reports_practice_description",
        "status": "planned",
        "report_dir": "practice_progress_project",
    },
    {
        "key": "review_sync",
        "label_key": "admin_model_reports_review_label",
        "description_key": "admin_model_reports_review_description",
        "status": "planned",
        "report_dir": "review_sync_project",
    },
    {
        "key": "resource_matching",
        "label_key": "admin_model_reports_resource_label",
        "description_key": "admin_model_reports_resource_description",
        "status": "planned",
        "report_dir": "resource_matching_project",
    },
]

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


def _render_report_action_row(
    *,
    row_key: str,
    generate_label: str,
    download_label: str,
    generate_action,
    download_path: Path,
    comment_text: str,
    success_text: str,
    error_text_prefix: str,
    disabled: bool = False,
) -> None:
    generate_col, download_col, comment_col = st.columns(3)
    with generate_col:
        if st.button(generate_label, key=f"{row_key}_generate", use_container_width=True, disabled=disabled):
            try:
                if disabled:
                    return
                generate_action()
                if success_text:
                    st.success(success_text)
            except Exception as exc:
                if error_text_prefix:
                    st.error(f"{error_text_prefix}: {exc}")
    with download_col:
        if not disabled and download_path.exists():
            st.download_button(
                download_label,
                data=download_path.read_bytes(),
                file_name=download_path.name,
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                key=f"{row_key}_download",
                use_container_width=True,
            )
        else:
            st.button(download_label, key=f"{row_key}_download_disabled", use_container_width=True, disabled=True)
    with comment_col:
        st.caption(comment_text)


def _store_model_report_result(report_state: dict, model_key: str, variant_key: str, result: dict) -> None:
    model_state = report_state.get(model_key) or {}
    model_state = {**model_state, variant_key: result}
    updated_state = {**report_state, model_key: model_state}
    st.session_state["admin_model_reports"] = updated_state


def _load_json_artifact(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


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
def _fetch_subscriptions(user_ids: tuple[str, ...] = ()) -> list[dict]:
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
            .select(_ADMIN_OVERRIDE_COLUMNS)
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
def _fetch_recent_app_activity(user_ids: tuple[str, ...] = ()) -> dict[str, str]:
    usage: dict[str, str] = {}
    safe_user_ids = [str(user_id or "").strip() for user_id in user_ids if str(user_id or "").strip()]
    if not safe_user_ids:
        return usage

    def _remember(user_id: Any, *timestamps: Any) -> None:
        safe_user_id = str(user_id or "").strip()
        if not safe_user_id:
            return
        usage[safe_user_id] = _latest_timestamp(usage.get(safe_user_id, ""), *timestamps)

    try:
        profile_rows = getattr(
            get_sb().table("profiles").select("user_id,last_used_at").in_("user_id", safe_user_ids).limit(len(safe_user_ids)).execute(),
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
                get_sb().table(table_name).select(select_columns).in_(user_column, safe_user_ids).limit(5000).execute(),
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
    video_rows = _minimal_rows("videos")
    program_rows = _minimal_rows("learning_programs")
    ai_rows = _minimal_rows("ai_usage_logs")
    return {
        "worksheets": len(worksheet_rows),
        "exams": len(exam_rows),
        "lesson_plans": len(plan_rows),
        "videos": len(video_rows),
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
            "ai_events": int(len(ai_usage_df)),
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


def _render_admin_eic() -> None:
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
        (t("admin_metric_ai_events"), str(metrics["ai_events"])),
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
        st.caption("Browse the live intelligence systems running in Classio today. Use the component picker to inspect the current mechanism, product role, evidence maturity, and recommended next action.")
        _render_admin_intelligence_systems_browser()

        st.markdown(f"### {t('admin_eic_legacy_diagnostics_title')}")
        st.caption(t("admin_eic_legacy_diagnostics_caption"))
        report_state = st.session_state.get("admin_model_reports") or {}
        admin_profile = load_profile_row(str(get_current_user_id() or "").strip())
        report_lang = str((admin_profile or {}).get("preferred_ui_language") or st.session_state.get("ui_lang") or "en").strip().lower()
        if report_lang not in ("en", "es", "tr"):
            report_lang = "en"

        for spec in MODEL_REPORT_SPECS:
            expanded = spec["key"] == "student_recommendations"
            with st.expander(t(spec["label_key"]), expanded=expanded):
                st.caption(t(spec["description_key"]))
                report_dir = Path("reports") / str(spec.get("report_dir") or spec["key"])
                if spec["key"] == "student_recommendations":
                    student_state = report_state.get("student_recommendations") or {}
                    single_path = Path(
                        str(
                            (student_state.get("single_student") or {}).get("docx_path")
                            or report_dir / "classio_ml_student_recommendation_report_single_student.docx"
                        )
                    )
                    multi_path = Path(
                        str(
                            (student_state.get("multi_student") or {}).get("docx_path")
                            or report_dir / "classio_ml_student_recommendation_report_multi_student.docx"
                        )
                    )
                    single_state = student_state.get("single_student") or {}
                    multi_state = student_state.get("multi_student") or {}
                    single_student = str(single_state.get("student_id") or "")
                    multi_samples = int(((multi_state.get("diagnostics") or {}).get("sample_count") or 0))
                    _render_report_action_row(
                        row_key="admin_student_single_report",
                        generate_label=t("admin_model_reports_generate_student_single_button"),
                        download_label=t("admin_model_reports_download_button"),
                        generate_action=lambda: _store_model_report_result(
                            report_state,
                            "student_recommendations",
                            "single_student",
                            __import__("scripts.generate_student_recommendation_report", fromlist=["generate_report"]).generate_report(report_dir, scope="single_student", lang=report_lang),
                        ),
                        download_path=single_path,
                        comment_text=t("admin_model_reports_student_single_comment", student_id=single_student if single_student else "n/a"),
                        success_text=t("admin_model_reports_student_single_success"),
                        error_text_prefix=t("admin_model_reports_student_single_error"),
                    )
                    _render_report_action_row(
                        row_key="admin_student_multi_report",
                        generate_label=t("admin_model_reports_generate_student_multi_button"),
                        download_label=t("admin_model_reports_download_button"),
                        generate_action=lambda: _store_model_report_result(
                            report_state,
                            "student_recommendations",
                            "multi_student",
                            __import__("scripts.generate_student_recommendation_report", fromlist=["generate_report"]).generate_report(report_dir, scope="multi_student", lang=report_lang),
                        ),
                        download_path=multi_path,
                        comment_text=t("admin_model_reports_student_multi_comment", samples=multi_samples),
                        success_text=t("admin_model_reports_student_multi_success"),
                        error_text_prefix=t("admin_model_reports_student_multi_error"),
                    )
                elif spec["key"] == "teacher_recommendations":
                    teacher_state = report_state.get("teacher_recommendations") or {}
                    single_path = Path(
                        str(
                            (teacher_state.get("single_teacher") or {}).get("docx_path")
                            or report_dir / "classio_ml_teacher_recommendation_report_single_teacher.docx"
                        )
                    )
                    multi_path = Path(
                        str(
                            (teacher_state.get("multi_teacher") or {}).get("docx_path")
                            or report_dir / "classio_ml_teacher_recommendation_report_multi_teacher.docx"
                        )
                    )
                    single_state = teacher_state.get("single_teacher") or {}
                    multi_state = teacher_state.get("multi_teacher") or {}
                    single_teacher = str(single_state.get("teacher_id") or "")
                    multi_samples = int(((multi_state.get("diagnostics") or {}).get("sample_count") or 0))
                    _render_report_action_row(
                        row_key="admin_teacher_single_report",
                        generate_label=t("admin_model_reports_generate_teacher_single_button"),
                        download_label=t("admin_model_reports_download_button"),
                        generate_action=lambda: _store_model_report_result(
                            report_state,
                            "teacher_recommendations",
                            "single_teacher",
                            __import__("scripts.generate_teacher_recommendation_report", fromlist=["generate_report"]).generate_report(report_dir, scope="single_teacher", lang=report_lang),
                        ),
                        download_path=single_path,
                        comment_text=t("admin_model_reports_teacher_single_comment", teacher_id=single_teacher if single_teacher else "n/a"),
                        success_text=t("admin_model_reports_teacher_single_success"),
                        error_text_prefix=t("admin_model_reports_teacher_single_error"),
                    )
                    _render_report_action_row(
                        row_key="admin_teacher_multi_report",
                        generate_label=t("admin_model_reports_generate_teacher_multi_button"),
                        download_label=t("admin_model_reports_download_button"),
                        generate_action=lambda: _store_model_report_result(
                            report_state,
                            "teacher_recommendations",
                            "multi_teacher",
                            __import__("scripts.generate_teacher_recommendation_report", fromlist=["generate_report"]).generate_report(report_dir, scope="multi_teacher", lang=report_lang),
                        ),
                        download_path=multi_path,
                        comment_text=t("admin_model_reports_teacher_multi_comment", samples=multi_samples),
                        success_text=t("admin_model_reports_teacher_multi_success"),
                        error_text_prefix=t("admin_model_reports_teacher_multi_error"),
                    )
                else:
                    st.info(t("admin_model_reports_placeholder_info"))
                    _render_report_action_row(
                        row_key=f"admin_placeholder_single_{spec['key']}",
                        generate_label=t("admin_model_reports_generate_single_button"),
                        download_label=t("admin_model_reports_download_button"),
                        generate_action=lambda: None,
                        download_path=Path("__missing__"),
                        comment_text=t("admin_model_reports_placeholder_single_comment"),
                        success_text="",
                        error_text_prefix="",
                        disabled=True,
                    )
                    _render_report_action_row(
                        row_key=f"admin_placeholder_multi_{spec['key']}",
                        generate_label=t("admin_model_reports_generate_aggregate_button"),
                        download_label=t("admin_model_reports_download_button"),
                        generate_action=lambda: None,
                        download_path=Path("__missing__"),
                        comment_text=t("admin_model_reports_placeholder_multi_comment"),
                        success_text="",
                        error_text_prefix="",
                        disabled=True,
                    )

        st.markdown("### Validated Supervised Experiment Status")
        st.caption("The approved assigned-resource experiment now lives in the separate Developer Workspace. Normal Admin keeps only the latest validated summary.")
        _render_admin_validated_experiment_summary()

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
        .admin-explorer-status-row{display:flex;justify-content:flex-end;margin-bottom:10px;}
        .admin-explorer-status-badge{display:inline-flex;align-items:center;border-radius:999px;padding:6px 11px;font-size:.72rem;font-weight:900;letter-spacing:.02em;box-shadow:0 8px 18px rgba(15,23,42,.08);border:1px solid transparent;backdrop-filter:blur(8px);}
        .admin-explorer-status-badge--pending{background:linear-gradient(180deg, rgba(245,158,11,.18), rgba(245,158,11,.10));color:#b45309;border-color:rgba(245,158,11,.26);}
        .admin-explorer-status-badge--published{background:linear-gradient(180deg, rgba(59,130,246,.18), rgba(59,130,246,.10));color:#1d4ed8;border-color:rgba(59,130,246,.24);}
        .admin-explorer-status-badge--solved{background:linear-gradient(180deg, rgba(16,185,129,.18), rgba(16,185,129,.10));color:#047857;border-color:rgba(16,185,129,.24);}
        .admin-explorer-status-badge--archived{background:linear-gradient(180deg, rgba(100,116,139,.18), rgba(100,116,139,.10));color:#475569;border-color:rgba(100,116,139,.22);}
        .admin-user-stats{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px;margin-top:12px;}
        .admin-user-stat{border-radius:14px;padding:10px 11px;background:var(--panel);border:1px solid var(--border);}
        .admin-user-stat-label{font-size:.7rem;text-transform:uppercase;letter-spacing:.05em;color:var(--muted);font-weight:800;}
        .admin-user-stat-value{margin-top:4px;font-size:.92rem;font-weight:900;color:var(--text);}
        .admin-eic-header-card{
            border-radius:24px;padding:22px 22px 18px;margin-top:10px;
            background:
              radial-gradient(circle at top right, color-mix(in srgb, var(--primary) 18%, transparent), transparent 36%),
              radial-gradient(circle at bottom left, rgba(16,185,129,.14), transparent 34%),
              linear-gradient(180deg, color-mix(in srgb, var(--panel) 96%, white 4%), var(--panel-soft));
            border:1px solid color-mix(in srgb, var(--border) 84%, var(--primary) 16%);
            box-shadow:0 14px 32px rgba(15,23,42,.07);
        }
        .admin-eic-meta{display:flex;gap:8px;flex-wrap:wrap;margin-top:14px;}
        .admin-eic-badge{
            display:inline-flex;align-items:center;border-radius:999px;padding:6px 10px;font-size:.74rem;font-weight:900;
            border:1px solid color-mix(in srgb, var(--border) 70%, var(--primary) 30%);
            background:color-mix(in srgb, var(--panel) 88%, white 12%);color:var(--text);
        }
        .admin-eic-badge--healthy{background:rgba(16,185,129,.14);color:#047857;border-color:rgba(16,185,129,.28);}
        .admin-eic-badge--attention{background:rgba(245,158,11,.16);color:#b45309;border-color:rgba(245,158,11,.28);}
        .admin-eic-badge--collecting{background:rgba(59,130,246,.14);color:#1d4ed8;border-color:rgba(59,130,246,.24);}
        .admin-eic-badge--restricted{background:rgba(100,116,139,.14);color:#475569;border-color:rgba(100,116,139,.24);}
        .admin-eic-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:12px;margin-top:12px;}
        .admin-eic-card{
            border-radius:20px;padding:16px 16px 14px;background:linear-gradient(180deg, color-mix(in srgb, var(--panel) 96%, white 4%), var(--panel-soft));
            border:1px solid var(--border);box-shadow:0 10px 24px rgba(15,23,42,.05);
        }
        .admin-eic-card-title{font-size:1rem;font-weight:900;color:var(--text);line-height:1.3;}
        .admin-eic-card-subtitle{margin-top:6px;color:var(--muted);font-size:.84rem;line-height:1.45;}
        .admin-eic-card-copy{margin-top:10px;color:var(--text);font-size:.9rem;line-height:1.5;}
        .admin-eic-card-list{margin:10px 0 0 18px;color:var(--text);font-size:.9rem;line-height:1.55;}
        .admin-eic-card-list li{margin-bottom:4px;}
        .admin-eic-card-foot{margin-top:12px;padding-top:10px;border-top:1px solid var(--border);color:var(--muted);font-size:.82rem;line-height:1.45;}
        .admin-eic-report-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:12px;margin-top:10px;}
        .admin-eic-report-note{margin-top:10px;color:var(--muted);font-size:.83rem;line-height:1.45;}
        .admin-eic-empty{
            border-radius:18px;padding:14px 16px;background:linear-gradient(180deg, color-mix(in srgb, var(--panel-soft) 95%, white 5%), var(--panel));
            border:1px dashed var(--border);color:var(--muted);
        }
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
            (t("admin_ai_metric_videos"), str(content["videos"])),
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


def _render_staff_access() -> None:
    st.markdown(
        "<div class='admin-section-card'><div class='admin-card-title'>Staff Access</div><div class='admin-card-subtitle'>Assign or revoke technical staff roles without changing the user’s product role.</div></div>",
        unsafe_allow_html=True,
    )
    search_value = st.text_input("Search users", key="admin_staff_access_search", placeholder="Name, email, or user id")
    users = search_profiles_for_staff_access(search_value, limit=40, cache_bust=str(st.session_state.get("admin_staff_access_refresh_nonce") or 0))
    if not users:
        st.info("No matching users found.")
        return

    options = [
        f"{str(row.get('display_name') or row.get('email') or 'User').strip()} | {str(row.get('email') or '').strip()} | {str(row.get('user_id') or '').strip()}"
        for row in users
    ]
    picked = st.selectbox("User", options, key="admin_staff_access_user")
    picked_user_id = picked.rsplit("|", 1)[-1].strip()
    selected_user = next((row for row in users if str(row.get("user_id") or "").strip() == picked_user_id), {})
    assignments = list_staff_role_assignments(user_id=picked_user_id, cache_bust=str(st.session_state.get("admin_staff_access_refresh_nonce") or 0))
    active_assignments = [row for row in assignments if bool(row.get("is_active"))]
    active_roles = [str(row.get("role_key") or "") for row in active_assignments]

    summary_cols = st.columns(4, gap="small")
    summary_cards = [
        ("Product Role", _role_display_label(str(selected_user.get("role") or "teacher"))),
        ("Primary Role", _role_display_label(str(selected_user.get("primary_role") or str(selected_user.get("role") or "teacher")))),
        ("Active Staff Roles", ", ".join(active_roles) if active_roles else "None"),
        ("User ID", picked_user_id or "n/a"),
    ]
    for col, (label, value) in zip(summary_cols, summary_cards):
        with col:
            st.markdown(
                f"""
                <div class="admin-kpi-card">
                    <div class="admin-kpi-label">{_html.escape(label)}</div>
                    <div class="admin-kpi-value" style="font-size:1rem;">{_html.escape(value)}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    st.caption("Technical staff roles are additive. They do not replace teacher, student, admin, or school roles.")
    st.markdown("#### Active Technical Roles")
    if active_assignments:
        st.dataframe(
            pd.DataFrame(active_assignments)[["role_key", "assigned_at", "assigned_by", "assignment_reason"]],
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info("This user has no active technical staff roles.")

    assign_col, revoke_col = st.columns(2, gap="large")
    with assign_col:
        st.markdown("##### Assign Role")
        with st.form("admin_staff_access_assign_form"):
            role_key = st.selectbox("Staff role", ["developer", "data_scientist"], key="admin_staff_access_assign_role")
            reason = st.text_area("Assignment reason", key="admin_staff_access_assign_reason")
            confirm = st.checkbox("I confirm that I want to assign this technical staff role.", key="admin_staff_access_assign_confirm")
            submitted = st.form_submit_button("Assign technical role", type="primary")
            if submitted:
                if not confirm:
                    st.error("Explicit confirmation is required before assigning a staff role.")
                else:
                    ok, message = assign_staff_role(target_user_id=picked_user_id, role_key=role_key, assignment_reason=reason)
                    if ok:
                        st.success(message)
                        st.session_state["admin_staff_access_refresh_nonce"] = int(st.session_state.get("admin_staff_access_refresh_nonce") or 0) + 1
                        st.rerun()
                    else:
                        st.error(message)
    with revoke_col:
        st.markdown("##### Revoke Role")
        revoke_options = {
            f"{str(row.get('role_key') or '')} | assigned {str(row.get('assigned_at') or '')}": row
            for row in active_assignments
        }
        with st.form("admin_staff_access_revoke_form"):
            revoke_label = st.selectbox("Active assignment", list(revoke_options.keys()) or ["No active role"], key="admin_staff_access_revoke_role")
            reason = st.text_area("Revocation reason", key="admin_staff_access_revoke_reason")
            confirm = st.checkbox("I confirm that I want to revoke this active technical staff role.", key="admin_staff_access_revoke_confirm")
            submitted = st.form_submit_button("Revoke technical role", type="secondary", disabled=not bool(revoke_options))
            if submitted:
                if not confirm:
                    st.error("Explicit confirmation is required before revoking a staff role.")
                else:
                    target_row = revoke_options.get(revoke_label) or {}
                    ok, message = revoke_staff_role(
                        assignment_id=target_row.get("id"),
                        target_user_id=picked_user_id,
                        role_key=str(target_row.get("role_key") or ""),
                        revoke_reason=reason,
                    )
                    if ok:
                        st.success(message)
                        st.session_state["admin_staff_access_refresh_nonce"] = int(st.session_state.get("admin_staff_access_refresh_nonce") or 0) + 1
                        st.rerun()
                    else:
                        st.error(message)

    st.markdown("#### Recent Staff Role Changes")
    changes = recent_staff_role_changes(limit=25)
    if changes:
        st.dataframe(
            pd.DataFrame(changes)[["user_id", "role_key", "is_active", "assigned_at", "assigned_by", "revoked_at", "revoked_by", "assignment_reason"]],
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info("No staff-role changes have been recorded yet.")


def _render_admin_validated_experiment_summary() -> None:
    validated = get_latest_validated_run_summary(cache_bust=str(st.session_state.get("admin_ai_validated_refresh_nonce") or 0))
    cards = st.columns(4, gap="small")
    values = [
        ("Validated Run", str(validated.get("run_id") or "No validated run yet")),
        ("Run Status", str(validated.get("run_status") or "No validated run yet")),
        ("Integrity", str(validated.get("integrity_status") or "n/a")),
        ("Primary Leader", str(validated.get("primary_metric_leader") or "n/a")),
    ]
    for col, (label, value) in zip(cards, values):
        with col:
            st.markdown(
                f"""
                <div class="admin-kpi-card">
                    <div class="admin-kpi-label">{_html.escape(label)}</div>
                    <div class="admin-kpi-value" style="font-size:1rem;">{_html.escape(value)}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
    if validated:
        st.caption(
            "Latest validated summary: "
            f"{int(validated.get('included_row_count') or 0)} mature labels, "
            f"{int(validated.get('positive_label_count') or 0)} positives, "
            f"{int(validated.get('negative_label_count') or 0)} negatives."
        )
    else:
        st.info("No validated run yet.")
    if current_user_can_access_developer_workspace():
        if st.button("Open Developer Workspace", key="admin_open_developer_workspace", use_container_width=False):
            go_to("developer_workspace")
            st.rerun()


def _admin_clean_text(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def _translate_eic_value(value: str) -> str:
    safe_value = _admin_clean_text(value)
    key = f"admin_eic_value_{safe_value.lower()}"
    translated = t(key)
    return translated if translated != key else safe_value


def _decision_action_key(action: str) -> str:
    mapping = {
        "Continue collecting data": "admin_eic_action_continue_collecting_data",
        "Reevaluate later": "admin_eic_action_reevaluate_later",
        "Maintain current logic": "admin_eic_action_maintain_current_logic",
        "Improve exposure matching": "admin_eic_action_improve_exposure_matching",
        "continue_collecting_data": "admin_eic_action_continue_collecting_data",
        "reevaluate_later": "admin_eic_action_reevaluate_later",
        "maintain_current_logic": "admin_eic_action_maintain_current_logic",
        "improve_exposure_matching": "admin_eic_action_improve_exposure_matching",
        "expand_teacher_coverage": "admin_eic_action_expand_teacher_coverage",
        "Continue telemetry collection before supervised training.": "admin_eic_action_continue_collecting_data",
        "Keep as heuristic-plus-affinity ranker.": "admin_eic_action_maintain_current_logic",
        "Keep as feature engineering, not as a standalone ML claim.": "admin_eic_action_maintain_current_logic",
        "Retire the acceptance framing until real labels exist.": "admin_eic_action_continue_collecting_data",
        "Expand teacher coverage and continue collecting labels.": "admin_eic_action_expand_teacher_coverage",
        "Maintain current logic and monitor data quality.": "admin_eic_action_maintain_current_logic",
        "Maintain deterministic logic.": "admin_eic_action_maintain_current_logic",
        "Improve exposure matching and grow real usage.": "admin_eic_action_improve_exposure_matching",
        "Maintain and monitor.": "admin_eic_action_maintain_current_logic",
    }
    return mapping.get(_admin_clean_text(action), "admin_eic_action_reevaluate_later")


def _telemetry_percent(value: Any) -> str:
    try:
        return f"{round(float(value or 0.0) * 100.0, 1)}%"
    except Exception:
        return "0.0%"


def _legacy_report_rows() -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for spec in MODEL_REPORT_SPECS:
        report_dir = Path("reports") / str(spec.get("report_dir") or spec["key"])
        rows.append(
            {
                t("admin_eic_legacy_name"): t(spec["label_key"]),
                t("admin_eic_legacy_status"): get_legacy_report_status_display("live" if report_dir.exists() else "planned"),
                t("admin_eic_legacy_note"): t("admin_eic_legacy_diagnostic_warning"),
            }
        )
    return rows


def _render_staff_access() -> None:
    st.markdown(
        f"<div class='admin-section-card'><div class='admin-card-title'>{_html.escape(t('admin_staff_access_title'))}</div><div class='admin-card-subtitle'>{_html.escape(t('admin_staff_access_subtitle'))}</div></div>",
        unsafe_allow_html=True,
    )
    search_value = st.text_input(
        t("admin_staff_access_search_users"),
        key="admin_staff_access_search",
        placeholder=t("admin_staff_access_search_placeholder"),
    )
    users = search_profiles_for_staff_access(search_value, limit=40, cache_bust=str(st.session_state.get("admin_staff_access_refresh_nonce") or 0))
    if not users:
        st.info(t("admin_staff_access_no_matching_users"))
        return

    options = [
        f"{str(row.get('display_name') or row.get('email') or t('admin_staff_access_user_fallback')).strip()} | {str(row.get('email') or '').strip()} | {str(row.get('user_id') or '').strip()}"
        for row in users
    ]
    picked = st.selectbox(t("admin_staff_access_user_label"), options, key="admin_staff_access_user")
    picked_user_id = picked.rsplit("|", 1)[-1].strip()
    selected_user = next((row for row in users if str(row.get("user_id") or "").strip() == picked_user_id), {})
    assignments = list_staff_role_assignments(user_id=picked_user_id, cache_bust=str(st.session_state.get("admin_staff_access_refresh_nonce") or 0))
    active_assignments = [row for row in assignments if bool(row.get("is_active"))]
    active_roles = [get_staff_role_display(str(row.get("role_key") or "")) for row in active_assignments]

    summary_cols = st.columns(4, gap="small")
    summary_cards = [
        (t("admin_staff_access_product_role"), _role_display_label(str(selected_user.get("role") or "teacher"))),
        (t("admin_staff_access_primary_role"), _role_display_label(str(selected_user.get("primary_role") or str(selected_user.get("role") or "teacher")))),
        (t("admin_staff_access_active_roles"), ", ".join(active_roles) if active_roles else t("admin_staff_access_none")),
        (t("admin_staff_access_user_id"), picked_user_id or "n/a"),
    ]
    for col, (label, value) in zip(summary_cols, summary_cards):
        with col:
            st.markdown(
                f"""
                <div class="admin-kpi-card">
                    <div class="admin-kpi-label">{_html.escape(label)}</div>
                    <div class="admin-kpi-value" style="font-size:1rem;">{_html.escape(value)}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    st.caption(t("admin_staff_access_additive_caption"))
    st.markdown(f"#### {t('admin_staff_access_active_roles_heading')}")
    if active_assignments:
        active_df = pd.DataFrame(active_assignments)[["role_key", "assigned_at", "assigned_by", "assignment_reason"]].copy()
        active_df["role_key"] = active_df["role_key"].astype(str).map(get_staff_role_display)
        active_df = active_df.rename(
            columns={
                "role_key": t("admin_staff_access_role_label"),
                "assigned_at": t("admin_assigned_at_label"),
                "assigned_by": t("admin_assigned_by_label"),
                "assignment_reason": t("admin_staff_access_assignment_reason"),
            }
        )
        st.dataframe(active_df, use_container_width=True, hide_index=True)
    else:
        st.info(t("admin_staff_access_no_active_roles"))

    assign_col, revoke_col = st.columns(2, gap="large")
    with assign_col:
        st.markdown(f"##### {t('admin_staff_access_assign_heading')}")
        with st.form("admin_staff_access_assign_form"):
            staff_role_options = ["developer", "data_scientist"]
            role_key = st.selectbox(
                t("admin_staff_access_role_label"),
                staff_role_options,
                key="admin_staff_access_assign_role",
                format_func=get_staff_role_display,
            )
            reason = st.text_area(t("admin_staff_access_assignment_reason"), key="admin_staff_access_assign_reason")
            confirm = st.checkbox(t("admin_staff_access_assign_confirm"), key="admin_staff_access_assign_confirm")
            submitted = st.form_submit_button(t("admin_staff_access_assign_button"), type="primary")
            if submitted:
                if not confirm:
                    st.error(t("admin_staff_access_assign_confirm_error"))
                else:
                    ok, message = assign_staff_role(target_user_id=picked_user_id, role_key=role_key, assignment_reason=reason)
                    if ok:
                        st.success(message)
                        st.session_state["admin_staff_access_refresh_nonce"] = int(st.session_state.get("admin_staff_access_refresh_nonce") or 0) + 1
                        st.rerun()
                    st.error(message)
    with revoke_col:
        st.markdown(f"##### {t('admin_staff_access_revoke_heading')}")
        revoke_options = {
            f"{get_staff_role_display(str(row.get('role_key') or ''))} | {str(row.get('assigned_at') or '')}": row
            for row in active_assignments
        }
        with st.form("admin_staff_access_revoke_form"):
            revoke_label = st.selectbox(
                t("admin_staff_access_active_assignment_label"),
                list(revoke_options.keys()) or [t("admin_staff_access_no_active_role_option")],
                key="admin_staff_access_revoke_role",
            )
            reason = st.text_area(t("admin_staff_access_revocation_reason"), key="admin_staff_access_revoke_reason")
            confirm = st.checkbox(t("admin_staff_access_revoke_confirm"), key="admin_staff_access_revoke_confirm")
            submitted = st.form_submit_button(t("admin_staff_access_revoke_button"), type="secondary", disabled=not bool(revoke_options))
            if submitted:
                if not confirm:
                    st.error(t("admin_staff_access_revoke_confirm_error"))
                else:
                    target_row = revoke_options.get(revoke_label) or {}
                    ok, message = revoke_staff_role(
                        assignment_id=target_row.get("id"),
                        target_user_id=picked_user_id,
                        role_key=str(target_row.get("role_key") or ""),
                        revoke_reason=reason,
                    )
                    if ok:
                        st.success(message)
                        st.session_state["admin_staff_access_refresh_nonce"] = int(st.session_state.get("admin_staff_access_refresh_nonce") or 0) + 1
                        st.rerun()
                    st.error(message)

    st.markdown(f"#### {t('admin_staff_access_recent_changes_heading')}")
    changes = recent_staff_role_changes(limit=25)
    if changes:
        change_df = pd.DataFrame(changes)[["user_id", "role_key", "is_active", "assigned_at", "assigned_by", "revoked_at", "revoked_by", "assignment_reason"]].copy()
        change_df["role_key"] = change_df["role_key"].astype(str).map(get_staff_role_display)
        change_df = change_df.rename(
            columns={
                "user_id": t("admin_staff_access_user_id"),
                "role_key": t("admin_staff_access_role_label"),
                "is_active": t("admin_status_label"),
                "assigned_at": t("admin_assigned_at_label"),
                "assigned_by": t("admin_assigned_by_label"),
                "revoked_at": t("admin_revoked_at_label"),
                "revoked_by": t("admin_revoked_by_label"),
                "assignment_reason": t("admin_staff_access_assignment_reason"),
            }
        )
        st.dataframe(change_df, use_container_width=True, hide_index=True)
    else:
        st.info(t("admin_staff_access_no_changes"))


def _render_admin_validated_experiment_summary() -> None:
    cache_bust = str(st.session_state.get("admin_eic_refresh_nonce") or 0)
    catalog = list_experiment_catalog(cache_bust=cache_bust)
    rows = []
    validated_options: list[dict[str, str]] = []
    for item in catalog:
        validated = dict(item.get("latest_validated_run") or {})
        experiment_id = str(item.get("experiment_id") or "")
        experiment_label = str(item.get("display_label") or item.get("name") or "")
        run_id = str(validated.get("run_id") or "")
        rows.append(
            {
                "Experiment": experiment_label,
                t("admin_eic_validated_run"): run_id or t("admin_eic_value_none"),
                t("admin_eic_run_status"): get_run_status_display(str(validated.get("run_status") or "not_available")),
                t("admin_eic_integrity_status"): get_integrity_status_display(str(validated.get("integrity_status") or "not_run")),
                t("admin_eic_primary_leader"): str(validated.get("primary_metric_leader") or "n/a"),
                "Validated Runs": int(item.get("validated_run_count") or 0),
            }
        )
        if experiment_id and run_id:
            validated_options.append(
                {
                    "experiment_id": experiment_id,
                    "experiment_label": experiment_label,
                    "run_id": run_id,
                }
            )
    if rows:
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    else:
        st.info(t("admin_eic_empty_no_validated_run"))
        return

    if not validated_options:
        return

    st.markdown(
        f"<div class='admin-section-card' style='margin-top:12px;'><div class='admin-card-title'>{_html.escape(t('admin_eic_summary_reports_title'))}</div><div class='admin-card-subtitle'>{_html.escape(t('admin_eic_summary_reports_caption'))}</div></div>",
        unsafe_allow_html=True,
    )
    selected_experiment_id = st.selectbox(
        t("admin_eic_summary_reports_experiment_label"),
        [row["experiment_id"] for row in validated_options],
        format_func=lambda value: next(
            (row["experiment_label"] for row in validated_options if row["experiment_id"] == value),
            value,
        ),
        key="admin_eic_summary_report_experiment_id",
    )
    selected_option = next((row for row in validated_options if row["experiment_id"] == selected_experiment_id), validated_options[0])
    selected_run_id = str(selected_option.get("run_id") or "")
    st.caption(
        t(
            "admin_eic_summary_reports_run_caption",
            experiment=str(selected_option.get("experiment_label") or ""),
            run_id=selected_run_id or t("admin_eic_value_none"),
        )
    )
    capabilities = {CAPABILITY_VIEW_TECHNICAL_ARTIFACTS} if has_capability(CAPABILITY_VIEW_TECHNICAL_ARTIFACTS) else set()
    report_rows = list_available_eic_reports(selected_run_id, capabilities, language=_eic_lang())
    if not report_rows:
        st.info(t("admin_eic_report_unavailable_no_validated_run"))
        return

    for start in range(0, len(report_rows), 3):
        cols = st.columns(3, gap="medium")
        for col, report in zip(cols, report_rows[start : start + 3]):
            report_type = str(report.get("report_type") or "")
            report_status = str(report.get("status") or "not_available")
            with col:
                st.markdown(
                    f"""
                    <div class="admin-eic-card">
                        <div class="admin-eic-card-title">{_html.escape(str(report.get('title') or ''))}</div>
                        <div class="admin-eic-card-subtitle">{_html.escape(str(report.get('description') or ''))}</div>
                        <div class="admin-eic-meta">{_eic_badge(_eic_report_state_label(report_status), report_status)}</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
                if report_status == "available" and not bool(report.get("download_ready")):
                    if st.button(
                        t("admin_eic_report_generate_button"),
                        key=f"admin_eic_summary_generate_{selected_run_id}_{report_type}",
                        use_container_width=True,
                    ):
                        result = get_or_create_validated_report(selected_run_id, report_type, _eic_lang())
                        if result.get("ok"):
                            st.session_state.pop(f"admin_eic_summary_report_error_{selected_run_id}_{report_type}", None)
                            st.rerun()
                        st.session_state[f"admin_eic_summary_report_error_{selected_run_id}_{report_type}"] = str(
                            result.get("message") or t("admin_eic_report_generation_failed")
                        )
                        st.rerun()
                elif report_status == "available" and bool(report.get("download_ready")):
                    report_path = Path(str(report.get("path") or ""))
                    st.download_button(
                        label=t("admin_eic_report_download_button"),
                        data=report_path.read_bytes(),
                        file_name=report_path.name,
                        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                        use_container_width=True,
                        key=f"admin_eic_summary_download_{selected_run_id}_{report_type}",
                    )
                report_error = st.session_state.get(f"admin_eic_summary_report_error_{selected_run_id}_{report_type}")
                if report_error:
                    st.caption(f"{t('admin_eic_report_generation_failed_label')}: {report_error}")
                elif report_status != "available":
                    st.caption(f"{t('admin_eic_report_availability_label')}: {_eic_report_state_label(report_status)}")


def _eic_lang() -> str:
    return str(st.session_state.get("ui_lang") or "en")


def _eic_status_variant(status: str) -> str:
    safe = _admin_clean_text(status).lower()
    if safe in {"healthy", "validated", "production", "direct_observed_data", "validated_evidence_ready"}:
        return "healthy"
    if safe in {"collecting_data", "collecting_labels", "experimental", "exploratory", "limited", "partial", "feature_source", "proxy_only", "offline_evaluation"}:
        return "collecting"
    if safe in {"restricted", "no_validated_run", "not_available"}:
        return "restricted"
    return "attention"


def _eic_badge(label: str, status: str) -> str:
    variant = _eic_status_variant(status)
    return f"<span class='admin-eic-badge admin-eic-badge--{variant}'>{_html.escape(label)}</span>"


def _eic_now_text() -> str:
    lang = _eic_lang()
    stamp = datetime.now()
    if lang == "es":
        return stamp.strftime("%d/%m/%Y %H:%M")
    if lang == "tr":
        return stamp.strftime("%d.%m.%Y %H:%M")
    return stamp.strftime("%Y-%m-%d %H:%M")


def _eic_report_state_label(state: str) -> str:
    return t(f"admin_eic_report_state_{_admin_clean_text(state).lower() or 'not_available'}")


def _render_admin_intelligence_systems_browser(*, cache_bust: str = "", lang: str | None = None, select_key: str = "admin_ai_component_picker") -> None:
    lang = lang or _eic_lang()
    portfolio = eic_service.get_intelligence_component_portfolio(cache_bust=cache_bust)
    component_ids = [str(row.get("component_id") or "") for row in portfolio if str(row.get("component_id") or "").strip()]
    if not component_ids:
        st.info(t("admin_ai_empty_data"))
        return

    selected_component_id = st.selectbox(
        t("admin_eic_component_picker"),
        component_ids,
        format_func=lambda value: get_component_display_name(value, lang=lang),
        key=select_key,
    )
    selected_component = eic_service.get_component_business_detail(selected_component_id, cache_bust=cache_bust)
    if not selected_component:
        st.info(t("admin_ai_empty_data"))
        return

    selected_name = get_component_display_name(selected_component_id, lang=lang)
    selected_badges = "".join(
        [
            _eic_badge(
                get_component_type_display(str(selected_component.get("component_type") or ""), lang=lang),
                str(selected_component.get("component_type") or ""),
            ),
            _eic_badge(
                t(f"admin_eic_status_{str(selected_component.get('operational_status') or 'not_available').lower()}"),
                str(selected_component.get("operational_status") or ""),
            ),
            _eic_badge(
                t(f"admin_eic_status_{str(selected_component.get('data_maturity') or 'not_available').lower()}"),
                str(selected_component.get("data_maturity") or ""),
            ),
            _eic_badge(
                get_evidence_display(str(selected_component.get("evidence_maturity") or "not_available"), lang=lang),
                str(selected_component.get("evidence_maturity") or ""),
            ),
        ]
    )
    st.markdown(
        f"""
        <div class='admin-section-card'>
            <div class='admin-card-title'>{_html.escape(selected_name)}</div>
            <div class='admin-card-subtitle'>{_html.escape(t('admin_eic_system_detail_subtitle'))}</div>
            <div class="admin-eic-card" style="margin-top:12px;">
                <div class="admin-eic-card-title">{_html.escape(selected_name)}</div>
                <div class="admin-eic-card-subtitle">{_html.escape(str(selected_component.get('business_question') or ''))}</div>
                <div class="admin-eic-meta">{selected_badges}</div>
                <div class="admin-eic-card-copy">{_html.escape(str(selected_component.get('production_use') or ''))}</div>
                <div class="admin-eic-card-foot">
                    <strong>{_html.escape(t('admin_eic_component_next_action'))}:</strong>
                    {_html.escape(get_business_action_display(str(selected_component.get('recommended_next_action') or ''), lang=lang))}
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    detail_rows = [
        (t("admin_eic_component_business_question"), str(selected_component.get("business_question") or "")),
        (t("admin_eic_component_decision_supported"), str(selected_component.get("decision_supported") or "")),
        (t("admin_eic_component_operating_mechanism"), get_component_type_display(str(selected_component.get("component_type") or ""), lang=lang)),
        (t("admin_eic_component_product_surface"), str(selected_component.get("product_surface") or "")),
        (t("admin_eic_component_educational_value"), str(selected_component.get("educational_value") or "")),
        (t("admin_eic_component_current_limitation"), str(selected_component.get("limitation") or "")),
        (t("admin_eic_component_next_action"), get_business_action_display(str(selected_component.get("recommended_next_action") or ""), lang=lang)),
    ]
    st.dataframe(pd.DataFrame(detail_rows, columns=[t("admin_field_label"), t("admin_value_label")]), use_container_width=True, hide_index=True)
    st.caption(
        t(
            "admin_eic_component_data_health_caption",
            rows=str(selected_component.get("relevant_rows") or 0),
            coverage=str(selected_component.get("date_coverage") or t("admin_eic_status_not_available")),
            teachers=str(selected_component.get("teachers_represented") or 0),
            students=str(selected_component.get("students_represented") or 0),
            resources=str(selected_component.get("resources_represented") or 0),
        )
    )
    st.caption(f"{t('admin_eic_component_outcomes')}: {selected_component.get('outcome_metric') or t('admin_eic_status_not_available')}")


def _render_admin_ai_intelligence() -> None:
    refresh_nonce = int(st.session_state.get("admin_eic_refresh_nonce") or 0)
    cache_bust = str(refresh_nonce)
    lang = _eic_lang()
    summary = eic_service.get_intelligence_business_summary(cache_bust=cache_bust)
    portfolio = eic_service.get_intelligence_component_portfolio(cache_bust=cache_bust)
    validated_runs = eic_service.list_validated_experiment_summaries(limit=10, cache_bust=cache_bust)
    telemetry = eic_service.get_business_telemetry_health(cache_bust=cache_bust)
    decisions = eic_service.get_prioritized_intelligence_decisions(cache_bust=cache_bust)
    trend = eic_service.get_evidence_trend(cache_bust=cache_bust)
    latest_validated = summary.get("latest_validated_run") or {}
    evidence_label = get_evidence_display(
        str((latest_validated or {}).get("evidence_level") or (latest_validated or {}).get("evidence_verdict") or "not_available"),
        lang=lang,
    )
    evidence_source_status = str((latest_validated or {}).get("evidence_level") or (latest_validated or {}).get("evidence_verdict") or "not_available")
    status_badges = [
        _eic_badge(t("admin_eic_last_refreshed", value=_eic_now_text()), "healthy"),
        _eic_badge(t("admin_eic_header_validated_badge", value=evidence_label), evidence_source_status),
    ]
    if latest_validated.get("run_id"):
        status_badges.append(
            _eic_badge(
                t("admin_eic_header_run_badge", value=get_run_status_display(str(latest_validated.get("run_status") or "not_available"), lang=lang)),
                str(latest_validated.get("run_status") or "not_available"),
            )
        )
    st.markdown(
        f"""
            <div class="admin-eic-header-card">
            <div class="admin-card-title">{_html.escape(t('admin_eic_title'))}</div>
            <div class="admin-card-subtitle">{_html.escape(t('admin_eic_subtitle'))}</div>
            <div class="admin-eic-meta">{''.join(status_badges)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    action_cols = st.columns([0.28, 0.28, 0.44], gap="small")
    with action_cols[0]:
        if st.button(t("admin_eic_refresh"), key="admin_eic_refresh", use_container_width=True):
            clear_app_caches()
            st.session_state["admin_eic_refresh_nonce"] = refresh_nonce + 1
            st.rerun()
    with action_cols[1]:
        if current_user_can_access_developer_workspace():
            if st.button(t("admin_eic_open_developer_workspace"), key="admin_eic_open_developer_workspace", use_container_width=True):
                go_to("developer_workspace")
                st.rerun()
        else:
            st.markdown("", unsafe_allow_html=True)

    overview_tab, systems_tab, evidence_tab, health_tab, decisions_tab, reports_tab = st.tabs(
        [
            t("admin_eic_tab_overview"),
            t("admin_eic_tab_systems"),
            t("admin_eic_tab_evidence"),
            t("admin_eic_tab_data_health"),
            t("admin_eic_tab_decisions"),
            t("admin_eic_tab_reports"),
        ]
    )

    with overview_tab:
        cards = summary.get("cards") or []
        if cards:
            top_rows = []
            for card in cards[:4]:
                raw_value = str(card.get("value") or "")
                if card.get("label") == "evidence_level":
                    display_value = get_evidence_display(raw_value, lang=lang)
                elif card.get("label") == "recommended_business_action":
                    display_value = get_business_action_display(raw_value, lang=lang)
                else:
                    display_value = _translate_eic_value(raw_value)
                top_rows.append((t(f"admin_eic_card_{card['label']}"), display_value))
            _render_kpi_row(top_rows)
            st.markdown("<div class='admin-kpi-stack-gap'></div>", unsafe_allow_html=True)
            lower_rows = []
            for card in cards[4:8]:
                raw_value = str(card.get("value") or "")
                if card.get("label") == "evidence_level":
                    display_value = get_evidence_display(raw_value, lang=lang)
                elif card.get("label") == "recommended_business_action":
                    display_value = get_business_action_display(raw_value, lang=lang)
                else:
                    display_value = _translate_eic_value(raw_value)
                lower_rows.append((t(f"admin_eic_card_{card['label']}"), display_value))
            _render_kpi_row(lower_rows)
            st.markdown("<div class='admin-kpi-stack-gap'></div>", unsafe_allow_html=True)
            with st.expander(t("admin_eic_overview_metric_guide_title"), expanded=False):
                for card in cards:
                    label_key = str(card.get("label") or "")
                    status_key = str(card.get("status") or "not_available")
                    st.caption(
                        f"{t(f'admin_eic_card_{label_key}_help')} "
                        f"({_html.unescape(get_evidence_display(status_key, lang=lang) if label_key == 'evidence_level' else t(f'admin_eic_status_{status_key}'))})"
                    )
        top_decision = summary.get("top_decision") or {}
        if top_decision:
            st.info(
                f"{t('admin_eic_current_recommended_action')}: "
                f"{get_business_action_display(str(top_decision.get('recommended_action') or ''), lang=lang)}"
            )
        st.caption(
            t(
                "admin_eic_diagnostics_caption",
                duration=str((summary.get("diagnostics") or {}).get("query_duration_ms") or 0),
                rows=str((summary.get("diagnostics") or {}).get("rows_fetched") or 0),
            )
        )

    with systems_tab:
        _render_admin_intelligence_systems_browser(cache_bust=cache_bust, lang=lang, select_key="admin_eic_component_picker")

    with evidence_tab:
        latest_validated = summary.get("latest_validated_run") or {}
        if latest_validated:
            _render_admin_validated_experiment_summary()
            business_detail = eic_service.get_experiment_business_detail(str(latest_validated.get("run_id") or ""), cache_bust=cache_bust)
            if business_detail:
                result_rows = [
                    (t("admin_eic_model_primary_metric_leader"), _admin_clean_text((business_detail.get("model_results") or {}).get("primary_metric_leader")) or "—"),
                    (t("admin_eic_model_best_thresholded_classifier"), _admin_clean_text((business_detail.get("model_results") or {}).get("best_thresholded_classifier")) or "—"),
                    (t("admin_eic_model_precision_recall_leader"), _admin_clean_text((business_detail.get("model_results") or {}).get("precision_recall_leader")) or "—"),
                    (t("admin_eic_model_calibration_leader"), _admin_clean_text((business_detail.get("model_results") or {}).get("calibration_leader")) or "—"),
                    (
                        t("admin_eic_model_overall_conclusion"),
                        get_evidence_display(_admin_clean_text((business_detail.get("model_results") or {}).get("overall_evidence_conclusion")) or "not_available", lang=lang) or "—",
                    ),
                    (t("admin_eic_model_robust_winner"), t(f"admin_eic_boolean_{str((business_detail.get('model_results') or {}).get('robust_winner') or 'no')}")),
                ]
                st.dataframe(pd.DataFrame(result_rows, columns=[t("admin_field_label"), t("admin_value_label")]), use_container_width=True, hide_index=True)
                model_rows = (business_detail.get("model_results") or {}).get("models_compared") or []
                if model_rows:
                    model_df = pd.DataFrame(model_rows)
                    for column_name in list(model_df.columns):
                        model_df[column_name] = model_df[column_name].apply(
                            lambda value, name=column_name: get_model_comparison_value_display(name, value, lang=lang)
                        )
                    model_df = model_df.rename(
                        columns={column_name: get_model_comparison_column_display(column_name, lang=lang) for column_name in model_df.columns}
                    )
                    st.dataframe(model_df, use_container_width=True, hide_index=True)
        else:
            st.info(t("admin_eic_empty_no_validated_run"))
        st.markdown(f"### {t('admin_eic_validated_registry_title')}")
        if validated_runs:
            registry_df = pd.DataFrame(
                [
                    {
                        t("admin_eic_registry_run_date"): _format_admin_datetime(row.get("created_at")),
                        t("admin_eic_registry_experiment"): get_experiment_display_name(str(row.get("experiment_id") or "assigned_resource_open_within_7d"), lang=lang),
                        t("admin_eic_registry_dataset_size"): int(row.get("included_row_count") or 0),
                        t("admin_eic_registry_positive_labels"): int(row.get("positive_label_count") or 0),
                        t("admin_eic_registry_negative_labels"): int(row.get("negative_label_count") or 0),
                        t("admin_eic_registry_teachers"): int(row.get("teachers_represented") or 0),
                        t("admin_eic_registry_students"): int(row.get("students_represented") or 0),
                        t("admin_eic_registry_resources"): int(row.get("resources_represented") or 0),
                        t("admin_eic_registry_evidence_verdict"): get_evidence_display(str(row.get("evidence_level") or ""), lang=lang),
                        t("admin_eic_registry_integrity"): get_integrity_status_display(str(row.get("integrity_status") or "not_run"), lang=lang),
                        t("admin_eic_registry_maturity"): get_maturity_display(str(row.get("maturity_verdict") or ""), lang=lang),
                        t("admin_eic_registry_leader"): str(row.get("primary_metric_leader") or "—"),
                        t("admin_eic_registry_action"): get_business_action_display(str(row.get("recommended_business_action") or ""), lang=lang),
                    }
                    for row in validated_runs
                ]
            )
            st.dataframe(registry_df, use_container_width=True, hide_index=True)
        else:
            st.info(t("admin_eic_empty_no_validated_run"))
        st.caption(t("admin_eic_trend_available", labels=str((trend.get("observed_differences") or {}).get("mature_label_growth") or 0), teachers=str((trend.get("observed_differences") or {}).get("teacher_coverage_change") or 0)) if trend.get("available") else t("admin_eic_trend_unavailable"))

    with health_tab:
        telemetry_summary = telemetry.get("summary") or {}
        _render_kpi_row(
            [
                (t("admin_eic_health_total_exposures"), str(telemetry_summary.get("total_canonical_exposures") or 0)),
                (t("admin_eic_health_matched_open_coverage"), _telemetry_percent(telemetry_summary.get("matched_open_coverage"))),
                (t("admin_eic_health_unmatched_opens"), str(telemetry_summary.get("unmatched_opens") or 0)),
                (t("admin_eic_health_downstream_coverage"), _telemetry_percent(telemetry_summary.get("downstream_outcome_coverage"))),
            ]
        )
        st.markdown("<div class='admin-kpi-stack-gap'></div>", unsafe_allow_html=True)
        _render_kpi_row(
            [
                (t("admin_eic_health_mature_outcomes"), str(telemetry_summary.get("mature_outcomes_7d") or 0)),
                (t("admin_eic_health_represented_teachers"), str(telemetry_summary.get("represented_teachers") or 0)),
                (t("admin_eic_health_represented_students"), str(telemetry_summary.get("represented_students") or 0)),
                (t("admin_eic_health_represented_resources"), str(telemetry_summary.get("represented_resources") or 0)),
            ]
        )
        by_surface = telemetry.get("by_surface") or []
        if by_surface:
            surface_df = pd.DataFrame(
                [
                    {
                        t("admin_eic_health_surface"): str(row.get("surface") or "—"),
                        t("admin_eic_health_exposure_type"): str(row.get("exposure_type") or "—"),
                        t("admin_eic_health_exposures"): int(row.get("exposures") or 0),
                        t("admin_eic_health_status"): t(f"admin_eic_status_{str(row.get('status') or 'not_available').lower()}"),
                        t("admin_eic_health_matched_opens"): int(row.get("matched_opens") or 0),
                        t("admin_eic_health_unmatched_opens"): int(row.get("unmatched_opens") or 0),
                        t("admin_eic_health_downstream_coverage"): _telemetry_percent(row.get("downstream_outcome_coverage")),
                    }
                    for row in by_surface
                ]
            )
            st.dataframe(surface_df, use_container_width=True, hide_index=True)
        st.caption(
            t(
                "admin_eic_health_diagnostics_caption",
                duration=str((telemetry.get("diagnostics") or {}).get("query_duration_ms") or 0),
                rows=str((telemetry.get("diagnostics") or {}).get("rows_fetched") or 0),
            )
        )

    with decisions_tab:
        for decision in decisions:
            st.markdown(
                f"""
                <div class="admin-eic-card" style="margin-bottom:12px;">
                    <div class="admin-eic-card-title">{_html.escape(get_component_display_name(str(decision.get('component_id') or ''), lang=lang))}</div>
                    <div class="admin-eic-meta">
                        {_eic_badge(get_business_action_display(str(decision.get('recommended_action') or ''), lang=lang), str(decision.get('recommended_action') or ''))}
                    </div>
                    <div class="admin-eic-card-copy"><strong>{_html.escape(str(decision.get('issue') or ''))}</strong></div>
                    <div class="admin-eic-card-subtitle">{_html.escape(str(decision.get('evidence') or ''))}</div>
                    <div class="admin-eic-card-foot">{_html.escape(str(decision.get('business_impact') or ''))}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    with reports_tab:
        if latest_validated:
            run_id = str(latest_validated.get("run_id") or "")
            academic = eic_service.get_academic_evidence_summary(run_id, cache_bust=cache_bust)
            if academic.get("is_final"):
                academic_rows = [
                    (t("admin_eic_academic_run_id"), str(academic.get("run_id") or "")),
                    (t("admin_eic_academic_dataset_fingerprint"), str(academic.get("dataset_fingerprint") or "")),
                    (t("admin_eic_academic_dataset_size"), str(academic.get("dataset_size") or 0)),
                    (t("admin_eic_academic_class_balance"), _telemetry_percent(academic.get("class_balance"))),
                    (t("admin_eic_academic_selected_metric_leader"), str(academic.get("selected_metric_leader") or "—")),
                    (t("admin_eic_academic_production_readiness"), get_maturity_display(str(academic.get("production_readiness_decision") or ""), lang=lang) or "—"),
                ]
                st.dataframe(pd.DataFrame(academic_rows, columns=[t("admin_field_label"), t("admin_value_label")]), use_container_width=True, hide_index=True)
            capabilities = {CAPABILITY_VIEW_TECHNICAL_ARTIFACTS} if has_capability(CAPABILITY_VIEW_TECHNICAL_ARTIFACTS) else set()
            report_rows = list_available_eic_reports(run_id, capabilities, language=lang)
            st.markdown(
                f"<div class='admin-section-card'><div class='admin-card-title'>{_html.escape(t('admin_eic_reports_title'))}</div><div class='admin-card-subtitle'>{_html.escape(t('admin_eic_reports_subtitle'))}</div></div>",
                unsafe_allow_html=True,
            )
            for start in range(0, len(report_rows), 3):
                cols = st.columns(3, gap="medium")
                for col, report in zip(cols, report_rows[start : start + 3]):
                    report_type = str(report.get("report_type") or "")
                    report_status = str(report.get("status") or "not_available")
                    with col:
                        st.markdown(
                            f"""
                            <div class="admin-eic-card">
                                <div class="admin-eic-card-title">{_html.escape(str(report.get('title') or ''))}</div>
                                <div class="admin-eic-card-subtitle">{_html.escape(str(report.get('description') or ''))}</div>
                                <div class="admin-eic-meta">{_eic_badge(_eic_report_state_label(report_status), report_status)}</div>
                            </div>
                            """,
                            unsafe_allow_html=True,
                        )
                        if report_status == "available" and not bool(report.get("download_ready")):
                            if st.button(t("admin_eic_report_generate_button"), key=f"admin_eic_generate_{run_id}_{report_type}", use_container_width=True):
                                result = get_or_create_validated_report(run_id, report_type, lang)
                                if result.get("ok"):
                                    st.session_state.pop(f"admin_eic_report_error_{report_type}", None)
                                    st.rerun()
                                st.session_state[f"admin_eic_report_error_{report_type}"] = str(result.get("message") or t("admin_eic_report_generation_failed"))
                                st.rerun()
                        elif report_status == "available" and bool(report.get("download_ready")):
                            report_path = Path(str(report.get("path") or ""))
                            st.download_button(
                                label=t("admin_eic_report_download_button"),
                                data=report_path.read_bytes(),
                                file_name=report_path.name,
                                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                                use_container_width=True,
                                key=f"admin_eic_download_docx_{run_id}_{report_type}",
                            )
                        report_error = st.session_state.get(f"admin_eic_report_error_{report_type}")
                        if report_error:
                            st.caption(f"{t('admin_eic_report_generation_failed_label')}: {report_error}")
                        elif report_status != "available":
                            st.caption(f"{t('admin_eic_report_availability_label')}: {_eic_report_state_label(report_status)}")
            st.caption(t("admin_eic_report_download_note"))
        else:
            st.markdown(f"<div class='admin-eic-empty'>{_html.escape(t('admin_eic_report_unavailable_no_validated_run'))}</div>", unsafe_allow_html=True)
        with st.expander(t("admin_eic_legacy_diagnostics_title"), expanded=False):
            st.caption(t("admin_eic_legacy_diagnostics_caption"))
            st.dataframe(pd.DataFrame(_legacy_report_rows()), use_container_width=True, hide_index=True)


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
    tab_accounts, tab_users, tab_staff_access = st.tabs([
        f"🆕 {t('admin_accounts')}",
        f"👥 {t('admin_users')}",
        f"🔐 {t('admin_staff_access_title')}",
    ])
    with tab_accounts:
        _render_accounts(df)
    with tab_users:
        _render_users(df)
    with tab_staff_access:
        _render_staff_access()


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


def _explorer_move_status_label(status: str) -> str:
    mapping = {
        EXPLORER_MOVE_STATUS_PENDING: t("admin_explorer_moves_pending"),
        EXPLORER_MOVE_STATUS_PUBLISHED: t("admin_explorer_moves_published"),
        EXPLORER_MOVE_STATUS_SOLVED: t("admin_explorer_moves_solved"),
        EXPLORER_MOVE_STATUS_ARCHIVED: t("admin_explorer_moves_archived"),
    }
    return mapping.get(str(status or "").strip(), str(status or "").strip())


def _explorer_move_resource_label(row: dict) -> str:
    tool_key = str(row.get("tool_key") or "").strip()
    if tool_key and t(tool_key) != tool_key:
        return t(tool_key)
    resource_type = str(row.get("resource_type") or "").strip()
    fallback = {
        "lesson_plan": t("quick_lesson_planner"),
        "worksheet": t("worksheet_maker"),
        "exam": t("quick_exam_builder"),
    }
    return fallback.get(resource_type, resource_type.replace("_", " ").title())


def _format_admin_explorer_dt(value) -> str:
    try:
        dt = pd.to_datetime(value, errors="coerce", utc=True)
        if pd.isna(dt):
            return ""
        return dt.strftime("%Y-%m-%d %H:%M")
    except Exception:
        return ""


def _explorer_move_status_badge_class(status: str) -> str:
    status_map = {
        EXPLORER_MOVE_STATUS_PENDING: "admin-explorer-status-badge--pending",
        EXPLORER_MOVE_STATUS_PUBLISHED: "admin-explorer-status-badge--published",
        EXPLORER_MOVE_STATUS_SOLVED: "admin-explorer-status-badge--solved",
        EXPLORER_MOVE_STATUS_ARCHIVED: "admin-explorer-status-badge--archived",
    }
    return status_map.get(str(status or "").strip(), "admin-explorer-status-badge--pending")


def _log_explorer_move_action(move: dict, action_type: str, *, target_user_id: str = "", detail: str = "") -> None:
    move_id = str(move.get("id") or "").strip()
    title = str(move.get("title") or _explorer_move_resource_label(move) or "").strip()
    resource_label = _explorer_move_resource_label(move)
    status = str(move.get("status") or "").strip()
    visitor_id = str(move.get("anonymous_session_id") or "").strip()
    reason_parts = [
        f"move_id={move_id}" if move_id else "",
        f"resource={resource_label}" if resource_label else "",
        f"title={title}" if title else "",
        f"status={status}" if status else "",
        f"anonymous_session={visitor_id}" if visitor_id else "",
        f"detail={detail}" if detail else "",
    ]
    _log_admin_override(target_user_id, action_type, "; ".join(part for part in reason_parts if part))


def _render_explorer_move_preview(move: dict) -> None:
    resource_type = str(move.get("resource_type") or "").strip()
    meta = move.get("meta_json") if isinstance(move.get("meta_json"), dict) else {}
    payload = move.get("payload_json") if isinstance(move.get("payload_json"), dict) else {}
    move_id = str(move.get("id") or "preview")

    def _save_preview_payload(updated_payload: dict) -> bool:
        return persist_explorer_move_payload(move, updated_payload)

    def _render_admin_payload_editor(updated_payload: dict, *, resource_label: str, normalize_payload=None) -> None:
        from helpers.resource_editor import render_resource_editor

        render_resource_editor(
            resource_label=resource_label,
            payload=updated_payload,
            action_key_prefix=f"admin_explorer_move_{move_id}_{resource_label}_edit",
            on_apply=_save_preview_payload,
            normalize_payload=normalize_payload,
            context={
                "source": "explorer_moves_admin",
                "move_id": move_id,
                "subject": str(meta.get("subject") or ""),
                "topic": str(meta.get("topic") or ""),
                "learner_stage": str(meta.get("learner_stage") or ""),
                "level_or_band": str(meta.get("level_or_band") or ""),
            },
        )

    if resource_type == "lesson_plan":
        from helpers.planner_storage import _clean_plan_data, render_quick_lesson_plan_result

        render_quick_lesson_plan_result(
            payload,
            subject=str(meta.get("subject") or ""),
            learner_stage=str(meta.get("learner_stage") or ""),
            level_or_band=str(meta.get("level_or_band") or ""),
            lesson_purpose=str(meta.get("lesson_purpose") or ""),
            topic=str(meta.get("topic") or ""),
            read_only=True,
            action_key_prefix=f"admin_explorer_move_{move_id}",
            allow_image_generation=True,
            on_image_update=_save_preview_payload,
        )
        _render_admin_payload_editor(payload, resource_label="lesson_plan", normalize_payload=_clean_plan_data)
        return

    if resource_type == "worksheet":
        from helpers.worksheet_storage import _clean_worksheet_data, _normalize_worksheet_unicode, render_worksheet_result

        def _normalize_admin_worksheet(updated_payload: dict) -> dict:
            return _clean_worksheet_data(_normalize_worksheet_unicode(dict(updated_payload or {})))

        render_worksheet_result(
            payload,
            read_only=True,
            subject=str(meta.get("subject") or ""),
            learner_stage=str(meta.get("learner_stage") or ""),
            level_or_band=str(meta.get("level_or_band") or ""),
            worksheet_type=str(meta.get("worksheet_type") or ""),
            topic=str(meta.get("topic") or ""),
            action_key_prefix=f"admin_explorer_move_{move_id}",
            allow_image_generation=True,
            allow_auto_image_generation=False,
            on_image_update=_save_preview_payload,
        )
        _render_admin_payload_editor(payload, resource_label="worksheet", normalize_payload=_normalize_admin_worksheet)
        return

    if resource_type == "exam":
        from helpers.quick_exam_storage import render_exam_result

        def _normalize_admin_exam(updated_payload: dict) -> dict:
            import helpers.quick_exam_builder as eb

            exam_data = dict(updated_payload.get("exam_data") if isinstance(updated_payload.get("exam_data"), dict) else {})
            answer_key = updated_payload.get("answer_key") if isinstance(updated_payload.get("answer_key"), dict) else {}
            exam_data, answer_key = eb.repair_exam_answer_key(exam_data, answer_key)
            return {"exam_data": exam_data, "answer_key": answer_key}

        render_exam_result(
            payload.get("exam_data") or {},
            payload.get("answer_key") or {},
            read_only=True,
            action_key_prefix=f"admin_explorer_move_{move_id}",
            subject=str(meta.get("subject") or ""),
            learner_stage=str(meta.get("learner_stage") or ""),
            level_or_band=str(meta.get("level_or_band") or ""),
            topic=str(meta.get("topic") or ""),
            allow_image_generation=True,
            allow_auto_image_generation=False,
            on_image_update=_save_preview_payload,
        )
        _render_admin_payload_editor(
            {"exam_data": payload.get("exam_data") or {}, "answer_key": payload.get("answer_key") or {}},
            resource_label="exam",
            normalize_payload=_normalize_admin_exam,
        )
        return

    st.info(t("admin_explorer_moves_preview_unavailable"))


def _render_admin_explorer_moves(user_df: pd.DataFrame) -> None:
    card_col, refresh_col = st.columns([0.76, 0.24], vertical_alignment="center")
    with card_col:
        _render_section_callout(t("admin_explorer_moves_title"), t("admin_explorer_moves_subtitle"))
    with refresh_col:
        st.markdown("<div style='height:10px;'></div>", unsafe_allow_html=True)
        if st.button(t("admin_explorer_moves_refresh"), key="admin_explorer_moves_refresh", use_container_width=True):
            clear_app_caches()
            st.rerun()

    st.markdown("<div class='admin-kpi-stack-gap'></div>", unsafe_allow_html=True)

    if not explorer_moves_table_available():
        st.warning(t("admin_explorer_moves_unavailable"))
        return

    moves_df = load_explorer_moves_admin(limit=500)
    if moves_df.empty:
        st.info(t("admin_explorer_moves_empty"))
        return

    status_series = moves_df.get("status", pd.Series(dtype=str)).astype(str)
    _render_kpi_row(
        [
            (t("admin_explorer_moves_total"), str(int(len(moves_df)))),
            (t("admin_explorer_moves_pending"), str(int((status_series == EXPLORER_MOVE_STATUS_PENDING).sum()))),
            (t("admin_explorer_moves_published"), str(int((status_series == EXPLORER_MOVE_STATUS_PUBLISHED).sum()))),
            (t("admin_explorer_moves_solved"), str(int((status_series == EXPLORER_MOVE_STATUS_SOLVED).sum()))),
            (t("admin_explorer_moves_archived"), str(int((status_series == EXPLORER_MOVE_STATUS_ARCHIVED).sum()))),
        ]
    )

    status_options = {
        t("admin_explorer_moves_all_statuses"): "all",
        t("admin_explorer_moves_pending"): EXPLORER_MOVE_STATUS_PENDING,
        t("admin_explorer_moves_published"): EXPLORER_MOVE_STATUS_PUBLISHED,
        t("admin_explorer_moves_solved"): EXPLORER_MOVE_STATUS_SOLVED,
        t("admin_explorer_moves_archived"): EXPLORER_MOVE_STATUS_ARCHIVED,
    }
    type_options = {
        t("admin_explorer_moves_all_types"): "all",
        t("quick_lesson_planner"): "lesson_plan",
        t("worksheet_maker"): "worksheet",
        t("quick_exam_builder"): "exam",
    }
    filter_col1, filter_col2 = st.columns(2)
    with filter_col1:
        selected_status_label = st.selectbox(
            t("admin_explorer_moves_status"),
            options=list(status_options.keys()),
            key="admin_explorer_moves_status_filter",
        )
    with filter_col2:
        selected_type_label = st.selectbox(
            t("admin_explorer_moves_resource_type"),
            options=list(type_options.keys()),
            key="admin_explorer_moves_type_filter",
        )

    filtered = moves_df.copy()
    selected_status = status_options[selected_status_label]
    selected_type = type_options[selected_type_label]
    if selected_status != "all":
        filtered = filtered[filtered["status"].astype(str) == selected_status]
    if selected_type != "all":
        filtered = filtered[filtered["resource_type"].astype(str) == selected_type]

    resource_search = st.text_input(
        t("explore_resource_search"),
        key="admin_explorer_moves_resource_search",
        placeholder=t("explore_resource_search_placeholder"),
    ).strip()
    if resource_search:
        search_columns = [
            filtered.get("title", pd.Series("", index=filtered.index)),
            filtered.get("subject", pd.Series("", index=filtered.index)),
            filtered.get("topic", pd.Series("", index=filtered.index)),
            filtered.get("preview_text", pd.Series("", index=filtered.index)),
            filtered.get("anonymous_session_id", pd.Series("", index=filtered.index)),
        ]
        search_mask = pd.Series(False, index=filtered.index)
        for column in search_columns:
            search_mask = search_mask | column.fillna("").astype(str).str.contains(resource_search, case=False, regex=False)
        filtered = filtered[search_mask].copy()

    if filtered.empty:
        st.info(t("admin_explorer_moves_search_empty") if resource_search else t("admin_explorer_moves_empty"))
        return

    assignable_users_df = user_df.copy() if isinstance(user_df, pd.DataFrame) else pd.DataFrame()

    page_size_options = [10, 20, 50]
    page_control_col1, page_control_col2, page_control_col3 = st.columns([0.28, 0.42, 0.30])
    with page_control_col1:
        page_size = st.selectbox(
            t("admin_explorer_moves_page_size"),
            options=page_size_options,
            index=1,
            key="admin_explorer_moves_page_size_select",
        )

    total_items = int(len(filtered))
    total_pages = max(1, (total_items + int(page_size) - 1) // int(page_size))
    current_page = int(st.session_state.get("admin_explorer_moves_page", 1) or 1)
    current_page = max(1, min(current_page, total_pages))
    st.session_state["admin_explorer_moves_page"] = current_page

    with page_control_col2:
        st.caption(t("admin_explorer_moves_page_status", start=((current_page - 1) * int(page_size)) + 1, end=min(current_page * int(page_size), total_items), total=total_items))
    with page_control_col3:
        nav_col1, nav_col2, nav_col3 = st.columns([1, 1.2, 1])
        with nav_col1:
            if st.button(t("admin_explorer_moves_previous"), key="admin_explorer_moves_prev_page", use_container_width=True, disabled=current_page <= 1):
                st.session_state["admin_explorer_moves_page"] = current_page - 1
                st.rerun()
        with nav_col2:
            st.caption(t("admin_explorer_moves_page_indicator", current=current_page, total=total_pages))
        with nav_col3:
            if st.button(t("admin_explorer_moves_next"), key="admin_explorer_moves_next_page", use_container_width=True, disabled=current_page >= total_pages):
                st.session_state["admin_explorer_moves_page"] = current_page + 1
                st.rerun()

    start_idx = (current_page - 1) * int(page_size)
    end_idx = start_idx + int(page_size)
    paged_filtered = filtered.iloc[start_idx:end_idx].copy()

    selected_move_id = str(st.session_state.get("admin_explorer_move_selected") or "")
    for row in paged_filtered.to_dict("records"):
        move_id = str(row.get("id") or "")
        status = str(row.get("status") or "")
        title = str(row.get("title") or _explorer_move_resource_label(row)).strip()
        visitor_id = str(row.get("anonymous_session_id") or "").strip()
        preview_text = str(row.get("preview_text") or "").strip()
        meta_items = [
            _explorer_move_resource_label(row),
            _explorer_move_status_label(status),
        ]
        if str(row.get("subject") or "").strip():
            meta_items.append(str(row.get("subject") or "").strip().replace("_", " ").title())
        if str(row.get("topic") or "").strip():
            meta_items.append(str(row.get("topic") or "").strip())
        created_text = _format_admin_explorer_dt(row.get("created_at"))
        if created_text:
            meta_items.append(f"{t('admin_explorer_moves_generated')}: {created_text}")
        if visitor_id:
            meta_items.append(f"{t('admin_explorer_moves_anonymous_session')}: {visitor_id[:10]}")

        with st.container(border=True):
            st.markdown(
                f"<div class='admin-explorer-status-row'><span class='admin-explorer-status-badge {_explorer_move_status_badge_class(status)}'>{_html.escape(_explorer_move_status_label(status))}</span></div>",
                unsafe_allow_html=True,
            )
            st.markdown(f"**{_html.escape(title)}**")
            st.caption(" · ".join([item for item in meta_items if item]))
            if preview_text:
                st.write(preview_text)

            action_col1, action_col2, action_col3 = st.columns(3)
            with action_col1:
                preview_label = t("close") if selected_move_id == move_id else t("admin_explorer_moves_preview")
                if st.button(preview_label, key=f"admin_explorer_move_preview_{move_id}", use_container_width=True):
                    _log_explorer_move_action(
                        row,
                        "explorer_move_preview_close" if selected_move_id == move_id else "explorer_move_preview_open",
                    )
                    st.session_state["admin_explorer_move_selected"] = "" if selected_move_id == move_id else move_id
                    st.rerun()
            with action_col2:
                if st.button(
                    t("admin_explorer_moves_publish"),
                    key=f"admin_explorer_move_publish_{move_id}",
                    use_container_width=True,
                    disabled=status != EXPLORER_MOVE_STATUS_PENDING,
                ):
                    ok, msg = publish_explorer_move(row)
                    if ok:
                        _log_explorer_move_action(row, "explorer_move_publish")
                        st.success(t("admin_explorer_moves_publish_success"))
                        st.session_state["admin_explorer_move_selected"] = move_id
                        st.rerun()
                    st.error(t("admin_explorer_moves_publish_failed", error=msg))
            with action_col3:
                if st.button(
                    t("archive_toggle_label"),
                    key=f"admin_explorer_move_archive_{move_id}",
                    use_container_width=True,
                    disabled=status == EXPLORER_MOVE_STATUS_ARCHIVED,
                ):
                    ok, msg = archive_explorer_move(row)
                    if ok:
                        _log_explorer_move_action(row, "explorer_move_archive")
                        st.success(t("admin_explorer_moves_archive_success"))
                        st.session_state["admin_explorer_move_selected"] = move_id
                        st.rerun()
                    st.error(t("admin_explorer_moves_archive_failed", error=msg))

            if selected_move_id == move_id:
                st.markdown("<div style='height:6px;'></div>", unsafe_allow_html=True)
                _render_explorer_move_preview(row)
                st.markdown("<div style='height:8px;'></div>", unsafe_allow_html=True)
                st.markdown(f"#### {t('admin_explorer_moves_assign_title')}")
                target_row = _selected_user_row(assignable_users_df, f"admin_explorer_move_assign_target_{move_id}", label_key="admin_explorer_moves_select_profile") if not assignable_users_df.empty else {}
                if assignable_users_df.empty:
                    st.info(t("admin_explorer_moves_user_list_empty"))
                if target_row:
                    target_name = str(target_row.get("display_name") or target_row.get("email") or t("admin_user_fallback_name")).strip()
                    target_email = str(target_row.get("email") or "").strip()
                    st.caption(f"{target_name} · {target_email}")
                if st.button(
                    t("admin_explorer_moves_assign_button"),
                    key=f"admin_explorer_move_assign_btn_{move_id}",
                    use_container_width=True,
                    disabled=not bool(target_row),
                ):
                    target_user_id = str(target_row.get("user_id") or "").strip()
                    target_display = str(target_row.get("display_name") or target_row.get("email") or t("unknown")).strip()
                    ok, _record_id, msg = assign_explorer_move_to_profile(
                        row,
                        target_user_id,
                        target_display,
                    )
                    if ok:
                        _log_explorer_move_action(row, "explorer_move_assign", target_user_id=target_user_id, detail=f"assigned_to={target_display}")
                        st.success(t("admin_explorer_moves_assign_success"))
                    elif str(msg or "").startswith("duplicate_assignment::"):
                        solved_by = str(msg).split("::", 1)[1].strip() or t("unknown")
                        _log_explorer_move_action(row, "explorer_move_assign_duplicate", target_user_id=target_user_id, detail=f"assigned_to={target_display}; solved_by={solved_by}")
                        st.warning(
                            t(
                                "admin_explorer_moves_assign_duplicate",
                                admin=solved_by,
                            )
                        )
                    else:
                        st.error(t("admin_explorer_moves_assign_failed", error=msg))


def render_admin() -> None:
    require_admin()
    _inject_admin_styles()

    profiles = _fetch_profiles("")
    visible_user_ids = tuple(
        str(profile.get("user_id") or "").strip()
        for profile in profiles
        if str(profile.get("user_id") or "").strip()
    )
    subscriptions = _fetch_subscriptions(visible_user_ids)
    events = _fetch_events()
    overrides = _fetch_overrides()
    auth_activity = _fetch_auth_user_activity()
    app_activity = _fetch_recent_app_activity(visible_user_ids)
    df = _merge_profiles_subscriptions(profiles, subscriptions, auth_activity, app_activity)
    _render_admin_hero(df)

    (
        tab_overview,
        tab_operations,
        tab_pricing,
        tab_subscriptions,
        tab_ai_intelligence,
        tab_explorer_moves,
        tab_business,
        tab_audit,
    ) = st.tabs([
        f"📊 {t('admin_overview')}",
        f"🛠️ {t('admin_operations')}",
        f"💳 {t('admin_pricing')}",
        f"🧾 {t('admin_plans_subscriptions')}",
        f"🤖 {t('admin_ai_intelligence')}",
        f"🧭 {t('admin_explorer_moves')}",
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
    with tab_ai_intelligence:
        _render_admin_eic()
    with tab_explorer_moves:
        _render_admin_explorer_moves(df)
    with tab_business:
        _render_business_analytics(df, subscriptions)
    with tab_audit:
        _render_audit_log(overrides, events)
