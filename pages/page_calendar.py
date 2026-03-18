import streamlit as st
import datetime
from datetime import datetime as _dt, date, time, timedelta
import pandas as pd
from core.i18n import t
from core.timezone import today_local, get_app_tz
from core.navigation import page_header
from core.database import load_students, get_sb, clear_app_caches
from helpers.calendar_helpers import build_calendar_events, render_fullcalendar, _parse_time_value, validate_hhmm
from helpers.schedule import load_schedules, load_overrides, add_schedule, delete_schedule, add_override, delete_override
from helpers.ui_components import pretty_df, translate_df_headers

# 12.5) PAGE: CALENDAR
# =========================
def render_calendar():
    page_header(t("calendar"))
    st.caption(t("create_and_manage_your_weekly_program"))
    students = load_students()

    # ---------------------------------------
    # VIEW SELECTOR
    # ---------------------------------------
    view = st.radio(
        t("view"),
        options=["today", "this_week", "this_month"],
        index=1,
        horizontal=True,
        key="calendar_view",
        format_func=lambda k: t(k),
    )

    today_d = today_local()

    if view == "today":
        start_day = today_d
        end_day = today_d
    elif view == "this_week":
        start_day = today_d - timedelta(days=today_d.weekday())
        end_day = start_day + timedelta(days=6)
    else:
        start_day = date(today_d.year, today_d.month, 1)
        next_month = (
            date(today_d.year + 1, 1, 1)
            if today_d.month == 12
            else date(today_d.year, today_d.month + 1, 1)
        )
        end_day = next_month - timedelta(days=1)

    events = build_calendar_events(start_day, end_day)

    # ---------------------------------------
    # CALENDAR RENDER
    # ---------------------------------------
    if events.empty:
        st.info(t("no_data"))
    else:
        students_list = sorted(events["Student"].unique().tolist())

        if "calendar_filter_students" not in st.session_state:
            st.session_state.calendar_filter_students = students_list
        else:
            missing = [
                s for s in students_list
                if s not in st.session_state.calendar_filter_students
            ]
            if missing:
                st.session_state.calendar_filter_students = students_list

        colA, colB = st.columns([3, 1])
        with colA:
            selected_students = st.multiselect(
                t("filter_students"),
                students_list,
                key="calendar_filter_students",
            )
        with colB:
            if st.button(t("reset"), use_container_width=True, key="calendar_reset"):
                st.session_state.calendar_filter_students = students_list
                st.rerun()

        filtered = events[events["Student"].isin(selected_students)].copy()

        render_fullcalendar(
            filtered,
            height=980 if st.session_state.get("compact_mode", False) else 1050,
        )

    # =======================================
    # SCHEDULE SECTION
    # =======================================
    st.subheader(t("schedule"))

    if not students:
        st.info(t("no_students"))
    else:
        schedules = load_schedules()

        # ---------------------------------------
        # ADD SCHEDULE
        # ---------------------------------------
        with st.expander(f"{t('add')} {t('schedule')}", expanded=False):

            c1, c2, c3, c4, c5 = st.columns([2, 1, 1, 1, 1])

            with c1:
                sch_student = st.selectbox(
                    t("select_student"), students, key="cal_sch_student"
                )

            with c2:
                weekday_names = [
                    t("monday"), t("tuesday"), t("wednesday"),
                    t("thursday"), t("friday"), t("saturday"), t("sunday")
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
                    t("active_flag"), value=True, key="cal_sch_active"
                )

            if st.button(t("add"), key="cal_btn_add_schedule"):
                try:
                    add_schedule(
                        sch_student,
                        sch_weekday,
                        sch_time,
                        sch_duration,
                        sch_active,
                    )
                    st.success(t("saved"))
                    st.rerun()
                except ValueError as e:
                    st.error(str(e))
                except Exception as e:
                    st.error(f"{t('save')} failed.\n\n{e}")

        # ---------------------------------------
        # CURRENT SCHEDULE TABLE (TRANSLATED)
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
                    t("monday"), t("tuesday"), t("wednesday"),
                    t("thursday"), t("friday"), t("saturday"), t("sunday")
                ]

                show["weekday"] = pd.to_numeric(
                    show["weekday"], errors="coerce"
                ).fillna(0).astype(int).clip(0, 6)

                show["weekday"] = show["weekday"].apply(
                    lambda i: weekday_names[int(i)]
                )

                show = show[
                    ["id", "student", "weekday", "time", "duration_minutes", "active"]
                ].sort_values(["student", "weekday", "time"])

                st.dataframe(
                    translate_df_headers(pretty_df(show)),
                    use_container_width=True,
                    hide_index=True,
                )

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

    # =======================================
    # MODIFY CALENDAR (OVERRIDES)
    # =======================================
    st.subheader(t("modify_calendar"))

    overrides = load_overrides()
    students_master = load_students()

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
                    format_func=lambda x:
                        t("override_scheduled")
                        if x == "scheduled"
                        else t("override_cancel"),
                    key="ov_status",
                )

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

            new_dt = None
            if ov_status == "scheduled":
                hh, mm = _parse_time_value(ov_new_time)
                new_dt = _dt(
                    ov_new_dt.year,
                    ov_new_dt.month,
                    ov_new_dt.day,
                    hh,
                    mm,
                )

            if st.button(t("change"), key="ov_btn_save"):
                try:
                    if ov_status == "scheduled":
                        clean_time = validate_hhmm(ov_new_time)
                        hh, mm = map(int, clean_time.split(":"))
                        combined_dt = _dt.combine(ov_new_dt, time(hh, mm))
                    else:
                        combined_dt = None

                    add_override(
                        student=ov_student,
                        original_date=ov_original_date,
                        new_dt=combined_dt,
                        duration_minutes=ov_duration,
                        status=ov_status,
                        note=ov_note,
                    )
                    st.success(t("saved"))
                    st.rerun()

                except ValueError as e:
                    st.error(str(e))
                except Exception as e:
                    st.error(f"{t('override_save_failed')}\n\n{e}")

    # ---------------------------------------
    # PREVIOUS CHANGES TABLE (TRANSLATED)
    # ---------------------------------------
    with st.expander(t("previous_changes"), expanded=False):

        if overrides.empty:
            st.caption(t("no_data"))
        else:
            show = overrides.copy()

            for c in ["id", "student", "original_date", "new_datetime",
                      "duration_minutes", "status", "note"]:
                if c not in show.columns:
                    show[c] = None

            show["original_date"] = pd.to_datetime(
                show["original_date"], errors="coerce"
            ).dt.strftime("%Y-%m-%d")

            show["new_datetime"] = pd.to_datetime(
                show["new_datetime"], errors="coerce"
            ).dt.strftime("%Y-%m-%d %H:%M").fillna("—")

            show["duration_minutes"] = pd.to_numeric(
                show["duration_minutes"], errors="coerce"
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
                ["id", "student", "original_date",
                 "new_datetime", "duration_minutes",
                 "status", "note"]
            ].sort_values(["original_date", "student"])

            st.dataframe(
                translate_df_headers(pretty_df(show)),
                use_container_width=True,
                hide_index=True,
            )

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

# =========================
