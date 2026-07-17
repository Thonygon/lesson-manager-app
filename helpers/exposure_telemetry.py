from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta, timezone
import hashlib
import json
import logging
import os
from typing import Any
from uuid import NAMESPACE_URL, uuid5

import pandas as pd
import streamlit as st

from core.database import _execute_query_with_diagnostics, clear_app_caches, get_sb, register_cache
from core.state import get_current_user_id, get_current_user_role

logger = logging.getLogger(__name__)


_EXPOSURE_NAMESPACE = uuid5(NAMESPACE_URL, "classio/resource-exposure")
_CYCLE_SESSION_KEY = "_classio_exposure_cycles"
_ACTIVE_EXPOSURE_MAP_KEY = "_classio_active_exposure_ids"
_DEFAULT_MODEL_VERSION = "phase2_telemetry_v1"
_DEFAULT_WINDOW_DAYS = 35


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _now_iso() -> str:
    return _now().isoformat()


def _clean_text(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value in (None, "", "None"):
            return default
        return float(value)
    except Exception:
        return default


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        if value in (None, "", "None"):
            return default
        return int(value)
    except Exception:
        return default


def _nullable_profile_id(value: Any) -> str | None:
    text = _clean_text(value)
    return text or None


def _json_safe(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, bool)):
        return value
    if isinstance(value, float):
        return value if value == value else None
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(item) for item in value]
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


def _hash_text(value: str) -> str:
    return hashlib.sha256(str(value or "").encode("utf-8")).hexdigest()


def _model_version() -> str:
    raw = os.getenv("CLASSIO_MODEL_VERSION", "").strip()
    return raw or _DEFAULT_MODEL_VERSION


def _observation_window_days() -> int:
    raw = os.getenv("CLASSIO_EXPOSURE_TELEMETRY_WINDOW_DAYS", str(_DEFAULT_WINDOW_DAYS))
    try:
        return max(7, min(int(raw), 180))
    except Exception:
        return _DEFAULT_WINDOW_DAYS


def _frame_signature(items: list[dict[str, Any]], *, keys: list[str]) -> str:
    values: list[str] = []
    for idx, item in enumerate(items):
        row = item.get("row") if isinstance(item.get("row"), dict) else {}
        parts = [str(idx)]
        for key in keys:
            if key.startswith("row."):
                parts.append(str(row.get(key.split(".", 1)[1]) or ""))
            else:
                parts.append(str(item.get(key) or ""))
        values.append("|".join(parts))
    return _hash_text("||".join(values))


def _cycle_state() -> dict[str, Any]:
    payload = st.session_state.get(_CYCLE_SESSION_KEY)
    if isinstance(payload, dict):
        return payload
    payload = {}
    st.session_state[_CYCLE_SESSION_KEY] = payload
    return payload


def _active_exposure_state() -> dict[str, str]:
    payload = st.session_state.get(_ACTIVE_EXPOSURE_MAP_KEY)
    if isinstance(payload, dict):
        return payload
    payload = {}
    st.session_state[_ACTIVE_EXPOSURE_MAP_KEY] = payload
    return payload


def get_surface_cycle_id(
    *,
    surface: str,
    exposure_type: str,
    signature: str,
    viewer_user_id: str,
    ttl_minutes: int = 20,
) -> str:
    key = f"{viewer_user_id}:{exposure_type}:{surface}"
    state = _cycle_state()
    record = state.get(key) if isinstance(state.get(key), dict) else {}
    now = _now()
    last_seen_at = str(record.get("last_seen_at") or "")
    previous_seen = None
    if last_seen_at:
        try:
            previous_seen = datetime.fromisoformat(last_seen_at)
        except Exception:
            previous_seen = None
    should_rotate = (
        not record
        or str(record.get("signature") or "") != str(signature or "")
        or previous_seen is None
        or (now - previous_seen) > timedelta(minutes=max(1, ttl_minutes))
    )
    if should_rotate:
        cycle_seed = f"{key}:{signature}:{now.isoformat()}"
        cycle_id = str(uuid5(_EXPOSURE_NAMESPACE, cycle_seed))
        record = {
            "cycle_id": cycle_id,
            "signature": str(signature or ""),
            "last_seen_at": now.isoformat(),
        }
    else:
        record["last_seen_at"] = now.isoformat()
    state[key] = record
    st.session_state[_CYCLE_SESSION_KEY] = state
    return str(record.get("cycle_id") or "")


