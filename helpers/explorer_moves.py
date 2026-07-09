from __future__ import annotations

import json
import logging
import math
import secrets
from datetime import datetime as _dt, timezone
from typing import Any, Optional

import pandas as pd
import streamlit as st

from core.database import clear_app_caches, get_sb, register_cache
from core.i18n import t
from core.state import get_current_user_id, with_owner


logger = logging.getLogger(__name__)

EXPLORER_MOVES_TABLE = "explorer_moves"
EXPLORER_MOVE_STATUS_PENDING = "pending"
EXPLORER_MOVE_STATUS_PUBLISHED = "published"
EXPLORER_MOVE_STATUS_SOLVED = "solved"
EXPLORER_MOVE_STATUS_ARCHIVED = "archived"

EXPLORER_MOVE_RESOURCE_TYPES = ("lesson_plan", "worksheet", "exam")


def _now_iso() -> str:
    return _dt.now(timezone.utc).isoformat()


def _clean_text(value: Any) -> str:
    return str(value or "").strip()


def _json_safe(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, bool)):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(item) for item in value]
    if isinstance(value, (_dt, pd.Timestamp)):
        try:
            return value.isoformat()
        except Exception:
            return str(value)
    try:
        json.dumps(value)
        return value
    except Exception:
        return str(value)


def _current_admin_name() -> str:
    return _clean_text(st.session_state.get("user_name")) or t("unknown")


def _parse_assignment_notes(raw_notes: Any) -> dict:
    raw_text = _clean_text(raw_notes)
    if not raw_text:
        return {"assignments": []}
    try:
        data = json.loads(raw_text)
    except Exception:
        return {"assignments": [], "legacy_note": raw_text}
    if not isinstance(data, dict):
        return {"assignments": []}
    assignments = data.get("assignments") if isinstance(data.get("assignments"), list) else []
    data["assignments"] = [item for item in assignments if isinstance(item, dict)]
    return data


def _serialize_assignment_notes(data: dict) -> str:
    return json.dumps(data or {"assignments": []}, ensure_ascii=True, separators=(",", ":"))


def ensure_explorer_visitor_id() -> str:
    visitor_id = _clean_text(st.session_state.get("_explorer_visitor_id"))
    if visitor_id:
        return visitor_id
    visitor_id = secrets.token_hex(10)
    st.session_state["_explorer_visitor_id"] = visitor_id
    return visitor_id


def _resource_title(resource_type: str, payload: dict, meta: dict) -> str:
    if resource_type == "exam":
        exam_data = payload.get("exam_data") if isinstance(payload, dict) else {}
        return _clean_text((exam_data or {}).get("title")) or _clean_text(meta.get("topic")) or t("quick_exam_builder")
    return _clean_text(payload.get("title")) or _clean_text(meta.get("topic")) or {
        "lesson_plan": t("quick_lesson_planner"),
        "worksheet": t("worksheet_maker"),
    }.get(resource_type, t("untitled_plan"))


def _resource_language(payload: dict, meta: dict) -> str:
    if isinstance(payload.get("exam_data"), dict):
        exam_data = payload.get("exam_data") or {}
        return _clean_text(exam_data.get("student_material_language") or exam_data.get("plan_language") or meta.get("language"))
    return _clean_text(payload.get("student_material_language") or payload.get("plan_language") or meta.get("language"))


def _resource_preview(resource_type: str, payload: dict, meta: dict) -> str:
    topic = _clean_text(meta.get("topic"))
    if topic:
        return topic
    if resource_type == "lesson_plan":
        return _clean_text(payload.get("objective"))
    if resource_type == "worksheet":
        return _clean_text(payload.get("instructions"))
    if resource_type == "exam":
        exam_data = payload.get("exam_data") if isinstance(payload, dict) else {}
        return _clean_text((exam_data or {}).get("instructions"))
    return ""


