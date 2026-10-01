from __future__ import annotations

from core.database import get_sb
from core.state import get_current_user_id
from services.subscription_service import get_user_plan, get_usage, _usage_tracking_upsert

FEATURE_ALIASES = {
    "ai_generations": "ai_tools",
    "pdf_exports": "pdf_export",
    "word_exports": "word_export",
}

FEATURE_DEFAULTS = {
    "videos_access": True,
}


def get_feature_limit(user_id: str | None, feature: str) -> int | None:
    plan = get_user_plan(user_id)
    limits = plan.get("limits_json") or {}
    limit = limits.get(feature)
    if limit is None:
        return None
    try:
        return int(limit)
    except Exception:
        return None


def get_feature_usage_status(user_id: str | None, feature: str) -> dict:
    usage = get_usage(user_id)
    used = int(usage.get(feature) or 0)
    limit = get_feature_limit(user_id, feature)
    remaining = None if limit is None else max(0, limit - used)
    return {
        "used": used,
        "limit": limit,
        "remaining": remaining,
    }


def user_has_feature(user_id: str | None, feature: str) -> bool:
    plan = get_user_plan(user_id)
    features = plan.get("features_json") or {}
    feature_key = FEATURE_ALIASES.get(str(feature), str(feature))
    if feature_key in features:
        return bool(features.get(feature_key, False))
    return bool(FEATURE_DEFAULTS.get(feature_key, False))


def check_usage_limit(user_id: str | None, feature: str) -> bool:
    status = get_feature_usage_status(user_id, feature)
    if status["limit"] is None:
        return True
    return status["used"] < int(status["limit"])


def increment_usage(user_id: str | None, feature: str, amount: int = 1) -> bool:
    uid = str(user_id or get_current_user_id() or "").strip()
    if not uid:
        return False
    usage = get_usage(uid)
    current = int(usage.get(feature) or 0)
    payload = {"user_id": uid, feature: current + int(amount)}
    try:
        _usage_tracking_upsert(payload)
        return True
    except Exception:
        return False


def can_export_pdf(user_id: str | None = None) -> bool:
    uid = user_id or get_current_user_id()
    return user_has_feature(uid, "pdf_export") and check_usage_limit(uid, "pdf_exports")


def can_export_word(user_id: str | None = None) -> bool:
    uid = user_id or get_current_user_id()
    return user_has_feature(uid, "word_export") and check_usage_limit(uid, "word_exports")


def can_use_ai_tool(user_id: str | None = None) -> bool:
    uid = user_id or get_current_user_id()
    return user_has_feature(uid, "ai_tools") and check_usage_limit(uid, "ai_generations")