def _exposure_identity(payload: dict[str, Any]) -> str:
    keys = [
        "cycle_id",
        "viewer_user_id",
        "teacher_id",
        "student_id",
        "resource_id",
        "resource_type",
        "exposure_type",
        "surface",
        "position",
        "recommendation_bucket",
        "recommendation_focus_kind",
        "learning_program_assignment_id",
        "learning_program_topic_id",
    ]
    raw = "|".join(str(payload.get(key) or "") for key in keys)
    return str(uuid5(_EXPOSURE_NAMESPACE, raw))


def _exposure_idempotency_key(payload: dict[str, Any]) -> str:
    return _hash_text(
        "|".join(
            [
                str(payload.get("exposure_id") or ""),
                str(payload.get("surface") or ""),
                str(payload.get("position") or ""),
                str(payload.get("viewer_user_id") or ""),
            ]
        )
    )


def _event_idempotency_key(*, exposure_id: str, event_type: str, event_at: str, score_pct: Any = None) -> str:
    return _hash_text("|".join([exposure_id, event_type, event_at, str(score_pct or "")]))


def _store_active_exposure(signature: str, exposure_id: str) -> None:
    state = _active_exposure_state()
    state[str(signature or "")] = str(exposure_id or "")
    st.session_state[_ACTIVE_EXPOSURE_MAP_KEY] = state


def lookup_active_exposure_id(signature: str) -> str:
    return str((_active_exposure_state().get(str(signature or "")) or "")).strip()


def _fetch_existing_exposure_id(idempotency_key: str) -> str:
    try:
        rows = (
            get_sb()
            .table("resource_exposures")
            .select("exposure_id")
            .eq("idempotency_key", idempotency_key)
            .limit(1)
            .execute()
        ).data or []
        return str((rows[0] if rows else {}).get("exposure_id") or "").strip()
    except Exception:
        return ""


def _insert_exposure_row(payload: dict[str, Any]) -> str:
    idempotency_key = str(payload.get("idempotency_key") or "").strip()
    exposure_id = str(payload.get("exposure_id") or "").strip()
    if not idempotency_key or not exposure_id:
        return ""
    try:
        get_sb().table("resource_exposures").insert(payload).execute()
        return exposure_id
    except Exception as exc:
        if "cycle_id" in str(exc):
            fallback_payload = dict(payload)
            fallback_payload.pop("cycle_id", None)
            try:
                get_sb().table("resource_exposures").insert(fallback_payload).execute()
                return exposure_id
            except Exception:
                logger.exception(
                    "Failed to insert resource exposure after cycle_id fallback",
                    extra={"exposure_id": exposure_id, "idempotency_key": idempotency_key},
                )
                return _fetch_existing_exposure_id(idempotency_key)
        logger.exception("Failed to insert resource exposure", extra={"exposure_id": exposure_id, "idempotency_key": idempotency_key})
        return _fetch_existing_exposure_id(idempotency_key)


def _insert_event_row(payload: dict[str, Any]) -> bool:
    idempotency_key = str(payload.get("idempotency_key") or "").strip()
    if not idempotency_key:
        return False
    try:
        get_sb().table("resource_exposure_events").insert(payload).execute()
        return True
    except Exception:
        logger.exception("Failed to insert resource exposure event", extra={"idempotency_key": idempotency_key, "event_type": payload.get("event_type")})
        try:
            rows = (
                get_sb()
                .table("resource_exposure_events")
                .select("id")
                .eq("idempotency_key", idempotency_key)
                .limit(1)
                .execute()
            ).data or []
            return bool(rows)
        except Exception:
            return False