def _normalize_move_frame(rows: list[dict] | None) -> pd.DataFrame:
    df = pd.DataFrame(rows or [])
    if df.empty:
        return pd.DataFrame()
    for column in ("created_at", "updated_at", "published_at"):
        if column in df.columns:
            df[column] = pd.to_datetime(df[column], errors="coerce", utc=True)
    if "created_at" in df.columns:
        df = df.sort_values("created_at", ascending=False, na_position="last")
    return df.reset_index(drop=True)


def explorer_moves_table_available() -> bool:
    try:
        get_sb().table(EXPLORER_MOVES_TABLE).select("id").limit(1).execute()
        return True
    except Exception:
        return False


def stage_explorer_move(
    *,
    resource_type: str,
    tool_key: str,
    payload: dict,
    meta: Optional[dict] = None,
    source_section: str = "explore_ai_tools",
) -> str | None:
    if get_current_user_id():
        return None

    meta = _json_safe(dict(meta or {}))
    payload = _json_safe(dict(payload or {}))
    visitor_id = ensure_explorer_visitor_id()
    resource_type = _clean_text(resource_type)
    if resource_type not in EXPLORER_MOVE_RESOURCE_TYPES:
        return None

    row = {
        "resource_type": resource_type,
        "tool_key": _clean_text(tool_key),
        "source_section": _clean_text(source_section) or "explore_ai_tools",
        "title": _resource_title(resource_type, payload, meta),
        "subject": _clean_text(meta.get("subject")),
        "topic": _clean_text(meta.get("topic")),
        "learner_stage": _clean_text(meta.get("learner_stage")),
        "level_or_band": _clean_text(meta.get("level_or_band")),
        "language": _resource_language(payload, meta),
        "preview_text": _resource_preview(resource_type, payload, meta),
        "payload_json": payload,
        "meta_json": meta,
        "anonymous_session_id": visitor_id,
        "status": EXPLORER_MOVE_STATUS_PENDING,
        "created_at": _now_iso(),
        "updated_at": _now_iso(),
    }
    attempts: list[tuple[str, dict[str, Any]]] = [("primary", row)]

    fallback_row = dict(row)
    fallback_row["payload_json"] = _json_safe(row.get("payload_json") or {})
    fallback_row["meta_json"] = _json_safe(row.get("meta_json") or {})
    attempts.append(("json_safe_retry", fallback_row))

    last_error: Exception | None = None
    for attempt_name, attempt_row in attempts:
        try:
            response = get_sb().table(EXPLORER_MOVES_TABLE).insert(attempt_row).execute()
            clear_app_caches()
            try:
                _load_explorer_moves_cached.clear()
            except Exception:
                pass
            rows = getattr(response, "data", None) or []
            move_id = _clean_text(rows[0].get("id")) if rows else None
            if move_id:
                return move_id
            logger.warning(
                "Explorer move staging returned no row id",
                extra={
                    "resource_type": resource_type,
                    "tool_key": _clean_text(tool_key),
                    "attempt": attempt_name,
                    "visitor_id": visitor_id,
                },
            )
        except Exception as exc:
            last_error = exc
            logger.exception(
                "Failed to stage explorer move",
                extra={
                    "resource_type": resource_type,
                    "tool_key": _clean_text(tool_key),
                    "attempt": attempt_name,
                    "visitor_id": visitor_id,
                    "title": _clean_text(attempt_row.get("title")),
                    "subject": _clean_text(attempt_row.get("subject")),
                    "topic": _clean_text(attempt_row.get("topic")),
                },
            )

    if last_error is not None:
        st.session_state.setdefault("_explorer_stage_failures", []).append(
            {
                "resource_type": resource_type,
                "tool_key": _clean_text(tool_key),
                "topic": _clean_text(row.get("topic")),
                "title": _clean_text(row.get("title")),
                "visitor_id": visitor_id,
                "error": str(last_error),
                "created_at": _now_iso(),
            }
        )
    return None


@st.cache_data(ttl=45, show_spinner=False)
def _load_explorer_moves_cached(limit: int = 500) -> pd.DataFrame:
    response = (
        get_sb()
        .table(EXPLORER_MOVES_TABLE)
        .select("*")
        .order("created_at", desc=True)
        .limit(limit)
        .execute()
    )
    return _normalize_move_frame(getattr(response, "data", None) or [])


