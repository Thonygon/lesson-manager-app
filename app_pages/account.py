from __future__ import annotations

import streamlit as st

from core.state import get_current_user_id
from services.payment_service import create_customer_portal_session, payments_configured
from services.subscription_service import get_user_plan, get_user_subscription, usage_dataframe


def _format_date(value) -> str:
    if not value:
        return "—"
    return str(value)


def render_account() -> None:
    st.title("Account & Subscription")
    st.caption("Manage your Classio plan, usage, and billing portal access.")

    if st.query_params.get("checkout") == "success":
        st.success("Checkout completed. Your plan will update after the verified Stripe webhook is processed.")

    user_id = get_current_user_id()
    plan = get_user_plan(user_id)
    subscription = get_user_subscription(user_id)

    c1, c2, c3 = st.columns(3)
    c1.metric("Current plan", plan.get("name", "Free"))
    c2.metric("Subscription status", subscription.get("subscription_status") or "free")
    c3.metric("Renews / ends", _format_date(subscription.get("current_period_end")))

    if subscription.get("cancel_at_period_end"):
        st.warning("This subscription is set to cancel at period end. Access remains until the current period expires.")

    st.subheader("Usage this month")
    st.dataframe(usage_dataframe(user_id), use_container_width=True, hide_index=True)

    st.subheader("Billing")
    st.write("Billing changes are handled by the payment provider portal, not manually inside Classio.")
    cols = st.columns(3)
    with cols[0]:
        if st.button("Upgrade / view pricing", type="primary"):
            st.session_state["page"] = "pricing"
            st.rerun()
    with cols[1]:
        if st.button("Manage billing"):
            if not payments_configured():
                st.warning("Stripe Customer Portal is not configured yet.")
            else:
                try:
                    url = create_customer_portal_session(user_id)
                    st.link_button("Open billing portal", url)
                except Exception as exc:
                    st.error(str(exc))
    with cols[2]:
        st.caption("Downgrades and cancellations apply according to the provider subscription settings.")

    if subscription.get("provider_customer_id"):
        with st.expander("Provider IDs"):
            st.code(subscription.get("provider_customer_id"), language=None)
            st.code(subscription.get("provider_subscription_id") or "No subscription id", language=None)
