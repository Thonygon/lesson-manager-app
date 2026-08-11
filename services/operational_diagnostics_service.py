from __future__ import annotations

import hashlib
import logging
import os
import re
import threading
import time
import traceback
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

import streamlit as st

from core.database import get_sb
from core.state import get_current_user_id, get_current_user_role
from services.authorization_service import (
    CAPABILITY_MANAGE_OPERATIONAL_DIAGNOSTICS,
    CAPABILITY_VIEW_OPERATIONAL_DIAGNOSTICS,
    require_capability,
)
from services.privileged_action_service import record_privileged_action


logger = logging.getLogger(__name__)

DIAGNOSTICS_TABLE = "application_diagnostic_events"
DIAGNOSTICS_RPC = "record_application_diagnostic"
DIAGNOSTICS_STATUS_RPC = "update_application_diagnostic_status"
VALID_SEVERITIES = {"warning", "error", "critical"}
VALID_STATUSES = {"open", "acknowledged", "resolved", "ignored"}
SAFE_CONTEXT_KEYS = {
    "resource_type",
    "resource_id",
    "http_status",
    "query_name",
    "fallback_used",
    "record_count",
    "correlation_id",
}

_CAPTURE_LOCK = threading.Lock()
_RECENT_FINGERPRINTS: dict[str, tuple[float, str]] = {}
_CAPTURE_STATE = threading.local()
_LOCAL_SUPPRESSION_SECONDS = 60.0

