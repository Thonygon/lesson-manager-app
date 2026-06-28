from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from core.database import clear_app_caches, get_sb
from services.subscription_service import reset_usage


RESET_SCOPE_STUDENT = "student"
RESET_SCOPE_TEACHER = "teacher"
RESET_SCOPE_FULL = "full"
RESET_SCOPES = {RESET_SCOPE_STUDENT, RESET_SCOPE_TEACHER, RESET_SCOPE_FULL}

_ARCHIVED_STATUS = "archived"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _rows(result: Any) -> list[dict]:
    return getattr(result, "data", None) or []


def _apply_filters(query: Any, filters: list[tuple[str, Any]]) -> Any:
    for column_name, value in filters:
        query = query.eq(column_name, value)
    return query


def _safe_select(table_name: str, filters: list[tuple[str, Any]], columns: str = "*") -> list[dict]:
    try:
        query = get_sb().table(table_name).select(columns)
        query = _apply_filters(query, filters)
        return _rows(query.execute())
    except Exception:
        return []


def _safe_count(table_name: str, filters: list[tuple[str, Any]]) -> int:
    try:
        query = get_sb().table(table_name).select("*", count="exact", head=True)
        query = _apply_filters(query, filters)
        result = query.execute()
        return int(getattr(result, "count", 0) or 0)
    except Exception:
        return len(_safe_select(table_name, filters, "id"))


def _safe_delete(table_name: str, filters: list[tuple[str, Any]]) -> int:
    count = _safe_count(table_name, filters)
    if count <= 0:
        return 0
    try:
        query = get_sb().table(table_name).delete()
        query = _apply_filters(query, filters)
        query.execute()
        return count
    except Exception:
        return 0


def _safe_update(
    table_name: str,
    filters: list[tuple[str, Any]],
    payload: dict[str, Any],
    *,
    optional_columns: list[str] | None = None,
) -> int:
    count = _safe_count(table_name, filters)
    if count <= 0:
        return 0
    safe_payload = dict(payload or {})
    optional_columns = list(optional_columns or [])
    last_exc: Exception | None = None
    while True:
        try:
            query = get_sb().table(table_name).update(safe_payload)
            query = _apply_filters(query, filters)
            query.execute()
            return count
        except Exception as exc:
            last_exc = exc
            message = str(exc)
            removed = False
            for column_name in list(optional_columns):
                if column_name in safe_payload and column_name in message:
                    safe_payload.pop(column_name, None)
                    optional_columns.remove(column_name)
                    removed = True
                    break
            if not removed:
                return 0
    raise last_exc  # pragma: no cover


def _add_row(rows: list[dict[str, Any]], label_key: str, action: str, count: int, note_key: str = "") -> None:
    if int(count or 0) <= 0:
        return
    rows.append(
        {
            "label_key": label_key,
            "action": action,
            "count": int(count or 0),
            "note_key": note_key,
        }
    )


def _resource_archive_count(table_name: str, user_id: str) -> tuple[int, int]:
    filters = [("user_id", user_id)]
    total = _safe_count(table_name, filters)
    public = _safe_count(table_name, filters + [("is_public", True)])
    return total, public


def _build_student_preview_rows(user_id: str, remove_relationships: bool) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    _add_row(rows, "admin_reset_preview_student_assignments", "archive", _safe_count("teacher_assignments", [("student_id", user_id)]), "admin_reset_preview_student_assignments_note")
    _add_row(rows, "admin_reset_preview_student_attempts", "delete", _safe_count("teacher_assignment_attempts", [("student_id", user_id)]))
    _add_row(rows, "admin_reset_preview_student_reviews", "delete", _safe_count("teacher_review_requests", [("student_id", user_id)]))
    _add_row(rows, "admin_reset_preview_student_program_assignments", "delete", _safe_count("learning_program_assignments", [("user_id", user_id)]))
    _add_row(rows, "admin_reset_preview_student_program_progress", "delete", _safe_count("learning_program_progress", [("user_id", user_id)]))
    _add_row(rows, "admin_reset_preview_student_sessions", "delete", _safe_count("practice_sessions", [("user_id", user_id)]))
    _add_row(rows, "admin_reset_preview_student_answers", "delete", _safe_count("practice_answers", [("user_id", user_id)]))
    _add_row(rows, "admin_reset_preview_student_progress", "delete", _safe_count("practice_progress", [("user_id", user_id)]))
    if remove_relationships:
        _add_row(rows, "admin_reset_preview_relationships", "archive", _safe_count("teacher_student_links", [("student_id", user_id)]), "admin_reset_preview_relationships_student_note")
        _add_row(rows, "admin_reset_preview_relationship_subjects", "archive", _safe_count("teacher_student_subjects", [("student_id", user_id)]))
    return rows


