from __future__ import annotations

from datetime import date, datetime, timezone
import re
from typing import Any

import streamlit as st

from core.database import clear_app_caches, get_sb
from core.i18n import t
from core.state import get_current_user_id
from helpers.lesson_planner import QUICK_SUBJECTS, normalize_subject, subject_label


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _clean_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _clean_display_text(value: Any) -> str:
    text = _clean_text(value)
    if text:
        text = text[0].upper() + text[1:]
    return text


def _normalize_name(value: Any) -> str:
    return _clean_text(value).casefold()


def _normalize_email(value: Any) -> str:
    return _clean_text(value).casefold()


def _slugify_subject(value: str) -> str:
    text = _clean_text(value).casefold()
    text = re.sub(r"[^a-z0-9]+", "_", text).strip("_")
    return text or "other"


def _rows(result) -> list[dict]:
    return getattr(result, "data", None) or []


def _profile_label(profile: dict) -> str:
    return (
        _clean_text(profile.get("display_name"))
        or _clean_text(profile.get("username"))
        or _clean_text(profile.get("email"))
        or "—"
    )


def _load_profiles_map(user_ids: list[str]) -> dict[str, dict]:
    user_ids = [str(uid).strip() for uid in user_ids if str(uid).strip()]
    if not user_ids:
        return {}
    try:
        res = (
            get_sb()
            .table("profiles")
            .select("user_id, display_name, username, avatar_url, email, primary_subjects, custom_subjects")
            .in_("user_id", user_ids)
            .execute()
        )
        return {str(row.get("user_id")): row for row in _rows(res)}
    except Exception:
        return {}


def _subject_scope_dict(subject_key: str, subject_label_text: str = "") -> dict:
    normalized = normalize_subject(subject_key or subject_label_text)
    if normalized in QUICK_SUBJECTS and normalized != "other":
        return {
            "subject_key": normalized,
            "subject_label": subject_label(normalized),
            "is_custom": False,
        }

    label = _clean_display_text(subject_label_text or subject_key)
    return {
        "subject_key": _slugify_subject(label),
        "subject_label": label,
        "is_custom": True,
    }


def _serialize_subject_scopes(values: list[str]) -> list[dict]:
    scopes: list[dict] = []
    seen: set[tuple[str, str]] = set()
    for value in values or []:
        scope = _subject_scope_dict(str(value))
        key = (scope["subject_key"], scope["subject_label"])
        if key in seen:
            continue
        seen.add(key)
        scopes.append(scope)
    return scopes


def _available_subject_scopes_from_profile(profile: dict) -> list[dict]:
    scopes: list[dict] = []
    seen: set[tuple[str, str]] = set()

    for subject_key in profile.get("primary_subjects") or []:
        if not subject_key:
            continue
        scope = _subject_scope_dict(str(subject_key))
        key = (scope["subject_key"], scope["subject_label"])
        if key not in seen:
            seen.add(key)
            scopes.append(scope)

    for custom_subject in profile.get("custom_subjects") or []:
        if not custom_subject:
            continue
        scope = _subject_scope_dict(str(custom_subject), str(custom_subject))
        key = (scope["subject_key"], scope["subject_label"])
        if key not in seen:
            seen.add(key)
            scopes.append(scope)

    return scopes


def _subject_scope_label(scope: dict) -> str:
    return _clean_display_text(scope.get("subject_label") or subject_label(scope.get("subject_key") or "other"))


def _load_teacher_student_rows(teacher_id: str) -> list[dict]:
    teacher_id = str(teacher_id or "").strip()
    if not teacher_id:
        return []
    try:
        rows = _rows(
            get_sb()
            .table("students")
            .select("*")
            .eq("user_id", teacher_id)
            .order("student")
            .execute()
        )
    except Exception:
        return []

    cleaned = []
    for row in rows:
        cleaned.append(
            {
                **row,
                "student": _clean_text(row.get("student")),
                "email": _clean_text(row.get("email")),
                "linked_student_user_id": str(row.get("linked_student_user_id") or "").strip(),
                "teacher_student_link_id": row.get("teacher_student_link_id"),
                "student_source": _clean_text(row.get("student_source")) or "manual",
            }
        )
    return cleaned


def _student_record_display_label(row: dict) -> str:
    name = _clean_display_text(row.get("student")) or "—"
    extras: list[str] = []
    email = _clean_text(row.get("email"))
    if email:
        extras.append(email)
    if row.get("linked_student_user_id"):
        extras.append("Classio")
    if extras:
        return f"{name} · {' · '.join(extras)}"
    return name


