from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
import uuid

import streamlit as st

from core.database import get_sb, json_safe
from core.state import get_current_user_id, get_current_user_role


JOB_TABLE = "system_jobs"
JOB_STATES = ("QUEUED", "RUNNING", "COMPLETED", "FAILED", "CANCELLED", "STALE")
ACTIVE_JOB_STATES = {"QUEUED", "RUNNING"}
LEGAL_JOB_TRANSITIONS = {
    "QUEUED": {"RUNNING", "CANCELLED", "STALE", "FAILED"},
    "RUNNING": {"COMPLETED", "FAILED", "CANCELLED", "STALE"},
    "FAILED": set(),
    "COMPLETED": set(),
    "CANCELLED": set(),
    "STALE": {"QUEUED"},
}


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _utc_now_iso() -> str:
    return _utc_now().isoformat()


def _clean_text(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def can_transition_job_state(current_status: str, next_status: str) -> bool:
    safe_current = _clean_text(current_status).upper()
    safe_next = _clean_text(next_status).upper()
    return safe_next in LEGAL_JOB_TRANSITIONS.get(safe_current, set())


def build_job_id(prefix: str = "job") -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


@st.cache_data(ttl=10, show_spinner=False)
def list_jobs(
    *,
    job_type: str = "",
    statuses: list[str] | None = None,
    limit: int = 100,
    cache_bust: str = "",
) -> list[dict[str, Any]]:
    query = (
        get_sb()
        .table(JOB_TABLE)
        .select("*")
        .order("created_at", desc=True)
        .limit(max(1, min(int(limit), 500)))
    )
    safe_job_type = _clean_text(job_type)
    if safe_job_type:
        query = query.eq("job_type", safe_job_type)
    safe_statuses = [status for status in (statuses or []) if _clean_text(status)]
    if safe_statuses:
        query = query.in_("status", safe_statuses)
    try:
        return [dict(row) for row in (query.execute().data or [])]
    except Exception:
        return []


def get_job(job_id: str) -> dict[str, Any]:
    safe_job_id = _clean_text(job_id)
    if not safe_job_id:
        return {}
    rows = (
        get_sb()
        .table(JOB_TABLE)
        .select("*")
        .eq("job_id", safe_job_id)
        .limit(1)
        .execute()
    ).data or []
    return dict(rows[0]) if rows else {}


def clear_job_cache() -> None:
    list_jobs.clear()


def create_job(
    *,
    job_type: str,
    job_version: str,
    idempotency_key: str,
    payload_json: dict[str, Any] | None = None,
    priority: int = 50,
    related_entity_type: str = "",
    related_entity_id: str = "",
    max_retries: int = 1,
) -> tuple[bool, dict[str, Any] | None, str]:
    existing = [
        row
        for row in list_jobs(statuses=sorted(ACTIVE_JOB_STATES), limit=200, cache_bust="active-check")
        if _clean_text(row.get("idempotency_key")) == _clean_text(idempotency_key)
    ]
    if existing:
        return False, dict(existing[0]), "A matching active job already exists."

    payload = {
        "job_id": build_job_id("mljob"),
        "job_type": _clean_text(job_type),
        "job_version": _clean_text(job_version),
        "status": "QUEUED",
        "priority": int(priority),
        "requested_by": _clean_text(get_current_user_id()) or None,
        "requested_by_role": _clean_text(get_current_user_role()),
        "requested_at": _utc_now_iso(),
        "progress_pct": 0,
        "current_stage": "queued",
        "payload_json": json_safe(payload_json or {}),
        "retry_count": 0,
        "max_retries": int(max_retries),
        "idempotency_key": _clean_text(idempotency_key),
        "related_entity_type": _clean_text(related_entity_type),
        "related_entity_id": _clean_text(related_entity_id),
    }
    try:
        get_sb().table(JOB_TABLE).insert(payload).execute()
        clear_job_cache()
        return True, get_job(payload["job_id"]), "Job created."
    except Exception as exc:
        return False, None, str(exc)


def update_job_state(
    job_id: str,
    *,
    next_status: str | None = None,
    current_stage: str | None = None,
    progress_pct: float | int | None = None,
    result_json: dict[str, Any] | None = None,
    warning_json: dict[str, Any] | None = None,
    error_code: str | None = None,
    error_message: str | None = None,
) -> tuple[bool, str]:
    job = get_job(job_id)
    if not job:
        return False, "Job not found."

    payload: dict[str, Any] = {"updated_at": _utc_now_iso(), "heartbeat_at": _utc_now_iso()}
    if next_status:
        safe_next_status = _clean_text(next_status).upper()
        current_status = _clean_text(job.get("status")).upper()
        if safe_next_status != current_status and not can_transition_job_state(current_status, safe_next_status):
            return False, f"Illegal job transition: {current_status} -> {safe_next_status}"
        payload["status"] = safe_next_status
        if safe_next_status == "RUNNING":
            payload["started_at"] = job.get("started_at") or _utc_now_iso()
        if safe_next_status in {"COMPLETED", "FAILED", "CANCELLED", "STALE"}:
            payload["completed_at"] = _utc_now_iso()
    if current_stage is not None:
        payload["current_stage"] = _clean_text(current_stage)
    if progress_pct is not None:
        payload["progress_pct"] = max(0, min(float(progress_pct), 100))
    if result_json is not None:
        payload["result_json"] = json_safe(result_json)
    if warning_json is not None:
        payload["warning_json"] = json_safe(warning_json)
    if error_code is not None:
        payload["error_code"] = _clean_text(error_code)
    if error_message is not None:
        payload["error_message"] = str(error_message)
    try:
        get_sb().table(JOB_TABLE).update(payload).eq("job_id", _clean_text(job_id)).execute()
        clear_job_cache()
        return True, "Job updated."
    except Exception as exc:
        return False, str(exc)


def mark_stale_jobs(*, stale_after_minutes: int = 30) -> int:
    now = _utc_now()
    stale_before = now - timedelta(minutes=max(1, int(stale_after_minutes)))
    updated = 0
    for row in list_jobs(statuses=sorted(ACTIVE_JOB_STATES), limit=200, cache_bust="stale-scan"):
        heartbeat_text = _clean_text(row.get("heartbeat_at") or row.get("updated_at") or row.get("requested_at"))
        if not heartbeat_text:
            continue
        try:
            heartbeat_at = datetime.fromisoformat(heartbeat_text.replace("Z", "+00:00"))
        except Exception:
            continue
        if heartbeat_at.tzinfo is None:
            heartbeat_at = heartbeat_at.replace(tzinfo=timezone.utc)
        if heartbeat_at < stale_before:
            ok, _ = update_job_state(str(row.get("job_id") or ""), next_status="STALE", current_stage="stale")
            if ok:
                updated += 1
    return updated