def _build_teacher_preview_rows(user_id: str, archive_shared_resources: bool, remove_relationships: bool) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    _add_row(rows, "admin_reset_preview_students", "delete", _safe_count("students", [("user_id", user_id)]))
    _add_row(rows, "admin_reset_preview_classes", "delete", _safe_count("classes", [("user_id", user_id)]))
    _add_row(rows, "admin_reset_preview_payments", "delete", _safe_count("payments", [("user_id", user_id)]))
    _add_row(rows, "admin_reset_preview_schedules", "delete", _safe_count("schedules", [("user_id", user_id)]))
    _add_row(rows, "admin_reset_preview_calendar_overrides", "delete", _safe_count("calendar_overrides", [("user_id", user_id)]))
    _add_row(rows, "admin_reset_preview_schedule_freezes", "delete", _safe_count("student_schedule_freezes", [("user_id", user_id)]))
    _add_row(rows, "admin_reset_preview_ai_logs", "delete", _safe_count("ai_usage_logs", [("user_id", user_id)]))
    _add_row(rows, "admin_reset_preview_pricing_items", "delete", _safe_count("pricing_items", [("user_id", user_id)]))
    _add_row(rows, "admin_reset_preview_review_requests_received", "delete", _safe_count("teacher_review_requests", [("teacher_id", user_id)]))

    worksheet_total, worksheet_public = _resource_archive_count("worksheets", user_id)
    _add_row(rows, "admin_reset_preview_worksheets", "archive", worksheet_total, "admin_reset_preview_resources_note" if archive_shared_resources and worksheet_public else "")
    if archive_shared_resources and worksheet_public:
        _add_row(rows, "admin_reset_preview_worksheets_shared", "archive", worksheet_public)

    exam_total, exam_public = _resource_archive_count("quick_exams", user_id)
    _add_row(rows, "admin_reset_preview_exams", "archive", exam_total, "admin_reset_preview_resources_note" if archive_shared_resources and exam_public else "")
    if archive_shared_resources and exam_public:
        _add_row(rows, "admin_reset_preview_exams_shared", "archive", exam_public)

    plan_total, plan_public = _resource_archive_count("lesson_plans", user_id)
    _add_row(rows, "admin_reset_preview_plans", "archive", plan_total, "admin_reset_preview_resources_note" if archive_shared_resources and plan_public else "")
    if archive_shared_resources and plan_public:
        _add_row(rows, "admin_reset_preview_plans_shared", "archive", plan_public)

    program_total, program_public = _resource_archive_count("learning_programs", user_id)
    _add_row(rows, "admin_reset_preview_programs", "archive", program_total, "admin_reset_preview_resources_note" if archive_shared_resources and program_public else "")
    if archive_shared_resources and program_public:
        _add_row(rows, "admin_reset_preview_programs_shared", "archive", program_public)

    _add_row(rows, "admin_reset_preview_teacher_assignments", "archive", _safe_count("teacher_assignments", [("teacher_id", user_id)]), "admin_reset_preview_teacher_assignments_note")
    _add_row(rows, "admin_reset_preview_teacher_attempts", "delete", _safe_count("teacher_assignment_attempts", [("teacher_id", user_id)]))

    if remove_relationships:
        _add_row(rows, "admin_reset_preview_relationships", "archive", _safe_count("teacher_student_links", [("teacher_id", user_id)]), "admin_reset_preview_relationships_teacher_note")
        _add_row(rows, "admin_reset_preview_relationship_subjects", "archive", _safe_count("teacher_student_subjects", [("teacher_id", user_id)]))

    _add_row(rows, "admin_reset_preview_usage", "reset", 1 if _safe_count("usage_tracking", [("user_id", user_id)]) else 0)
    _add_row(rows, "admin_reset_preview_branding", "delete", _safe_count("branding_settings", [("user_id", user_id)]))
    _add_row(rows, "admin_reset_preview_professional_profile", "delete", _safe_count("professional_profiles", [("user_id", user_id)]))
    return rows


