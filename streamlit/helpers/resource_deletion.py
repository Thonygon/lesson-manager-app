from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import streamlit as st

from core.database import clear_app_caches, get_sb
from core.i18n import t
from core.state import get_current_user_id
from helpers.archive_utils import ARCHIVED_STATUS, DELETED_STATUS, is_archived_status


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_record_id(record_id: Any) -> Any:
    raw = str(record_id or "").strip()
    if not raw:
        return None
    return int(raw) if raw.isdigit() else raw


def _rows(result) -> list[dict]:
    return getattr(result, "data", None) or []


def _truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in {"1", "true", "yes", "on", "public"}


def _assignment_rows(*, assignment_type: str, source_type: str, source_record_id: Any) -> list[dict]:
    teacher_id = str(get_current_user_id() or "").strip()
    safe_id = _safe_record_id(source_record_id)
    if not teacher_id or safe_id is None or not assignment_type or not source_type:
        return []
    try:
        return _rows(
            get_sb()
            .table("teacher_assignments")
            .select("id,student_id,status")
            .eq("teacher_id", teacher_id)
            .eq("assignment_type", assignment_type)
            .eq("source_type", source_type)
            .eq("source_record_id", safe_id)
            .execute()
        )
    except Exception:
        return []


def assignment_summary(*, assignment_type: str, source_type: str, source_record_id: Any) -> dict[str, int]:
    rows = _assignment_rows(
        assignment_type=assignment_type,
        source_type=source_type,
        source_record_id=source_record_id,
    )
    student_ids = {str(row.get("student_id") or "").strip() for row in rows if str(row.get("student_id") or "").strip()}
    active_rows = [row for row in rows if str(row.get("status") or "").strip().lower() != "archived"]
    return {
        "assignment_count": len(rows),
        "student_count": len(student_ids),
        "active_assignment_count": len(active_rows),
    }


def _detach_assignment_sources(*, assignment_type: str, source_type: str, source_record_id: Any) -> None:
    teacher_id = str(get_current_user_id() or "").strip()
    safe_id = _safe_record_id(source_record_id)
    if not teacher_id or safe_id is None or not assignment_type or not source_type:
        return
    base_query = (
        get_sb()
        .table("teacher_assignments")
        .update(
            {
                "source_record_id": None,
                "source_archived": True,
                "source_archived_at": _now_iso(),
                "updated_at": _now_iso(),
            }
        )
        .eq("teacher_id", teacher_id)
        .eq("assignment_type", assignment_type)
        .eq("source_type", source_type)
        .eq("source_record_id", safe_id)
    )
    try:
        base_query.execute()
    except Exception:
        try:
            (
                get_sb()
                .table("teacher_assignments")
                .update({"source_record_id": None, "updated_at": _now_iso()})
                .eq("teacher_id", teacher_id)
                .eq("assignment_type", assignment_type)
                .eq("source_type", source_type)
                .eq("source_record_id", safe_id)
                .execute()
            )
        except Exception:
            pass


def _update_resource_status(table_name: str, record_id: Any, status: str) -> tuple[bool, str]:
    teacher_id = str(get_current_user_id() or "").strip()
    safe_id = _safe_record_id(record_id)
    if not teacher_id:
        return False, "auth_required"
    if safe_id is None:
        return False, "invalid_id"
    payload = {"status": status, "updated_at": _now_iso()}
    try:
        (
            get_sb()
            .table(table_name)
            .update(payload)
            .eq("id", safe_id)
            .eq("user_id", teacher_id)
            .execute()
        )
    except Exception:
        try:
            (
                get_sb()
                .table(table_name)
                .update({"status": status})
                .eq("id", safe_id)
                .eq("user_id", teacher_id)
                .execute()
            )
        except Exception as exc:
            return False, str(exc)
    clear_app_caches()
    return True, "ok"


def _hard_delete_resource(table_name: str, record_id: Any) -> tuple[bool, str]:
    teacher_id = str(get_current_user_id() or "").strip()
    safe_id = _safe_record_id(record_id)
    if not teacher_id:
        return False, "auth_required"
    if safe_id is None:
        return False, "invalid_id"
    try:
        get_sb().table(table_name).delete().eq("id", safe_id).eq("user_id", teacher_id).execute()
        clear_app_caches()
        return True, "ok"
    except Exception as exc:
        return False, str(exc)


def delete_archived_resource(
    *,
    table_name: str,
    row: dict,
    assignment_type: str = "",
    source_type: str = "",
) -> tuple[bool, str, dict[str, int]]:
    teacher_id = str(get_current_user_id() or "").strip()
    record_id = row.get("id") if isinstance(row, dict) else None
    if not teacher_id:
        return False, "auth_required", {}
    if not isinstance(row, dict) or _safe_record_id(record_id) is None:
        return False, "invalid_id", {}
    if str(row.get("user_id") or "").strip() != teacher_id:
        return False, "not_owner", {}
    if not is_archived_status(row.get("status")):
        return False, "resource_delete_requires_archive", {}
    if "is_public" in row and _truthy(row.get("is_public")):
        return False, "resource_delete_requires_private", {}

    summary = assignment_summary(
        assignment_type=assignment_type,
        source_type=source_type,
        source_record_id=record_id,
    )
    if summary.get("assignment_count", 0) > 0:
        _detach_assignment_sources(
            assignment_type=assignment_type,
            source_type=source_type,
            source_record_id=record_id,
        )
        ok, msg = _update_resource_status(table_name, record_id, DELETED_STATUS)
        return ok, msg, summary

    ok, msg = _hard_delete_resource(table_name, record_id)
    return ok, msg, summary