def _resolve_teacher_student_match(teacher_id: str, student_profile: dict) -> dict:
    student_user_id = str(student_profile.get("user_id") or "").strip()
    student_email = _normalize_email(student_profile.get("email"))
    student_name = _normalize_name(_profile_label(student_profile))
    rows = _load_teacher_student_rows(teacher_id)

    usable_rows = [
        row for row in rows
        if not row.get("linked_student_user_id") or row.get("linked_student_user_id") == student_user_id
    ]

    exact_link_rows = [
        row for row in rows
        if row.get("linked_student_user_id") and row.get("linked_student_user_id") == student_user_id
    ]
    if len(exact_link_rows) == 1:
        return {
            "mode": "linked_existing",
            "requires_choice": False,
            "selected_row": exact_link_rows[0],
            "candidates": [],
            "summary_key": "teacher_request_auto_link_existing",
        }

    email_matches = []
    if student_email:
        email_matches = [
            row for row in usable_rows
            if _normalize_email(row.get("email")) == student_email
        ]
        if len(email_matches) == 1:
            return {
                "mode": "auto_email",
                "requires_choice": False,
                "selected_row": email_matches[0],
                "candidates": [],
                "summary_key": "teacher_request_auto_link_email",
            }

    name_matches = []
    if student_name:
        name_matches = [
            row for row in usable_rows
            if _normalize_name(row.get("student")) == student_name
        ]

    candidate_map: dict[int, dict] = {}
    for row in email_matches + name_matches:
        if row.get("id") is not None:
            candidate_map[int(row["id"])] = row
    candidates = list(candidate_map.values())

    if candidates:
        return {
            "mode": "review",
            "requires_choice": True,
            "selected_row": None,
            "candidates": candidates,
            "summary_key": "teacher_request_review_match",
        }

    return {
        "mode": "create_new",
        "requires_choice": False,
        "selected_row": None,
        "candidates": [],
        "summary_key": "teacher_request_new_record_will_be_created",
    }


def get_teacher_request_resolution(link_id: int) -> dict:
    teacher_id = str(get_current_user_id() or "").strip()
    if not teacher_id or not link_id:
        return {"mode": "create_new", "requires_choice": False, "selected_row": None, "candidates": []}
    try:
        rows = _rows(
            get_sb()
            .table("teacher_student_links")
            .select("*")
            .eq("id", link_id)
            .eq("teacher_id", teacher_id)
            .limit(1)
            .execute()
        )
    except Exception:
        return {"mode": "create_new", "requires_choice": False, "selected_row": None, "candidates": []}
    if not rows:
        return {"mode": "create_new", "requires_choice": False, "selected_row": None, "candidates": []}
    link = rows[0]
    profiles = _load_profiles_map([str(link.get("student_id") or "").strip()])
    student_profile = profiles.get(str(link.get("student_id") or "").strip(), {})
    if student_profile:
        student_profile = {**student_profile, "user_id": str(link.get("student_id") or "").strip()}
    return _resolve_teacher_student_match(teacher_id, student_profile)


def _sync_student_record_for_link(
    *,
    teacher_id: str,
    link: dict,
    local_student_record_id: int | None = None,
) -> tuple[bool, str]:
    student_id = str(link.get("student_id") or "").strip()
    if not teacher_id or not student_id:
        return False, "teacher_request_failed"

    profiles = _load_profiles_map([student_id])
    student_profile = profiles.get(student_id, {})
    if student_profile:
        student_profile = {**student_profile, "user_id": student_id}
    display_name = _clean_display_text(_profile_label(student_profile)) or "Student"
    student_email = _clean_text(student_profile.get("email"))
    now = _now_iso()
    sb = get_sb()

    resolution = _resolve_teacher_student_match(teacher_id, student_profile)

    chosen_row = None
    if local_student_record_id is not None:
        chosen_row = next(
            (
                row for row in _load_teacher_student_rows(teacher_id)
                if int(row.get("id") or 0) == int(local_student_record_id)
            ),
            None,
        )
        if not chosen_row:
            return False, "teacher_request_match_required"
    elif resolution.get("selected_row"):
        chosen_row = resolution["selected_row"]
    elif resolution.get("requires_choice"):
        return False, "teacher_request_match_required"

    if chosen_row:
        payload = {
            "linked_student_user_id": student_id,
            "teacher_student_link_id": link.get("id"),
            "student_source": "classio_linked_existing",
            "linked_at": now,
        }
        if student_email and not _clean_text(chosen_row.get("email")):
            payload["email"] = student_email
        if not _clean_text(chosen_row.get("student")):
            payload["student"] = display_name
        sb.table("students").update(payload).eq("id", chosen_row["id"]).eq("user_id", teacher_id).execute()
        return True, "teacher_request_accepted_linked_existing"

    payload = {
        "user_id": teacher_id,
        "student": display_name,
        "email": student_email,
        "zoom_link": "",
        "notes": "",
        "color": "#3B82F6",
        "phone": "",
        "address": "",
        "linked_student_user_id": student_id,
        "teacher_student_link_id": link.get("id"),
        "student_source": "classio_link",
        "linked_at": now,
    }
    sb.table("students").insert(payload).execute()
    return True, "teacher_request_accepted_created_student"


