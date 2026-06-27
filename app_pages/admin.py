from __future__ import annotations

import secrets
import html as _html
import math
from datetime import timedelta

import pandas as pd
import streamlit as st

from app_pages.pricing import render_plan_preview_cards
from core.database import clear_app_caches, get_sb, upsert_profile_row
from core.i18n import t
from core.state import get_current_user_id
from core.timezone import DEFAULT_TZ_NAME, today_local
from helpers.currency import CURRENCIES, CURRENCY_CODES, get_exchange_rate, get_preferred_currency
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
    ("business", "graph-up-arrow", "admin_business_analytics"),
    ("audit", "clock-history", "admin_audit_log"),
]

OPERATIONS_TABS = [
    ("accounts", "person-plus-fill", "admin_accounts"),
    ("users", "people-fill", "admin_users"),
]
_ADMIN_USERS_PAGE_SIZE = 4

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
        st.warning(f"Could not load profiles: {exc}")
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


def _minimal_rows(table: str, columns: str = "id,created_at", limit: int = 5000) -> list[dict]:
    try:
        return getattr(get_sb().table(table).select(columns).limit(limit).execute(), "data", None) or []
    except Exception:
        return []


def _merge_profiles_subscriptions(profiles: list[dict], subscriptions: list[dict]) -> pd.DataFrame:
    sub_by_user = {str(row.get("user_id")): row for row in subscriptions}
    rows = []
    for profile in profiles:
        uid = str(profile.get("user_id") or "")
        sub = sub_by_user.get(uid, {})
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
            }
        )
    return pd.DataFrame(rows)


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
        return False, "Email is required."
    if role not in ADMIN_ROLE_OPTIONS:
        return False, "Invalid role."

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
        return False, "Could not create or locate the auth user."

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
        return False, "Could not save the user profile."

    update_user_plan(user_id, str(plan_id or "free"), status=subscription_status, manual_override=True)
    _log_admin_override(user_id, "account_create", f"Created account with role={role}, plan={plan_id}. {notes}".strip())
    clear_app_caches()
    return True, user_id


def _update_profile_fields(user_id: str, payload: dict, note: str, action_type: str) -> tuple[bool, str]:
    user_id = str(user_id or "").strip()
    if not user_id:
        return False, "User ID is required."
    try:
        get_sb().table("profiles").update(payload).eq("user_id", user_id).execute()
        _log_admin_override(user_id, action_type, note)
        clear_app_caches()
        return True, "Saved."
    except Exception as exc:
        return False, str(exc)


def _upsert_plan(payload: dict) -> tuple[bool, str]:
    try:
        get_sb().table("plans").upsert(payload, on_conflict="id").execute()
        clear_app_caches()
        return True, "Plan saved."
    except Exception as exc:
        return False, str(exc)


