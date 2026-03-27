import streamlit as st
import datetime
import pandas as pd
from core.i18n import t
from core.timezone import today_local, get_app_tz
from core.navigation import go_to, page_header
from core.database import get_sb, load_table, load_students, add_class, clear_app_caches
from helpers.language import LANG_EN, LANG_ES, allowed_lesson_language_from_package, translate_language_value
from core.database import delete_row, update_class_row
from helpers.package_lang_lookups import latest_payment_languages_for_student
from helpers.lesson_planner import QUICK_SUBJECTS
from helpers.planner_storage import render_quick_lesson_planner_expander

# 12.3) PAGE: ADD LESSON
# =========================
def translate_subject_value(value: str) -> str:
    v = str(value or "").strip().lower()
    subject_map = {
        "english": t("subject_english"),
        "spanish": t("subject_spanish"),
        "mathematics": t("subject_mathematics"),
        "science": t("subject_science"),
        "music": t("subject_music"),
        "study_skills": t("subject_study_skills"),
        "other": t("other"),
    }
    return subject_map.get(v, str(value or ""))

SUBJECT_DB_MAP = {
    "english": "English",
    "spanish": "Spanish",
    "mathematics": "Mathematics",
    "science": "Science",
    "music": "Music",
    "study_skills": "Study Skills",
    "other": "Other",
}

DB_TO_KEY_MAP = {v: k for k, v in SUBJECT_DB_MAP.items()}

def normalize_subject_key_for_editor(value: str) -> str:
    s = str(value or "").strip()
    if not s:
        return ""
    low = s.lower()
    if low in SUBJECT_DB_MAP:
        return low
    return DB_TO_KEY_MAP.get(s, "")

def _clean_subject_custom(text: str) -> str:
    return " ".join(str(text or "").split()).strip()