def record_exposure(payload: dict[str, Any]) -> str:
    base = dict(payload or {})
    base["teacher_id"] = _nullable_profile_id(base.get("teacher_id"))
    base["student_id"] = _nullable_profile_id(base.get("student_id"))
    base["viewer_user_id"] = _nullable_profile_id(base.get("viewer_user_id") or get_current_user_id())
    base["resource_id"] = _clean_text(base.get("resource_id"))
    base["resource_type"] = _clean_text(base.get("resource_type"))
    base["exposure_type"] = _clean_text(base.get("exposure_type"))
    base["surface"] = _clean_text(base.get("surface"))
    base["model_component_id"] = _clean_text(base.get("model_component_id"))
    base["model_version"] = _clean_text(base.get("model_version") or _model_version())
    base["recommendation_bucket"] = _clean_text(base.get("recommendation_bucket"))
    base["recommendation_focus_kind"] = _clean_text(base.get("recommendation_focus_kind"))
    base["context_json"] = _json_safe(base.get("context_json") or {})
    base["shown_at"] = str(base.get("shown_at") or _now_iso())
    base["created_at"] = str(base.get("created_at") or base["shown_at"])
    exposure_id = _clean_text(base.get("exposure_id")) or _exposure_identity(base)
    base["exposure_id"] = exposure_id
    base["idempotency_key"] = _clean_text(base.get("idempotency_key")) or _exposure_idempotency_key(base)
    return _insert_exposure_row(base)


def record_exposure_event(
    *,
    exposure_id: str,
    event_type: str,
    event_at: str | None = None,
    score_pct: Any = None,
    outcome_json: dict[str, Any] | None = None,
    teacher_id: str = "",
    student_id: str = "",
    viewer_user_id: str = "",
    is_backfilled: bool = False,
) -> bool:
    clean_exposure_id = _clean_text(exposure_id)
    clean_event_type = _clean_text(event_type)
    if not clean_exposure_id or not clean_event_type:
        return False
    resolved_event_at = str(event_at or _now_iso())
    payload = {
        "exposure_id": clean_exposure_id,
        "event_type": clean_event_type,
        "event_at": resolved_event_at,
        "score_pct": score_pct,
        "outcome_json": _json_safe(outcome_json or {}),
        "idempotency_key": _event_idempotency_key(
            exposure_id=clean_exposure_id,
            event_type=clean_event_type,
            event_at=resolved_event_at,
            score_pct=score_pct,
        ),
        "is_backfilled": bool(is_backfilled),
        "teacher_id": _nullable_profile_id(teacher_id),
        "student_id": _nullable_profile_id(student_id),
        "viewer_user_id": _nullable_profile_id(viewer_user_id or get_current_user_id()),
        "created_at": resolved_event_at,
    }
    return _insert_event_row(payload)


def attach_student_recommendation_exposures(rows: list[dict[str, Any]], *, surface: str) -> list[dict[str, Any]]:
    safe_rows = [dict(row) for row in (rows or []) if isinstance(row, dict)]
    viewer_user_id = _clean_text(get_current_user_id())
    if not safe_rows or not viewer_user_id:
        return safe_rows
    signature = _frame_signature(safe_rows[:12], keys=["resource_type", "id", "assignment_id", "score"])
    cycle_id = get_surface_cycle_id(
        surface=surface,
        exposure_type="optional_student_recommendation",
        signature=signature,
        viewer_user_id=viewer_user_id,
    )
    enriched: list[dict[str, Any]] = []
    for position, item in enumerate(safe_rows[:12], start=1):
        row = item.get("row") if isinstance(item.get("row"), dict) else {}
        resource_id = _clean_text(item.get("id"))
        if not resource_id:
            enriched.append(item)
            continue
        payload = {
            "cycle_id": cycle_id,
            "teacher_id": "",
            "student_id": viewer_user_id,
            "viewer_user_id": viewer_user_id,
            "resource_id": resource_id,
            "resource_type": _clean_text(item.get("resource_type")),
            "exposure_type": "optional_student_recommendation",
            "surface": surface,
            "position": position,
            "shown_at": _now_iso(),
            "model_component_id": "student_recommendation_ranker",
            "heuristic_score": _safe_float(item.get("score")) - (_safe_float(item.get("ml_blend_weight")) * _safe_float(item.get("ml_score"))),
            "learned_score": _safe_float(item.get("ml_score")),
            "final_score": _safe_float(item.get("score")),
            "context_json": {
                "subject": _clean_text(item.get("subject")),
                "topic": _clean_text(item.get("topic")),
                "level": _clean_text(item.get("level")),
                "assigned_resource": bool(item.get("assigned_resource")),
                "assignment_id": _safe_int(item.get("assignment_id")) or None,
                "source_created_at": row.get("created_at"),
            },
        }
        exposure_id = record_exposure(payload)
        signature_key = f"student_reco:{surface}:{item.get('resource_type')}:{resource_id}"
        if exposure_id:
            item["_telemetry_exposure_id"] = exposure_id
            _store_active_exposure(signature_key, exposure_id)
        enriched.append(item)
    return enriched


