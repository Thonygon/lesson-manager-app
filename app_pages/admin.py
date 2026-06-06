from __future__ import annotations

import pandas as pd
import streamlit as st

from core.database import get_sb
from services.auth_service import require_admin
from services.subscription_service import list_active_plans, reset_usage, update_user_plan


def _fetch_profiles(search: str = "") -> list[dict]:
    try:
        q = get_sb().table("profiles").select(
            "user_id,email,role,current_plan,subscription_status,created_at,account_status,admin_notes"
        ).order("created_at", desc=True).limit(200)
        if search:
            q = q.ilike("email", f"%{search}%")
        return getattr(q.execute(), "data", None) or []
    except Exception as exc:
        st.warning(f"Could not load profiles: {exc}")
        return []


def _fetch_subscriptions() -> list[dict]:
    try:
        return getattr(get_sb().table("user_subscriptions").select("*").limit(200).execute(), "data", None) or []
    except Exception:
        return []


def _fetch_events() -> list[dict]:
    try:
        return getattr(
            get_sb()
            .table("payment_events")
            .select("id,provider,event_type,processed,created_at")
            .order("created_at", desc=True)
            .limit(50)
            .execute(),
            "data",
            None,
        ) or []
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
                "role": profile.get("role"),
                "current_plan": profile.get("current_plan") or sub.get("plan_id") or "free",
                "subscription_status": profile.get("subscription_status") or sub.get("subscription_status") or "free",
                "customer_id": sub.get("provider_customer_id"),
                "manual_override": sub.get("manual_override"),
                "account_status": profile.get("account_status"),
                "created_at": profile.get("created_at"),
                "admin_notes": profile.get("admin_notes"),
            }
        )
    return pd.DataFrame(rows)


def render_admin() -> None:
    require_admin()
    st.title("Admin")
    st.caption("Internal Classio management dashboard. This page is protected by a profiles.role = admin check.")

    search = st.text_input("Search users by email")
    profiles = _fetch_profiles(search.strip())
    subscriptions = _fetch_subscriptions()
    df = _merge_profiles_subscriptions(profiles, subscriptions)

    st.subheader("Users")
    if df.empty:
        st.info("No users found or admin tables are not migrated yet.")
    else:
        st.dataframe(df, use_container_width=True, hide_index=True)

    st.subheader("Manual subscription controls")
    plan_ids = [str(plan.get("id")) for plan in list_active_plans()]
    with st.form("admin_plan_form"):
        user_id = st.text_input("User ID")
        plan_id = st.selectbox("Plan", plan_ids, index=0)
        status = st.selectbox("Status", ["active", "trialing", "past_due", "cancelled", "free"], index=0)
        reason = st.text_input("Reason / note", placeholder="Beta access, lifetime grant, support fix…")
        submitted = st.form_submit_button("Assign plan / grant access", type="primary")
        if submitted:
            if not user_id.strip():
                st.error("User ID is required.")
            else:
                try:
                    update_user_plan(user_id.strip(), plan_id, status=status, manual_override=True)
                    if reason.strip():
                        get_sb().table("admin_overrides").insert(
                            {
                                "user_id": user_id.strip(),
                                "override_type": "plan_assignment",
                                "reason": reason.strip(),
                                "created_by": str(st.session_state.get("user_id") or ""),
                            }
                        ).execute()
                    st.success("Plan updated.")
                except Exception as exc:
                    st.error(str(exc))

    with st.form("admin_user_actions"):
        action_user_id = st.text_input("Target user ID", key="admin_action_user")
        action = st.selectbox("Action", ["reset_usage", "suspend_user", "unsuspend_user"])
        notes = st.text_area("Admin notes")
        submitted = st.form_submit_button("Apply action")
        if submitted:
            if not action_user_id.strip():
                st.error("Target user ID is required.")
            else:
                try:
                    if action == "reset_usage":
                        reset_usage(action_user_id.strip())
                    elif action == "suspend_user":
                        get_sb().table("profiles").update({"account_status": "suspended", "admin_notes": notes}).eq("user_id", action_user_id.strip()).execute()
                    elif action == "unsuspend_user":
                        get_sb().table("profiles").update({"account_status": "active", "admin_notes": notes}).eq("user_id", action_user_id.strip()).execute()
                    st.success("Action applied.")
                except Exception as exc:
                    st.error(str(exc))

    st.subheader("Recent payment / webhook events")
    events = _fetch_events()
    if events:
        st.dataframe(pd.DataFrame(events), use_container_width=True, hide_index=True)
    else:
        st.info("No payment events recorded yet.")
