import streamlit as st
import datetime
import pandas as pd
import html
import re
from core.i18n import t
from core.timezone import today_local, get_app_tz
from core.navigation import go_to, page_header
from core.database import (
    LESSON_NOTE_DEFAULT_TOKEN,
    get_sb,
    load_table,
    load_students,
    add_class,
    clear_app_caches,
)
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


def _sanitize_lesson_note_for_display(note: str) -> str:
    text = str(note or "").strip()
    if not text:
        return ""
    if text == LESSON_NOTE_DEFAULT_TOKEN:
        return LESSON_NOTE_DEFAULT_TOKEN
    for _ in range(3):
        text = html.unescape(text).strip()
    if text == LESSON_NOTE_DEFAULT_TOKEN:
        return LESSON_NOTE_DEFAULT_TOKEN
    text = re.sub(r"(?i)</?\s*div\b[^>]*>", " ", text)
    text = re.sub(r"(?i)\b/?\s*div\s*>", " ", text)
    text = re.sub(r"(?i)^/?\s*div\s*$", " ", text)
    text = " ".join(text.split()).strip()
    return text


def _lesson_note_display_text(note: str) -> str:
    cleaned = _sanitize_lesson_note_for_display(note)
    if not cleaned or cleaned == LESSON_NOTE_DEFAULT_TOKEN:
        return t("lesson_note_default")
    return cleaned


def _render_add_lesson_form(students: list[str]) -> None:
    st.markdown(f"### {t('record_attendance')}")

    if st.session_state.get("lesson_saved"):
        st.success(t("saved"))
        del st.session_state["lesson_saved"]

    if not students:
        st.info(t("no_students"))
        return

    student = st.selectbox(t("select_student"), students, key="lesson_student")
    number = st.number_input(t("units"), min_value=1, max_value=10, value=1, step=1, key="lesson_number")
    lesson_date = st.date_input(t("date"), key="lesson_date")

    modality_internal = st.selectbox(
        t("modality"),
        ["Online", "Offline"],
        format_func=lambda x: t("online") if x == "Online" else t("offline"),
        key="lesson_modality",
    )

    note = st.text_input(
        t("note_lesson"),
        key="lesson_note",
        placeholder=t("lesson_note_default"),
    )

    pkg_lang = latest_payment_languages_for_student(student)
    _, lang_default = allowed_lesson_language_from_package(pkg_lang)

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
            st.text_input(t("other_subject_label"), key="lesson_subject_other")
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

        st.session_state["lesson_saved"] = True
        st.rerun()


def _render_lesson_editor(student: str) -> None:
    with st.expander(t("lesson_editor"), expanded=False):
        lesson_editor_students = load_students()
        if not lesson_editor_students:
            st.info(t("no_students"))
            return

        student = st.selectbox(
            t("select_student"),
            lesson_editor_students,
            key="lesson_editor_student",
        )

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
                confirm_del = st.checkbox(t("confirm_delete_student"), key="confirm_del_lesson")
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
            return

        classes["student"] = classes.get("student", "").astype(str).str.strip()
        classes = classes[classes["student"] == student].copy()
        if classes.empty:
            st.info(t("no_data"))
            return

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
        classes["note"] = (
            classes["note"]
            .fillna("")
            .astype(str)
            .replace(LESSON_NOTE_DEFAULT_TOKEN, "")
        )

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
                "subject_custom": st.column_config.TextColumn(t("other_subject_label")),
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


def _render_view_lessons() -> None:
    classes = load_table("classes")

    if classes.empty:
        st.info(t("no_data"))
        return

    for col in ["lesson_date", "number_of_lesson", "student", "modality", "subject", "subject_custom", "note"]:
        if col not in classes.columns:
            classes[col] = None

    classes["lesson_date"] = pd.to_datetime(classes["lesson_date"], errors="coerce")
    classes["number_of_lesson"] = pd.to_numeric(classes["number_of_lesson"], errors="coerce").fillna(0).astype(int)
    classes["student"] = classes["student"].fillna("").astype(str).str.strip()
    classes["modality"] = classes["modality"].fillna("Online").astype(str).str.strip()
    classes["subject"] = classes["subject"].fillna("").astype(str).str.strip()
    classes["subject_custom"] = classes["subject_custom"].fillna("").astype(str).str.strip()
    classes["note"] = classes["note"].fillna("").astype(str).str.strip()

    valid = classes.dropna(subset=["lesson_date"]).copy()
    if valid.empty:
        st.info(t("no_data"))
        return

    valid["year"] = valid["lesson_date"].dt.year.astype(int)
    current_year = datetime.date.today().year
    available_years = sorted(valid["year"].unique(), reverse=True)

    selected_year = st.selectbox(
        t("filter_by_year"),
        options=available_years,
        index=0 if current_year not in available_years else available_years.index(current_year),
        key="view_lessons_year",
    )

    year_df = valid[valid["year"] == selected_year].sort_values("lesson_date", ascending=False)
    if year_df.empty:
        st.info(t("no_lessons_year", year=selected_year))
        return

    st.caption(f"**{len(year_df)}** {t('lessons')} · {selected_year}")

    for _, row in year_df.iterrows():
        date_str = row["lesson_date"].strftime("%d %b %Y")
        student_name = row["student"] or "—"
        units = int(row["number_of_lesson"])
        modality = row["modality"]
        subject = row["subject"] or "—"
        subject_custom = row.get("subject_custom", "") or ""
        if subject == "Other" and subject_custom.strip():
            subject = subject_custom.strip()

        modality_label = t("online") if modality == "Online" else t("offline")
        modality_color = "#0ea5e9" if modality == "Online" else "#f59e0b"
        note_text = html.escape(_lesson_note_display_text(row.get("note") or ""))

        st.markdown(
            f"""
            <div style="
                background:linear-gradient(180deg, var(--panel), var(--panel-2));
                border:1px solid var(--border);
                border-left:4px solid #10b981;
                border-radius:12px;
                padding:14px 16px 12px 16px;
                margin-bottom:10px;
                box-shadow:var(--shadow-md);
            ">
                <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:6px;">
                    <div style="font-weight:700;font-size:1rem;color:var(--text);">
                        {student_name}
                    </div>
                    <div style="font-size:1.05rem;font-weight:800;color:#10b981;">
                        {units} {t('units')}
                    </div>
                </div>
                <div style="margin-top:6px;display:flex;flex-wrap:wrap;gap:6px;align-items:center;">
                    <span style="font-size:0.82rem;color:var(--muted);">📅 {date_str}</span>
                    <span style="font-size:0.82rem;color:var(--muted);">·</span>
                    <span style="font-size:0.82rem;padding:2px 8px;border-radius:10px;
                                 background:{modality_color}22;color:{modality_color};font-weight:600;">
                        {modality_label}
                    </span>
                    {f'<span style="font-size:0.82rem;color:var(--muted);">· 📖 {subject}</span>' if subject != "—" else ""}
                    {f'<span style="font-size:0.82rem;color:var(--muted);">· 📝 {note_text}</span>' if note_text else ""}
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )


def render_add_lesson():
    page_header(t("lessons"))
    st.caption(t("keep_track_of_your_lessons"))

    students = load_students()

    # --- Quick lesson planner expander ---
    render_quick_lesson_planner_expander()
    tab_add, tab_view = st.tabs([
        f"➕ {t('record_attendance')}",
        f"📋 {t('tab_view_lessons')}",
    ])

    with tab_add:
        _render_add_lesson_form(students)
        if students:
            _render_lesson_editor("")

    with tab_view:
        _render_view_lessons()

# =========================
