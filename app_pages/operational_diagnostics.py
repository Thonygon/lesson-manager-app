from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import pandas as pd
import streamlit as st

from core.i18n import t
from services.authorization_service import (
    CAPABILITY_MANAGE_OPERATIONAL_DIAGNOSTICS,
    CAPABILITY_VIEW_DEVELOPER_WORKSPACE,
    CAPABILITY_VIEW_OPERATIONAL_DIAGNOSTICS,
    has_capability,
    require_capability,
)
from services.operational_diagnostics_service import (
    VALID_SEVERITIES,
    VALID_STATUSES,
    capture_exception,
    clear_diagnostics_cache,
    list_diagnostics,
    short_event_reference,
    update_diagnostic_status,
)


_SEVERITY_ORDER = {"critical": 0, "error": 1, "warning": 2}
_STATUS_ORDER = {"open": 0, "acknowledged": 1, "resolved": 2, "ignored": 3}


def _text(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def _format_timestamp(value: Any) -> str:
    raw = _text(value)
    if not raw:
        return "-"
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        return parsed.strftime("%Y-%m-%d %H:%M UTC")
    except (TypeError, ValueError):
        return raw[:32]


def _localized_option(prefix: str, value: str) -> str:
    key = f"{prefix}_{value}"
    translated = t(key)
    return translated if translated != key else value.replace("_", " ").title()


def _filtered_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    columns = st.columns(4, gap="small")
    with columns[0]:
        severity = st.selectbox(
            t("operational_diagnostics_filter_severity"),
            ["all", "critical", "error", "warning"],
            format_func=lambda value: _localized_option("operational_diagnostics_severity", value),
            key="operational_diagnostics_severity_filter",
        )
    with columns[1]:
        status = st.selectbox(
            t("operational_diagnostics_filter_status"),
            ["all", "open", "acknowledged", "resolved", "ignored"],
            format_func=lambda value: _localized_option("operational_diagnostics_status", value),
            key="operational_diagnostics_status_filter",
        )
    faces = sorted({_text(row.get("user_face")) for row in rows if _text(row.get("user_face"))})
    with columns[2]:
        face = st.selectbox(
            t("operational_diagnostics_filter_face"),
            ["all", *faces],
            format_func=lambda value: _localized_option("operational_diagnostics_face", value),
            key="operational_diagnostics_face_filter",
        )
    with columns[3]:
        search = _text(
            st.text_input(
                t("operational_diagnostics_filter_search"),
                placeholder=t("operational_diagnostics_filter_search_placeholder"),
                key="operational_diagnostics_search",
            )
        ).lower()

    pages = sorted({_text(row.get("page_key")) for row in rows if _text(row.get("page_key"))})
    releases = sorted({_text(row.get("release_version")) for row in rows if _text(row.get("release_version"))}, reverse=True)
    scope_columns = st.columns(3, gap="small")
    with scope_columns[0]:
        page = st.selectbox(
            t("operational_diagnostics_filter_page"),
            ["all", *pages],
            format_func=lambda value: t("operational_diagnostics_filter_all_pages") if value == "all" else value,
            key="operational_diagnostics_page_filter",
        )
    with scope_columns[1]:
        release = st.selectbox(
            t("operational_diagnostics_filter_release"),
            ["all", *releases],
            format_func=lambda value: t("operational_diagnostics_filter_all_releases") if value == "all" else value,
            key="operational_diagnostics_release_filter",
        )
    with scope_columns[2]:
        window = st.selectbox(
            t("operational_diagnostics_filter_window"),
            ["24h", "7d", "30d", "90d", "all"],
            format_func=lambda value: _localized_option("operational_diagnostics_window", value),
            key="operational_diagnostics_window_filter",
        )

    cutoff = None
    window_delta = {
        "24h": timedelta(hours=24),
        "7d": timedelta(days=7),
        "30d": timedelta(days=30),
        "90d": timedelta(days=90),
    }.get(window)
    if window_delta:
        cutoff = datetime.now(timezone.utc) - window_delta

    filtered = []
    for row in rows:
        if severity in VALID_SEVERITIES and row.get("severity") != severity:
            continue
        if status in VALID_STATUSES and row.get("status") != status:
            continue
        if face != "all" and row.get("user_face") != face:
            continue
        if page != "all" and row.get("page_key") != page:
            continue
        if release != "all" and row.get("release_version") != release:
            continue
        if cutoff:
            try:
                last_seen = datetime.fromisoformat(_text(row.get("last_seen_at")).replace("Z", "+00:00"))
            except (TypeError, ValueError):
                continue
            if last_seen.tzinfo is None:
                last_seen = last_seen.replace(tzinfo=timezone.utc)
            if last_seen < cutoff:
                continue
        haystack = " ".join(
            _text(row.get(key))
            for key in ("event_id", "component", "operation", "page_key", "exception_type", "safe_message", "release_version")
        ).lower()
        if search and search not in haystack:
            continue
        filtered.append(row)
    filtered.sort(
        key=lambda row: (
            _STATUS_ORDER.get(_text(row.get("status")), 9),
            _SEVERITY_ORDER.get(_text(row.get("severity")), 9),
            -int(row.get("occurrence_count") or 0),
        )
    )
    return filtered


def _render_summary(rows: list[dict[str, Any]]) -> None:
    active = [row for row in rows if row.get("status") in {"open", "acknowledged"}]
    values = [
        (t("operational_diagnostics_metric_open"), len(active)),
        (t("operational_diagnostics_metric_critical"), sum(row.get("severity") == "critical" for row in active)),
        (t("operational_diagnostics_metric_errors"), sum(row.get("severity") == "error" for row in active)),
        (t("operational_diagnostics_metric_occurrences"), sum(int(row.get("occurrence_count") or 0) for row in rows)),
    ]
    for column, (label, value) in zip(st.columns(4, gap="small"), values):
        with column:
            st.metric(label, value)


def _render_table(rows: list[dict[str, Any]]) -> None:
    display_rows = [
        {
            t("operational_diagnostics_column_reference"): short_event_reference(_text(row.get("event_id"))),
            t("operational_diagnostics_column_severity"): _localized_option("operational_diagnostics_severity", _text(row.get("severity"))),
            t("operational_diagnostics_column_status"): _localized_option("operational_diagnostics_status", _text(row.get("status"))),
            t("operational_diagnostics_column_surface"): _localized_option("operational_diagnostics_face", _text(row.get("user_face"))),
            t("operational_diagnostics_column_location"): _text(row.get("page_key")) or _text(row.get("component")),
            t("operational_diagnostics_column_issue"): _text(row.get("exception_type")) or _text(row.get("safe_message"))[:80],
            t("operational_diagnostics_column_count"): int(row.get("occurrence_count") or 0),
            t("operational_diagnostics_column_last_seen"): _format_timestamp(row.get("last_seen_at")),
        }
        for row in rows
    ]
    st.dataframe(pd.DataFrame(display_rows), use_container_width=True, hide_index=True)


def _render_detail(row: dict[str, Any]) -> None:
    event_id = _text(row.get("event_id"))
    st.markdown(f"### {short_event_reference(event_id)}")
    details = [
        (t("operational_diagnostics_detail_first_seen"), _format_timestamp(row.get("first_seen_at"))),
        (t("operational_diagnostics_detail_last_seen"), _format_timestamp(row.get("last_seen_at"))),
        (t("operational_diagnostics_detail_release"), _text(row.get("release_version")) or "unknown"),
        (t("operational_diagnostics_detail_occurrences"), str(int(row.get("occurrence_count") or 0))),
    ]
    for column, (label, value) in zip(st.columns(4, gap="small"), details):
        with column:
            st.caption(label)
            st.code(value, language=None)

    st.caption(t("operational_diagnostics_detail_operation"))
    st.code(f"{_text(row.get('component'))} :: {_text(row.get('operation'))}", language=None)
    st.caption(t("operational_diagnostics_detail_message"))
    st.code(_text(row.get("safe_message")) or "-", language=None)
    with st.expander(t("operational_diagnostics_detail_stack"), expanded=False):
        st.code(str(row.get("safe_stack") or "-"), language="text")
    with st.expander(t("operational_diagnostics_detail_context"), expanded=False):
        st.json(row.get("context_json") or {})

    if not has_capability(CAPABILITY_MANAGE_OPERATIONAL_DIAGNOSTICS):
        st.caption(t("operational_diagnostics_read_only"))
        return

    note = st.text_area(
        t("operational_diagnostics_resolution_note"),
        value=_text(row.get("resolution_note")),
        key=f"operational_diagnostics_note_{event_id}",
    )
    actions = [
        ("acknowledged", t("operational_diagnostics_action_acknowledge")),
        ("resolved", t("operational_diagnostics_action_resolve")),
        ("open", t("operational_diagnostics_action_reopen")),
        ("ignored", t("operational_diagnostics_action_ignore")),
    ]
    for column, (status, label) in zip(st.columns(4, gap="small"), actions):
        with column:
            if st.button(label, key=f"operational_diagnostics_{status}_{event_id}", use_container_width=True):
                try:
                    ok, message = update_diagnostic_status(event_id, status=status, resolution_note=note)
                except Exception as exc:
                    reference = capture_exception(
                        exc,
                        component="app_pages.operational_diagnostics",
                        operation="update_status",
                        page_key="operational_diagnostics",
                        user_face="developer",
                    )
                    st.error(t("operational_diagnostics_update_failed", reference=short_event_reference(reference)))
                    return
                if ok:
                    st.success(t(message) if t(message) != message else t("operational_diagnostics_update_success"))
                    st.rerun()
                else:
                    st.error(t(message) if t(message) != message else message)


def render_operational_diagnostics() -> None:
    require_capability(CAPABILITY_VIEW_DEVELOPER_WORKSPACE, message=t("developer_workspace_access_required"))
    require_capability(CAPABILITY_VIEW_OPERATIONAL_DIAGNOSTICS, message=t("operational_diagnostics_access_required"))

    title_column, refresh_column = st.columns([5, 1], gap="medium")
    with title_column:
        st.title(t("operational_diagnostics_title"))
        st.caption(t("operational_diagnostics_subtitle"))
    with refresh_column:
        if st.button(t("operational_diagnostics_refresh"), use_container_width=True, key="operational_diagnostics_refresh"):
            clear_diagnostics_cache()
            st.rerun()

    try:
        rows = list_diagnostics(limit=500)
    except Exception as exc:
        reference = capture_exception(
            exc,
            component="app_pages.operational_diagnostics",
            operation="load_diagnostics",
            page_key="operational_diagnostics",
            user_face="developer",
        )
        st.error(t("operational_diagnostics_load_failed"))
        st.caption(t("operational_diagnostics_user_reference", reference=short_event_reference(reference)))
        st.info(t("operational_diagnostics_migration_hint"))
        return

    _render_summary(rows)
    if not rows:
        st.success(t("operational_diagnostics_empty"))
        return

    filtered = _filtered_rows(rows)
    if not filtered:
        st.info(t("operational_diagnostics_no_matches"))
        return
    page_size = 50
    total_pages = max(1, (len(filtered) + page_size - 1) // page_size)
    selected_page = st.number_input(
        t("operational_diagnostics_page_number"),
        min_value=1,
        max_value=total_pages,
        value=min(int(st.session_state.get("operational_diagnostics_page") or 1), total_pages),
        step=1,
        key="operational_diagnostics_page",
    )
    start = (int(selected_page) - 1) * page_size
    visible_rows = filtered[start : start + page_size]
    st.caption(t("operational_diagnostics_page_summary", page=int(selected_page), total=total_pages, count=len(filtered)))
    _render_table(visible_rows)

    labels = {
        f"{short_event_reference(_text(row.get('event_id')))} · {_text(row.get('exception_type')) or _text(row.get('operation'))}": row
        for row in visible_rows
    }
    selected = st.selectbox(t("operational_diagnostics_select_issue"), list(labels), key="operational_diagnostics_selected_issue")
    _render_detail(labels[selected])