def render_add_lesson():
    page_header(t("lessons"))
    st.caption(t("keep_track_of_your_lessons"))

    students = load_students()

    # --- Quick lesson planner expander ---
    render_quick_lesson_planner_expander()

    st.markdown(f"### {t('record_attendance')}")
    if not students:
        st.info(t("no_students"))
    else:
        student = st.selectbox(t("select_student"), students, key="lesson_student")
        number = st.number_input(t("units"), min_value=1, max_value=10, value=1, step=1, key="lesson_number")
        lesson_date = st.date_input(t("date"), key="lesson_date")

        modality_internal = st.selectbox(
            t("modality"),
            ["Online", "Offline"],
            format_func=lambda x: t("online") if x == "Online" else t("offline"),
            key="lesson_modality",
        )
        note = st.text_input(t("notes_optional"), key="lesson_note")

        pkg_lang = latest_payment_languages_for_student(student)
        _, lang_default = allowed_lesson_language_from_package(pkg_lang)

        # Subject selector — QUICK_SUBJECTS
        _subject_options = QUICK_SUBJECTS 
        _subject_default_idx = 0
        if lang_default in QUICK_SUBJECTS:
            _subject_default_idx = QUICK_SUBJECTS.index(lang_default)

        subject_choice = st.selectbox(
            t("subject"),
            QUICK_SUBJECTS,
            index=_subject_default_idx,
            format_func=translate_subject_value,
            key="lesson_subject_select",
        )

        subject_custom = None
        if subject_choice == "other":
            subject_custom = _clean_subject_custom(
                st.text_input(t("subject_other"), key="lesson_subject_other")
            )
            subject_db = "Other"
        else:
            subject_db = SUBJECT_DB_MAP.get(subject_choice)

        if st.button(t("save"), key="btn_save_lesson"):
            if subject_choice == "other" and not subject_custom:
                st.error(t("subject_other_required"))
                st.stop()

            add_class(
                student=student,
                number_of_lesson=int(number),
                lesson_date=lesson_date.isoformat(),
                modality=modality_internal,
                note=note,
                subject=subject_db,
                subject_custom=subject_custom,
            )
            st.success(t("saved"))
            st.rerun()

        with st.expander(t("lesson_editor"), expanded=False):
            st.caption(t("warning_apply"))

            with st.expander(t("delete_lesson"), expanded=False):
                st.caption(t("warning_apply"))
                del_lesson_id = st.number_input(
                    t("lesson_id"),
                    min_value=1,
                    step=1,
                    key="del_lesson_id",
                )
                c1, c2 = st.columns([1, 2])
                with c1:
                    confirm_del = st.checkbox(t("confirm_delete_student"), key="confirm_del_lesson")  # reuse text
                with c2:
                    if st.button(t("delete_lesson"), disabled=not confirm_del, key="btn_delete_lesson"):
                        try:
                            delete_row("classes", int(del_lesson_id))
                            st.success(t("done_ok"))
                            st.rerun()
                        except Exception as e:
                            st.error(f"{t('delete')} failed: {e}")

            st.divider()

            classes = load_table("classes")
            if classes.empty:
                st.info(t("no_data"))
            else:
                classes["student"] = classes.get("student", "").astype(str).str.strip()
                classes = classes[classes["student"] == student].copy()
                if classes.empty:
                    st.info(t("no_data"))
                else:
                    for c in ["id", "lesson_date", "number_of_lesson", "modality", "subject", "subject_custom", "note"]:
                        if c not in classes.columns:
                            classes[c] = None

                    classes["lesson_date"] = pd.to_datetime(classes["lesson_date"], errors="coerce").dt.date
                    classes["number_of_lesson"] = pd.to_numeric(
                        classes["number_of_lesson"], errors="coerce"
                    ).fillna(1).astype(int)
                    classes["modality"] = classes["modality"].fillna("Online").astype(str)
                    classes["subject"] = (
                        classes["subject"]
                        .fillna("")
                        .astype(str)
                        .apply(normalize_subject_key_for_editor)
                    )
                    classes["subject_custom"] = (
                        classes["subject_custom"]
                        .fillna("")
                        .astype(str)
                        .map(_clean_subject_custom)
                    )
                    classes["note"] = classes["note"].fillna("").astype(str)

                    show_cols = [
                        "id",
                        "lesson_date",
                        "number_of_lesson",
                        "modality",
                        "subject",
                        "subject_custom",
                        "note",
                    ]
                    ed = (
                        classes[show_cols]
                        .sort_values(["lesson_date", "id"], ascending=[False, False])
                        .reset_index(drop=True)
                    )

                    edited = st.data_editor(
                        ed,
                        use_container_width=True,
                        hide_index=True,
                        num_rows="fixed",
                        column_config={
                            "id": st.column_config.NumberColumn(t("id"), disabled=True),
                            "lesson_date": st.column_config.DateColumn(t("date")),
                            "number_of_lesson": st.column_config.NumberColumn(
                                t("units"), min_value=1, step=1
                            ),
                            "modality": st.column_config.SelectboxColumn(
                                t("modality"), options=["Online", "Offline"]
                            ),
                            "subject": st.column_config.SelectboxColumn(
                                t("subject"),
                                options=QUICK_SUBJECTS,
                                format_func=translate_subject_value,
                            ),
                            "subject_custom": st.column_config.TextColumn(t("subject_other")),
                            "note": st.column_config.TextColumn(t("note")),
                        },
                    )

                    if st.button(t("apply_changes"), key="apply_class_bulk"):
                        ok_all = True

                        for _, r in edited.iterrows():
                            cid = int(r["id"])

                            subject_key = str(r.get("subject", "") or "").strip().lower()
                            subject_custom = _clean_subject_custom(r.get("subject_custom", ""))

                            subject_db = SUBJECT_DB_MAP.get(subject_key) if subject_key else None

                            if subject_key == "other":
                                if not subject_custom:
                                    st.error(t("subject_other_required"))
                                    ok_all = False
                                    continue
                            else:
                                subject_custom = None

                            updates = {
                                "lesson_date": pd.to_datetime(r["lesson_date"]).date().isoformat()
                                if pd.notna(r["lesson_date"])
                                else None,
                                "number_of_lesson": int(r["number_of_lesson"]),
                                "modality": str(r["modality"]).strip(),
                                "note": str(r.get("note", "") or "").strip(),
                                "subject": subject_db,
                                "subject_custom": subject_custom,
                            }

                            if not update_class_row(cid, updates):
                                ok_all = False

                        if ok_all:
                            clear_app_caches()
                            st.success(t("done_ok"))
                            st.rerun()
                        else:
                            st.error(t("some_updates_failed"))

# =========================
