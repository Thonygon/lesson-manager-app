from __future__ import annotations

import os
import streamlit as st

from services.subscription_service import get_user_subscription

CHECKOUT_PRICE_SECRETS = {
    "teacher_pro": "STRIPE_PRICE_TEACHER_PRO",
    "school": "STRIPE_PRICE_SCHOOL",
}


def _get_secret(name: str, default: str = "") -> str:
    try:
        return str(st.secrets.get(name, default) or os.getenv(name, default) or "").strip()
    except Exception:
        return str(os.getenv(name, default) or "").strip()


def _stripe_client():
    api_key = _get_secret("STRIPE_SECRET_KEY")
    if not api_key:
        return None
    try:
        import stripe
    except ImportError:
        return None
    stripe.api_key = api_key
    return stripe


def payments_configured() -> bool:
    return _stripe_client() is not None


def create_checkout_session(user_id: str, email: str, plan_id: str) -> str:
    """Create a Stripe Checkout session and return its hosted URL."""
    stripe = _stripe_client()
    if stripe is None:
        raise RuntimeError("Stripe is not configured. Add STRIPE_SECRET_KEY and install stripe.")

    price_id = _get_secret(CHECKOUT_PRICE_SECRETS.get(plan_id, ""))
    if not price_id:
        raise RuntimeError(f"Missing Stripe price secret for plan: {plan_id}")

    app_url = _get_secret("APP_BASE_URL", "http://localhost:8501").rstrip("/")
    session = stripe.checkout.Session.create(
        mode="subscription",
        customer_email=email or None,
        line_items=[{"price": price_id, "quantity": 1}],
        success_url=f"{app_url}/?page=account&checkout=success",
        cancel_url=f"{app_url}/?page=pricing&checkout=cancelled",
        metadata={"user_id": str(user_id), "plan_id": str(plan_id)},
        subscription_data={"metadata": {"user_id": str(user_id), "plan_id": str(plan_id)}},
    )
    return str(session.url)


def create_customer_portal_session(user_id: str) -> str:
    stripe = _stripe_client()
    if stripe is None:
        raise RuntimeError("Stripe is not configured. Add STRIPE_SECRET_KEY and install stripe.")
    subscription = get_user_subscription(user_id)
    customer_id = str(subscription.get("provider_customer_id") or "").strip()
    if not customer_id:
        raise RuntimeError("No Stripe customer is linked to this account yet.")
    app_url = _get_secret("APP_BASE_URL", "http://localhost:8501").rstrip("/")
    portal = stripe.billing_portal.Session.create(customer=customer_id, return_url=f"{app_url}/?page=account")
    return str(portal.url)


def record_payment_event(provider: str, event_type: str, payload: dict, processed: bool = False) -> None:
    from core.database import get_sb

    get_sb().table("payment_events").insert(
        {
            "provider": provider,
            "event_type": event_type,
            "payload": payload,
            "processed": bool(processed),
        }
    ).execute()


def apply_stripe_subscription_update(subscription: dict, status: str | None = None) -> None:
    """
    Persist a verified Stripe subscription payload to Supabase.

    Call this only after webhook signature verification in the backend/webhook process.
    """
    from core.database import get_sb

    metadata = subscription.get("metadata") or {}
    user_id = str(metadata.get("user_id") or "").strip()
    plan_id = str(metadata.get("plan_id") or "teacher_pro").strip()
    if not user_id:
        return

    payload = {
        "user_id": user_id,
        "plan_id": plan_id,
        "subscription_status": status or subscription.get("status") or "active",
        "provider_customer_id": subscription.get("customer"),
        "provider_subscription_id": subscription.get("id"),
        "trial_end": subscription.get("trial_end"),
        "current_period_end": subscription.get("current_period_end"),
        "cancel_at_period_end": bool(subscription.get("cancel_at_period_end") or False),
        "manual_override": False,
    }
    get_sb().table("user_subscriptions").upsert(payload, on_conflict="user_id").execute()
    get_sb().table("profiles").update(
        {"current_plan": plan_id, "subscription_status": payload["subscription_status"]}
    ).eq("user_id", user_id).execute()
