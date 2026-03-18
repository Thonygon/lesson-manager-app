import streamlit as st
import datetime
import pandas as pd
from core.i18n import t
from core.state import get_current_user_id
from core.timezone import now_local, today_local
from core.navigation import go_to, page_header
from core.database import load_table, load_students, get_sb
from core.database import ensure_student, clear_app_caches, norm_student, update_student_profile
from helpers.student_meta import load_students_df
from helpers.history import show_student_history
from helpers.ui_components import translate_df_headers
from helpers.whatsapp import _digits_only, normalize_phone_for_whatsapp

# 12.2) PAGE: STUDENTS
# =========================
def render_students():
    page_header(t("students"))
    st.caption(t("add_and_manage_students"))

    students = load_students()
    students_df = load_students_df()

    st.markdown(f"### {t('add_new')}")
    new_student = st.text_input(t("new_student_name"), key="new_student_name")

    if st.button(f"{t('add')} {t('student')}", key="add_student"):
        if not new_student.strip():
            st.error(t("no_data"))
        else:
            ensure_student(new_student)
            st.success(t("done_ok"))
            st.rerun()

    st.markdown(f"### {t('manage_students')}")
    if students_df.empty:
        st.info(t("no_students"))
    else:
        with st.expander(t("student_profile"), expanded=False):
            student_list = sorted(students_df["student"].unique().tolist())
            selected_student = st.selectbox(t("select_student"), student_list, key="edit_student_select")

            student_row = students_df.loc[students_df["student"] == selected_student].iloc[0]
            sid = norm_student(selected_student)  # stable per student

            col1, col2 = st.columns(2)
            with col1:
                email = st.text_input(t("email"), value=student_row.get("email", ""), key=f"student_email_{sid}")
                zoom_link = st.text_input(t("zoom_link"), value=student_row.get("zoom_link", ""), key=f"student_zoom_{sid}")
                phone = st.text_input(t("whatsapp_phone"), value=student_row.get("phone", ""), key=f"student_phone_{sid}")
                st.caption(t("examples_phone"))
            with col2:
                color = st.color_picker(t("calendar_color"), value=student_row.get("color", "#3B82F6"), key=f"student_color_{sid}")
                notes = st.text_area(t("notes"), value=student_row.get("notes", ""), key=f"student_notes_{sid}")

            if phone and not normalize_phone_for_whatsapp(phone) and len(_digits_only(phone)) < 11:
                st.warning(t("examples_phone"))

            if st.button(t("save"), key=f"btn_save_student_profile_{sid}"):
                update_student_profile(selected_student, email, zoom_link, notes, color, phone)
                st.success(t("done_ok"))
                st.rerun()

    with st.expander(t("student_list"), expanded=False):
        s_col1, s_col2 = st.columns([2, 1])
        with s_col1:
            q = st.text_input(t("search"), value="", placeholder="Type a name…", key="students_list_search")
        with s_col2:
            st.caption(f"Total: **{len(students)}**")

        shown = students
        if q.strip():
            shown = [s for s in students if q.strip().lower() in s.lower()]

        list_df = pd.DataFrame({"Student": shown})
        st.dataframe(list_df, use_container_width=True, hide_index=True)

    with st.expander(t("student_history"), expanded=False):
        if not students:
            st.info(t("no_students"))
        else:
            hist_student = st.selectbox(t("select_student"), students, key="students_history_student")
            lessons_df, payments_df = show_student_history(hist_student)

            colA, colB = st.columns(2)
            with colA:
                st.markdown(f"### {t('lessons')}")
                st.dataframe(translate_df_headers(lessons_df), use_container_width=True, hide_index=True)
            with colB:
                st.markdown(f"### {t('payments')}")
                st.dataframe(translate_df_headers(payments_df), use_container_width=True, hide_index=True)

    with st.expander(t("delete_student"), expanded=False):
        st.caption(t("delete_student_warning"))
        if not students:
            st.info(t("no_students"))
        else:
            del_student = st.selectbox(t("select_student"), students, key="delete_student_select")
            confirm = st.checkbox(t("confirm_delete_student"), key="delete_student_confirm")
            if st.button(t("delete"), type="primary", disabled=not confirm, key="btn_delete_student"):
                try:
                    get_sb().table("students").delete().eq("student", del_student).execute()
                    clear_app_caches()
                    st.success(t("done_ok"))
                    st.rerun()
                except Exception as e:
                    st.error(f"{t('delete')} failed.\n\n{e}")

# =========================