register_cache(_load_explorer_moves_cached)


def load_explorer_moves_admin(limit: int = 500) -> pd.DataFrame:
    try:
        return _load_explorer_moves_cached(limit)
    except Exception:
        return pd.DataFrame()


def load_explorer_move(move_id: Any) -> dict:
    move_id = _clean_text(move_id)
    if not move_id:
        return {}
    try:
        response = (
            get_sb()
            .table(EXPLORER_MOVES_TABLE)
            .select("*")
            .eq("id", move_id)
            .limit(1)
            .execute()
        )
        rows = getattr(response, "data", None) or []
        return dict(rows[0]) if rows else {}
    except Exception:
        return {}


def update_explorer_move_status(
    move_id: str,
    status: str,
    *,
    published_table: str = "",
    published_record_id: Any = None,
    admin_notes: str = "",
) -> tuple[bool, str]:
    move_id = _clean_text(move_id)
    status = _clean_text(status)
    if not move_id or status not in {
        EXPLORER_MOVE_STATUS_PENDING,
        EXPLORER_MOVE_STATUS_PUBLISHED,
        EXPLORER_MOVE_STATUS_SOLVED,
        EXPLORER_MOVE_STATUS_ARCHIVED,
    }:
        return False, "invalid_status"

    payload: dict[str, Any] = {
        "status": status,
        "updated_at": _now_iso(),
    }
    if admin_notes:
        payload["admin_notes"] = _clean_text(admin_notes)
    if status == EXPLORER_MOVE_STATUS_PUBLISHED:
        payload["published_table"] = _clean_text(published_table)
        payload["published_record_id"] = published_record_id
        payload["published_at"] = _now_iso()
    try:
        get_sb().table(EXPLORER_MOVES_TABLE).update(payload).eq("id", move_id).execute()
        clear_app_caches()
        try:
            _load_explorer_moves_cached.clear()
        except Exception:
            pass
        return True, "ok"
    except Exception as exc:
        return False, str(exc)


def _insert_with_legacy_status_support(table: str, payload: dict) -> Any:
    try:
        response = get_sb().table(table).insert(payload).execute()
    except Exception as exc:
        if "status" not in str(exc).lower():
            raise
        legacy_payload = dict(payload)
        legacy_payload.pop("status", None)
        response = get_sb().table(table).insert(legacy_payload).execute()
    rows = getattr(response, "data", None) or []
    if rows and isinstance(rows, list):
        return rows[0].get("id")
    return None


def _insert_lesson_plan_for_user(move: dict, user_id: str, owner_name: str) -> Any:
    from helpers.archive_utils import ACTIVE_STATUS
    from helpers.planner_storage import planner_payload_from_inputs

    meta = move.get("meta_json") if isinstance(move.get("meta_json"), dict) else {}
    plan = dict(move.get("payload_json") if isinstance(move.get("payload_json"), dict) else {})
    payload = planner_payload_from_inputs(
        subject=_clean_text(meta.get("subject")),
        learner_stage=_clean_text(meta.get("learner_stage")),
        level_or_band=_clean_text(meta.get("level_or_band")),
        lesson_purpose=_clean_text(meta.get("lesson_purpose")),
        topic=_clean_text(meta.get("topic")),
        mode=_clean_text(meta.get("mode")) or "ai",
        plan=plan,
    )
    payload["user_id"] = user_id
    payload["author_name"] = owner_name
    payload["is_public"] = False
    payload["status"] = ACTIVE_STATUS
    payload["created_at"] = _now_iso()
    return _insert_with_legacy_status_support("lesson_plans", payload)