_EMAIL_RE = re.compile(r"(?i)\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b")
_JWT_RE = re.compile(r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\b")
_SECRET_RE = re.compile(
    r"(?i)\b(api[_-]?key|authorization|bearer|password|secret|token)\b\s*[:=]\s*([^\s,;]+)"
)
_URL_RE = re.compile(r"https?://\S+", re.IGNORECASE)
_UUID_RE = re.compile(r"\b[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}\b", re.IGNORECASE)


def _clean_text(value: Any, *, limit: int) -> str:
    return " ".join(str(value or "").split()).strip()[:limit]


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def diagnostics_enabled() -> bool:
    raw = str(os.getenv("CLASSIO_DIAGNOSTICS_ENABLED", "true") or "").strip().lower()
    return raw not in {"0", "false", "no", "off"}


def _environment_name() -> str:
    return _clean_text(os.getenv("CLASSIO_ENVIRONMENT", "production"), limit=40) or "production"


def _release_version() -> str:
    for key in ("CLASSIO_RELEASE", "VERCEL_GIT_COMMIT_SHA", "RENDER_GIT_COMMIT", "GIT_COMMIT"):
        value = _clean_text(os.getenv(key, ""), limit=120)
        if value:
            return value
    return "unknown"


def _redact_url_query(match: re.Match[str]) -> str:
    url = match.group(0)
    if "?" not in url:
        return url
    return f"{url.split('?', 1)[0]}?[redacted-query]"


def sanitize_text(value: Any, *, limit: int = 1000) -> str:
    text = str(value or "")
    text = _EMAIL_RE.sub("[redacted-email]", text)
    text = _JWT_RE.sub("[redacted-token]", text)
    text = _SECRET_RE.sub(lambda match: f"{match.group(1)}=[redacted]", text)
    text = _URL_RE.sub(_redact_url_query, text)
    text = _UUID_RE.sub("[redacted-id]", text)
    return text[: max(0, int(limit))]


def sanitize_context(context: dict[str, Any] | None) -> dict[str, Any]:
    safe: dict[str, Any] = {}
    for key, value in (context or {}).items():
        safe_key = str(key or "").strip()
        if safe_key not in SAFE_CONTEXT_KEYS or value is None:
            continue
        if isinstance(value, bool):
            safe[safe_key] = value
        elif isinstance(value, (int, float)):
            safe[safe_key] = value
        else:
            safe[safe_key] = sanitize_text(value, limit=160)
    return safe


def _safe_user_face(value: Any = None) -> str:
    face = _clean_text(value or get_current_user_role(), limit=20).lower()
    return face if face in {"student", "teacher", "admin", "developer"} else "unknown"


def _correlation_id() -> str:
    try:
        existing = _clean_text(st.session_state.get("_diagnostic_correlation_id"), limit=80)
        if existing:
            return existing
        generated = str(uuid4())
        st.session_state["_diagnostic_correlation_id"] = generated
        return generated
    except Exception:
        return str(uuid4())


def _stack_location(exc: BaseException) -> str:
    tb = traceback.extract_tb(exc.__traceback__) if exc.__traceback__ else []
    app_frames = [frame for frame in tb if "/site-packages/" not in frame.filename]
    frame = app_frames[-1] if app_frames else (tb[-1] if tb else None)
    if frame is None:
        return "unknown"
    filename = str(frame.filename).replace("\\", "/").rsplit("/", 2)[-1]
    return f"{filename}:{frame.name}:{frame.lineno}"


def build_fingerprint(exc: BaseException, *, component: str, operation: str) -> str:
    material = "|".join(
        [
            type(exc).__name__,
            _clean_text(component, limit=120),
            _clean_text(operation, limit=120),
            _stack_location(exc),
        ]
    )
    return hashlib.sha256(material.encode("utf-8", errors="replace")).hexdigest()


def _safe_stack(exc: BaseException) -> str:
    rendered = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
    return sanitize_text(rendered, limit=12000)


def _recent_reference(fingerprint: str, event_id: str) -> str:
    now = time.monotonic()
    with _CAPTURE_LOCK:
        stale = [
            key
            for key, (seen_at, _reference) in _RECENT_FINGERPRINTS.items()
            if now - seen_at > _LOCAL_SUPPRESSION_SECONDS * 5
        ]
        for key in stale:
            _RECENT_FINGERPRINTS.pop(key, None)
        recent = _RECENT_FINGERPRINTS.get(fingerprint)
        if recent and now - recent[0] < _LOCAL_SUPPRESSION_SECONDS:
            return recent[1]
        _RECENT_FINGERPRINTS[fingerprint] = (now, event_id)
    return ""


def _remember_persisted_reference(fingerprint: str, event_id: str) -> None:
    with _CAPTURE_LOCK:
        _RECENT_FINGERPRINTS[fingerprint] = (time.monotonic(), event_id)


def _rpc_result_event_id(result: Any, fallback_event_id: str) -> str:
    rows = getattr(result, "data", None) or []
    if isinstance(rows, dict):
        rows = [rows]
    if rows and isinstance(rows[0], dict):
        return str(rows[0].get("captured_event_id") or rows[0].get("event_id") or fallback_event_id)
    return fallback_event_id


def capture_exception(
    exc: BaseException,
    *,
    component: str,
    operation: str,
    severity: str = "error",
    page_key: str = "",
    user_face: str = "",
    context: dict[str, Any] | None = None,
) -> str:
    event_id = str(uuid4())
    safe_severity = severity if severity in VALID_SEVERITIES else "error"
    fingerprint = build_fingerprint(exc, component=component, operation=operation)
    safe_message = sanitize_text(exc, limit=1000)
    safe_context = dict(context or {})
    safe_context.setdefault("correlation_id", _correlation_id())
    current_user_id = _clean_text(get_current_user_id(), limit=80)

    if not diagnostics_enabled() or getattr(_CAPTURE_STATE, "active", False):
        return event_id
    if not current_user_id:
        return event_id
    recent_reference = _recent_reference(fingerprint, event_id)
    if recent_reference:
        return recent_reference

    _CAPTURE_STATE.active = True
    try:
        result = get_sb().rpc(
            DIAGNOSTICS_RPC,
            {
                "p_event_id": event_id,
                "p_fingerprint": fingerprint,
                "p_severity": safe_severity,
                "p_component": _clean_text(component, limit=120) or "application",
                "p_operation": _clean_text(operation, limit=120) or "unknown",
                "p_page_key": _clean_text(page_key, limit=120),
                "p_user_face": _safe_user_face(user_face),
                "p_environment": _environment_name(),
                "p_release_version": _release_version(),
                "p_exception_type": type(exc).__name__[:160],
                "p_safe_message": safe_message,
                "p_safe_stack": _safe_stack(exc),
                "p_context_json": sanitize_context(safe_context),
            },
        ).execute()
        persisted_event_id = _rpc_result_event_id(result, event_id)
        _remember_persisted_reference(fingerprint, persisted_event_id)
        return persisted_event_id
    except Exception as reporting_exc:
        with _CAPTURE_LOCK:
            _RECENT_FINGERPRINTS.pop(fingerprint, None)
        if "authentication_required" in sanitize_text(reporting_exc, limit=240).lower():
            _remember_persisted_reference(fingerprint, event_id)
            return event_id
        logger.error(
            "Operational diagnostic capture unavailable event_id=%s reporter_error=%s",
            event_id,
            sanitize_text(type(reporting_exc).__name__, limit=120),
        )
        return event_id
    finally:
        _CAPTURE_STATE.active = False


def capture_warning(
    code: str,
    *,
    component: str,
    operation: str,
    page_key: str = "",
    user_face: str = "",
    context: dict[str, Any] | None = None,
) -> str:
    return capture_exception(
        RuntimeError(_clean_text(code, limit=240) or "operational_warning"),
        component=component,
        operation=operation,
        severity="warning",
        page_key=page_key,
        user_face=user_face,
        context=context,
    )


def short_event_reference(event_id: str) -> str:
    compact = re.sub(r"[^A-Fa-f0-9]", "", str(event_id or ""))
    return f"ERR-{compact[:8].upper()}" if compact else "ERR-UNKNOWN"


@st.cache_data(ttl=20, show_spinner=False)
def list_diagnostics(
    *,
    severity: str = "all",
    status: str = "all",
    user_face: str = "all",
    page_key: str = "",
    release_version: str = "",
    limit: int = 100,
    cache_bust: str = "",
) -> list[dict[str, Any]]:
    require_capability(CAPABILITY_VIEW_OPERATIONAL_DIAGNOSTICS)
    query = (
        get_sb()
        .table(DIAGNOSTICS_TABLE)
        .select(
            "id,event_id,fingerprint,severity,status,component,operation,page_key,user_face,environment,release_version,"
            "exception_type,safe_message,safe_stack,context_json,occurrence_count,first_seen_at,last_seen_at,"
            "acknowledged_at,resolved_at,resolution_note,created_at,updated_at"
        )
        .order("last_seen_at", desc=True)
        .limit(max(1, min(int(limit), 500)))
    )
    if severity in VALID_SEVERITIES:
        query = query.eq("severity", severity)
    if status in VALID_STATUSES:
        query = query.eq("status", status)
    if user_face in {"student", "teacher", "admin", "developer", "unknown"}:
        query = query.eq("user_face", user_face)
    if _clean_text(page_key, limit=120):
        query = query.eq("page_key", _clean_text(page_key, limit=120))
    if _clean_text(release_version, limit=120):
        query = query.eq("release_version", _clean_text(release_version, limit=120))
    return [dict(row) for row in (query.execute().data or [])]


@st.cache_data(ttl=30, show_spinner=False)
def count_active_critical_diagnostics(cache_bust: str = "") -> int:
    require_capability(CAPABILITY_VIEW_OPERATIONAL_DIAGNOSTICS)
    result = (
        get_sb()
        .table(DIAGNOSTICS_TABLE)
        .select("event_id", count="exact")
        .eq("severity", "critical")
        .in_("status", ["open", "acknowledged"])
        .limit(1)
        .execute()
    )
    return int(getattr(result, "count", 0) or 0)


def update_diagnostic_status(event_id: str, *, status: str, resolution_note: str = "") -> tuple[bool, str]:
    require_capability(CAPABILITY_MANAGE_OPERATIONAL_DIAGNOSTICS)
    safe_event_id = _clean_text(event_id, limit=80)
    safe_status = _clean_text(status, limit=24).lower()
    if not safe_event_id or safe_status not in VALID_STATUSES:
        return False, "operational_diagnostics_invalid_status_update"

    existing = (
        get_sb()
        .table(DIAGNOSTICS_TABLE)
        .select("event_id,status,resolution_note")
        .eq("event_id", safe_event_id)
        .limit(1)
        .execute()
    ).data or []
    if not existing:
        return False, "operational_diagnostics_event_not_found"

    safe_note = sanitize_text(resolution_note, limit=1000)
    current_row = dict(existing[0])
    rpc_rows = (
        get_sb()
        .rpc(
            DIAGNOSTICS_STATUS_RPC,
            {
                "p_event_id": safe_event_id,
                "p_status": safe_status,
                "p_resolution_note": safe_note or None,
            },
        )
        .execute()
    ).data or []
    if rpc_rows and rpc_rows[0] is False:
        return False, "operational_diagnostics_event_not_found"

    list_diagnostics.clear()
    count_active_critical_diagnostics.clear()
    record_privileged_action(
        action_type="operational_diagnostic_status_changed",
        entity_type="application_diagnostic_event",
        entity_id=safe_event_id,
        before_json=current_row,
        after_json={"status": safe_status, "resolution_note": safe_note},
        reason=safe_note,
    )
    return True, "operational_diagnostics_update_success"


def clear_diagnostics_cache() -> None:
    list_diagnostics.clear()
    count_active_critical_diagnostics.clear()