def _teacher_material_meta(row: dict[str, Any], kind: str, source: str) -> dict[str, Any]:
    return {
        "subject": _clean_text(row.get("subject")),
        "topic": _clean_text(row.get("topic") or row.get("title")),
        "level": _clean_text(row.get("level") if kind == "exam" else row.get("level_or_band")),
        "source": _clean_text(source),
    }


def attach_teacher_material_feed_exposures(
    rows: list[dict[str, Any]],
    *,
    kind: str,
    source: str,
    surface: str,
) -> list[dict[str, Any]]:
    safe_rows = [dict(row) for row in (rows or []) if isinstance(row, dict)]
    viewer_user_id = _clean_text(get_current_user_id())
    if not safe_rows or not viewer_user_id:
        return safe_rows
    signature = _frame_signature(safe_rows[:12], keys=["row.id", "id", "title", "topic"])
    cycle_id = get_surface_cycle_id(
        surface=surface,
        exposure_type="teacher_material_feed",
        signature=signature,
        viewer_user_id=viewer_user_id,
    )
    enriched: list[dict[str, Any]] = []
    for position, row in enumerate(safe_rows[:12], start=1):
        resource_id = _clean_text(row.get("id"))
        if not resource_id:
            enriched.append(row)
            continue
        payload = {
            "cycle_id": cycle_id,
            "teacher_id": viewer_user_id,
            "student_id": "",
            "viewer_user_id": viewer_user_id,
            "resource_id": resource_id,
            "resource_type": _clean_text(kind),
            "exposure_type": "teacher_material_feed",
            "surface": surface,
            "position": position,
            "shown_at": _now_iso(),
            "model_component_id": "teacher_material_feed_ranker",
            "context_json": _teacher_material_meta(row, kind, source),
        }
        exposure_id = record_exposure(payload)
        signature_key = f"teacher_material:{surface}:{kind}:{source}:{resource_id}"
        if exposure_id:
            row["_telemetry_exposure_id"] = exposure_id
            _store_active_exposure(signature_key, exposure_id)
        enriched.append(row)
    return enriched


def attach_teacher_objective_exposures(rows: list[dict[str, Any]], *, surface: str) -> list[dict[str, Any]]:
    safe_rows = [dict(row) for row in (rows or []) if isinstance(row, dict)]
    viewer_user_id = _clean_text(get_current_user_id())
    if not safe_rows or not viewer_user_id:
        return safe_rows
    signature = _frame_signature(safe_rows[:12], keys=["title", "learning_program_assignment_id", "learning_program_topic_id", "recommendation_bucket"])
    cycle_id = get_surface_cycle_id(
        surface=surface,
        exposure_type="teacher_objective_recommendation",
        signature=signature,
        viewer_user_id=viewer_user_id,
    )
    enriched: list[dict[str, Any]] = []
    for position, item in enumerate(safe_rows[:12], start=1):
        topic_id = _safe_int(item.get("learning_program_topic_id"))
        assignment_id = _safe_int(item.get("learning_program_assignment_id"))
        resource_id = f"topic:{topic_id}" if topic_id > 0 else _clean_text(item.get("title"))
        payload = {
            "cycle_id": cycle_id,
            "teacher_id": viewer_user_id,
            "student_id": _clean_text(item.get("student_id")),
            "viewer_user_id": viewer_user_id,
            "resource_id": resource_id,
            "resource_type": "teacher_objective",
            "exposure_type": "teacher_objective_recommendation",
            "surface": surface,
            "position": position,
            "recommendation_bucket": _clean_text(item.get("recommendation_bucket")),
            "recommendation_focus_kind": _clean_text(item.get("focus_kind")),
            "learning_program_assignment_id": assignment_id or None,
            "learning_program_topic_id": topic_id or None,
            "shown_at": _now_iso(),
            "model_component_id": "teacher_recommendation_objective_selector",
            "heuristic_score": _safe_float(item.get("score")),
            "final_score": _safe_float(item.get("score")),
            "context_json": {
                "program_id": _safe_int(item.get("program_id")) or None,
                "subject_key": _clean_text(item.get("subject_key")),
                "title": _clean_text(item.get("title")),
            },
        }
        exposure_id = record_exposure(payload)
        signature_key = f"teacher_objective:{surface}:{assignment_id}:{topic_id}:{position}"
        if exposure_id:
            item["_telemetry_exposure_id"] = exposure_id
            _store_active_exposure(signature_key, exposure_id)
        enriched.append(item)
    return enriched


