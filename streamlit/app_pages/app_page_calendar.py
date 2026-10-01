import streamlit as st
import datetime
from datetime import datetime as _dt, date, time, timedelta
import pandas as pd
from core.i18n import t
from core.state import get_current_user_id
from core.timezone import today_local, get_app_tz, get_app_tz_name
from core.navigation import go_to, page_header
from core.database import load_students, get_sb, clear_app_caches
from helpers.calendar_helpers import build_calendar_events, render_fullcalendar, _parse_time_value, validate_hhmm
from helpers.schedule import (
    active_schedule_freezes,
    add_schedule,
    add_schedule_freeze,
    add_override,
    delete_override,
    delete_schedule,
    find_gcal_event_id,
    load_overrides,
    load_schedule_freezes,
    load_schedules,
    resume_schedule_freeze,
    update_schedule_freeze,
    update_schedule_from_date,
)
from helpers.ui_components import pretty_df, translate_df_headers, render_styled_dataframe
from helpers.empty_states import render_empty_state
from helpers.google_calendar import (
    gcal_configured,
    get_google_auth_url,
    save_gcal_tokens,
    load_gcal_tokens,
    clear_gcal_tokens,
    is_gcal_connected,
    create_gcal_event,
    delete_gcal_event,
)

# 12.5) PAGE: CALENDAR
# =========================


def _format_schedule_option(schedules_df: pd.DataFrame, schedule_id: int) -> str:
    if schedules_df is None or schedules_df.empty:
        return str(schedule_id)
    match = schedules_df[pd.to_numeric(schedules_df["id"], errors="coerce") == int(schedule_id)]
    if match.empty:
        return str(schedule_id)
    row = match.iloc[0]
    weekday_names = [
        t("monday"),
        t("tuesday"),
        t("wednesday"),
        t("thursday"),
        t("friday"),
        t("saturday"),
        t("sunday"),
    ]
    weekday_idx = int(pd.to_numeric(row.get("weekday"), errors="coerce") or 0)
    start_text = row.get("start_date")
    if pd.notna(start_text) and start_text:
        return f"#{int(schedule_id)} · {row.get('student', '')} · {weekday_names[max(0, min(6, weekday_idx))]} · {row.get('time', '')} · {start_text.isoformat()}"
    return f"#{int(schedule_id)} · {row.get('student', '')} · {weekday_names[max(0, min(6, weekday_idx))]} · {row.get('time', '')}"


def _format_pause_option(pauses_df: pd.DataFrame, pause_id: int) -> str:
    if pauses_df is None or pauses_df.empty:
        return str(pause_id)
    match = pauses_df[pd.to_numeric(pauses_df["id"], errors="coerce") == int(pause_id)]
    if match.empty:
        return str(pause_id)
    row = match.iloc[0]
    start_text = row.get("start_date")
    end_text = row.get("end_date")
    start_label = start_text.isoformat() if pd.notna(start_text) and start_text else t("today")
    end_label = end_text.isoformat() if pd.notna(end_text) and end_text else t("schedule_pause_until_resumed")
    return f"#{int(pause_id)} · {row.get('student', '')} · {start_label} → {end_label}"


def _safe_date_value(value, fallback: date) -> date:
    if value is None or pd.isna(value):
        return fallback
    if isinstance(value, pd.Timestamp):
        return value.date()
    if isinstance(value, datetime.datetime):
        return value.date()
    return value

def _render_calendar_new_user_setup():
    render_empty_state(
        title_key="calendar_empty_title",
        body_key="calendar_empty_body",
        steps=[
            "calendar_empty_need_student",
            "calendar_empty_need_schedule",
            "calendar_empty_need_optional_gcal",
        ],
        eyebrow_key="calendar_empty_label",
        icon="📅",
    )

    st.markdown(f"#### {t('calendar_empty_start_here')}")
    setup_cols = st.columns(3)
    with setup_cols[0]:
        if st.button(t("calendar_empty_add_student"), key="calendar_empty_add_student", use_container_width=True, type="primary"):
            go_to("students")
            st.rerun()
    with setup_cols[1]:
        if st.button(t("calendar_empty_add_lesson"), key="calendar_empty_add_lesson", use_container_width=True):
            go_to("add_lesson")
            st.rerun()
    with setup_cols[2]:
        st.button(t("calendar_empty_schedule_locked"), key="calendar_empty_schedule_locked", use_container_width=True, disabled=True)

    with st.expander(f"{t('add')} {t('schedule')}", expanded=True):
        st.info(t("calendar_empty_add_schedule_hint"))