def _insert_worksheet_for_user(move: dict, user_id: str, owner_name: str) -> Any:
    from helpers.archive_utils import ACTIVE_STATUS
    from helpers.worksheet_storage import _normalize_worksheet_unicode, _wb

    meta = move.get("meta_json") if isinstance(move.get("meta_json"), dict) else {}
    worksheet = dict(move.get("payload_json") if isinstance(move.get("payload_json"), dict) else {})
    worksheet = _normalize_worksheet_unicode(worksheet)
    subject = _clean_text(meta.get("subject"))
    payload = {
        "user_id": user_id,
        "subject": subject,
        "topic": _clean_text(meta.get("topic")),
        "learner_stage": _clean_text(meta.get("learner_stage")),
        "level_or_band": _clean_text(meta.get("level_or_band")),
        "worksheet_type": _clean_text(meta.get("worksheet_type")),
        "plan_language": _clean_text(worksheet.get("plan_language") or _wb().get_plan_language()),
        "student_material_language": _clean_text(worksheet.get("student_material_language")),
        "source_type": "ai",
        "worksheet_json": worksheet,
        "title": _clean_text(worksheet.get("title")),
        "author_name": owner_name,
        "subject_display": subject.replace("_", " ").title() if subject else "",
        "is_public": False,
        "status": ACTIVE_STATUS,
        "created_at": _now_iso(),
    }
    return _insert_with_legacy_status_support("worksheets", payload)


def _insert_exam_for_user(move: dict, user_id: str, owner_name: str) -> Any:
    from helpers.archive_utils import ACTIVE_STATUS

    meta = move.get("meta_json") if isinstance(move.get("meta_json"), dict) else {}
    payload = move.get("payload_json") if isinstance(move.get("payload_json"), dict) else {}
    exam_data = dict(payload.get("exam_data") if isinstance(payload.get("exam_data"), dict) else {})
    answer_key = payload.get("answer_key") if isinstance(payload.get("answer_key"), dict) else {}
    insert_payload = {
        "user_id": user_id,
        "title": _clean_text(exam_data.get("title")),
        "subject": _clean_text(meta.get("subject")),
        "topic": _clean_text(meta.get("topic")),
        "learner_stage": _clean_text(meta.get("learner_stage")),
        "level": _clean_text(meta.get("level_or_band")),
        "exam_length": _clean_text(meta.get("exam_length")),
        "exercise_types": meta.get("exercise_types") or [],
        "exam_data": exam_data,
        "answer_key": answer_key,
        "author_name": owner_name,
        "is_public": False,
        "status": ACTIVE_STATUS,
        "created_at": _now_iso(),
    }
    return _insert_with_legacy_status_support("quick_exams", insert_payload)


def assign_explorer_move_to_profile(move: dict, target_user_id: str, owner_name: str) -> tuple[bool, Any, str]:
    target_user_id = _clean_text(target_user_id)
    owner_name = _clean_text(owner_name) or t("unknown")
    if not target_user_id:
        return False, None, "missing_target_user"
    admin_name = _current_admin_name()
    notes_data = _parse_assignment_notes(move.get("admin_notes"))
    assignments = notes_data.get("assignments") if isinstance(notes_data.get("assignments"), list) else []
    for assignment in assignments:
        if _clean_text(assignment.get("target_user_id")) == target_user_id:
            solved_by = _clean_text(assignment.get("assigned_by_admin")) or admin_name
            return False, None, f"duplicate_assignment::{solved_by}"
    resource_type = _clean_text(move.get("resource_type"))
    try:
        if resource_type == "lesson_plan":
            record_id = _insert_lesson_plan_for_user(move, target_user_id, owner_name)
        elif resource_type == "worksheet":
            record_id = _insert_worksheet_for_user(move, target_user_id, owner_name)
        elif resource_type == "exam":
            record_id = _insert_exam_for_user(move, target_user_id, owner_name)
        else:
            return False, None, "unsupported_resource"
        move_id = _clean_text(move.get("id"))
        if move_id and record_id not in (None, "", 0, "0"):
            assignments.append(
                {
                    "target_user_id": target_user_id,
                    "target_owner_name": owner_name,
                    "assigned_by_admin": admin_name,
                    "assigned_at": _now_iso(),
                    "record_id": record_id,
                }
            )
            notes_data["assignments"] = assignments
            ok, msg = update_explorer_move_status(
                move_id,
                EXPLORER_MOVE_STATUS_SOLVED,
                admin_notes=_serialize_assignment_notes(notes_data),
            )
            if not ok:
                return False, record_id, msg
        clear_app_caches()
        return (record_id not in (None, "", 0, "0")), record_id, "ok"
    except Exception as exc:
        return False, None, str(exc)