def attach_teacher_resource_recommendation_exposures(
    resources: list[dict[str, Any]],
    *,
    recommendation_item: dict[str, Any],
    surface: str,
) -> list[dict[str, Any]]:
    safe_resources = [dict(row) for row in (resources or []) if isinstance(row, dict)]
    viewer_user_id = _clean_text(get_current_user_id())
    if not safe_resources or not viewer_user_id:
        return safe_resources
    signature = _frame_signature(safe_resources[:12], keys=["kind", "source", "score", "row.id"])
    cycle_id = get_surface_cycle_id(
        surface=surface,
        exposure_type="teacher_resource_recommendation",
        signature=f"{signature}:{_safe_int(recommendation_item.get('learning_program_topic_id'))}",
        viewer_user_id=viewer_user_id,
    )
    assignment_id = _safe_int(recommendation_item.get("learning_program_assignment_id"))
    topic_id = _safe_int(recommendation_item.get("learning_program_topic_id"))
    enriched: list[dict[str, Any]] = []
    for position, resource in enumerate(safe_resources[:12], start=1):
        row = resource.get("row") if isinstance(resource.get("row"), dict) else {}
        resource_id = _clean_text(row.get("id"))
        if not resource_id:
            enriched.append(resource)
            continue
        payload = {
            "cycle_id": cycle_id,
            "teacher_id": viewer_user_id,
            "student_id": _clean_text(recommendation_item.get("student_id")),
            "viewer_user_id": viewer_user_id,
            "resource_id": resource_id,
            "resource_type": _clean_text(resource.get("kind")),
            "exposure_type": "teacher_resource_recommendation",
            "surface": surface,
            "position": position,
            "recommendation_bucket": _clean_text(recommendation_item.get("recommendation_bucket")),
            "recommendation_focus_kind": _clean_text(recommendation_item.get("focus_kind")),
            "learning_program_assignment_id": assignment_id or None,
            "learning_program_topic_id": topic_id or None,
            "shown_at": _now_iso(),
            "model_component_id": "teacher_recommendation_resource_ranker",
            "heuristic_score": _safe_float(resource.get("score")),
            "final_score": _safe_float(resource.get("score")),
            "context_json": {
                "source": _clean_text(resource.get("source")),
                "subject": _clean_text(row.get("subject")),
                "topic": _clean_text(row.get("topic")),
            },
        }
        exposure_id = record_exposure(payload)
        signature_key = f"teacher_resource:{surface}:{assignment_id}:{topic_id}:{resource.get('kind')}:{resource_id}"
        if exposure_id:
            resource["_telemetry_exposure_id"] = exposure_id
            _store_active_exposure(signature_key, exposure_id)
        enriched.append(resource)
    return enriched


def record_assignment_exposure_from_assignment_row(
    assignment_row: dict[str, Any],
    *,
    shown_at: str | None = None,
    is_backfilled: bool = False,
) -> str:
    row = dict(assignment_row or {})
    assignment_id = _safe_int(row.get("id"))
    if assignment_id <= 0:
        return ""
    if _clean_text(row.get("resource_exposure_id")):
        return _clean_text(row.get("resource_exposure_id"))
    teacher_id = _clean_text(row.get("teacher_id"))
    student_id = _clean_text(row.get("student_id"))
    resource_id = _clean_text(row.get("source_record_id"))
    resource_type = _clean_text(row.get("assignment_type"))
    assigned_at = str(shown_at or row.get("assigned_at") or row.get("created_at") or _now_iso())
    payload = {
        "cycle_id": f"assignment:{assignment_id}",
        "teacher_id": teacher_id,
        "student_id": student_id,
        "viewer_user_id": teacher_id,
        "resource_id": resource_id or f"assignment:{assignment_id}",
        "resource_type": resource_type,
        "exposure_type": "assigned_resource",
        "surface": "assignment_creation",
        "position": 1,
        "recommendation_bucket": _clean_text(row.get("recommendation_bucket")),
        "recommendation_focus_kind": _clean_text(row.get("recommendation_focus_kind")),
        "learning_program_assignment_id": _safe_int(row.get("learning_program_assignment_id")) or None,
        "learning_program_topic_id": _safe_int(row.get("learning_program_topic_id")) or None,
        "shown_at": assigned_at,
        "model_component_id": "assignment_creation_workflow",
        "context_json": {
            "assignment_id": assignment_id,
            "source_type": _clean_text(row.get("source_type")),
            "status": _clean_text(row.get("status")),
        },
        "is_backfilled": bool(is_backfilled),
    }
    exposure_id = record_exposure(payload)
    if not exposure_id:
        return ""
    try:
        get_sb().table("teacher_assignments").update(
            {
                "resource_exposure_id": exposure_id,
                "updated_at": _now_iso(),
            }
        ).eq("id", assignment_id).execute()
    except Exception:
        pass
    record_exposure_event(
        exposure_id=exposure_id,
        event_type="assigned",
        event_at=assigned_at,
        teacher_id=teacher_id,
        student_id=student_id,
        viewer_user_id=teacher_id,
        is_backfilled=is_backfilled,
    )
    return exposure_id