def load_student_teacher_links(statuses: list[str] | None = None) -> list[dict]:
    uid = get_current_user_id()
    if not uid:
        return []
    try:
        query = (
            get_sb()
            .table("teacher_student_links")
            .select("*")
            .eq("student_id", uid)
            .order("created_at", desc=True)
        )
        if statuses:
            query = query.in_("status", statuses)
        rows = _rows(query.execute())
    except Exception:
        return []

    if not rows:
        return []

    link_ids = [row.get("id") for row in rows if row.get("id") is not None]
    teacher_ids = [str(row.get("teacher_id")) for row in rows if row.get("teacher_id")]

    subject_map: dict[int, list[dict]] = {}
    if link_ids:
        try:
            subj_rows = _rows(
                get_sb()
                .table("teacher_student_subjects")
                .select("*")
                .in_("link_id", link_ids)
                .order("subject_label")
                .execute()
            )
            for item in subj_rows:
                subject_map.setdefault(item.get("link_id"), []).append(item)
        except Exception:
            pass

    profiles = _load_profiles_map(teacher_ids)
    enriched = []
    for row in rows:
        teacher_profile = profiles.get(str(row.get("teacher_id")), {})
        enriched.append(
            {
                **row,
                "teacher_profile": teacher_profile,
                "teacher_name": _profile_label(teacher_profile),
                "active_subjects": [s for s in subject_map.get(row.get("id"), []) if str(s.get("status") or "") == "active"],
                "requested_subjects": row.get("requested_subjects") or [],
            }
        )
    return enriched


def load_incoming_teacher_requests() -> list[dict]:
    uid = get_current_user_id()
    if not uid:
        return []
    try:
        rows = _rows(
            get_sb()
            .table("teacher_student_links")
            .select("*")
            .eq("teacher_id", uid)
            .eq("status", "pending")
            .order("created_at", desc=True)
            .execute()
        )
    except Exception:
        return []

    profiles = _load_profiles_map([str(row.get("student_id")) for row in rows if row.get("student_id")])
    enriched = []
    for row in rows:
        student_profile = profiles.get(str(row.get("student_id")), {})
        enriched.append(
            {
                **row,
                "student_profile": student_profile,
                "student_name": _profile_label(student_profile),
                "requested_subjects": row.get("requested_subjects") or [],
            }
        )
    return enriched


def load_active_linked_students_for_teacher() -> list[dict]:
    uid = get_current_user_id()
    if not uid:
        return []
    try:
        rows = _rows(
            get_sb()
            .table("teacher_student_links")
            .select("*")
            .eq("teacher_id", uid)
            .eq("status", "active")
            .order("created_at", desc=True)
            .execute()
        )
    except Exception:
        return []

    if not rows:
        return []

    link_ids = [row.get("id") for row in rows if row.get("id") is not None]
    student_ids = [str(row.get("student_id")) for row in rows if row.get("student_id")]

    subjects_by_link: dict[int, list[dict]] = {}
    if link_ids:
        try:
            subj_rows = _rows(
                get_sb()
                .table("teacher_student_subjects")
                .select("*")
                .in_("link_id", link_ids)
                .eq("status", "active")
                .order("subject_label")
                .execute()
            )
            for item in subj_rows:
                subjects_by_link.setdefault(item.get("link_id"), []).append(item)
        except Exception:
            pass

    profiles = _load_profiles_map(student_ids)
    linked = []
    for row in rows:
        student_profile = profiles.get(str(row.get("student_id")), {})
        linked.append(
            {
                **row,
                "student_profile": student_profile,
                "student_name": _profile_label(student_profile),
                "subjects": subjects_by_link.get(row.get("id"), []),
            }
        )
    return linked


