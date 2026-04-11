import streamlit as st
import datetime
from datetime import datetime as _dt, date, time, timedelta
import pandas as pd
from core.i18n import t
from core.timezone import today_local, get_app_tz
from core.navigation import page_header
from core.database import load_students, get_sb, clear_app_caches
from helpers.calendar_helpers import build_calendar_events, render_fullcalendar, _parse_time_value, validate_hhmm
from helpers.schedule import load_schedules, load_overrides, add_schedule, delete_schedule, add_override, delete_override, find_gcal_event_id
from helpers.ui_components import pretty_df, translate_df_headers, render_styled_dataframe
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

def render_calendar():
    page_header(t("calendar"))
    st.caption(t("create_and_manage_your_weekly_program"))
    students = load_students()
    schedules = load_schedules()
    # =======================================
    # SCHEDULE SECTION
    # =======================================
    if not students:
        st.info(t("no_students"))
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
                c1, c2, c3, c4, c5 = st.columns([2, 1, 1, 1, 1])
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
                                    get_sb().table("calendar_overrides").update(
                                        {"gcal_event_id": gcal_eid}
                                    ).eq("student", sch_student).eq(
                                        "original_date", sch_one_time_date.isoformat()
                                    ).order("id", desc=True).limit(1).execute()
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

    start_day = today_d - timedelta(days=365)
    end_day = today_d + timedelta(days=365)

    events = build_calendar_events(start_day, end_day)

    # ---------------------------------------
    # CALENDAR RENDER
    # ---------------------------------------
    if events is None or events.empty:
        st.info(t("no_data"))
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
    # CURRENT SCHEDULE TABLE
    # ---------------------------------------
    with st.expander(t("current_schedule"), expanded=False):

        if schedules.empty:
            st.info(t("no_data"))
        else:
            show = schedules.copy()

            for c in ["id", "student", "weekday", "time", "duration_minutes", "active"]:
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

            show["weekday"] = pd.to_numeric(
                show["weekday"],
                errors="coerce",
            ).fillna(0).astype(int).clip(0, 6)

            show["weekday"] = show["weekday"].apply(
                lambda i: weekday_names[int(i)]
            )

            show = show[
                ["id", "student", "weekday", "time", "duration_minutes", "active"]
            ].sort_values(["student", "weekday", "time"])

            render_styled_dataframe(translate_df_headers(pretty_df(show)))

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
            st.info(t("no_students"))
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
                                    get_sb().table("calendar_overrides").update(
                                        {"gcal_event_id": gcal_eid}
                                    ).eq("student", ov_student).eq(
                                        "original_date", ov_original_date.isoformat()
                                    ).order("id", desc=True).limit(1).execute()
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
            st.caption(t("no_data"))
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

            render_styled_dataframe(translate_df_headers(pretty_df(show)))

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