def _build_full_preview_rows(user_id: str, archive_shared_resources: bool, remove_relationships: bool) -> list[dict[str, Any]]:
    rows = _build_student_preview_rows(user_id, remove_relationships)
    rows.extend(_build_teacher_preview_rows(user_id, archive_shared_resources, remove_relationships))
    _add_row(rows, "admin_reset_preview_app_settings", "delete", _safe_count("app_settings", [("user_id", user_id)]))
    _add_row(rows, "admin_reset_preview_activity_log", "delete", _safe_count("user_activity_log", [("user_id", user_id)]))
    return rows


def build_user_reset_preview(
    user_id: str,
    scope: str,
    *,
    archive_shared_resources: bool = True,
    remove_relationships: bool = True,
) -> dict[str, Any]:
    safe_user_id = str(user_id or "").strip()
    safe_scope = str(scope or "").strip().lower()
    if not safe_user_id or safe_scope not in RESET_SCOPES:
        return {"scope": safe_scope, "rows": [], "summary": {"delete": 0, "archive": 0, "reset": 0}}

    if safe_scope == RESET_SCOPE_STUDENT:
        rows = _build_student_preview_rows(safe_user_id, remove_relationships)
    elif safe_scope == RESET_SCOPE_TEACHER:
        rows = _build_teacher_preview_rows(safe_user_id, archive_shared_resources, remove_relationships)
    else:
        rows = _build_full_preview_rows(safe_user_id, archive_shared_resources, remove_relationships)

    summary = {"delete": 0, "archive": 0, "reset": 0}
    for row in rows:
        action = str(row.get("action") or "").strip().lower()
        if action in summary:
            summary[action] += int(row.get("count") or 0)
    return {"scope": safe_scope, "rows": rows, "summary": summary}


def _archive_student_assignments(user_id: str) -> int:
    now = _now_iso()
    return _safe_update(
        "teacher_assignments",
        [("student_id", user_id)],
        {
            "status": _ARCHIVED_STATUS,
            "source_archived": True,
            "source_archived_at": now,
            "updated_at": now,
        },
        optional_columns=["source_archived", "source_archived_at", "updated_at"],
    )


def _archive_teacher_assignments(user_id: str) -> int:
    now = _now_iso()
    return _safe_update(
        "teacher_assignments",
        [("teacher_id", user_id)],
        {
            "status": _ARCHIVED_STATUS,
            "source_archived": True,
            "source_archived_at": now,
            "updated_at": now,
        },
        optional_columns=["source_archived", "source_archived_at", "updated_at"],
    )


def _archive_relationship_side(column_name: str, user_id: str) -> tuple[int, int]:
    now = _now_iso()
    links = _safe_update(
        "teacher_student_links",
        [(column_name, user_id)],
        {"status": _ARCHIVED_STATUS, "archived_at": now, "updated_at": now},
        optional_columns=["archived_at", "updated_at"],
    )
    subjects = _safe_update(
        "teacher_student_subjects",
        [(column_name, user_id)],
        {"status": _ARCHIVED_STATUS, "deactivated_at": now, "updated_at": now},
        optional_columns=["deactivated_at", "updated_at"],
    )
    return links, subjects


def _archive_teacher_resources(user_id: str) -> dict[str, int]:
    now = _now_iso()
    counts = {
        "worksheets": _safe_update("worksheets", [("user_id", user_id)], {"status": _ARCHIVED_STATUS, "is_public": False, "updated_at": now}, optional_columns=["status", "is_public", "updated_at"]),
        "quick_exams": _safe_update("quick_exams", [("user_id", user_id)], {"status": _ARCHIVED_STATUS, "is_public": False, "updated_at": now}, optional_columns=["status", "is_public", "updated_at"]),
        "lesson_plans": _safe_update("lesson_plans", [("user_id", user_id)], {"status": _ARCHIVED_STATUS, "is_public": False, "updated_at": now}, optional_columns=["status", "is_public", "updated_at"]),
        "learning_programs": _safe_update("learning_programs", [("user_id", user_id)], {"status": _ARCHIVED_STATUS, "is_public": False, "updated_at": now}, optional_columns=["status", "is_public", "updated_at"]),
    }
    return counts


