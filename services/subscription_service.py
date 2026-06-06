from __future__ import annotations

from datetime import date, datetime, timezone
import pandas as pd
import streamlit as st

from core.database import get_sb
from core.state import get_current_user_id

PLAN_ORDER = ["free", "teacher_pro", "school", "beta_lifetime"]

DEFAULT_PLANS = [
    {
        "id": "free",
        "name": "Free",
        "price": 0,
        "billing_interval": "month",
        "features_json": {
            "ai_tools": True,
            "pdf_export": True,
            "premium_tools": False,
            "school_admin": False,
        },
        "limits_json": {
            "ai_generations": 10,
            "pdf_exports": 3,
            "students_count": 5,
            "classes_count": 20,
        },
        "active": True,
    },
    {
        "id": "teacher_pro",
        "name": "Teacher Pro",
        "price": 1900,
        "billing_interval": "month",
        "features_json": {
            "ai_tools": True,
            "pdf_export": True,
            "premium_tools": True,
            "school_admin": False,
        },
        "limits_json": {
            "ai_generations": 250,
            "pdf_exports": 100,
            "students_count": 75,
            "classes_count": 500,
        },
        "active": True,
    },
    {
        "id": "school",
        "name": "School Plan",
        "price": None,
        "billing_interval": "month",
        "features_json": {
            "ai_tools": True,
            "pdf_export": True,
            "premium_tools": True,
            "school_admin": True,
        },
        "limits_json": {
            "ai_generations": 2000,
            "pdf_exports": 1000,
            "students_count": 1000,
            "classes_count": 10000,
        },
        "active": True,
    },
    {
        "id": "beta_lifetime",
        "name": "Beta / Lifetime",
        "price": 0,
        "billing_interval": "lifetime",
        "features_json": {
            "ai_tools": True,
            "pdf_export": True,
            "premium_tools": True,
            "school_admin": False,
        },
        "limits_json": {
            "ai_generations": 1000,
            "pdf_exports": 500,
            "students_count": 500,
            "classes_count": 5000,
        },
        "active": True,
    },
]


def _normalize_plan(row: dict) -> dict:
    out = dict(row or {})
    out.setdefault("features_json", {})
    out.setdefault("limits_json", {})
    out.setdefault("active", True)
    return out


@st.cache_data(ttl=60, show_spinner=False)
def list_active_plans() -> list[dict]:
    try:
        res = get_sb().table("plans").select("*").eq("active", True).execute()
        rows = getattr(res, "data", None) or []
        if rows:
            order = {plan_id: idx for idx, plan_id in enumerate(PLAN_ORDER)}
            return sorted([_normalize_plan(r) for r in rows], key=lambda r: order.get(str(r.get("id")), 99))
    except Exception:
        pass
    return DEFAULT_PLANS


def get_plan_by_id(plan_id: str) -> dict:
    plan_id = str(plan_id or "free")
    for plan in list_active_plans():
        if str(plan.get("id")) == plan_id:
            return plan
    return DEFAULT_PLANS[0]


def get_user_subscription(user_id: str | None = None) -> dict:
    uid = str(user_id or get_current_user_id() or "").strip()
    if not uid:
        return {}
    try:
        res = (
            get_sb()
            .table("user_subscriptions")
            .select("*, plans(*)")
            .eq("user_id", uid)
            .limit(1)
            .execute()
        )
        rows = getattr(res, "data", None) or []
        return rows[0] if rows else {}
    except Exception:
        return {}


def get_profile_plan(user_id: str | None = None) -> str:
    uid = str(user_id or get_current_user_id() or "").strip()
    if not uid:
        return "free"
    try:
        res = get_sb().table("profiles").select("current_plan").eq("user_id", uid).limit(1).execute()
        rows = getattr(res, "data", None) or []
        return str((rows[0] if rows else {}).get("current_plan") or "free")
    except Exception:
        return "free"


def get_user_plan(user_id: str | None = None) -> dict:
    subscription = get_user_subscription(user_id)
    if subscription and subscription.get("manual_override"):
        return get_plan_by_id(subscription.get("plan_id") or "free")
    if subscription and str(subscription.get("subscription_status") or "").lower() in {"active", "trialing"}:
        return get_plan_by_id(subscription.get("plan_id") or "free")
    return get_plan_by_id(get_profile_plan(user_id))


def get_usage(user_id: str | None = None) -> dict:
    uid = str(user_id or get_current_user_id() or "").strip()
    defaults = {
        "user_id": uid,
        "ai_generations": 0,
        "pdf_exports": 0,
        "students_count": 0,
        "classes_count": 0,
        "monthly_reset_date": date.today().isoformat(),
    }
    if not uid:
        return defaults
    try:
        res = get_sb().table("usage_tracking").select("*").eq("user_id", uid).limit(1).execute()
        rows = getattr(res, "data", None) or []
        return {**defaults, **(rows[0] if rows else {})}
    except Exception:
        return defaults


def usage_dataframe(user_id: str | None = None) -> pd.DataFrame:
    usage = get_usage(user_id)
    plan = get_user_plan(user_id)
    limits = plan.get("limits_json") or {}
    rows = []
    for key, label in [
        ("ai_generations", "AI generations"),
        ("pdf_exports", "PDF exports"),
        ("students_count", "Students"),
        ("classes_count", "Classes"),
    ]:
        rows.append({"Metric": label, "Used": int(usage.get(key) or 0), "Limit": limits.get(key, "Unlimited")})
    return pd.DataFrame(rows)


def update_user_plan(user_id: str, plan_id: str, status: str = "active", manual_override: bool = True) -> None:
    payload = {
        "user_id": str(user_id),
        "plan_id": str(plan_id),
        "subscription_status": str(status),
        "manual_override": bool(manual_override),
    }
    get_sb().table("user_subscriptions").upsert(payload, on_conflict="user_id").execute()
    get_sb().table("profiles").update({"current_plan": str(plan_id), "subscription_status": str(status)}).eq("user_id", str(user_id)).execute()


def reset_usage(user_id: str) -> None:
    get_sb().table("usage_tracking").upsert(
        {
            "user_id": str(user_id),
            "ai_generations": 0,
            "pdf_exports": 0,
            "students_count": 0,
            "classes_count": 0,
            "monthly_reset_date": datetime.now(timezone.utc).date().isoformat(),
        },
        on_conflict="user_id",
    ).execute()