def _publish_lesson_plan(move: dict) -> tuple[bool, str, str, Any]:
    from helpers.archive_utils import ACTIVE_STATUS
    from helpers.planner_storage import planner_payload_from_inputs

    meta = move.get("meta_json") if isinstance(move.get("meta_json"), dict) else {}
    plan = dict(move.get("payload_json") if isinstance(move.get("payload_json"), dict) else {})
    plan["_admin_only_image_controls"] = True
    payload = planner_payload_from_inputs(
        subject=_clean_text(meta.get("subject")),
        learner_stage=_clean_text(meta.get("learner_stage")),
        level_or_band=_clean_text(meta.get("level_or_band")),
        lesson_purpose=_clean_text(meta.get("lesson_purpose")),
        topic=_clean_text(meta.get("topic")),
        mode=_clean_text(meta.get("mode")) or "ai",
        plan=plan,
    )
    payload["is_public"] = True
    payload["status"] = ACTIVE_STATUS
    payload["author_name"] = _current_admin_name()
    payload["created_at"] = _now_iso()
    record_id = _insert_with_legacy_status_support("lesson_plans", payload)
    clear_app_caches()
    return (record_id is not None), "lesson_plans", "", record_id


def _publish_worksheet(move: dict) -> tuple[bool, str, str, Any]:
    from helpers.archive_utils import ACTIVE_STATUS
    from helpers.worksheet_storage import _normalize_worksheet_unicode, _wb

    meta = move.get("meta_json") if isinstance(move.get("meta_json"), dict) else {}
    worksheet = dict(move.get("payload_json") if isinstance(move.get("payload_json"), dict) else {})
    worksheet["_admin_only_image_controls"] = True
    worksheet = _normalize_worksheet_unicode(worksheet)
    subject = _clean_text(meta.get("subject"))
    payload = with_owner({
        "subject": subject,
        "topic": _clean_text(meta.get("topic")),
        "learner_stage": _clean_text(meta.get("learner_stage")),
        "level_or_band": _clean_text(meta.get("level_or_band")),
        "worksheet_type": _clean_text(meta.get("worksheet_type")),
        "plan_language": _clean_text(worksheet.get("plan_language") or _wb().get_plan_language()),
        "student_material_language": _clean_text(worksheet.get("student_material_language")),
        "source_type": "ai",
        "worksheet_json": worksheet,
        "title": _clean_text(worksheet.get("title")),
        "author_name": _current_admin_name(),
        "subject_display": subject.replace("_", " ").title() if subject else "",
        "is_public": True,
        "status": ACTIVE_STATUS,
        "created_at": _now_iso(),
    })
    record_id = _insert_with_legacy_status_support("worksheets", payload)
    clear_app_caches()
    return (record_id is not None), "worksheets", "", record_id


def _publish_exam(move: dict) -> tuple[bool, str, str, Any]:
    from helpers.quick_exam_storage import save_exam_record, update_exam_visibility

    meta = move.get("meta_json") if isinstance(move.get("meta_json"), dict) else {}
    payload = move.get("payload_json") if isinstance(move.get("payload_json"), dict) else {}
    exam_data = dict(payload.get("exam_data") if isinstance(payload.get("exam_data"), dict) else {})
    exam_data["_admin_only_image_controls"] = True
    answer_key = payload.get("answer_key") if isinstance(payload.get("answer_key"), dict) else {}
    record_id = save_exam_record(
        subject=_clean_text(meta.get("subject")),
        learner_stage=_clean_text(meta.get("learner_stage")),
        level_or_band=_clean_text(meta.get("level_or_band")),
        topic=_clean_text(meta.get("topic")),
        exam_length=_clean_text(meta.get("exam_length")),
        exercise_types=meta.get("exercise_types") or [],
        exam_data=exam_data,
        answer_key=answer_key,
    )
    if not record_id:
        return False, "quick_exams", "save_failed", None
    ok, msg = update_exam_visibility(record_id, True)
    if not ok:
        return False, "quick_exams", msg, None
    clear_app_caches()
    return True, "quick_exams", "", record_id