def _paginate_calendar_table(df: pd.DataFrame, state_key: str, *, page_size: int = 12) -> tuple[pd.DataFrame, int, int, int, int, int]:
    total_rows = len(df)
    total_pages = max(1, (total_rows + page_size - 1) // page_size) if total_rows else 1
    current_page = int(st.session_state.get(state_key, 1) or 1)
    current_page = max(1, min(current_page, total_pages))
    st.session_state[state_key] = current_page
    start_idx = (current_page - 1) * page_size
    end_idx = min(start_idx + page_size, total_rows)
    page_df = df.iloc[start_idx:end_idx].copy() if total_rows else df
    return page_df, current_page, total_pages, start_idx, end_idx, total_rows


def _render_calendar_pagination(df: pd.DataFrame, state_key: str, *, page_size: int = 12) -> pd.DataFrame:
    page_df, current_page, total_pages, start_idx, end_idx, total_rows = _paginate_calendar_table(
        df,
        state_key,
        page_size=page_size,
    )
    if total_rows > page_size:
        prev_col, info_col, next_col = st.columns([1, 3, 1])
        with prev_col:
            if st.button("←", key=f"{state_key}_prev", use_container_width=True, disabled=current_page <= 1):
                st.session_state[state_key] = max(1, current_page - 1)
                st.rerun()
        with info_col:
            st.caption(f"{start_idx + 1}-{end_idx} / {total_rows} · {current_page}/{total_pages}")
        with next_col:
            if st.button("→", key=f"{state_key}_next", use_container_width=True, disabled=current_page >= total_pages):
                st.session_state[state_key] = min(total_pages, current_page + 1)
                st.rerun()
    return page_df

def render_calendar():
    page_header(t("calendar"))
    st.caption(t("create_and_manage_your_weekly_program"))
    students = load_students()
    schedules = load_schedules()
    supports_effective_dates = bool((getattr(schedules, "attrs", {}) or {}).get("supports_effective_dates", False))
    # =======================================
    # SCHEDULE SECTION
    # =======================================
    if not students:
        _render_calendar_new_user_setup()
    else:
        schedules = load_schedules()

        # ---------------------------------------
        # ADD SCHEDULE
        # ---------------------------------------
        with st.expander(f"{t('add')} {t('schedule')}", expanded=False):

            sch_mode = st.radio(
                t("schedule_type"),
                options=["weekly", "one_time"],
                format_func=lambda x: (
                    t("schedule_weekly") if x == "weekly" else t("schedule_one_time")
                ),
                key="cal_sch_mode",
                horizontal=True,
            )

            if sch_mode == "weekly":
                c1, c2, c3, c4, c5, c6 = st.columns([2, 1, 1, 1, 1, 1.2])
            else:
                c1, c2, c3, c4 = st.columns([2, 1, 1, 1])

            with c1:
                sch_student = st.selectbox(
                    t("select_student"),
                    students,
                    key="cal_sch_student",
                )

            if sch_mode == "weekly":
                with c2:
                    weekday_names = [
                        t("monday"),
                        t("tuesday"),
                        t("wednesday"),
                        t("thursday"),
                        t("friday"),
                        t("saturday"),
                        t("sunday"),
                    ]
                    sch_weekday = st.selectbox(
                        t("weekday"),
                        list(range(7)),
                        format_func=lambda x: weekday_names[int(x)],
                        key="cal_sch_weekday",
                    )

                with c3:
                    sch_time_obj = st.time_input(
                        t("time_hhmm"),
                        value=time(10, 0),
                        step=300,
                        key="cal_sch_time",
                    )
                    sch_time = sch_time_obj.strftime("%H:%M")

                with c4:
                    sch_duration = st.number_input(
                        t("duration_minutes"),
                        min_value=15,
                        max_value=360,
                        value=60,
                        step=15,
                        key="cal_sch_duration",
                    )

                with c5:
                    sch_active = st.checkbox(
                        t("active_flag"),
                        value=True,
                        key="cal_sch_active",
                    )
                with c6:
                    sch_start_date = st.date_input(
                        t("schedule_start_date"),
                        value=today_local(),
                        min_value=today_local(),
                        key="cal_sch_start_date",
                        disabled=not supports_effective_dates,
                    )
                    if not supports_effective_dates:
                        st.caption(t("schedule_effective_dates_unavailable"))
                if supports_effective_dates:
                    end_toggle_col, end_date_col = st.columns([1, 1.6])
                    with end_toggle_col:
                        sch_use_end_date = st.checkbox(
                            t("schedule_use_end_date"),
                            value=False,
                            key="cal_sch_use_end_date",
                        )
                    with end_date_col:
                        sch_end_date = st.date_input(
                            t("schedule_end_date"),
                            value=today_local() + datetime.timedelta(days=30),
                            min_value=sch_start_date,
                            key="cal_sch_end_date",
                        ) if sch_use_end_date else None
                else:
                    sch_use_end_date = False
                    sch_end_date = None
            else:
                with c2:
                    sch_one_time_date = st.date_input(
                        t("date"),
                        value=today_local(),
                        key="cal_sch_one_time_date",
                    )

                with c3:
                    sch_time_obj = st.time_input(
                        t("time_hhmm"),
                        value=time(10, 0),
                        step=300,
                        key="cal_sch_time_one",
                    )
                    sch_time = sch_time_obj.strftime("%H:%M")

                with c4:
                    sch_duration = st.number_input(
                        t("duration_minutes"),
                        min_value=15,
                        max_value=360,
                        value=60,
                        step=15,
                        key="cal_sch_duration_one",
                    )

            if st.button(t("add"), key="cal_btn_add_schedule"):
                try:
                    if sch_mode == "weekly":
                        add_schedule(
                            sch_student,
                            sch_weekday,
                            sch_time,
                            sch_duration,
                            sch_active,
                            start_date=sch_start_date,
                            end_date=sch_end_date if sch_use_end_date else None,
                        )
                    else:
                        hh, mm = map(int, sch_time.split(":"))
                        combined_dt = _dt.combine(sch_one_time_date, time(hh, mm))
                        add_override(
                            student=sch_student,
                            original_date=sch_one_time_date,
                            new_dt=combined_dt,
                            duration_minutes=sch_duration,
                            status="scheduled",
                            note=t("schedule_one_time"),
                        )
                        # Sync one-time lesson to Google Calendar
                        if st.session_state.get("gcal_auto_sync") and is_gcal_connected():
                            gcal_eid = create_gcal_event(sch_student, combined_dt, sch_duration)
                            if gcal_eid:
                                # Update the override with the gcal event ID
                                try:
                                    update_query = (
                                        get_sb().table("calendar_overrides").update(
                                            {"gcal_event_id": gcal_eid}
                                        ).eq("student", sch_student).eq(
                                            "original_date", sch_one_time_date.isoformat()
                                        )
                                    )
                                    current_user_id = str(get_current_user_id() or "").strip()
                                    if current_user_id:
                                        update_query = update_query.eq("user_id", current_user_id)
                                    update_query.order("id", desc=True).limit(1).execute()
                                except Exception:
                                    pass

                    st.success(t("saved"))
                    st.rerun()
                except ValueError as e:
                    st.error(str(e))
                except Exception as e:
                    st.error(f"{t('save')} failed.\n\n{e}")

    # ---------------------------------------
    # CALENDAR DATA WINDOW
    # ---------------------------------------
    today_d = today_local()

    # Keep the calendar responsive on reruns by generating only the recent and
    # upcoming window that users actively browse most often.
    start_day = today_d - timedelta(days=90)
    end_day = today_d + timedelta(days=180)

    events = build_calendar_events(start_day, end_day, get_app_tz_name())

    # ---------------------------------------
    # CALENDAR RENDER
    # ---------------------------------------
    if events is None or events.empty:
        if students:
            render_empty_state(
                title_key="calendar_empty_events_title",
                body_key="calendar_empty_events_body",
                steps=[
                    "calendar_empty_events_step_schedule",
                    "calendar_empty_events_step_one_time",
                    "calendar_empty_events_step_sync",
                ],
                icon="📅",
            )
    else:
        students_list = sorted(events["Student"].dropna().unique().tolist())

        if "calendar_filter_students" not in st.session_state:
            st.session_state["calendar_filter_students"] = students_list.copy()
        else:
            st.session_state["calendar_filter_students"] = [
                s for s in st.session_state["calendar_filter_students"]
                if s in students_list
            ]

        selected_students = st.multiselect(
            t("filter_students"),
            options=students_list,
            key="calendar_filter_students",
        )

        if selected_students:
            filtered = events[events["Student"].isin(selected_students)].copy()
        else:
            filtered = events.copy()

        render_fullcalendar(
            filtered,
            height=980 if st.session_state.get("compact_mode", False) else 1050,
        )

    # =======================================
    # GOOGLE CALENDAR INTEGRATION
    # =======================================
    if gcal_configured():
        st.subheader(t("gcal_title"))

        # --- Show result of OAuth callback ---
        if st.session_state.pop("_gcal_just_connected", False):
            st.success(t("gcal_connected"))
        if st.session_state.pop("_gcal_connect_failed", False):
            st.error(t("gcal_connect_failed"))

        if is_gcal_connected():
            st.success(t("gcal_status_connected"))
            st.caption(t("gcal_sync_hint"))

            gcal_sync = st.toggle(
                t("gcal_auto_sync"),
                value=st.session_state.get("gcal_auto_sync", True),
                key="gcal_auto_sync",
            )

            if st.button(t("gcal_disconnect"), key="gcal_btn_disconnect"):
                clear_gcal_tokens()
                st.success(t("gcal_disconnected"))
                st.rerun()
        else:
            st.info(t("gcal_not_connected"))
            auth_url = get_google_auth_url()
            st.link_button(t("gcal_connect"), auth_url)

    # =======================================
    # MODIFY CALENDAR (OVERRIDES)
    # =======================================
    st.subheader(t("modify_calendar"))

    overrides = load_overrides()
    students_master = load_students()

    # ---------------------------------------
    # PAUSE STUDENT SCHEDULE
    # ---------------------------------------
    with st.expander(t("pause_student_schedule"), expanded=False):
        if not students_master:
            st.info(t("calendar_empty_add_schedule_hint"))
        else:
            st.caption(t("pause_student_schedule_caption"))
            p1, p2, p3 = st.columns([1.2, 1, 1], gap="medium")
            with p1:
                pause_student = st.selectbox(t("select_student"), students_master, key="schedule_pause_student")
                pause_reason = st.selectbox(
                    t("schedule_pause_reason"),
                    ["vacation", "break", "illness", "payment_pause", "other"],
                    format_func=lambda value: t(f"schedule_pause_reason_{value}"),
                    key="schedule_pause_reason",
                )
            with p2:
                use_start = st.checkbox(t("schedule_pause_use_start"), value=True, key="schedule_pause_use_start")
                pause_start = st.date_input(t("schedule_pause_start_date"), value=today_d, key="schedule_pause_start_date") if use_start else None
            with p3:
                use_end = st.checkbox(t("schedule_pause_use_end"), value=False, key="schedule_pause_use_end")
                pause_end = st.date_input(t("schedule_pause_end_date"), value=today_d + datetime.timedelta(days=14), key="schedule_pause_end_date") if use_end else None

            pause_note = st.text_input(t("schedule_pause_note"), key="schedule_pause_note")
            if st.button(t("schedule_pause_save"), key="schedule_pause_save", use_container_width=True):
                try:
                    add_schedule_freeze(
                        student=pause_student,
                        start_date=pause_start,
                        end_date=pause_end,
                        reason=pause_reason,
                        note=pause_note,
                    )
                    st.success(t("schedule_pause_saved"))
                    st.rerun()
                except Exception as exc:
                    st.error(str(exc))

            all_pauses = load_schedule_freezes()
            active_pauses = all_pauses[all_pauses["active"] == True].copy() if not all_pauses.empty else all_pauses
            st.markdown(f"#### {t('schedule_paused_students')}")
            if active_pauses.empty:
                st.caption(t("schedule_no_active_pauses"))
            else:
                show_pauses = active_pauses.copy()
                show_pauses["reason"] = show_pauses["reason"].apply(lambda value: t(f"schedule_pause_reason_{str(value or 'other')}"))
                show_pauses["start_date"] = show_pauses["start_date"].apply(lambda value: value.isoformat() if pd.notna(value) else t("today"))
                show_pauses["end_date"] = show_pauses["end_date"].apply(lambda value: value.isoformat() if pd.notna(value) else t("schedule_pause_until_resumed"))
                render_styled_dataframe(
                    translate_df_headers(
                        pretty_df(show_pauses[["id", "student", "start_date", "end_date", "reason", "note"]])
                    )
                )
                st.markdown(f"#### {t('edit_pause_schedule')}")
                st.caption(t("edit_pause_schedule_caption"))
                pause_options = show_pauses["id"].tolist()
                selected_pause_id = st.selectbox(
                    t("schedule_pause_resume_id"),
                    options=pause_options,
                    format_func=lambda value: _format_pause_option(active_pauses, value),
                    key="schedule_pause_edit_id",
                )
                selected_pause = active_pauses[pd.to_numeric(active_pauses["id"], errors="coerce") == int(selected_pause_id)].iloc[0]
                default_student = str(selected_pause.get("student") or "").strip()
                default_reason = str(selected_pause.get("reason") or "other").strip()
                current_start = selected_pause.get("start_date")
                current_end = selected_pause.get("end_date")
                ep1, ep2, ep3 = st.columns([1.2, 1, 1], gap="medium")
                with ep1:
                    pause_edit_student = st.selectbox(
                        t("select_student"),
                        students_master,
                        index=max(0, students_master.index(default_student)) if default_student in students_master else 0,
                        key=f"schedule_pause_edit_student_{selected_pause_id}",
                    )
                    pause_edit_reason = st.selectbox(
                        t("schedule_pause_reason"),
                        ["vacation", "break", "illness", "payment_pause", "other"],
                        index=max(0, ["vacation", "break", "illness", "payment_pause", "other"].index(default_reason)) if default_reason in ["vacation", "break", "illness", "payment_pause", "other"] else 4,
                        format_func=lambda value: t(f"schedule_pause_reason_{value}"),
                        key=f"schedule_pause_edit_reason_{selected_pause_id}",
                    )
                with ep2:
                    pause_edit_use_start = st.checkbox(
                        t("schedule_pause_use_start"),
                        value=pd.notna(current_start),
                        key=f"schedule_pause_edit_use_start_{selected_pause_id}",
                    )
                    pause_edit_start = st.date_input(
                        t("schedule_pause_start_date"),
                        value=_safe_date_value(current_start, today_d),
                        key=f"schedule_pause_edit_start_{selected_pause_id}",
                    ) if pause_edit_use_start else None
                with ep3:
                    pause_edit_use_end = st.checkbox(
                        t("schedule_pause_use_end"),
                        value=pd.notna(current_end),
                        key=f"schedule_pause_edit_use_end_{selected_pause_id}",
                    )
                    pause_edit_end = st.date_input(
                        t("schedule_pause_end_date"),
                        value=_safe_date_value(current_end, today_d + datetime.timedelta(days=14)),
                        key=f"schedule_pause_edit_end_{selected_pause_id}",
                    ) if pause_edit_use_end else None
                pause_edit_note = st.text_input(
                    t("schedule_pause_note"),
                    value=str(selected_pause.get("note") or ""),
                    key=f"schedule_pause_edit_note_{selected_pause_id}",
                )
                if st.button(t("schedule_save_changes"), key=f"schedule_pause_edit_save_{selected_pause_id}", use_container_width=True):
                    try:
                        update_schedule_freeze(
                            int(selected_pause_id),
                            student=pause_edit_student,
                            start_date=pause_edit_start,
                            end_date=pause_edit_end,
                            reason=pause_edit_reason,
                            note=pause_edit_note,
                            active=True,
                        )
                        st.success(t("schedule_pause_updated"))
                        st.rerun()
                    except Exception as exc:
                        st.error(str(exc))
                resume_id = st.number_input(t("schedule_pause_resume_id"), min_value=1, step=1, key="schedule_pause_resume_id")
                if st.button(t("schedule_pause_resume"), key="schedule_pause_resume", use_container_width=True):
                    resume_schedule_freeze(int(resume_id))
                    st.success(t("schedule_pause_resumed"))
                    st.rerun()

    # ---------------------------------------
    # CURRENT SCHEDULE TABLE
    # ---------------------------------------
    with st.expander(t("current_schedule"), expanded=False):

        if schedules.empty:
            render_empty_state(
                title_key="calendar_empty_schedule_title",
                body_key="calendar_empty_schedule_body",
                steps=[
                    "calendar_empty_events_step_schedule",
                    "calendar_empty_events_step_one_time",
                    "calendar_empty_events_step_sync",
                ],
                icon="📋",
            )
        else:
            show = schedules.copy()

            for c in ["id", "student", "weekday", "time", "duration_minutes", "active", "start_date", "end_date"]:
                if c not in show.columns:
                     show[c] = None

            weekday_names = [
                t("monday"),
                t("tuesday"),
                t("wednesday"),
                t("thursday"),
                t("friday"),
                t("saturday"),
                t("sunday"),
            ]

            show["start_date"] = pd.to_datetime(show["start_date"], errors="coerce")
            show["end_date"] = pd.to_datetime(show["end_date"], errors="coerce")
            show["weekday"] = pd.to_numeric(
                show["weekday"],
                errors="coerce",
            ).fillna(0).astype(int).clip(0, 6)

            current_schedule_cutoff = pd.Timestamp(today_local())
            show = show[
                show["end_date"].isna() | (show["end_date"] >= current_schedule_cutoff)
            ].copy()
            show["weekday"] = show["weekday"].apply(
                lambda i: weekday_names[int(i)]
            )
            show["start_date"] = show["start_date"].apply(
                lambda value: value.date().isoformat() if pd.notna(value) else ""
            )
            show["end_date"] = show["end_date"].apply(
                lambda value: value.date().isoformat() if pd.notna(value) else t("ongoing")
            )

            show = show[
                ["id", "student", "weekday", "time", "duration_minutes", "start_date", "end_date", "active"]
            ].sort_values(["student", "weekday", "time"])
            show = show.rename(
                columns={
                    "start_date": t("schedule_start_date"),
                    "end_date": t("schedule_end_date"),
                }
            )

            show_page = _render_calendar_pagination(show, "calendar_current_schedule_page")
            render_styled_dataframe(translate_df_headers(pretty_df(show_page)))

            st.markdown(f"#### {t('edit_schedule')}")
            if supports_effective_dates:
                st.caption(t("edit_schedule_caption"))
            else:
                st.caption(t("schedule_effective_dates_unavailable"))

            editable_schedules = schedules.copy()
            for c in ["id", "student", "weekday", "time", "duration_minutes", "active", "start_date", "end_date"]:
                if c not in editable_schedules.columns:
                    editable_schedules[c] = None
            editable_schedules["start_date"] = pd.to_datetime(editable_schedules["start_date"], errors="coerce")
            editable_schedules["end_date"] = pd.to_datetime(editable_schedules["end_date"], errors="coerce")
            editable_schedules = editable_schedules[
                editable_schedules["end_date"].isna() | (editable_schedules["end_date"] >= current_schedule_cutoff)
            ].copy()

            if not supports_effective_dates:
                st.info(t("schedule_edit_requires_migration"))
            elif not editable_schedules.empty:
                edit_options = editable_schedules.sort_values(["student", "weekday", "time", "id"])["id"].tolist()
                selected_schedule_id = st.selectbox(
                    t("schedule_id"),
                    options=edit_options,
                    format_func=lambda value: _format_schedule_option(editable_schedules, value),
                    key="cal_edit_schedule_id",
                )
                selected_row = editable_schedules[pd.to_numeric(editable_schedules["id"], errors="coerce") == int(selected_schedule_id)].iloc[0]
                weekday_idx = int(pd.to_numeric(selected_row.get("weekday"), errors="coerce") or 0)
                time_parts = _parse_time_value(selected_row.get("time"))
                duration_value = int(pd.to_numeric(selected_row.get("duration_minutes"), errors="coerce") or 60)
                effective_default = today_local()
                current_end_date = _safe_date_value(selected_row.get("end_date"), today_local() + datetime.timedelta(days=30)) if pd.notna(selected_row.get("end_date")) else None
                e1, e2, e3 = st.columns(3)
                with e1:
                    edit_student = st.selectbox(
                        t("select_student"),
                        students,
                        index=max(0, students.index(str(selected_row.get("student") or "").strip())) if str(selected_row.get("student") or "").strip() in students else 0,
                        key=f"cal_edit_student_{selected_schedule_id}",
                    )
                    edit_weekday = st.selectbox(
                        t("weekday"),
                        list(range(7)),
                        index=max(0, min(6, weekday_idx)),
                        format_func=lambda x: weekday_names[int(x)],
                        key=f"cal_edit_weekday_{selected_schedule_id}",
                    )
                with e2:
                    edit_time_obj = st.time_input(
                        t("time_hhmm"),
                        value=time(time_parts[0], time_parts[1]),
                        step=300,
                        key=f"cal_edit_time_{selected_schedule_id}",
                    )
                    edit_duration = st.number_input(
                        t("duration_minutes"),
                        min_value=15,
                        max_value=360,
                        value=duration_value,
                        step=15,
                        key=f"cal_edit_duration_{selected_schedule_id}",
                    )
                with e3:
                    edit_active = st.checkbox(
                        t("active_flag"),
                        value=bool(selected_row.get("active")),
                        key=f"cal_edit_active_{selected_schedule_id}",
                    )
                    edit_effective_date = st.date_input(
                        t("schedule_edit_effective_date"),
                        value=effective_default,
                        min_value=today_local(),
                        key=f"cal_edit_effective_date_{selected_schedule_id}",
                    )
                    edit_use_end_date = st.checkbox(
                        t("schedule_use_end_date"),
                        value=current_end_date is not None,
                        key=f"cal_edit_use_end_date_{selected_schedule_id}",
                    )
                    edit_end_date = st.date_input(
                        t("schedule_end_date"),
                        value=current_end_date or (effective_default + datetime.timedelta(days=30)),
                        min_value=edit_effective_date,
                        key=f"cal_edit_end_date_{selected_schedule_id}",
                    ) if edit_use_end_date else None

                if st.button(t("schedule_save_changes"), key=f"cal_btn_edit_schedule_{selected_schedule_id}", use_container_width=True):
                    try:
                        update_schedule_from_date(
                            int(selected_schedule_id),
                            student=edit_student,
                            weekday=int(edit_weekday),
                            time_str=edit_time_obj.strftime("%H:%M"),
                            duration_minutes=int(edit_duration),
                            active=bool(edit_active),
                            effective_start_date=edit_effective_date,
                            end_date=edit_end_date if edit_use_end_date else None,
                        )
                        st.success(t("schedule_updated"))
                        st.rerun()
                    except ValueError as exc:
                        st.error(str(exc))
                    except Exception as exc:
                        st.error(f"{t('save')} failed.\n\n{exc}")

            st.markdown(f"#### {t('delete_scheduled_lesson')}")
            st.caption(t("delete_schedule_warning"))

            del_id = st.number_input(
                t("schedule_id"),
                min_value=1,
                step=1,
                key="cal_del_schedule_id",
            )

            confirm_del_s = st.checkbox(
                t("delete_warning_undo"),
                key="confirm_del_schedule",
            )

            if st.button(
                t("delete"),
                disabled=not confirm_del_s,
                key="cal_btn_delete_schedule",
            ):
                delete_schedule(del_id)
                st.success(t("deleted"))
                st.rerun()

    # ---------------------------------------
    # CANCEL OR RESCHEDULE
    # ---------------------------------------
    with st.expander(t("cancel_or_reschedule"), expanded=False):

        if not students_master:
            st.info(t("calendar_empty_add_schedule_hint"))
        else:
            c1, c2 = st.columns(2)

            with c1:
                ov_student = st.selectbox(
                    t("override_student"),
                    students_master,
                    key="ov_student",
                )

                ov_original_date = st.date_input(
                    t("override_original_date"),
                    value=today_d,
                    key="ov_original_date",
                )

                ov_status = st.selectbox(
                    t("override_status"),
                    options=["scheduled", "cancelled"],
                    format_func=lambda x: (
                        t("override_scheduled")
                        if x == "scheduled"
                        else t("override_cancel")
                    ),
                    key="ov_status",
                )

            if ov_status == "scheduled":
                with c2:
                    ov_new_dt = st.date_input(
                        t("override_new_date"),
                        value=today_d,
                        key="ov_new_date",
                    )

                    ov_new_time_obj = st.time_input(
                        t("override_new_time_hhmm"),
                        value=time(10, 0),
                        step=300,
                        key="ov_new_time",
                    )
                    ov_new_time = ov_new_time_obj.strftime("%H:%M")

                    ov_duration = st.number_input(
                        t("override_duration"),
                        min_value=15,
                        max_value=360,
                        value=60,
                        step=15,
                        key="ov_duration",
                    )

            ov_note = st.text_input(
                t("override_note"),
                value="",
                key="ov_note",
            )

            if st.button(t("change"), key="ov_btn_save"):
                try:
                    if ov_status == "scheduled":
                        clean_time = validate_hhmm(ov_new_time)
                        hh, mm = map(int, clean_time.split(":"))
                        combined_dt = _dt.combine(ov_new_dt, time(hh, mm))
                        duration = ov_duration
                    else:
                        combined_dt = None
                        duration = 60

                    add_override(
                        student=ov_student,
                        original_date=ov_original_date,
                        new_dt=combined_dt,
                        duration_minutes=duration,
                        status=ov_status,
                        note=ov_note,
                    )

                    # Google Calendar sync
                    if st.session_state.get("gcal_auto_sync") and is_gcal_connected():
                        # Delete the old event for this student+date
                        old_gcal_eid = find_gcal_event_id(ov_student, ov_original_date)
                        if old_gcal_eid:
                            delete_gcal_event(old_gcal_eid)

                        if ov_status == "scheduled" and combined_dt:
                            # Create new event for rescheduled lesson
                            gcal_eid = create_gcal_event(ov_student, combined_dt, duration, ov_note)
                            if gcal_eid:
                                try:
                                    update_query = (
                                        get_sb().table("calendar_overrides").update(
                                            {"gcal_event_id": gcal_eid}
                                        ).eq("student", ov_student).eq(
                                            "original_date", ov_original_date.isoformat()
                                        )
                                    )
                                    current_user_id = str(get_current_user_id() or "").strip()
                                    if current_user_id:
                                        update_query = update_query.eq("user_id", current_user_id)
                                    update_query.order("id", desc=True).limit(1).execute()
                                except Exception:
                                    pass

                    st.success(t("saved"))
                    st.rerun()

                except ValueError as e:
                    st.error(str(e))
                except Exception as e:
                    st.error(f"{t('override_save_failed')}\n\n{e}")

    # ---------------------------------------
    # PREVIOUS CHANGES TABLE
    # ---------------------------------------
    with st.expander(t("previous_changes"), expanded=False):

        if overrides.empty:
            st.caption(t("calendar_no_changes_yet"))
        else:
            show = overrides.copy()

            for c in [
                "id",
                "student",
                "original_date",
                "new_datetime",
                "duration_minutes",
                "status",
                "note",
            ]:
                if c not in show.columns:
                    show[c] = None

            show["original_date"] = pd.to_datetime(
                show["original_date"],
                errors="coerce",
            ).dt.strftime("%Y-%m-%d")

            show["new_datetime"] = pd.to_datetime(
                show["new_datetime"],
                errors="coerce",
            ).dt.strftime("%Y-%m-%d %H:%M").fillna("—")

            show["duration_minutes"] = pd.to_numeric(
                show["duration_minutes"],
                errors="coerce",
            ).fillna(60).astype(int)

            def _translate_override_status(x):
                s = str(x or "").strip().lower()
                if s == "scheduled":
                    return t("override_scheduled")
                if s == "cancelled":
                    return t("override_cancel")
                return str(x)

            show["status"] = show["status"].apply(_translate_override_status)

            show = show[
                [
                    "id",
                    "student",
                    "original_date",
                    "new_datetime",
                    "duration_minutes",
                    "status",
                    "note",
                ]
            ].sort_values(["original_date", "student"])

            show_page = _render_calendar_pagination(show, "calendar_previous_changes_page")
            render_styled_dataframe(translate_df_headers(pretty_df(show_page)))

            del_id = st.number_input(
                t("override_id"),
                min_value=1,
                step=1,
                key="ov_del_id",
            )

            confirm_del_o = st.checkbox(
                t("delete_warning_undo"),
                key="confirm_del_override",
            )

            if st.button(
                t("delete"),
                disabled=not confirm_del_o,
                key="ov_del_btn",
            ):
                delete_override(del_id)
                st.success(t("deleted"))
                st.rerun()