def create_teacher_request(teacher_id: str, requested_subjects: list[str], note: str = "") -> tuple[bool, str]:
    student_id = str(get_current_user_id() or "").strip()
    teacher_id = str(teacher_id or "").strip()
    if not student_id or not teacher_id:
        return False, "no_data"
    if teacher_id == student_id:
        return False, "teacher_request_self"

    requested_scopes = _serialize_subject_scopes(requested_subjects)
    if not requested_scopes:
        return False, "select_active_subjects"

    sb = get_sb()
    try:
        existing_rows = _rows(
            sb.table("teacher_student_links")
            .select("*")
            .eq("teacher_id", teacher_id)
            .eq("student_id", student_id)
            .limit(1)
            .execute()
        )
        now = _now_iso()
        payload = {
            "teacher_id": teacher_id,
            "student_id": student_id,
            "requested_by": student_id,
            "requested_subjects": requested_scopes,
            "request_note": _clean_text(note),
            "status": "pending",
            "responded_at": None,
            "responded_by": None,
            "archived_at": None,
            "updated_at": now,
        }
        if existing_rows:
            row = existing_rows[0]
            status = str(row.get("status") or "").strip()
            if status in {"pending", "active"}:
                return False, "teacher_request_exists"
            sb.table("teacher_student_links").update(payload).eq("id", row["id"]).execute()
        else:
            payload["created_at"] = now
            sb.table("teacher_student_links").insert(payload).execute()
        clear_app_caches()
        return True, "teacher_request_sent"
    except Exception:
        return False, "teacher_request_failed"


def respond_to_teacher_request(
    link_id: int,
    accept: bool,
    active_subjects: list[str],
    local_student_record_id: int | None = None,
) -> tuple[bool, str]:
    teacher_id = str(get_current_user_id() or "").strip()
    if not teacher_id or not link_id:
        return False, "no_data"

    sb = get_sb()
    try:
        rows = _rows(
            sb.table("teacher_student_links")
            .select("*")
            .eq("id", link_id)
            .eq("teacher_id", teacher_id)
            .limit(1)
            .execute()
        )
        if not rows:
            return False, "no_data"
        link = rows[0]
        now = _now_iso()
        if not accept:
            sb.table("teacher_student_links").update(
                {
                    "status": "rejected",
                    "responded_at": now,
                    "responded_by": teacher_id,
                    "updated_at": now,
                }
            ).eq("id", link_id).execute()
            clear_app_caches()
            return True, "teacher_request_rejected"

        scopes = _serialize_subject_scopes(active_subjects)
        if not scopes:
            stored = link.get("requested_subjects") or []
            scopes = [scope for scope in stored if isinstance(scope, dict)]
        if not scopes:
            return False, "select_active_subjects"

        sb.table("teacher_student_links").update(
            {
                "status": "active",
                "responded_at": now,
                "responded_by": teacher_id,
                "updated_at": now,
            }
        ).eq("id", link_id).execute()

        existing_subject_rows = _rows(
            sb.table("teacher_student_subjects").select("*").eq("link_id", link_id).execute()
        )
        existing_by_key = {
            str(row.get("subject_key") or ""): row
            for row in existing_subject_rows
            if str(row.get("subject_key") or "")
        }
        active_keys = set()
        for scope in scopes:
            subject_key = str(scope.get("subject_key") or "").strip()
            subject_label_text = _clean_display_text(scope.get("subject_label") or subject_key)
            if not subject_key:
                continue
            active_keys.add(subject_key)
            row = existing_by_key.get(subject_key)
            payload = {
                "link_id": link_id,
                "teacher_id": teacher_id,
                "student_id": str(link.get("student_id") or "").strip(),
                "subject_key": subject_key,
                "subject_label": subject_label_text,
                "status": "active",
                "activated_at": now,
                "deactivated_at": None,
                "updated_at": now,
            }
            if row:
                sb.table("teacher_student_subjects").update(payload).eq("id", row["id"]).execute()
            else:
                payload["created_at"] = now
                sb.table("teacher_student_subjects").insert(payload).execute()

        for row in existing_subject_rows:
            subject_key = str(row.get("subject_key") or "").strip()
            if subject_key and subject_key not in active_keys:
                sb.table("teacher_student_subjects").update(
                    {"status": "archived", "deactivated_at": now, "updated_at": now}
                ).eq("id", row["id"]).execute()

        sync_ok, sync_msg = _sync_student_record_for_link(
            teacher_id=teacher_id,
            link=link,
            local_student_record_id=local_student_record_id,
        )
        if not sync_ok:
            return False, sync_msg

        clear_app_caches()
        return True, sync_msg
    except Exception:
        return False, "teacher_request_failed"


def archive_teacher_student_link(link_id: int) -> tuple[bool, str]:
    uid = str(get_current_user_id() or "").strip()
    if not uid or not link_id:
        return False, "no_data"
    try:
        rows = _rows(
            get_sb()
            .table("teacher_student_links")
            .select("*")
            .eq("id", link_id)
            .limit(1)
            .execute()
        )
        if not rows:
            return False, "no_data"
        link = rows[0]
        if uid not in {str(link.get("teacher_id") or "").strip(), str(link.get("student_id") or "").strip()}:
            return False, "no_data"
        now = _now_iso()
        get_sb().table("teacher_student_links").update(
            {"status": "archived", "archived_at": now, "updated_at": now}
        ).eq("id", link_id).execute()
        get_sb().table("teacher_student_subjects").update(
            {"status": "archived", "deactivated_at": now, "updated_at": now}
        ).eq("link_id", link_id).execute()
        clear_app_caches()
        return True, "teacher_relationship_archived"
    except Exception:
        return False, "teacher_relationship_failed"


