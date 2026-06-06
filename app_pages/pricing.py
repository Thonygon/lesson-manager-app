from __future__ import annotations

import streamlit as st

from core.state import get_current_user_id
from services.payment_service import create_checkout_session, payments_configured
from services.subscription_service import list_active_plans

PLAN_COPY = {
    "free": {
        "tagline": "Start tracking classes with light AI and export limits.",
        "cta": "Current starter plan",
        "features": ["Limited classes", "Limited AI generations", "Limited PDF exports"],
    },
    "teacher_pro": {
        "tagline": "For independent teachers ready to run Classio daily.",
        "cta": "Start Pro checkout",
        "features": ["More AI generations", "More students and classes", "Premium exports and tools"],
    },
    "school": {
        "tagline": "For teams, institutions, and multi-teacher administration.",
        "cta": "Contact / request school checkout",
        "features": ["Multiple teachers", "Shared administration", "Institution controls"],
    },
    "beta_lifetime": {
        "tagline": "Granted manually by Classio admins for beta/lifetime access.",
        "cta": "Admin-assigned only",
        "features": ["Manual admin assignment", "Extended limits", "Founder/beta access"],
    },
}


def _money(plan: dict) -> str:
    price = plan.get("price")
    if price is None:
        return "Custom"
    try:
        cents = int(price)
    except Exception:
        cents = 0
    if cents == 0:
        return "Free"
    return f"${cents / 100:,.0f}/{plan.get('billing_interval') or 'month'}"


def _limit(plan: dict, key: str) -> str:
    value = (plan.get("limits_json") or {}).get(key)
    return "Unlimited" if value is None else str(value)


def render_pricing() -> None:
    st.title("Pricing")
    st.caption("Choose the launch plan that matches your teaching setup. Paid access is activated only after Stripe webhook confirmation.")

    if st.query_params.get("checkout") == "cancelled":
        st.warning("Checkout was cancelled. Your current plan has not changed.")

    plans = [plan for plan in list_active_plans() if str(plan.get("id")) != "beta_lifetime"]
    cols = st.columns(len(plans) or 1)
    user_id = get_current_user_id()
    email = str(st.session_state.get("user_email") or "")

    for col, plan in zip(cols, plans):
        plan_id = str(plan.get("id") or "free")
        copy = PLAN_COPY.get(plan_id, PLAN_COPY["free"])
        with col:
            st.markdown(f"### {plan.get('name', plan_id)}")
            st.markdown(f"## {_money(plan)}")
            st.write(copy["tagline"])
            for feature in copy["features"]:
                st.write(f"✓ {feature}")
            st.divider()
            st.write(f"AI generations: **{_limit(plan, 'ai_generations')} / month**")
            st.write(f"PDF exports: **{_limit(plan, 'pdf_exports')} / month**")
            st.write(f"Students: **{_limit(plan, 'students_count')}**")
            st.write(f"Classes: **{_limit(plan, 'classes_count')} / month**")

            if plan_id == "free":
                st.info("Free plan is available automatically.")
            elif plan_id == "school":
                st.info("School plan checkout can be wired to a dedicated Stripe price or handled by sales.")
                if st.button(copy["cta"], key=f"upgrade_{plan_id}"):
                    st.session_state["school_plan_interest"] = True
                    st.success("Thanks — school-plan request captured for follow-up.")
            else:
                if st.button(copy["cta"], key=f"upgrade_{plan_id}", type="primary"):
                    if not payments_configured():
                        st.warning("Stripe checkout is not configured yet. Add STRIPE_SECRET_KEY and plan price IDs before launch.")
                    else:
                        try:
                            url = create_checkout_session(user_id, email, plan_id)
                            st.link_button("Continue to secure checkout", url)
                        except Exception as exc:
                            st.error(str(exc))

    st.divider()
    st.subheader("Plan comparison")
    rows = []
    for plan in plans:
        features = plan.get("features_json") or {}
        rows.append(
            {
                "Plan": plan.get("name"),
                "Price": _money(plan),
                "AI tools": "Yes" if features.get("ai_tools") else "No",
                "Premium tools": "Yes" if features.get("premium_tools") else "No",
                "School admin": "Yes" if features.get("school_admin") else "No",
                "AI limit": _limit(plan, "ai_generations"),
                "PDF limit": _limit(plan, "pdf_exports"),
                "Student limit": _limit(plan, "students_count"),
            }
        )
    st.dataframe(rows, use_container_width=True, hide_index=True)

    st.info("Trial and final launch pricing can be adjusted in the plans table without changing this page.")
