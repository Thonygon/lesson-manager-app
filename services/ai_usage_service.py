from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from core.database import clear_app_caches, get_sb
from core.state import get_current_user_id


def _provider_display_name(value: Any) -> str:
    safe = str(value or "").strip().lower()
    if safe == "gemini":
        return "Gemini"
    if safe == "openai":
        return "OpenAI"
    if safe == "openrouter":
        return "OpenRouter"
    return str(value or "").strip()


def build_provider_chain(providers: list[str] | tuple[str, ...] | None) -> str:
    cleaned = [_provider_display_name(provider) for provider in (providers or []) if str(provider or "").strip()]
    return " -> ".join([item for item in cleaned if item])


def with_provider_chain(meta: dict[str, Any] | None, providers: list[str] | tuple[str, ...] | None) -> dict[str, Any]:
    payload = dict(meta or {})
    provider_chain = build_provider_chain(providers)
    if provider_chain and not payload.get("provider_chain"):
        payload["provider_chain"] = provider_chain
    return payload


def log_ai_usage_event(feature_name: str, status: str, meta: dict[str, Any] | None = None) -> None:
    payload = {
        "feature_name": " ".join(str(feature_name or "").split()).strip() or "unknown",
        "status": " ".join(str(status or "").split()).strip() or "unknown",
        "meta_json": dict(meta or {}),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    user_id = " ".join(str(get_current_user_id() or "").split()).strip()
    if user_id:
        payload["user_id"] = user_id
    try:
        get_sb().table("ai_usage_logs").insert(payload).execute()
        clear_app_caches()
    except Exception:
        pass