def create_teacher_assignment(
    *,
    link_id: int,
    subject_scope_id: int,
    assignment_type: str,
    source_type: str,
    title: str,
    subject_key: str,
    subject_label_text: str,
    content_snapshot: dict,
    topic: str = "",
    teacher_note: str = "",
    due_date: date | None = None,
    source_record_id: int | None = None,
) -> tuple[bool, str]:
    teacher_id = str(get_current_user_id() or "").strip()
    if not teacher_id:
        return False, "no_data"
    try:
        link_rows = _rows(
            get_sb()
            .table("teacher_student_links")
            .select("*")
            .eq("id", link_id)
            .eq("teacher_id", teacher_id)
            .eq("status", "active")
            .limit(1)
            .execute()
        )
        if not link_rows:
            return False, "assignment_link_required"
        link = link_rows[0]
        scope_rows = _rows(
            get_sb()
            .table("teacher_student_subjects")
            .select("*")
            .eq("id", subject_scope_id)
            .eq("link_id", link_id)
            .eq("teacher_id", teacher_id)
            .eq("status", "active")
            .limit(1)
            .execute()
        )
        if not scope_rows:
            return False, "assignment_subject_required"
        scope = scope_rows[0]
        now = _now_iso()
        due_at = None
        if due_date:
            due_at = datetime.combine(due_date, datetime.min.time()).replace(tzinfo=timezone.utc).isoformat()
        payload = {
            "link_id": link_id,
            "subject_scope_id": subject_scope_id,
            "teacher_id": teacher_id,
            "student_id": str(link.get("student_id") or "").strip(),
            "assignment_type": assignment_type,
            "source_type": source_type,
            "source_record_id": source_record_id,
            "title": _clean_display_text(title),
            "subject_key": str(scope.get("subject_key") or subject_key or "").strip(),
            "subject_label": _clean_display_text(scope.get("subject_label") or subject_label_text or subject_label(subject_key)),
            "topic": _clean_display_text(topic),
            "teacher_note": _clean_text(teacher_note),
            "content_snapshot": content_snapshot or {},
            "status": "assigned",
            "due_at": due_at,
            "assigned_at": now,
            "created_at": now,
            "updated_at": now,
        }
        get_sb().table("teacher_assignments").insert(payload).execute()
        clear_app_caches()
        return True, "assignment_created"
    except Exception:
        return False, "assignment_create_failed"


def load_student_assignments(statuses: list[str] | None = None) -> list[dict]:
    uid = str(get_current_user_id() or "").strip()
    if not uid:
        return []
    try:
        query = (
            get_sb()
            .table("teacher_assignments")
            .select("*")
            .eq("student_id", uid)
            .order("created_at", desc=True)
        )
        if statuses:
            query = query.in_("status", statuses)
        rows = _rows(query.execute())
    except Exception:
        return []

    if not rows:
        return []

    teacher_profiles = _load_profiles_map([str(row.get("teacher_id")) for row in rows if row.get("teacher_id")])
    grouped_rows = []
    for row in rows:
        teacher_profile = teacher_profiles.get(str(row.get("teacher_id")), {})
        grouped_rows.append(
            {
                **row,
                "teacher_profile": teacher_profile,
                "teacher_name": _profile_label(teacher_profile),
                "subject_display": _clean_display_text(row.get("subject_label") or subject_label(row.get("subject_key") or "")),
            }
        )
    return grouped_rows


def get_student_assignment_summary(limit: int = 4) -> list[dict]:
    statuses = ["assigned", "started", "submitted", "graded", "completed", "overdue"]
    assignments = load_student_assignments(statuses=statuses)
    if not assignments:
        return []

    status_priority = {
        "overdue": 0,
        "assigned": 1,
        "started": 2,
        "submitted": 3,
        "graded": 4,
        "completed": 5,
    }

    def _sort_key(row: dict):
        due_at = row.get("due_at") or "9999-12-31T00:00:00+00:00"
        status = str(row.get("status") or "").strip()
        return (
            status_priority.get(status, 99),
            due_at,
            str(row.get("created_at") or ""),
        )

    ordered = sorted(assignments, key=_sort_key)
    return ordered[:limit]