def _delete_state_keys(key_prefix: str, record_id: Any) -> tuple[str, str, str, str]:
    safe_key = f"{key_prefix}_{record_id}"
    return (
        safe_key,
        f"{safe_key}_delete_pending",
        f"{safe_key}_delete_confirm",
        f"{safe_key}_delete_summary",
    )


def _can_render_delete(row: dict) -> bool:
    teacher_id = str(get_current_user_id() or "").strip()
    if not teacher_id or not isinstance(row, dict):
        return False
    return str(row.get("user_id") or "").strip() == teacher_id and is_archived_status(row.get("status"))


def render_archive_delete_button(
    *,
    row: dict,
    key_prefix: str,
    assignment_type: str = "",
    source_type: str = "",
) -> None:
    record_id = row.get("id")
    if not _can_render_delete(row):
        return
    if "is_public" in row and _truthy(row.get("is_public")):
        st.caption(t("resource_delete_make_private_first"))
        return

    safe_key, pending_key, _confirm_key, summary_key = _delete_state_keys(key_prefix, record_id)

    if st.button(t("delete"), key=f"{safe_key}_delete_btn", use_container_width=True):
        st.session_state[summary_key] = assignment_summary(
            assignment_type=assignment_type,
            source_type=source_type,
            source_record_id=record_id,
        )
        st.session_state[pending_key] = True


def render_archive_delete_confirmation(
    *,
    table_name: str,
    row: dict,
    key_prefix: str,
    assignment_type: str = "",
    source_type: str = "",
    on_deleted=None,
) -> None:
    record_id = row.get("id") if isinstance(row, dict) else None
    if not _can_render_delete(row):
        return
    safe_key, pending_key, confirm_key, summary_key = _delete_state_keys(key_prefix, record_id)
    if not st.session_state.get(pending_key):
        return

    summary = st.session_state.get(summary_key)
    if not isinstance(summary, dict):
        summary = assignment_summary(
            assignment_type=assignment_type,
            source_type=source_type,
            source_record_id=record_id,
        )
        st.session_state[summary_key] = summary
    assigned_count = int(summary.get("student_count") or summary.get("assignment_count") or 0)

    if assigned_count > 0:
        warning_text = t("resource_delete_assigned_warning", count=assigned_count)
        checkbox_label = t("resource_delete_assigned_confirm")
    else:
        warning_text = t("resource_delete_unassigned_warning")
        checkbox_label = t("resource_delete_unassigned_confirm")

    with st.container(border=True):
        st.markdown(f"**{t('delete')}**")
        st.caption(warning_text)
        confirmed = st.checkbox(checkbox_label, key=confirm_key)
        action_cols = st.columns([1, 1, 3], gap="small")
        with action_cols[0]:
            if st.button(t("cancel"), key=f"{safe_key}_delete_cancel", use_container_width=True):
                st.session_state.pop(pending_key, None)
                st.session_state.pop(confirm_key, None)
                st.session_state.pop(summary_key, None)
                st.rerun()
        with action_cols[1]:
            if st.button(t("delete"), key=f"{safe_key}_delete_confirm_btn", use_container_width=True, disabled=not confirmed):
                ok, msg, result_summary = delete_archived_resource(
                    table_name=table_name,
                    row=row,
                    assignment_type=assignment_type,
                    source_type=source_type,
                )
                if ok:
                    st.session_state.pop(pending_key, None)
                    st.session_state.pop(confirm_key, None)
                    st.session_state.pop(summary_key, None)
                    if callable(on_deleted):
                        on_deleted()
                    if int(result_summary.get("assignment_count") or 0) > 0:
                        st.success(t("resource_delete_library_only_success"))
                    else:
                        st.success(t("resource_delete_success"))
                    st.rerun()
                else:
                    st.error(t("resource_delete_failed", error=msg))


def render_archive_delete_control(
    *,
    table_name: str,
    row: dict,
    key_prefix: str,
    assignment_type: str = "",
    source_type: str = "",
    on_deleted=None,
) -> None:
    render_archive_delete_button(
        row=row,
        key_prefix=key_prefix,
        assignment_type=assignment_type,
        source_type=source_type,
    )
    render_archive_delete_confirmation(
        table_name=table_name,
        row=row,
        key_prefix=key_prefix,
        assignment_type=assignment_type,
        source_type=source_type,
        on_deleted=on_deleted,
    )