def _business_metrics(df: pd.DataFrame) -> dict[str, int]:
    today = today_local()
    last_30 = pd.Timestamp(today - timedelta(days=30))
    created_at = pd.to_datetime(df.get("created_at"), errors="coerce", utc=True) if not df.empty and "created_at" in df.columns else pd.Series(dtype="datetime64[ns, UTC]")
    return {
        "total_users": int(len(df)),
        "teachers": int((df.get("role", pd.Series(dtype=str)).astype(str) == "teacher").sum()) if not df.empty else 0,
        "students": int((df.get("role", pd.Series(dtype=str)).astype(str) == "student").sum()) if not df.empty else 0,
        "admins": int((df.get("role", pd.Series(dtype=str)).astype(str) == "admin").sum()) if not df.empty else 0,
        "paid_users": int(df.get("subscription_status", pd.Series(dtype=str)).astype(str).isin(["active", "trialing"]).sum()) if not df.empty else 0,
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
                <div style="padding:14px 16px;border-radius:18px;border:1px solid rgba(148,163,184,.22);
                background:linear-gradient(180deg,rgba(255,255,255,.98),rgba(248,250,252,.96));min-height:92px;">
                    <div style="font-size:.78rem;font-weight:800;color:#64748b;text-transform:uppercase;letter-spacing:.04em;">{label}</div>
                    <div style="margin-top:8px;font-size:1.55rem;font-weight:900;color:#0f172a;">{value}</div>
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
              radial-gradient(circle at top right, rgba(37,99,235,.18), transparent 30%),
              radial-gradient(circle at bottom left, rgba(16,185,129,.14), transparent 34%),
              linear-gradient(135deg, rgba(255,255,255,.98), rgba(239,246,255,.98) 48%, rgba(236,253,245,.96));
            border:1px solid rgba(59,130,246,.16);
            box-shadow:0 18px 42px rgba(15,23,42,.08);
        }
        .admin-hero-title{font-size:1.5rem;font-weight:900;color:#0f172a;letter-spacing:-.02em;}
        .admin-hero-subtitle{margin-top:.45rem;max-width:920px;color:#475569;line-height:1.5;}
        .admin-chiprow{display:flex;gap:8px;flex-wrap:wrap;margin-top:14px;}
        .admin-chip{display:inline-flex;align-items:center;border-radius:999px;padding:6px 10px;font-size:.76rem;font-weight:800;background:#fff;color:#1e293b;border:1px solid rgba(148,163,184,.2);}
        .admin-section-card{
            border-radius:22px;padding:18px 18px 16px;margin-top:10px;background:linear-gradient(180deg, rgba(255,255,255,.98), rgba(248,250,252,.96));
            border:1px solid rgba(148,163,184,.18);box-shadow:0 10px 24px rgba(15,23,42,.05);
        }
        .admin-card-title{font-size:1rem;font-weight:900;color:#0f172a;}
        .admin-card-subtitle{margin-top:4px;color:#64748b;font-size:.84rem;line-height:1.45;}
        .admin-plan-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(230px,1fr));gap:12px;margin-top:12px;}
        .admin-plan-card{
            border-radius:18px;padding:14px;background:rgba(255,255,255,.92);border:1px solid rgba(148,163,184,.2);
        }
        .admin-plan-name{font-size:.98rem;font-weight:900;color:#0f172a;}
        .admin-plan-meta{margin-top:4px;color:#64748b;font-size:.8rem;}
        .admin-plan-price{margin-top:8px;font-size:1.2rem;font-weight:900;color:#2563eb;}
        .admin-user-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:14px;margin-top:12px;}
        .admin-user-card{
            border-radius:20px;padding:16px;background:linear-gradient(180deg, rgba(255,255,255,.98), rgba(248,250,252,.96));
            border:1px solid rgba(148,163,184,.18);box-shadow:0 10px 24px rgba(15,23,42,.05);
        }
        .admin-user-top{display:flex;justify-content:space-between;gap:10px;align-items:flex-start;}
        .admin-user-name{font-size:1rem;font-weight:900;color:#0f172a;line-height:1.25;}
        .admin-user-email{margin-top:2px;color:#64748b;font-size:.82rem;word-break:break-word;}
        .admin-pill-row{display:flex;gap:6px;flex-wrap:wrap;margin-top:10px;}
        .admin-pill{display:inline-flex;align-items:center;border-radius:999px;padding:5px 9px;font-size:.72rem;font-weight:800;background:#eff6ff;color:#1d4ed8;border:1px solid rgba(59,130,246,.14);}
        .admin-user-stats{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px;margin-top:12px;}
        .admin-user-stat{border-radius:14px;padding:10px 11px;background:#fff;border:1px solid rgba(148,163,184,.14);}
        .admin-user-stat-label{font-size:.7rem;text-transform:uppercase;letter-spacing:.05em;color:#64748b;font-weight:800;}
        .admin-user-stat-value{margin-top:4px;font-size:.92rem;font-weight:900;color:#0f172a;}
        </style>
        """,
        unsafe_allow_html=True,
    )


def _render_admin_hero(df: pd.DataFrame) -> None:
    metrics = _business_metrics(df)
    chips = [
        f"{metrics['total_users']} users",
        f"{metrics['paid_users']} paid",
        f"{metrics['admins']} admins",
        f"{metrics['new_last_30']} new in 30d",
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
    _render_kpi_row(
        [
            ("Users", str(metrics["total_users"])),
            ("Paid users", str(metrics["paid_users"])),
            ("New 30d", str(metrics["new_last_30"])),
            ("Suspended", str(metrics["suspended_users"])),
        ]
    )
    st.markdown("")
    _render_kpi_row(
        [
            ("Worksheets", str(content["worksheets"])),
            ("Exams", str(content["exams"])),
            ("Lesson plans", str(content["lesson_plans"])),
            ("AI events", str(content["ai_events"])),
        ]
    )

    left, right = st.columns([1.1, 0.9], gap="large")
    with left:
        st.markdown("### Recent accounts")
        preview = df[["email", "role", "current_plan", "subscription_status", "created_at"]].head(12) if not df.empty else pd.DataFrame()
        if preview.empty:
            st.info("No profiles found yet.")
        else:
            st.dataframe(preview, use_container_width=True, hide_index=True)
    with right:
        st.markdown("### Plan mix")
        if df.empty:
            st.info("No plan data yet.")
        else:
            plan_mix = (
                df.groupby("current_plan", as_index=False)
                .size()
                .rename(columns={"size": "users"})
                .sort_values("users", ascending=False)
            )
            st.bar_chart(plan_mix.set_index("current_plan"))


def _filter_admin_users(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    search_col, role_col, status_col, plan_col = st.columns([1.5, 1, 1, 1], gap="medium")
    with search_col:
        user_options = [t("admin_all_users")] + [f"{str(row.get('display_name') or row.get('email') or t('admin_user_fallback_name'))} | {str(row.get('email') or '—')} | {str(row.get('user_id') or '')}" for row in df.to_dict("records")]
        picked_user = st.selectbox(t("admin_quick_pick_user"), user_options, key="admin_ops_user_pick")
    with role_col:
        role_filter = st.multiselect(t("admin_role_label"), sorted(df["role"].dropna().astype(str).unique().tolist()), key="admin_ops_role_filter")
    with status_col:
        status_filter = st.multiselect(t("admin_status_label"), sorted(df["account_status"].dropna().astype(str).unique().tolist()), key="admin_ops_status_filter")
    with plan_col:
        plan_filter = st.multiselect(t("admin_plan_label"), sorted(df["current_plan"].dropna().astype(str).unique().tolist()), key="admin_ops_plan_filter")

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

    preview_df = df.sort_values("created_at", ascending=False, na_position="last").copy()
    preview_df, *_ = _slice_admin_users_page(preview_df, "admin_users_cards_page")
    cards_html = ["<div class='admin-user-grid'>"]
    for idx, (_, row) in enumerate(preview_df.iterrows()):
        name = str(row.get("display_name") or row.get("email") or t("admin_user_fallback_name"))
        email = str(row.get("email") or t("admin_no_email"))
        role = str(row.get("role") or "—")
        plan = str(row.get("current_plan") or "free")
        status = str(row.get("account_status") or "active")
        cards_html.append(
            "<div class='admin-user-card'>"
            f"<div class='admin-user-top'><div><div class='admin-user-name'>{_html.escape(name)}</div><div class='admin-user-email'>{_html.escape(email)}</div></div></div>"
            f"<div class='admin-pill-row'><span class='admin-pill'>{_html.escape(role)}</span><span class='admin-pill'>{_html.escape(plan)}</span><span class='admin-pill'>{_html.escape(status)}</span></div>"
            f"<div class='admin-user-stats'><div class='admin-user-stat'><div class='admin-user-stat-label'>{_html.escape(t('admin_logins_label'))}</div><div class='admin-user-stat-value'>{int(row.get('login_count') or 0)}</div></div><div class='admin-user-stat'><div class='admin-user-stat-label'>{_html.escape(t('admin_students_label'))}</div><div class='admin-user-stat-value'>{int(row.get('active_student_count') or 0)}</div></div></div>"
            "</div>"
        )
    cards_html.append("</div>")
    st.markdown("".join(cards_html), unsafe_allow_html=True)
    _render_admin_users_pagination(df.sort_values("created_at", ascending=False, na_position="last").copy(), "admin_users_cards_page")

    show_table = st.toggle(t("admin_open_full_row_data_table"), key="admin_users_show_table")
    if show_table:
        st.dataframe(df, use_container_width=True, hide_index=True)

    options = [f"{row.email or '—'} | {row.user_id}" for row in df.itertuples()]
    selected_label = st.selectbox(t("admin_select_user_to_edit"), options, key="admin_users_select")
    row = df.iloc[options.index(selected_label)]
    left, right = st.columns([1.05, 0.95], gap="large")
    with left:
        st.markdown(f"### {t('admin_user_details')}")
        detail_rows = [{"field": col, "value": row.get(col)} for col in df.columns]
        st.dataframe(pd.DataFrame(detail_rows), use_container_width=True, hide_index=True)
    with right:
        st.markdown(f"### {t('admin_edit_user_row')}")
        with st.form("admin_user_inline_edit_form"):
            display_name = st.text_input(t("admin_display_name_label"), value=str(row.get("display_name") or ""))
            email = st.text_input(t("admin_email_label"), value=str(row.get("email") or ""))
            role = st.selectbox(t("admin_role_label"), ADMIN_ROLE_OPTIONS, index=ADMIN_ROLE_OPTIONS.index(str(row.get("role") or "teacher")) if str(row.get("role") or "teacher") in ADMIN_ROLE_OPTIONS else 0)
            can_teach = st.checkbox(t("admin_can_teach_label"), value=bool(row.get("can_teach", role in {"teacher", "school_admin", "admin"})))
            can_study = st.checkbox(t("admin_can_study_label"), value=bool(row.get("can_study", role == "student")))
            active_mode_options = _active_mode_options(role, can_teach, can_study)
            current_active_mode = str(row.get("last_active_mode") or active_mode_options[0])
            active_mode = st.selectbox(
                t("admin_default_active_mode_label"),
                active_mode_options,
                index=active_mode_options.index(current_active_mode) if current_active_mode in active_mode_options else 0,
            )
            account_status = st.selectbox(t("admin_account_status_label"), ACCOUNT_STATUS_OPTIONS, index=ACCOUNT_STATUS_OPTIONS.index(str(row.get("account_status") or "active")) if str(row.get("account_status") or "active") in ACCOUNT_STATUS_OPTIONS else 0)
            plan_options = [str(plan.get("id")) for plan in list_plan_catalog()]
            current_plan = str(row.get("current_plan") or "free")
            plan_id = st.selectbox(t("admin_plan_label"), plan_options, index=plan_options.index(current_plan) if current_plan in plan_options else 0)
            subscription_status = st.selectbox(t("admin_subscription_status_label"), SUBSCRIPTION_STATUS_OPTIONS, index=SUBSCRIPTION_STATUS_OPTIONS.index(str(row.get("subscription_status") or "free")) if str(row.get("subscription_status") or "free") in SUBSCRIPTION_STATUS_OPTIONS else 0)
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


def _render_accounts(df: pd.DataFrame) -> None:
    st.markdown(
        f"<div class='admin-section-card'><div class='admin-card-title'>{_html.escape(t('admin_create_account_title'))}</div><div class='admin-card-subtitle'>{_html.escape(t('admin_create_account_subtitle'))}</div></div>",
        unsafe_allow_html=True,
    )
    plans = list_plan_catalog()
    plan_ids = [str(plan.get("id")) for plan in plans]
    with st.form("admin_create_account_form"):
        display_name = st.text_input(t("admin_display_name_label"))
        email = st.text_input(t("admin_email_label"))
        role = st.selectbox(t("admin_role_label"), ADMIN_ROLE_OPTIONS, index=0)
        default_can_teach = role in {"teacher", "school_admin", "admin"}
        default_can_study = role == "student"
        can_teach = st.checkbox(t("admin_can_teach_label"), value=default_can_teach)
        can_study = st.checkbox(t("admin_can_study_label"), value=default_can_study)
        active_mode_options = _active_mode_options(role, can_teach, can_study)
        active_mode = st.selectbox(t("admin_default_active_mode_label"), active_mode_options, index=0)
        subscription_status_default = "free"
        plan_id = st.selectbox(t("admin_initial_plan_label"), plan_ids, index=0 if "free" not in plan_ids else plan_ids.index("free"))
        subscription_status = st.selectbox(t("admin_subscription_status_label"), SUBSCRIPTION_STATUS_OPTIONS, index=SUBSCRIPTION_STATUS_OPTIONS.index(subscription_status_default))
        account_status = st.selectbox(t("admin_account_status_label"), ACCOUNT_STATUS_OPTIONS, index=0)
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
        st.info("No users available yet.")
        return
    st.markdown("<div class='admin-section-card'><div class='admin-card-title'>Roles, access and status</div><div class='admin-card-subtitle'>Control roles, teaching/study permissions, account status, and subscription plans from one premium workspace.</div></div>", unsafe_allow_html=True)
    options = [f"{row.email or '—'} | {row.user_id}" for row in df.itertuples()]
    selected_label = st.selectbox("Select user", options, key="admin_roles_select")
    row = df.iloc[options.index(selected_label)]
    current_role = str(row.get("role") or "teacher")
    plan_options = [str(plan.get("id")) for plan in list_plan_catalog()]
    current_plan = str(row.get("current_plan") or "free")
    with st.form("admin_role_access_form"):
        role = st.selectbox("Role", ADMIN_ROLE_OPTIONS, index=ADMIN_ROLE_OPTIONS.index(current_role) if current_role in ADMIN_ROLE_OPTIONS else 0)
        can_teach = st.checkbox("Can teach", value=(role in {"teacher", "school_admin", "admin"}))
        can_study = st.checkbox("Can study", value=(role == "student"))
        active_mode = st.selectbox("Default active mode", ["teacher", "student"], index=0 if str(row.get("last_active_mode") or "teacher") != "student" else 1)
        account_status = st.selectbox("Account status", ACCOUNT_STATUS_OPTIONS, index=ACCOUNT_STATUS_OPTIONS.index(str(row.get("account_status") or "active")) if str(row.get("account_status") or "active") in ACCOUNT_STATUS_OPTIONS else 0)
        plan_id = st.selectbox("Assigned plan", plan_options, index=plan_options.index(current_plan) if current_plan in plan_options else 0)
        subscription_status = st.selectbox("Subscription status", SUBSCRIPTION_STATUS_OPTIONS, index=SUBSCRIPTION_STATUS_OPTIONS.index(str(row.get("subscription_status") or "free")) if str(row.get("subscription_status") or "free") in SUBSCRIPTION_STATUS_OPTIONS else 0)
        notes = st.text_area("Admin notes", value=str(row.get("admin_notes") or ""))
        submitted = st.form_submit_button("Save access settings", type="primary")
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
        selected_plan_id = st.selectbox(t("admin_select_plan"), list(plan_lookup.keys()) or ["free"], key="admin_plan_select")
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
    st.markdown("<div class='admin-section-card'><div class='admin-card-title'>Subscription control</div><div class='admin-card-subtitle'>Grant access, reset limits, and manage exceptions for users and internal beta accounts.</div></div>", unsafe_allow_html=True)
    plans = list_active_plans()
    plan_ids = [str(plan.get("id")) for plan in plans]
    user_options = [f"{row.email or '—'} | {row.user_id}" for row in df.itertuples()] if not df.empty else []
    with st.form("admin_plan_form"):
        selected_user = st.selectbox("User", user_options, key="admin_subscription_user_select") if user_options else None
        plan_id = st.selectbox("Plan", plan_ids, index=0 if plan_ids else None)
        status = st.selectbox("Status", SUBSCRIPTION_STATUS_OPTIONS, index=0)
        reason = st.text_input("Reason / note", placeholder="Beta access, lifetime grant, support fix…")
        submitted = st.form_submit_button("Assign plan / grant access", type="primary")
        if submitted:
            user_id = (str(selected_user).rsplit("|", 1)[-1].strip() if selected_user else "")
            if not user_id:
                st.error("User ID is required.")
            else:
                try:
                    update_user_plan(user_id, plan_id, status=status, manual_override=True)
                    _log_admin_override(user_id, "plan_assignment", reason or f"Assigned {plan_id} with status {status}")
                    clear_app_caches()
                    st.success("Plan updated.")
                except Exception as exc:
                    st.error(str(exc))

    with st.form("admin_user_actions"):
        action_user = st.selectbox("Target user", user_options, key="admin_action_user_select") if user_options else None
        action = st.selectbox("Action", ["reset_usage", "suspend_user", "unsuspend_user"])
        notes = st.text_area("Admin notes")
        submitted = st.form_submit_button("Apply action")
        if submitted:
            action_user_id = (str(action_user).rsplit("|", 1)[-1].strip() if action_user else "")
            if not action_user_id:
                st.error("Target user ID is required.")
            else:
                try:
                    if action == "reset_usage":
                        reset_usage(action_user_id)
                    elif action == "suspend_user":
                        get_sb().table("profiles").update({"account_status": "suspended", "admin_notes": notes}).eq("user_id", action_user_id).execute()
                    elif action == "unsuspend_user":
                        get_sb().table("profiles").update({"account_status": "active", "admin_notes": notes}).eq("user_id", action_user_id).execute()
                    _log_admin_override(action_user_id, action, notes or action)
                    clear_app_caches()
                    st.success("Action applied.")
                except Exception as exc:
                    st.error(str(exc))

    st.markdown("### Recent payment / webhook events")
    if events:
        st.dataframe(pd.DataFrame(events), use_container_width=True, hide_index=True)
    else:
        st.info("No payment events recorded yet.")


def _render_business_analytics(df: pd.DataFrame, subscriptions: list[dict]) -> None:
    st.markdown("<div class='admin-section-card'><div class='admin-card-title'>Business analytics</div><div class='admin-card-subtitle'>Track growth, plan adoption, subscription mix, and product volume from the admin side.</div></div>", unsafe_allow_html=True)
    signup_rows = _series_from_rows(df.to_dict("records") if not df.empty else [], period="M", date_key="created_at")
    if signup_rows.empty:
        st.info("Not enough profile data yet to show signup trends.")
    else:
        st.line_chart(signup_rows.set_index("period")["count"])

    if not df.empty:
        plan_mix = (
            df.groupby("current_plan", as_index=False)
            .size()
            .rename(columns={"size": "users"})
            .sort_values("users", ascending=False)
        )
        left, right = st.columns(2, gap="large")
        with left:
            st.markdown("### Accounts by plan")
            st.bar_chart(plan_mix.set_index("current_plan"))
        with right:
            st.markdown("### Subscription states")
            status_mix = (
                df.groupby("subscription_status", as_index=False)
                .size()
                .rename(columns={"size": "users"})
                .sort_values("users", ascending=False)
            )
            st.bar_chart(status_mix.set_index("subscription_status"))

    content = _content_metrics()
    st.markdown("### Product volume")
    volume_df = pd.DataFrame(
        [
            {"metric": "Worksheets", "count": content["worksheets"]},
            {"metric": "Exams", "count": content["exams"]},
            {"metric": "Lesson plans", "count": content["lesson_plans"]},
            {"metric": "Learning programs", "count": content["learning_programs"]},
            {"metric": "AI usage logs", "count": content["ai_events"]},
        ]
    )
    st.bar_chart(volume_df.set_index("metric"))


def _render_audit_log(overrides: list[dict], events: list[dict]) -> None:
    st.markdown("<div class='admin-section-card'><div class='admin-card-title'>Audit and operations trail</div><div class='admin-card-subtitle'>Review manual overrides, billing events, and operational interventions.</div></div>", unsafe_allow_html=True)
    if overrides:
        st.dataframe(pd.DataFrame(overrides), use_container_width=True, hide_index=True)
    else:
        st.info("No admin override history recorded yet.")

    st.markdown("### Payment event trail")
    if events:
        st.dataframe(pd.DataFrame(events), use_container_width=True, hide_index=True)
    else:
        st.info("No payment events recorded yet.")


def render_admin() -> None:
    require_admin()
    _inject_admin_styles()

    profiles = _fetch_profiles("")
    subscriptions = _fetch_subscriptions()
    events = _fetch_events()
    overrides = _fetch_overrides()
    df = _merge_profiles_subscriptions(profiles, subscriptions)
    _render_admin_hero(df)

    (
        tab_overview,
        tab_operations,
        tab_pricing,
        tab_subscriptions,
        tab_business,
        tab_audit,
    ) = st.tabs([
        f"📊 {t('admin_overview')}",
        f"🛠️ {t('admin_operations')}",
        f"💳 {t('admin_pricing')}",
        f"🧾 {t('admin_plans_subscriptions')}",
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
    with tab_business:
        _render_business_analytics(df, subscriptions)
    with tab_audit:
        _render_audit_log(overrides, events)
