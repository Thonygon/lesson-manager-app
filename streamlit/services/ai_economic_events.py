"""Durable, metadata-only operation and provider-attempt journal for Classio AI."""

from __future__ import annotations

from contextvars import ContextVar
from dataclasses import dataclass
from datetime import datetime, timezone
import re
from typing import Any, Callable, TypeVar
from uuid import UUID, uuid4

from core.database import get_sb
from core.state import get_current_user_id


@dataclass
class _Operation:
    feature: str
    modality: str
    operation_id: str = ""
    attempt_no: int = 0
    hinted: bool = False
    telemetry_failed: bool = False


_current: ContextVar[_Operation | None] = ContextVar("classio_ai_economic_operation", default=None)
T = TypeVar("T")


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _actor_id() -> str | None:
    try:
        return str(UUID(str(get_current_user_id())))
    except (TypeError, ValueError, AttributeError):
        return None


def _row(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if hasattr(value, "model_dump"):
        return value.model_dump(exclude_none=True)
    return {}


def _value(value: Any, name: str) -> Any:
    return value.get(name) if isinstance(value, dict) else getattr(value, name, None)


def _count(value: Any) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else None


def _numeric_usage(value: Any, depth: int = 0) -> dict[str, Any]:
    if depth > 2:
        return {}
    safe = {}
    for key, item in list(_row(value).items())[:30]:
        if not isinstance(key, str) or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{0,60}", key):
            continue
        number = _count(item)
        if number is not None:
            safe[key] = number
        else:
            nested = _numeric_usage(item, depth + 1)
            if nested:
                safe[key] = nested
    return safe


def provider_usage(provider: str, response: Any) -> dict[str, Any]:
    raw = _row(_value(response, "usage_metadata") or _value(response, "usageMetadata")) if provider == "gemini" else _row(_value(response, "usage"))
    prompt_details = _row(raw.get("prompt_tokens_details"))
    completion_details = _row(raw.get("completion_tokens_details"))
    def field(*names: str) -> int | None:
        for name in names:
            number = _count(raw.get(name))
            if number is not None:
                return number
        return None
    return {
        "input_tokens": field("prompt_token_count", "promptTokenCount") if provider == "gemini" else field("prompt_tokens"),
        "output_tokens": field("candidates_token_count", "candidatesTokenCount") if provider == "gemini" else field("completion_tokens"),
        "cached_input_tokens": field("cached_content_token_count", "cachedContentTokenCount") if provider == "gemini" else _count(prompt_details.get("cached_tokens")),
        "reasoning_tokens": field("thoughts_token_count", "thoughtsTokenCount") if provider == "gemini" else _count(completion_details.get("reasoning_tokens")),
        "usage_observed": bool(raw),
        "usage_json": _numeric_usage(raw),
    }


def _confirm_update(result: Any, table: str) -> None:
    rows = getattr(result, "data", None)
    if not isinstance(rows, list) or len(rows) != 1:
        raise RuntimeError(f"AI economic telemetry {table} update was not confirmed")


def note_functional_event(feature: str, status: str, meta: dict[str, Any] | None = None) -> None:
    """Use existing functional events as the operation boundary when present."""
    current = _current.get()
    if status == "requested":
        try:
            import streamlit as st
            st.session_state.pop("_classio_last_successful_ai_operation", None)
        except Exception:
            pass
        if current and current.operation_id:
            _finish_operation(current, "failed", "interrupted")
        modality = "image" if str((meta or {}).get("kind") or "") == "image_support" else "text"
        _current.set(_Operation(feature=str(feature or "unknown")[:80], modality=modality, hinted=True))
    elif status in {"success", "failed"} and current and current.feature == feature:
        if current.operation_id:
            _finish_operation(current, status, None if status == "success" else "functional_failed")
        _current.set(None)


def _ensure_operation(modality: str) -> _Operation:
    current = _current.get()
    if current and current.telemetry_failed:
        raise RuntimeError("AI economic telemetry is unavailable")
    if current is None:
        current = _Operation(feature="unclassified_ai", modality=modality)
        _current.set(current)
    if current.operation_id:
        return current
    current.modality = modality
    current.operation_id = str(uuid4())
    payload = {
        "operation_id": current.operation_id,
        "actor_user_id": _actor_id(),
        "source": "streamlit",
        "feature_name": current.feature,
        "modality": modality,
        "status": "started",
    }
    try:
        get_sb().table("classio_ai_operations").insert(payload).execute()
    except Exception:
        current.telemetry_failed = True
        raise RuntimeError("AI economic telemetry could not start") from None
    return current


@dataclass(frozen=True)
class Attempt:
    attempt_id: str
    operation: _Operation
    provider: str


def start_provider_attempt(provider: str, model: str, modality: str = "text") -> Attempt:
    operation = _ensure_operation(modality)
    operation.attempt_no += 1
    attempt_id = str(uuid4())
    payload = {
        "attempt_id": attempt_id,
        "operation_id": operation.operation_id,
        "attempt_no": operation.attempt_no,
        "provider": provider,
        "model_requested": str(model)[:160],
        "modality": modality,
        "status": "started",
    }
    try:
        get_sb().table("classio_provider_attempts").insert(payload).execute()
    except Exception:
        operation.telemetry_failed = True
        raise RuntimeError("AI economic attempt could not start") from None
    return Attempt(attempt_id, operation, provider)


def _finish_operation(operation: _Operation, status: str, error_kind: str | None) -> None:
    if operation.telemetry_failed:
        raise RuntimeError("AI economic telemetry is unavailable")
    payload = {"status": status, "finished_at": _utc_now(), "error_kind": error_kind}
    try:
        result = get_sb().table("classio_ai_operations").update(payload).eq("operation_id", operation.operation_id).execute()
        _confirm_update(result, "operation")
        if status == "success" and operation.modality == "text" and _actor_id():
            try:
                import streamlit as st
                st.session_state["_classio_last_successful_ai_operation"] = {"id": operation.operation_id, "actor_id": _actor_id(), "finished_at": payload["finished_at"]}
            except Exception:
                pass
    except Exception:
        operation.telemetry_failed = True
        raise RuntimeError("AI economic operation could not finish") from None


def latest_successful_generation_operation_id() -> str:
    """Return the current teacher's most recent successful text operation."""
    try:
        import streamlit as st
        row = st.session_state.get("_classio_last_successful_ai_operation") or {}
        if row.get("actor_id") != _actor_id():
            return ""
        finished_at = datetime.fromisoformat(str(row.get("finished_at") or ""))
        if abs((datetime.now(timezone.utc) - finished_at).total_seconds()) > 3600:
            return ""
        return str(UUID(str(row.get("id") or "")))
    except Exception:
        return ""


def finish_provider_attempt(attempt: Attempt, status: str, response: Any = None, *, model_reported: str | None = None, http_status: int | None = None, image_count: int | None = None, image_size_requested: str | None = None, error_kind: str | None = None) -> None:
    operation = attempt.operation
    usage = provider_usage(attempt.provider, response)
    payload = {
        "status": status,
        "finished_at": _utc_now(),
        "model_reported": str(model_reported)[:160] if model_reported else None,
        "http_status": http_status,
        "provider_request_id": str(_value(response, "id") or _value(response, "response_id") or _value(response, "responseId") or "")[:160] or None,
        "image_count": image_count,
        "image_size_requested": image_size_requested[:40] if image_size_requested else None,
        "error_kind": error_kind,
        **usage,
    }
    try:
        result = get_sb().table("classio_provider_attempts").update(payload).eq("attempt_id", attempt.attempt_id).execute()
        _confirm_update(result, "attempt")
        if not operation.hinted:
            _finish_operation(operation, status, error_kind)
            _current.set(None)
    except Exception:
        operation.telemetry_failed = True
        raise RuntimeError("AI economic attempt could not finish") from None


def run_recorded_provider_attempt(provider: str, model: str, call: Callable[[], Any], extract: Callable[[Any], T], *, modality: str = "text", image_size_requested: str | None = None) -> T:
    attempt = start_provider_attempt(provider, model, modality)
    response = None
    try:
        response = call()
        value = extract(response)
        if not value:
            raise ValueError("AI provider returned no usable result")
    except Exception as exc:
        http_status = getattr(exc, "status_code", None) or getattr(exc, "code", None)
        finish_provider_attempt(
            attempt, "failed", response,
            http_status=http_status if isinstance(http_status, int) and 100 <= http_status <= 599 else None,
            image_size_requested=image_size_requested,
            error_kind=re.sub(r"[^a-z0-9_]", "_", type(exc).__name__.lower())[:80],
        )
        raise
    reported = str(_value(response, "model") or model)
    finish_provider_attempt(attempt, "success", response, model_reported=reported, image_count=1 if modality == "image" else None, image_size_requested=image_size_requested)
    return value