def has_active_teacher_relationships() -> bool:
    return bool(load_student_teacher_links(statuses=["active"]))


def mark_assignment_started(assignment_id: int) -> None:
    uid = str(get_current_user_id() or "").strip()
    if not uid or not assignment_id:
        return
    try:
        now = _now_iso()
        get_sb().table("teacher_assignments").update(
            {
                "status": "started",
                "opened_at": now,
                "updated_at": now,
            }
        ).eq("id", assignment_id).eq("student_id", uid).in_("status", ["assigned", "overdue"]).execute()
        clear_app_caches()
    except Exception:
        pass


def update_topic_assignment_status(assignment_id: int, status: str) -> None:
    uid = str(get_current_user_id() or "").strip()
    if not uid or not assignment_id:
        return
    status = str(status or "").strip()
    if status not in {"started", "completed"}:
        return
    now = _now_iso()
    payload = {"status": status, "updated_at": now}
    if status == "started":
        payload["opened_at"] = now
    if status == "completed":
        payload["completed_at"] = now
    try:
        get_sb().table("teacher_assignments").update(payload).eq("id", assignment_id).eq("student_id", uid).execute()
        clear_app_caches()
    except Exception:
        pass


def record_assignment_attempt_from_practice(
    assignment_id: int,
    session_id: int | None,
    result: dict,
    exercise_data: dict,
) -> None:
    uid = str(get_current_user_id() or "").strip()
    if not uid or not assignment_id or not isinstance(result, dict):
        return
    try:
        rows = _rows(
            get_sb()
            .table("teacher_assignments")
            .select("*")
            .eq("id", assignment_id)
            .eq("student_id", uid)
            .limit(1)
            .execute()
        )
        if not rows:
            return
        assignment = rows[0]
        now = _now_iso()
        score_pct = round(float(result.get("score_pct") or 0), 1)
        total = int(result.get("total") or 0)
        correct = int(result.get("correct") or 0)

        existing_attempts = _rows(
            get_sb()
            .table("teacher_assignment_attempts")
            .select("id")
            .eq("assignment_id", assignment_id)
            .eq("student_id", uid)
            .execute()
        )
        attempt_number = len(existing_attempts) + 1
        attempt_payload = {
            "assignment_id": assignment_id,
            "teacher_id": str(assignment.get("teacher_id") or "").strip(),
            "student_id": uid,
            "practice_session_id": session_id,
            "attempt_number": attempt_number,
            "status": "graded",
            "score_pct": score_pct,
            "total_questions": total,
            "correct_count": correct,
            "submission_payload": {
                "result": result,
                "source_type": exercise_data.get("source_type"),
                "source_id": exercise_data.get("source_id"),
                "title": exercise_data.get("title"),
            },
            "started_at": assignment.get("opened_at") or now,
            "submitted_at": now,
            "graded_at": now,
            "completed_at": now,
            "created_at": now,
            "updated_at": now,
        }
        get_sb().table("teacher_assignment_attempts").insert(attempt_payload).execute()
        get_sb().table("teacher_assignments").update(
            {
                "status": "graded",
                "score_pct": score_pct,
                "total_questions": total,
                "correct_count": correct,
                "submitted_at": now,
                "graded_at": now,
                "completed_at": now,
                "updated_at": now,
            }
        ).eq("id", assignment_id).eq("student_id", uid).execute()
        clear_app_caches()
    except Exception:
        pass


def load_teacher_assignment_progress(student_id: str | None = None, subject_key: str | None = None) -> list[dict]:
    teacher_id = str(get_current_user_id() or "").strip()
    if not teacher_id:
        return []
    try:
        query = (
            get_sb()
            .table("teacher_assignments")
            .select("*")
            .eq("teacher_id", teacher_id)
            .order("created_at", desc=True)
        )
        if student_id:
            query = query.eq("student_id", str(student_id).strip())
        if subject_key:
            query = query.eq("subject_key", str(subject_key).strip())
        assignments = _rows(query.execute())
    except Exception:
        return []

    if not assignments:
        return []

    assignment_ids = [row.get("id") for row in assignments if row.get("id") is not None]
    attempts_map: dict[int, list[dict]] = {}
    if assignment_ids:
        try:
            attempts = _rows(
                get_sb()
                .table("teacher_assignment_attempts")
                .select("*")
                .in_("assignment_id", assignment_ids)
                .order("created_at", desc=True)
                .execute()
            )
            for item in attempts:
                attempts_map.setdefault(item.get("assignment_id"), []).append(item)
        except Exception:
            pass

    profiles = _load_profiles_map([str(row.get("student_id")) for row in assignments if row.get("student_id")])
    enriched = []
    for row in assignments:
        student_profile = profiles.get(str(row.get("student_id")), {})
        attempts = attempts_map.get(row.get("id"), [])
        latest = attempts[0] if attempts else {}
        enriched.append(
            {
                **row,
                "student_profile": student_profile,
                "student_name": _profile_label(student_profile),
                "subject_display": _clean_display_text(row.get("subject_label") or subject_label(row.get("subject_key") or "")),
                "attempt_count": len(attempts),
                "latest_attempt": latest,
            }
        )
    return enriched


