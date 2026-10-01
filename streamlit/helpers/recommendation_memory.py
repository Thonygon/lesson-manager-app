from __future__ import annotations

from datetime import datetime, timedelta, timezone
import os
from typing import Any

import streamlit as st

from core.database import _execute_query_with_diagnostics, get_sb, register_cache
from core.state import get_current_user_id, get_current_user_role
from helpers.recommendation_models import clear_recommendation_model_caches

_SESSION_KEY = "active_recommendation_context"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _rows(result) -> list[dict]:
    return getattr(result, "data", None) or []


def _clean_text(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def _safe_int(value: Any) -> int:
    try:
        if value in (None, "", "None"):
            return 0
        return int(value)
    except Exception:
        return 0


def _safe_float(value: Any) -> float:
    try:
        return float(value or 0.0)
    except Exception:
        return 0.0


def _safe_dict(value: Any) -> dict:
    return value if isinstance(value, dict) else {}


def _metadata_topic_id(metadata: dict | None) -> int:
    payload = _safe_dict(metadata)
    for key in ("learning_program_topic_id", "program_topic_id", "topic_id"):
        topic_id = _safe_int(payload.get(key))
        if topic_id > 0:
            return topic_id
    return 0


def _metadata_program_id(metadata: dict | None) -> int:
    payload = _safe_dict(metadata)
    for key in ("program_id", "learning_program_id"):
        program_id = _safe_int(payload.get(key))
        if program_id > 0:
            return program_id
    return 0


def _context_program_id(context: dict | None) -> int:
    payload = _safe_dict(context)
    return _metadata_program_id(payload)


def _fetch_single_row(table: str, columns: str, row_id: int) -> dict:
    if row_id <= 0:
        return {}
    try:
        rows = _rows(get_sb().table(table).select(columns).eq("id", row_id).limit(1).execute())
        return rows[0] if rows else {}
    except Exception:
        return {}


def _fetch_assignment_context(assignment_id: int) -> dict:
    row = _fetch_single_row(
        "teacher_assignments",
        "id,learning_program_assignment_id,learning_program_topic_id,recommendation_bucket,"
        "recommendation_focus_kind,recommendation_context",
        assignment_id,
    )
    if row:
        return row
    return _fetch_single_row(
        "teacher_assignments",
        "id,learning_program_assignment_id,learning_program_topic_id,recommendation_bucket,recommendation_focus_kind",
        assignment_id,
    )


def _fetch_attempt_context(attempt_id: int) -> dict:
    return _fetch_single_row(
        "teacher_assignment_attempts",
        "id,assignment_id,learning_program_assignment_id,learning_program_topic_id,"
        "recommendation_bucket,recommendation_focus_kind",
        attempt_id,
    )


def _resolve_recommendation_event_context(
    *,
    learning_program_assignment_id: int,
    learning_program_topic_id: int,
    program_id: int,
    recommendation_bucket: str,
    recommendation_focus_kind: str,
    teacher_assignment_id: int,
    assignment_attempt_id: int,
    metadata: dict | None,
) -> dict[str, Any]:
    resolved = {
        "learning_program_assignment_id": learning_program_assignment_id,
        "learning_program_topic_id": learning_program_topic_id,
        "program_id": program_id,
        "recommendation_bucket": recommendation_bucket,
        "recommendation_focus_kind": recommendation_focus_kind,
    }
    if resolved["learning_program_topic_id"] <= 0:
        resolved["learning_program_topic_id"] = _metadata_topic_id(metadata)
    if resolved["program_id"] <= 0:
        resolved["program_id"] = _metadata_program_id(metadata)

    attempt_row = {}
    if assignment_attempt_id > 0 and (
        resolved["learning_program_topic_id"] <= 0
        or resolved["learning_program_assignment_id"] <= 0
        or not resolved["recommendation_bucket"]
        or not resolved["recommendation_focus_kind"]
    ):
        attempt_row = _fetch_attempt_context(assignment_attempt_id)
        if attempt_row:
            teacher_assignment_id = teacher_assignment_id or _safe_int(attempt_row.get("assignment_id"))
            resolved["learning_program_assignment_id"] = (
                resolved["learning_program_assignment_id"]
                or _safe_int(attempt_row.get("learning_program_assignment_id"))
            )
            resolved["learning_program_topic_id"] = (
                resolved["learning_program_topic_id"]
                or _safe_int(attempt_row.get("learning_program_topic_id"))
            )
            resolved["recommendation_bucket"] = resolved["recommendation_bucket"] or _clean_text(
                attempt_row.get("recommendation_bucket")
            )
            resolved["recommendation_focus_kind"] = resolved["recommendation_focus_kind"] or _clean_text(
                attempt_row.get("recommendation_focus_kind")
            )

    if teacher_assignment_id > 0 and (
        resolved["learning_program_topic_id"] <= 0
        or resolved["learning_program_assignment_id"] <= 0
        or resolved["program_id"] <= 0
        or not resolved["recommendation_bucket"]
        or not resolved["recommendation_focus_kind"]
    ):
        assignment_row = _fetch_assignment_context(teacher_assignment_id)
        if assignment_row:
            resolved["learning_program_assignment_id"] = (
                resolved["learning_program_assignment_id"]
                or _safe_int(assignment_row.get("learning_program_assignment_id"))
            )
            resolved["learning_program_topic_id"] = (
                resolved["learning_program_topic_id"]
                or _safe_int(assignment_row.get("learning_program_topic_id"))
            )
            resolved["recommendation_bucket"] = resolved["recommendation_bucket"] or _clean_text(
                assignment_row.get("recommendation_bucket")
            )
            resolved["recommendation_focus_kind"] = resolved["recommendation_focus_kind"] or _clean_text(
                assignment_row.get("recommendation_focus_kind")
            )
            if resolved["program_id"] <= 0:
                resolved["program_id"] = _context_program_id(assignment_row.get("recommendation_context"))

    return resolved


def _history_window_days() -> int:
    raw_value = os.getenv("RECOMMENDATION_HISTORY_DAYS", "180")
    try:
        return max(30, min(int(raw_value), 3650))
    except Exception:
        return 180


def _history_cutoff_iso() -> str:
    return (datetime.now(timezone.utc) - timedelta(days=_history_window_days())).isoformat()


def _event_summary_limit() -> int:
    raw_value = os.getenv("RECOMMENDATION_EVENT_SUMMARY_LIMIT", "500")
    try:
        return max(50, min(int(raw_value), 5000))
    except Exception:
        return 500


def _event_summary_rpc_enabled() -> bool:
    return str(os.getenv("RECOMMENDATION_EVENT_SUMMARY_RPC_ENABLED", "") or "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def set_active_recommendation_context(payload: dict | None) -> None:
    st.session_state[_SESSION_KEY] = dict(payload or {})


def get_active_recommendation_context() -> dict:
    payload = st.session_state.get(_SESSION_KEY)
    return dict(payload or {})


def clear_active_recommendation_context() -> None:
    st.session_state.pop(_SESSION_KEY, None)


def recommendation_context_for_assignment(
    *,
    link: dict,
    subject_scope: dict,
    topic_text: str = "",
) -> dict:
    payload = get_active_recommendation_context()
    if not payload:
        return {}
    student_id = _clean_text(link.get("student_id"))
    payload_student_id = _clean_text(payload.get("student_id"))
    if student_id and payload_student_id and student_id != payload_student_id:
        return {}
    subject_key = _clean_text(subject_scope.get("subject_key"))
    payload_subject_key = _clean_text(payload.get("subject_key"))
    if subject_key and payload_subject_key and subject_key != payload_subject_key:
        return {}
    expected_topic = _clean_text(topic_text).casefold()
    payload_topics = {
        _clean_text(payload.get("title")).casefold(),
        _clean_text(payload.get("objective")).casefold(),
        _clean_text(payload.get("topic_title")).casefold(),
    }
    payload_topics.discard("")
    if expected_topic and payload_topics and expected_topic not in payload_topics:
        return {}
    return payload


def record_recommendation_event(
    *,
    event_type: str,
    teacher_id: str = "",
    student_id: str = "",
    learning_program_assignment_id: int | None = None,
    learning_program_topic_id: int | None = None,
    program_id: int | None = None,
    recommendation_bucket: str = "",
    recommendation_focus_kind: str = "",
    resource_kind: str = "",
    resource_record_id: int | None = None,
    teacher_assignment_id: int | None = None,
    assignment_attempt_id: int | None = None,
    event_weight: float = 0.0,
    metadata: dict | None = None,
) -> None:
    teacher_id = _clean_text(teacher_id or get_current_user_id())
    student_id = _clean_text(student_id)
    event_type = _clean_text(event_type)
    if not teacher_id or not student_id or not event_type:
        return
    normalized_metadata = metadata or {}
    resolved_context = _resolve_recommendation_event_context(
        learning_program_assignment_id=_safe_int(learning_program_assignment_id),
        learning_program_topic_id=_safe_int(learning_program_topic_id),
        program_id=_safe_int(program_id),
        recommendation_bucket=_clean_text(recommendation_bucket),
        recommendation_focus_kind=_clean_text(recommendation_focus_kind),
        teacher_assignment_id=_safe_int(teacher_assignment_id),
        assignment_attempt_id=_safe_int(assignment_attempt_id),
        metadata=normalized_metadata,
    )
    payload = {
        "teacher_id": teacher_id,
        "student_id": student_id,
        "learning_program_assignment_id": _safe_int(resolved_context["learning_program_assignment_id"]) or None,
        "learning_program_topic_id": _safe_int(resolved_context["learning_program_topic_id"]) or None,
        "program_id": _safe_int(resolved_context["program_id"]) or None,
        "recommendation_bucket": _clean_text(resolved_context["recommendation_bucket"]),
        "recommendation_focus_kind": _clean_text(resolved_context["recommendation_focus_kind"]),
        "resource_kind": _clean_text(resource_kind),
        "resource_record_id": _safe_int(resource_record_id) or None,
        "teacher_assignment_id": _safe_int(teacher_assignment_id) or None,
        "assignment_attempt_id": _safe_int(assignment_attempt_id) or None,
        "event_type": event_type,
        "event_weight": _safe_float(event_weight),
        "metadata": normalized_metadata,
        "created_at": _now_iso(),
        "updated_at": _now_iso(),
    }
    try:
        get_sb().table("learning_program_recommendation_events").insert(payload).execute()
        clear_recommendation_model_caches()
        try:
            load_recommendation_event_summary.clear()
        except Exception:
            pass
    except Exception:
        pass


@st.cache_data(ttl=45, show_spinner=False)
def load_recommendation_event_summary(
    assignment_ids_key: tuple[int, ...],
    student_id: str = "",
) -> dict[tuple[int, int, str], dict]:
    assignment_ids = [int(item) for item in assignment_ids_key if int(item or 0) > 0]
    student_id = _clean_text(student_id)
    if not assignment_ids and not student_id:
        return {}

    actor_id = _clean_text(get_current_user_id())
    actor_role = _clean_text(get_current_user_role()).lower()
    teacher_scope = actor_id if actor_id and actor_role == "teacher" else ""
    student_scope = student_id or (actor_id if actor_id and actor_role == "student" else "")
    cutoff_iso = _history_cutoff_iso()
    row_limit = _event_summary_limit()
    rows: list[dict] = []
    used_summary_rpc = False
    if _event_summary_rpc_enabled():
        try:
            rpc_result = _execute_query_with_diagnostics(
                get_sb().rpc(
                    "classio_recommendation_event_summary",
                    {
                        "p_teacher_id": teacher_scope or None,
                        "p_student_id": student_scope or None,
                        "p_assignment_ids": assignment_ids or None,
                        "p_since": cutoff_iso,
                        "p_row_limit": row_limit,
                    },
                ),
                function_name="load_recommendation_event_summary",
                source_name="classio_recommendation_event_summary",
            )
            rows = _rows(rpc_result)
            used_summary_rpc = bool(rows)
        except Exception:
            rows = []

    if not rows:
        try:
            query = (
                get_sb()
                .table("learning_program_recommendation_events")
                .select(
                    "teacher_id,student_id,learning_program_assignment_id,learning_program_topic_id,"
                    "recommendation_bucket,event_type,resource_kind,metadata,created_at"
                )
                .gte("created_at", cutoff_iso)
                .order("created_at", desc=True)
                .limit(row_limit)
            )
            if assignment_ids:
                query = query.in_("learning_program_assignment_id", assignment_ids)
            if teacher_scope:
                query = query.eq("teacher_id", teacher_scope)
            if student_scope:
                query = query.eq("student_id", student_scope)
            rows = _rows(
                _execute_query_with_diagnostics(
                    query,
                    function_name="load_recommendation_event_summary",
                    source_name="learning_program_recommendation_events",
                )
            )
        except Exception:
            return {}

    summary: dict[tuple[int, int, str], dict] = {}
    for row in rows:
        signature = (
            _safe_int(row.get("learning_program_assignment_id")),
            _safe_int(row.get("learning_program_topic_id")),
            _clean_text(row.get("recommendation_bucket")),
        )
        item = summary.setdefault(
            signature,
            {
                "count": 0,
                "last_event_type": "",
                "last_event_at": "",
                "latest_score": None,
                "improved_count": 0,
                "assigned_count": 0,
                "teacher_marked_done_count": 0,
                "resolved_low_score_signatures": set(),
                "resource_kinds": set(),
            },
        )
        if "event_count" in row:
            item["count"] = _safe_int(row.get("event_count"))
            item["last_event_type"] = _clean_text(row.get("last_event_type"))
            item["last_event_at"] = str(row.get("last_event_at") or "")
            if row.get("latest_score") not in (None, ""):
                try:
                    item["latest_score"] = float(row.get("latest_score"))
                except Exception:
                    item["latest_score"] = None
            item["improved_count"] = _safe_int(row.get("improved_count"))
            item["assigned_count"] = _safe_int(row.get("assigned_count"))
            item["teacher_marked_done_count"] = _safe_int(row.get("teacher_marked_done_count"))
            item["resolved_low_score_signatures"] = {
                _clean_text(value)
                for value in (row.get("resolved_low_score_signatures") or [])
                if _clean_text(value)
            }
            item["resource_kinds"] = {
                _clean_text(value)
                for value in (row.get("resource_kinds") or [])
                if _clean_text(value)
            }
            continue

        item["count"] += 1
        if not item["last_event_at"] or str(row.get("created_at") or "") > str(item["last_event_at"]):
            item["last_event_at"] = str(row.get("created_at") or "")
            item["last_event_type"] = _clean_text(row.get("event_type"))
        metadata = row.get("metadata") or {}
        if item["latest_score"] is None and metadata.get("score_pct") not in (None, ""):
            try:
                item["latest_score"] = float(metadata.get("score_pct"))
            except Exception:
                pass
        if _clean_text(row.get("event_type")) == "student_improved":
            item["improved_count"] += 1
        if _clean_text(row.get("event_type")) == "assignment_created":
            item["assigned_count"] += 1
        if _clean_text(row.get("event_type")) == "teacher_marked_done":
            item["teacher_marked_done_count"] += 1
            resolved_signature = _clean_text(metadata.get("resolved_low_score_signature"))
            if resolved_signature:
                item["resolved_low_score_signatures"].add(resolved_signature)
        resource_kind = _clean_text(row.get("resource_kind"))
        if resource_kind:
            item["resource_kinds"].add(resource_kind)

    if used_summary_rpc:
        try:
            query = (
                get_sb()
                .table("learning_program_recommendation_events")
                .select(
                    "learning_program_assignment_id,learning_program_topic_id,"
                    "recommendation_bucket,metadata"
                )
                .gte("created_at", cutoff_iso)
                .eq("event_type", "teacher_marked_done")
                .limit(row_limit)
            )
            if assignment_ids:
                query = query.in_("learning_program_assignment_id", assignment_ids)
            if teacher_scope:
                query = query.eq("teacher_id", teacher_scope)
            if student_scope:
                query = query.eq("student_id", student_scope)
            resolved_rows = _rows(
                _execute_query_with_diagnostics(
                    query,
                    function_name="load_recommendation_event_summary_resolved_low_scores",
                    source_name="learning_program_recommendation_events",
                )
            )
            for row in resolved_rows:
                signature = (
                    _safe_int(row.get("learning_program_assignment_id")),
                    _safe_int(row.get("learning_program_topic_id")),
                    _clean_text(row.get("recommendation_bucket")),
                )
                resolved_signature = _clean_text((row.get("metadata") or {}).get("resolved_low_score_signature"))
                if resolved_signature and signature in summary:
                    summary[signature].setdefault("resolved_low_score_signatures", set()).add(resolved_signature)
        except Exception:
            pass

    return summary


register_cache(load_recommendation_event_summary, "recommendations", "assignments")