def ensure_assignment_exposure_for_assignment_id(assignment_id: int) -> str:
    safe_assignment_id = _safe_int(assignment_id)
    if safe_assignment_id <= 0:
        return ""
    try:
        rows = (
            get_sb()
            .table("teacher_assignments")
            .select(
                "id,teacher_id,student_id,assignment_type,source_type,source_record_id,status,"
                "assigned_at,created_at,recommendation_bucket,recommendation_focus_kind,"
                "learning_program_assignment_id,learning_program_topic_id,resource_exposure_id"
            )
            .eq("id", safe_assignment_id)
            .limit(1)
            .execute()
        ).data or []
    except Exception:
        return ""
    return record_assignment_exposure_from_assignment_row((rows[0] if rows else {}))


def backfill_assignment_exposures(*, teacher_id: str = "", limit: int = 250) -> dict[str, int]:
    safe_teacher_id = _clean_text(teacher_id or get_current_user_id())
    if not safe_teacher_id:
        return {"scanned": 0, "created": 0, "skipped": 0}
    try:
        query = (
            get_sb()
            .table("teacher_assignments")
            .select(
                "id,teacher_id,student_id,assignment_type,source_type,source_record_id,status,"
                "assigned_at,created_at,recommendation_bucket,recommendation_focus_kind,"
                "learning_program_assignment_id,learning_program_topic_id,resource_exposure_id"
            )
            .eq("teacher_id", safe_teacher_id)
            .order("assigned_at", desc=False)
            .limit(max(1, int(limit)))
        )
        rows = getattr(
            _execute_query_with_diagnostics(
                query,
                function_name="backfill_assignment_exposures",
                source_name="teacher_assignments",
            ),
            "data",
            None,
        ) or []
    except Exception:
        rows = []
    scanned = 0
    created = 0
    skipped = 0
    for row in rows:
        scanned += 1
        if _clean_text(row.get("resource_exposure_id")):
            skipped += 1
            continue
        if not _clean_text(row.get("student_id")) or not _clean_text(row.get("source_record_id")):
            skipped += 1
            continue
        exposure_id = record_assignment_exposure_from_assignment_row(row, is_backfilled=True)
        if exposure_id:
            created += 1
        else:
            skipped += 1
    clear_app_caches()
    return {"scanned": scanned, "created": created, "skipped": skipped}


def _legacy_surface_unmatched_opens(
    *,
    teacher_id: str,
    start_iso: str,
    end_iso: str,
) -> pd.DataFrame:
    try:
        rows = (
            get_sb()
            .table("user_activity_log")
            .select("user_id,activity_type,meta_json,created_at")
            .gte("created_at", start_iso)
            .lte("created_at", end_iso)
            .in_("activity_type", ["student_recommendation_open", "teacher_material_open"])
            .order("created_at", desc=False)
            .limit(2000)
            .execute()
        ).data or []
    except Exception:
        rows = []
    filtered = []
    for row in rows:
        user_id = _clean_text(row.get("user_id"))
        meta = row.get("meta_json") if isinstance(row.get("meta_json"), dict) else {}
        if user_id != teacher_id and _clean_text(meta.get("teacher_id")) != teacher_id and get_current_user_role() == "teacher":
            continue
        filtered.append(
            {
                "activity_type": _clean_text(row.get("activity_type")),
                "surface": _clean_text(meta.get("surface")),
                "resource_type": _clean_text(meta.get("resource_kind")),
                "resource_id": _clean_text(meta.get("resource_id")),
                "created_at": str(row.get("created_at") or ""),
            }
        )
    return pd.DataFrame(filtered)