def _execute_student_reset(user_id: str, *, remove_relationships: bool) -> dict[str, int]:
    counters = {
        "student_assignments": _archive_student_assignments(user_id),
        "student_attempts": _safe_delete("teacher_assignment_attempts", [("student_id", user_id)]),
        "student_reviews": _safe_delete("teacher_review_requests", [("student_id", user_id)]),
        "student_program_assignments": _safe_delete("learning_program_assignments", [("user_id", user_id)]),
        "student_program_progress": _safe_delete("learning_program_progress", [("user_id", user_id)]),
        "student_sessions": _safe_delete("practice_sessions", [("user_id", user_id)]),
        "student_answers": _safe_delete("practice_answers", [("user_id", user_id)]),
        "student_progress": _safe_delete("practice_progress", [("user_id", user_id)]),
    }
    if remove_relationships:
        links, subjects = _archive_relationship_side("student_id", user_id)
        counters["student_relationships"] = links
        counters["student_relationship_subjects"] = subjects
    return counters


def _execute_teacher_reset(
    user_id: str,
    *,
    archive_shared_resources: bool,
    remove_relationships: bool,
) -> dict[str, int]:
    del archive_shared_resources  # resources are always archived, including shared ones
    counters = {
        "students": _safe_delete("students", [("user_id", user_id)]),
        "classes": _safe_delete("classes", [("user_id", user_id)]),
        "payments": _safe_delete("payments", [("user_id", user_id)]),
        "schedules": _safe_delete("schedules", [("user_id", user_id)]),
        "calendar_overrides": _safe_delete("calendar_overrides", [("user_id", user_id)]),
        "student_schedule_freezes": _safe_delete("student_schedule_freezes", [("user_id", user_id)]),
        "ai_usage_logs": _safe_delete("ai_usage_logs", [("user_id", user_id)]),
        "pricing_items": _safe_delete("pricing_items", [("user_id", user_id)]),
        "teacher_review_requests": _safe_delete("teacher_review_requests", [("teacher_id", user_id)]),
        "teacher_assignment_attempts": _safe_delete("teacher_assignment_attempts", [("teacher_id", user_id)]),
        "branding_settings": _safe_delete("branding_settings", [("user_id", user_id)]),
        "professional_profiles": _safe_delete("professional_profiles", [("user_id", user_id)]),
        "teacher_assignments": _archive_teacher_assignments(user_id),
    }
    counters.update(_archive_teacher_resources(user_id))
    if remove_relationships:
        links, subjects = _archive_relationship_side("teacher_id", user_id)
        counters["teacher_relationships"] = links
        counters["teacher_relationship_subjects"] = subjects
    try:
        reset_usage(user_id)
        counters["usage_tracking"] = 1
    except Exception:
        counters["usage_tracking"] = 0
    return counters


def _profile_updates_for_scope(scope: str, notes: str) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "admin_notes": str(notes or "").strip(),
        "account_status": "active",
    }
    if scope in {RESET_SCOPE_TEACHER, RESET_SCOPE_FULL}:
        payload["active_student_count"] = 0
        payload["last_page"] = None
    if scope == RESET_SCOPE_FULL:
        payload["onboarding_completed"] = False
    return payload


def execute_user_reset(
    user_id: str,
    scope: str,
    *,
    notes: str = "",
    archive_shared_resources: bool = True,
    remove_relationships: bool = True,
) -> tuple[bool, str, dict[str, int]]:
    safe_user_id = str(user_id or "").strip()
    safe_scope = str(scope or "").strip().lower()
    if not safe_user_id:
        return False, "missing_user_id", {}
    if safe_scope not in RESET_SCOPES:
        return False, "invalid_scope", {}

    counters: dict[str, int] = {}
    try:
        if safe_scope == RESET_SCOPE_STUDENT:
            counters.update(_execute_student_reset(safe_user_id, remove_relationships=remove_relationships))
        elif safe_scope == RESET_SCOPE_TEACHER:
            counters.update(
                _execute_teacher_reset(
                    safe_user_id,
                    archive_shared_resources=archive_shared_resources,
                    remove_relationships=remove_relationships,
                )
            )
        else:
            counters.update(_execute_student_reset(safe_user_id, remove_relationships=remove_relationships))
            counters.update(
                _execute_teacher_reset(
                    safe_user_id,
                    archive_shared_resources=archive_shared_resources,
                    remove_relationships=remove_relationships,
                )
            )
            counters["app_settings"] = _safe_delete("app_settings", [("user_id", safe_user_id)])
            counters["user_activity_log"] = _safe_delete("user_activity_log", [("user_id", safe_user_id)])

        get_sb().table("profiles").update(_profile_updates_for_scope(safe_scope, notes)).eq("user_id", safe_user_id).execute()
        clear_app_caches()
        return True, "ok", counters
    except Exception as exc:
        return False, str(exc), counters