def extract_assignable_plan_topics(plan: dict, subject: str, topic: str, lesson_purpose: str = "") -> list[dict]:
    extracted: list[dict] = []
    raw_topics = plan.get("lesson_topics") or plan.get("topics") or []
    for idx, item in enumerate(raw_topics, 1):
        if isinstance(item, dict):
            title = _clean_display_text(item.get("title") or item.get("topic") or item.get("name"))
            summary = _clean_display_text(item.get("summary") or item.get("description") or item.get("focus"))
            focus = _clean_display_text(item.get("focus") or item.get("summary") or "")
        else:
            title = _clean_display_text(item)
            summary = ""
            focus = ""
        if title:
            extracted.append(
                {
                    "topic_title": title,
                    "topic_summary": summary,
                    "focus_area": focus,
                    "sequence_order": idx,
                }
            )

    if extracted:
        return extracted

    title = _clean_display_text(topic or plan.get("title") or t("untitled_plan"))
    objective = _clean_display_text(plan.get("objective") or "")
    success_criteria = plan.get("success_criteria") or []
    focus = _clean_display_text(lesson_purpose)
    if not focus and success_criteria:
        focus = _clean_display_text(success_criteria[0])
    return [
        {
            "topic_title": title,
            "topic_summary": objective,
            "focus_area": focus,
            "sequence_order": 1,
        }
    ]


def _assignment_target_options() -> list[dict]:
    return load_active_linked_students_for_teacher()


def _link_option_label(link: dict) -> str:
    subjects = ", ".join(_clean_display_text(s.get("subject_label")) for s in link.get("subjects", []) if s.get("subject_label"))
    if subjects:
        return f"{link.get('student_name', '—')} · {subjects}"
    return link.get("student_name", "—")


def _render_assignment_target_fields(prefix: str, available_links: list[dict]) -> tuple[dict | None, dict | None, date | None, str]:
    link = None
    subject = None
    due_date = None
    teacher_note = ""

    if not available_links:
        st.info(t("no_linked_students"))
        return None, None, None, ""

    link_idx = st.selectbox(
        t("select_student"),
        options=list(range(len(available_links))),
        format_func=lambda idx: _link_option_label(available_links[idx]),
        key=f"{prefix}_student_link_idx",
    )
    link = available_links[link_idx]
    subject_rows = link.get("subjects", [])
    if not subject_rows:
        st.warning(t("no_active_subjects"))
        return None, None, None, ""

    subject_idx = st.selectbox(
        t("subject_label"),
        options=list(range(len(subject_rows))),
        format_func=lambda idx: _clean_display_text(subject_rows[idx].get("subject_label")),
        key=f"{prefix}_subject_scope_idx",
    )
    subject = subject_rows[subject_idx]

    use_due_date = st.checkbox(t("assignment_set_due_date"), key=f"{prefix}_use_due_date")
    if use_due_date:
        due_date = st.date_input(
            t("due_date"),
            value=date.today(),
            key=f"{prefix}_due_date",
        )

    teacher_note = st.text_area(
        t("teacher_note"),
        key=f"{prefix}_teacher_note",
        height=90,
        placeholder=t("assignment_teacher_note_placeholder"),
    )
    return link, subject, due_date, teacher_note


def render_assignment_panel_for_worksheet(
    *,
    prefix: str,
    worksheet: dict,
    subject: str,
    topic: str,
    learner_stage: str,
    level_or_band: str,
) -> None:
    st.markdown(f"### {t('assign_to_student')}")
    links = _assignment_target_options()
    link, subject_scope, due_date, teacher_note = _render_assignment_target_fields(prefix, links)
    if not link or not subject_scope:
        return
    if st.button(t("create_assignment"), key=f"{prefix}_assign_btn", use_container_width=True):
        snapshot = {
            "worksheet": worksheet,
            "meta": {
                "subject": subject,
                "topic": topic,
                "learner_stage": learner_stage,
                "level_or_band": level_or_band,
                "worksheet_type": worksheet.get("worksheet_type", ""),
            },
        }
        ok, key = create_teacher_assignment(
            link_id=link["id"],
            subject_scope_id=subject_scope["id"],
            assignment_type="worksheet",
            source_type="worksheet_builder",
            title=str(worksheet.get("title") or topic or t("untitled_worksheet")),
            subject_key=str(subject_scope.get("subject_key") or subject or ""),
            subject_label_text=str(subject_scope.get("subject_label") or subject_label(subject or "")),
            topic=topic,
            teacher_note=teacher_note,
            due_date=due_date,
            content_snapshot=snapshot,
        )
        if ok:
            st.success(t(key))
        else:
            st.error(t(key))