@st.cache_data(ttl=120, show_spinner=False)
def load_telemetry_health_snapshot(*, teacher_id: str, days: int = 30) -> dict[str, Any]:
    safe_teacher_id = _clean_text(teacher_id)
    if not safe_teacher_id:
        return {
            "summary": {},
            "by_surface": [],
            "date_range": {"start": "", "end": ""},
        }
    window_days = max(7, min(int(days or 30), _observation_window_days()))
    end_dt = _now()
    start_dt = end_dt - timedelta(days=window_days)
    start_iso = start_dt.isoformat()
    end_iso = end_dt.isoformat()
    try:
        exposure_rows = (
            get_sb()
            .table("resource_exposures")
            .select(
                "exposure_id,teacher_id,student_id,viewer_user_id,resource_id,resource_type,"
                "exposure_type,surface,shown_at,is_backfilled,created_at"
            )
            .eq("teacher_id", safe_teacher_id)
            .gte("shown_at", start_iso)
            .lte("shown_at", end_iso)
            .order("shown_at", desc=False)
            .limit(5000)
            .execute()
        ).data or []
    except Exception:
        exposure_rows = []
    try:
        event_rows = (
            get_sb()
            .table("resource_exposure_events")
            .select(
                "exposure_id,event_type,event_at,score_pct,is_backfilled,teacher_id,student_id,viewer_user_id,created_at"
            )
            .eq("teacher_id", safe_teacher_id)
            .gte("event_at", start_iso)
            .lte("event_at", end_iso)
            .order("event_at", desc=False)
            .limit(5000)
            .execute()
        ).data or []
    except Exception:
        event_rows = []

    exposure_df = pd.DataFrame(exposure_rows)
    event_df = pd.DataFrame(event_rows)
    if exposure_df.empty:
        exposure_df = pd.DataFrame(columns=["exposure_id", "exposure_type", "surface", "shown_at", "student_id", "resource_id"])
    if event_df.empty:
        event_df = pd.DataFrame(columns=["exposure_id", "event_type", "event_at", "student_id"])

    matched_open_ids = set(
        event_df.loc[event_df["event_type"].astype(str) == "opened", "exposure_id"].astype(str)
    ) if not event_df.empty and "event_type" in event_df.columns else set()
    exposure_ids = set(exposure_df.get("exposure_id", pd.Series(dtype=str)).astype(str))
    events_without_exposures = int(len(set(event_df.get("exposure_id", pd.Series(dtype=str)).astype(str)) - exposure_ids)) if not event_df.empty else 0
    duplicate_idempotency_signatures = 0
    repeated_legitimate_exposures = 0
    if not exposure_df.empty:
        repeated_legitimate_exposures = int(
            exposure_df.groupby(["viewer_user_id", "surface", "resource_type", "resource_id"], dropna=False).size().gt(1).sum()
        )

    legacy_open_df = _legacy_surface_unmatched_opens(teacher_id=safe_teacher_id, start_iso=start_iso, end_iso=end_iso)
    unmatched_legacy_opens = 0
    if not legacy_open_df.empty and not exposure_df.empty:
        exposure_signatures = {
            (
                str(row.get("surface") or ""),
                str(row.get("resource_type") or ""),
                str(row.get("resource_id") or ""),
            )
            for row in exposure_df.to_dict("records")
        }
        unmatched_legacy_opens = int(
            sum(
                1
                for row in legacy_open_df.to_dict("records")
                if (
                    str(row.get("surface") or ""),
                    str(row.get("resource_type") or ""),
                    str(row.get("resource_id") or ""),
                ) not in exposure_signatures
            )
        )
    elif not legacy_open_df.empty:
        unmatched_legacy_opens = int(len(legacy_open_df))

    by_surface_rows = []
    grouped = exposure_df.groupby(["exposure_type", "surface"], dropna=False) if not exposure_df.empty else []
    for (exposure_type, surface), group in grouped:
        surface_ids = set(group["exposure_id"].astype(str))
        surface_events = event_df[event_df["exposure_id"].astype(str).isin(surface_ids)] if not event_df.empty else pd.DataFrame()
        opens = int((surface_events.get("event_type", pd.Series(dtype=str)).astype(str) == "opened").sum()) if not surface_events.empty else 0
        matched_opens = int(len(surface_ids & matched_open_ids))
        downstream_mask = surface_events.get("event_type", pd.Series(dtype=str)).astype(str).isin(
            ["completed", "scored", "teacher_reviewed", "student_improved", "assigned", "accepted"]
        ) if not surface_events.empty else pd.Series(dtype=bool)
        downstream_count = int(downstream_mask.sum()) if not surface_events.empty else 0
        shown_values = pd.to_datetime(group.get("shown_at", pd.Series(dtype=str)), errors="coerce", utc=True)
        mature_cutoff = _now() - timedelta(days=7)
        mature_count = int((shown_values <= mature_cutoff).sum()) if len(shown_values) else 0
        total = int(len(group))
        open_rate = (matched_opens / total) if total else 0.0
        downstream_rate = (downstream_count / total) if total else 0.0
        status = "INSUFFICIENT DATA"
        if total >= 10 and matched_opens == total and open_rate >= 0:
            status = "HEALTHY"
        elif total >= 3 and matched_opens > 0:
            status = "PARTIAL"
        elif total > 0:
            status = "BROKEN"
        by_surface_rows.append(
            {
                "exposure_type": str(exposure_type or ""),
                "surface": str(surface or ""),
                "exposures": total,
                "matched_opens": matched_opens,
                "unmatched_opens": max(0, opens - matched_opens),
                "open_rate": round(open_rate, 4),
                "downstream_outcome_rate": round(downstream_rate, 4),
                "duplicate_warnings": 0,
                "date_start": str(group["shown_at"].min() or "") if "shown_at" in group.columns else "",
                "date_end": str(group["shown_at"].max() or "") if "shown_at" in group.columns else "",
                "status": status,
                "mature_exposures": mature_count,
            }
        )

    summary = {
        "total_exposures": int(len(exposure_df)),
        "opens": int((event_df.get("event_type", pd.Series(dtype=str)).astype(str) == "opened").sum()) if not event_df.empty else 0,
        "open_rate": round((len(matched_open_ids) / max(1, len(exposure_df))), 4) if len(exposure_df) else 0.0,
        "exposures_with_matched_opens": int(len(matched_open_ids)),
        "unmatched_opens": int(unmatched_legacy_opens),
        "duplicate_idempotency_signatures": int(duplicate_idempotency_signatures),
        "repeated_legitimate_exposures": int(repeated_legitimate_exposures),
        "events_without_exposures": int(events_without_exposures),
        "outcome_coverage": round(
            (
                event_df.get("event_type", pd.Series(dtype=str)).astype(str).isin(
                    ["completed", "scored", "teacher_reviewed", "student_improved", "assigned", "accepted"]
                ).sum()
                / max(1, len(exposure_df))
            ),
            4,
        ) if len(exposure_df) else 0.0,
        "event_date_range": {
            "start": str(event_df["event_at"].min() or "") if not event_df.empty and "event_at" in event_df.columns else "",
            "end": str(event_df["event_at"].max() or "") if not event_df.empty and "event_at" in event_df.columns else "",
        },
        "represented_teachers": len({safe_teacher_id}) if len(exposure_df) else 0,
        "represented_students": int(exposure_df.get("student_id", pd.Series(dtype=str)).astype(str).replace("", pd.NA).dropna().nunique()),
        "represented_resources": int(exposure_df.get("resource_id", pd.Series(dtype=str)).astype(str).replace("", pd.NA).dropna().nunique()),
        "exposure_maturity_7d": int(
            (
                pd.to_datetime(exposure_df.get("shown_at", pd.Series(dtype=str)), errors="coerce", utc=True)
                <= (_now() - timedelta(days=7))
            ).sum()
        ) if len(exposure_df) else 0,
    }
    return {
        "summary": summary,
        "by_surface": by_surface_rows,
        "date_range": {"start": start_iso, "end": end_iso},
    }


register_cache(load_telemetry_health_snapshot)