def publish_explorer_move(move: dict) -> tuple[bool, str]:
    resource_type = _clean_text(move.get("resource_type"))
    if resource_type == "lesson_plan":
        ok, table_name, error, record_id = _publish_lesson_plan(move)
    elif resource_type == "worksheet":
        ok, table_name, error, record_id = _publish_worksheet(move)
    elif resource_type == "exam":
        ok, table_name, error, record_id = _publish_exam(move)
    else:
        return False, "unsupported_resource"

    if not ok or record_id in (None, "", 0, "0"):
        return False, error or "publish_failed"

    status_ok, status_msg = update_explorer_move_status(
        _clean_text(move.get("id")),
        EXPLORER_MOVE_STATUS_PUBLISHED,
        published_table=table_name,
        published_record_id=record_id,
    )
    if not status_ok:
        return False, status_msg
    return True, "ok"


def persist_explorer_move_payload(move: dict, payload: dict) -> bool:
    move_id = _clean_text(move.get("id"))
    resource_type = _clean_text(move.get("resource_type"))
    if not move_id:
        return False
    payload = dict(payload or {})
    try:
        get_sb().table(EXPLORER_MOVES_TABLE).update(
            {
                "payload_json": payload,
                "updated_at": _now_iso(),
            }
        ).eq("id", move_id).execute()
    except Exception:
        logger.exception("Failed to persist explorer move payload")
        return False

    published_table = _clean_text(move.get("published_table"))
    published_record_id = move.get("published_record_id")
    if published_table and published_record_id not in (None, "", 0, "0"):
        try:
            if resource_type == "lesson_plan" and published_table == "lesson_plans":
                from helpers.planner_storage import _persist_lesson_plan_cover

                if not _persist_lesson_plan_cover(published_record_id, payload):
                    return False
            elif resource_type == "worksheet" and published_table == "worksheets":
                from helpers.worksheet_storage import _persist_saved_worksheet_visuals

                if not _persist_saved_worksheet_visuals(published_record_id, payload):
                    return False
            elif resource_type == "exam" and published_table == "quick_exams":
                from helpers.quick_exam_storage import _persist_saved_exam_visuals

                exam_data = payload.get("exam_data") if isinstance(payload.get("exam_data"), dict) else {}
                if not _persist_saved_exam_visuals(published_record_id, exam_data):
                    return False
        except Exception:
            logger.exception("Failed to sync explorer move payload to published record")
            return False

    clear_app_caches()
    try:
        _load_explorer_moves_cached.clear()
    except Exception:
        pass
    return True


def archive_explorer_move(move: dict) -> tuple[bool, str]:
    move_id = _clean_text(move.get("id"))
    published_table = _clean_text(move.get("published_table"))
    published_record_id = move.get("published_record_id")
    if published_table and published_record_id not in (None, "", 0, "0"):
        if published_table == "lesson_plans":
            from helpers.planner_storage import update_lesson_plan_archive

            ok, msg = update_lesson_plan_archive(published_record_id, True)
        elif published_table == "worksheets":
            from helpers.worksheet_storage import update_worksheet_archive

            ok, msg = update_worksheet_archive(published_record_id, True)
        elif published_table == "quick_exams":
            from helpers.quick_exam_storage import update_exam_archive

            ok, msg = update_exam_archive(published_record_id, True)
        else:
            ok, msg = False, "unsupported_published_table"
        if not ok:
            return False, msg

    return update_explorer_move_status(move_id, EXPLORER_MOVE_STATUS_ARCHIVED)