def render_assignment_panel_for_exam(
    *,
    prefix: str,
    exam_data: dict,
    answer_key: dict,
    subject: str,
    topic: str,
    learner_stage: str,
    level_or_band: str,
) -> None:
    st.markdown(f"### {t('assign_to_student')}")
    links = _assignment_target_options()
    link, subject_scope, due_date, teacher_note = _render_assignment_target_fields(prefix, links)
    if not link or not subject_scope:
        return
    if st.button(t("create_assignment"), key=f"{prefix}_assign_btn", use_container_width=True):
        snapshot = {
            "exam_data": exam_data,
            "answer_key": answer_key,
            "meta": {
                "subject": subject,
                "topic": topic,
                "learner_stage": learner_stage,
                "level_or_band": level_or_band,
            },
        }
        ok, key = create_teacher_assignment(
            link_id=link["id"],
            subject_scope_id=subject_scope["id"],
            assignment_type="exam",
            source_type="exam_builder",
            title=str(exam_data.get("title") or topic or t("quick_exam_generic_exam_title")),
            subject_key=str(subject_scope.get("subject_key") or subject or ""),
            subject_label_text=str(subject_scope.get("subject_label") or subject_label(subject or "")),
            topic=topic,
            teacher_note=teacher_note,
            due_date=due_date,
            content_snapshot=snapshot,
        )
        if ok:
            st.success(t(key))
        else:
            st.error(t(key))


def render_assignment_panel_for_lesson_plan(
    *,
    prefix: str,
    plan: dict,
    subject: str,
    topic: str,
    lesson_purpose: str,
) -> None:
    st.markdown(f"### {t('assign_to_student')}")
    links = _assignment_target_options()
    link, subject_scope, due_date, teacher_note = _render_assignment_target_fields(prefix, links)
    if not link or not subject_scope:
        return

    topics = extract_assignable_plan_topics(plan, subject=subject, topic=topic, lesson_purpose=lesson_purpose)
    topic_options = {f"{item['sequence_order']}. {item['topic_title']}": item for item in topics}
    selected_labels = st.multiselect(
        t("assigned_topics"),
        options=list(topic_options.keys()),
        default=list(topic_options.keys())[:1],
        key=f"{prefix}_plan_topics",
    )
    if st.button(t("create_assignment"), key=f"{prefix}_assign_btn", use_container_width=True):
        if not selected_labels:
            st.error(t("select_assigned_topics"))
            return
        created = 0
        for label in selected_labels:
            item = topic_options[label]
            snapshot = {
                "topic_title": item["topic_title"],
                "topic_summary": item.get("topic_summary", ""),
                "focus_area": item.get("focus_area", ""),
                "sequence_order": item.get("sequence_order", 1),
                "plan_title": plan.get("title", ""),
            }
            ok, _key = create_teacher_assignment(
                link_id=link["id"],
                subject_scope_id=subject_scope["id"],
                assignment_type="lesson_plan_topic",
                source_type="lesson_plan_builder",
                title=item["topic_title"],
                subject_key=str(subject_scope.get("subject_key") or subject or ""),
                subject_label_text=str(subject_scope.get("subject_label") or subject_label(subject or "")),
                topic=item["topic_title"],
                teacher_note=teacher_note,
                due_date=due_date,
                content_snapshot=snapshot,
            )
            if ok:
                created += 1
        if created:
            st.success(t("assignment_topics_created", count=created))
        else:
            st.error(t("assignment_create_failed"))


def group_assignments_by_teacher_subject(assignments: list[dict]) -> list[tuple[str, list[tuple[str, list[dict]]]]]:
    grouped: dict[str, dict[str, list[dict]]] = {}
    for row in assignments:
        teacher_name = row.get("teacher_name", "—")
        subject_name = row.get("subject_display", "—")
        grouped.setdefault(teacher_name, {}).setdefault(subject_name, []).append(row)
    ordered: list[tuple[str, list[tuple[str, list[dict]]]]] = []
    for teacher_name in sorted(grouped):
        subject_groups = []
        for subject_name in sorted(grouped[teacher_name]):
            subject_groups.append((subject_name, grouped[teacher_name][subject_name]))
        ordered.append((teacher_name, subject_groups))
    return ordered
