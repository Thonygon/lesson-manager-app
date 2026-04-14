import streamlit as st
import datetime
import math
from datetime import datetime as _dt, timezone
import pandas as pd
from core.i18n import t
from core.navigation import go_to, page_header
from core.database import get_sb, load_table, load_students, add_payment, clear_app_caches, recalculate_package_dates
from helpers.language import LANG_EN, LANG_ES, LANG_BOTH, ALLOWED_LANGS, DEFAULT_PACKAGE_LANGS, pack_languages, allowed_lesson_language_from_package, translate_language_value
from core.database import delete_row, update_payment_row, update_class_row
from helpers.pricing import render_pricing_editor
from helpers.package_lang_lookups import latest_payment_languages_for_student
from helpers.currency import CURRENCIES, CURRENCY_CODES, get_preferred_currency, currency_symbol, guess_currency_from_timezone
from helpers.lesson_planner import QUICK_SUBJECTS

# 12.4) PAGE: ADD PAYMENT
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

def render_add_payment():
    page_header(t("payment"))
    st.caption(t("add_and_manage_your_payments"))

    tab_add, tab_view = st.tabs([
        f"➕ {t('tab_add_payment')}",
        f"📋 {t('tab_view_payments')}",
    ])

    with tab_add:
        _render_add_payment_form()

    with tab_view:
        _render_view_payments()

def _render_add_payment_form():
    """Add payment form + payment editor (original logic)."""
    render_pricing_editor()

    students = load_students()
    if not students:
        st.info(t("no_students"))
    else:
        student_p = st.selectbox(t("select_student"), students, key="pay_student")

        lessons_paid = st.number_input(
            t("lessons_paid"),
            min_value=1,
            max_value=500,
            value=44,
            step=1,
            key="pay_lessons_paid",
        )
        payment_date = st.date_input(t("payment_date"), key="pay_date")

        # ── Currency selector (top of form, before price) ──────────
        # Priority: profile preference → browser timezone guess → TRY
        _profile_cur = get_preferred_currency()          # reads session_state["preferred_currency"]
        _tz_cur = guess_currency_from_timezone()
        _pay_cur_default = _profile_cur if _profile_cur != "TRY" else (_tz_cur or _profile_cur)
        _pay_cur_idx = CURRENCY_CODES.index(_pay_cur_default) if _pay_cur_default in CURRENCY_CODES else 0

        pay_currency = st.selectbox(
            t("payment_currency"),
            CURRENCY_CODES,
            index=_pay_cur_idx,
            format_func=lambda c: f"{CURRENCIES[c]['symbol']}  {c} — {CURRENCIES[c]['name']}",
            key="pay_currency",
        )

        sym = currency_symbol(pay_currency)

        paid_amount = st.number_input(
            f"{t('paid_amount')} ({sym})",
            min_value=0.0,
            value=0.0,
            step=100.0,
            key="pay_amount",
        )

        # IMPORTANT: store canonical DB values ("Online"/"Offline"), display translated labels
        modality_p = st.selectbox(
            t("modality"),
            options=["Online", "Offline"],
            format_func=lambda x: t("online") if x == "Online" else t("offline"),
            key="pay_modality",
        )

        # Subject selector
        _subject_options = list(QUICK_SUBJECTS)
        _subject_default_idx = 0 if _subject_options else None

        subject_choice = st.selectbox(
            t("subject"),
            _subject_options,
            index=_subject_default_idx,
            format_func=translate_subject_value,
            key="pay_subject_select",
        )

        pay_subject_custom = None
        pay_subject_db = SUBJECT_DB_MAP.get(subject_choice)

        if subject_choice == "other":
            pay_subject_custom = _clean_subject_custom(
                st.text_input(t("other_subject_label"), key="pay_subject_other")
            )
            pay_subject_db = "Other"

        use_custom_start = st.checkbox(
            t("starts_different"),
            value=False,
            key="pay_custom_start",
        )
        if use_custom_start:
            pkg_start = st.date_input(t("package_start"), value=payment_date, key="pay_pkg_start")
        else:
            pkg_start = payment_date

        # If you later add expiry UI, set pkg_expiry to a date
        pkg_expiry = None

        if st.button(t("save"), key="btn_save_payment"):
            if subject_choice == "other" and not pay_subject_custom:
                st.error(t("subject_other_required"))
                st.stop()

            add_payment(
                student=student_p,
                number_of_lesson=int(lessons_paid),
                payment_date=payment_date.isoformat(),
                paid_amount=float(paid_amount),
                modality=str(modality_p),
                subject=pay_subject_db,
                subject_custom=pay_subject_custom,
                package_start_date=pkg_start.isoformat() if pkg_start else payment_date.isoformat(),
                package_expiry_date=pkg_expiry.isoformat() if pkg_expiry else None,
                lesson_adjustment_units=0,
                package_normalized=False,
                normalized_note="",
                currency=pay_currency,
            )

        # ----------------------------
        # PAYMENT EDITOR (BULK + DELETE BY ID INSIDE)
        # ----------------------------
        with st.expander(t("payment_editor"), expanded=False):
            st.caption(t("warning_apply"))

            with st.expander(t("repair_package_dates"), expanded=False):
                st.caption(t("repair_package_dates_help"))
                c_fix_student, c_fix_all = st.columns(2)
                with c_fix_student:
                    if st.button(t("repair_package_dates_student"), key="repair_pkg_dates_student"):
                        summary = recalculate_package_dates(student_p)
                        st.success(
                            t("repair_package_dates_done").format(
                                updated=int(summary.get("updated", 0)),
                                mismatches=int(summary.get("mismatches", 0)),
                            )
                        )
                        st.rerun()
                with c_fix_all:
                    if st.button(t("repair_package_dates_all"), key="repair_pkg_dates_all"):
                        summary = recalculate_package_dates()
                        st.success(
                            t("repair_package_dates_done").format(
                                updated=int(summary.get("updated", 0)),
                                mismatches=int(summary.get("mismatches", 0)),
                            )
                        )
                        st.rerun()

            # Delete by ID (inside editor)
            with st.expander(t("delete_payment"), expanded=False):
                st.caption(t("delete_payment_help"))

                del_payment_id = st.number_input(
                    t("payment_id"),
                    min_value=1,
                    step=1,
                    key="del_payment_id",
                )
                c1, c2 = st.columns([1, 2])
                with c1:
                    confirm_del_p = st.checkbox(t("delete_warning_undo"), key="confirm_del_payment")
                with c2:
                    if st.button(t("delete_payment"), disabled=not confirm_del_p, key="btn_delete_payment"):
                        try:
                            delete_row("payments", int(del_payment_id))
                            st.success(t("payment_deleted"))
                            st.rerun()
                        except Exception as e:
                            st.error(f"{t('delete_failed')}: {e}")

            st.divider()

            payments = load_table("payments")
            if payments.empty:
                st.info(t("no_data"))
            else:
                payments["student"] = payments.get("student", "").astype(str).str.strip()
                payments = payments[payments["student"] == student_p].copy()

                if payments.empty:
                    st.info(t("no_data"))
                else:
                    for c in [
                        "id",
                        "payment_date",
                        "number_of_lesson",
                        "paid_amount",
                        "modality",
                        "subject",
                        "subject_custom",
                        "package_start_date",
                        "package_expiry_date",
                        "lesson_adjustment_units",
                        "package_normalized",
                        "normalized_note",
                    ]:
                        if c not in payments.columns:
                            payments[c] = None

                    payments["payment_date"] = pd.to_datetime(payments["payment_date"], errors="coerce").dt.date
                    payments["package_start_date"] = pd.to_datetime(payments["package_start_date"], errors="coerce").dt.date
                    payments["package_expiry_date"] = pd.to_datetime(payments["package_expiry_date"], errors="coerce").dt.date
                    payments["number_of_lesson"] = pd.to_numeric(
                        payments["number_of_lesson"], errors="coerce"
                    ).fillna(0).astype(int)
                    payments["paid_amount"] = pd.to_numeric(
                        payments["paid_amount"], errors="coerce"
                    ).fillna(0.0)
                    payments["lesson_adjustment_units"] = pd.to_numeric(
                        payments["lesson_adjustment_units"], errors="coerce"
                    ).fillna(0).astype(int)
                    payments["package_normalized"] = payments["package_normalized"].fillna(False).astype(bool)
                    payments["subject"] = (
                        payments["subject"]
                        .fillna("")
                        .astype(str)
                        .apply(normalize_subject_key_for_editor)
                    )
                    payments["subject_custom"] = (
                        payments["subject_custom"]
                        .fillna("")
                        .astype(str)
                        .map(_clean_subject_custom)
                    )
                    payments["modality"] = payments["modality"].fillna("Online").astype(str).str.strip()
                    payments["normalized_note"] = payments["normalized_note"].fillna("").astype(str)

                    show_cols = [
                        "id",
                        "payment_date",
                        "number_of_lesson",
                        "paid_amount",
                        "modality",
                        "subject",
                        "subject_custom",
                        "package_start_date",
                        "package_expiry_date",
                        "lesson_adjustment_units",
                        "package_normalized",
                        "normalized_note",
                    ]
                    ed = (
                        payments[show_cols]
                        .sort_values(["payment_date", "id"], ascending=[False, False])
                        .reset_index(drop=True)
                    )

                    edited = st.data_editor(
                        ed,
                        use_container_width=True,
                        hide_index=True,
                        num_rows="fixed",
                        column_config={
                            "id": st.column_config.NumberColumn(t("id"), disabled=True),
                            "payment_date": st.column_config.DateColumn(t("payment_date")),
                            "number_of_lesson": st.column_config.NumberColumn(t("lessons_paid"), min_value=1, step=1),
                            "paid_amount": st.column_config.NumberColumn(t("paid_amount"), min_value=0.0, step=100.0),
                            # Canonical values in DB, translated labels in UI
                            "modality": st.column_config.SelectboxColumn(
                                t("modality"),
                                options=["Online", "Offline"],
                                format_func=lambda x: t("online") if x == "Online" else t("offline"),
                            ),

                            "subject": st.column_config.SelectboxColumn(
                                t("subject"),
                                options=QUICK_SUBJECTS,
                                format_func=translate_subject_value,
                            ),

                            "subject_custom": st.column_config.TextColumn(t("other_subject_label")),
                            "package_start_date": st.column_config.DateColumn(t("package_start")),
                            "package_expiry_date": st.column_config.DateColumn(t("package_expiry")),
                            "lesson_adjustment_units": st.column_config.NumberColumn(t("adjust_units"), step=1),
                            "package_normalized": st.column_config.CheckboxColumn(t("package_normalized")),
                            "normalized_note": st.column_config.TextColumn(t("normalized_note")),
                        },
                    )

                    if st.button(t("apply_changes"), key="apply_payment_bulk"):
                        ok_all = True

                        for _, r in edited.iterrows():
                            pid = int(r["id"])

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

                            modality_val = str(r.get("modality") or "Online").strip()
                            if modality_val not in ("Online", "Offline"):
                                modality_val = "Online"

                            updates = {
                                "payment_date": pd.to_datetime(r["payment_date"]).date().isoformat()
                                if pd.notna(r["payment_date"])
                                else None,
                                "number_of_lesson": int(r["number_of_lesson"]),
                                "paid_amount": float(r["paid_amount"]),
                                "modality": modality_val,
                                "subject": subject_db,
                                "subject_custom": subject_custom,
                                "package_start_date": pd.to_datetime(r["package_start_date"]).date().isoformat()
                                if pd.notna(r["package_start_date"])
                                else None,
                                "package_expiry_date": pd.to_datetime(r["package_expiry_date"]).date().isoformat()
                                if pd.notna(r["package_expiry_date"])
                                else None,
                                "lesson_adjustment_units": int(r.get("lesson_adjustment_units", 0)),
                                "package_normalized": bool(r.get("package_normalized", False)),
                                "normalized_note": str(r.get("normalized_note", "") or "").strip(),
                                "normalized_at": _dt.now(timezone.utc).isoformat()
                                if (
                                    bool(r.get("package_normalized", False))
                                    or str(r.get("normalized_note", "") or "").strip()
                                )
                                else None,
                            }

                            if not update_payment_row(pid, updates):
                                ok_all = False

                        # Auto-fill missing subject when package becomes single-language
                        latest_lang = latest_payment_languages_for_student(student_p)
                        _, single_default = allowed_lesson_language_from_package(latest_lang)
                        if single_default is not None:
                            try:
                                cls = load_table("classes")
                                if not cls.empty:
                                    cls["student"] = cls.get("student", "").astype(str).str.strip()
                                    cls = cls[cls["student"] == student_p].copy()
                                    if "subject" not in cls.columns:
                                        cls["subject"] = None
                                    cls["subject"] = cls["subject"].fillna("").astype(str)

                                    missing = cls[
                                        (cls["subject"].str.strip() == "") | (cls["subject"].isna())
                                    ]
                                    for _, rr in missing.iterrows():
                                        update_class_row(int(rr["id"]), {"subject": single_default})
                            except Exception:
                                pass

                        if ok_all:
                            st.success(t("updated"))
                            st.rerun()
                        else:
                            st.error(t("some_updates_failed"))


def _render_view_payments():
    """View all payments sorted by year, displayed as informative cards."""
    payments = load_table("payments")

    if payments.empty:
        st.info(t("no_data"))
        return

    # Normalise columns
    for col in ["payment_date", "paid_amount", "number_of_lesson", "student", "modality", "subject", "subject_custom", "currency"]:
        if col not in payments.columns:
            payments[col] = None

    payments["payment_date"] = pd.to_datetime(payments["payment_date"], errors="coerce")
    payments["paid_amount"] = pd.to_numeric(payments["paid_amount"], errors="coerce").fillna(0.0)
    payments["number_of_lesson"] = pd.to_numeric(payments["number_of_lesson"], errors="coerce").fillna(0).astype(int)
    payments["student"] = payments["student"].fillna("").astype(str).str.strip()
    payments["modality"] = payments["modality"].fillna("Online").astype(str).str.strip()
    payments["subject"] = payments["subject"].fillna("").astype(str).str.strip()
    payments["subject_custom"] = payments["subject_custom"].fillna("").astype(str).str.strip()
    payments["currency"] = payments["currency"].fillna("").astype(str).str.strip()

    valid = payments.dropna(subset=["payment_date"]).copy()
    if valid.empty:
        st.info(t("no_data"))
        return

    valid["year"] = valid["payment_date"].dt.year.astype(int)
    current_year = datetime.date.today().year
    available_years = sorted(valid["year"].unique(), reverse=True)

    selected_year = st.selectbox(
        t("filter_by_year"),
        options=available_years,
        index=0 if current_year not in available_years else available_years.index(current_year),
        key="view_payments_year",
    )

    year_df = valid[valid["year"] == selected_year].sort_values("payment_date", ascending=False)

    if year_df.empty:
        st.info(t("no_payments_year", year=selected_year))
        return

    st.caption(f"**{len(year_df)}** {t('payments')} · {selected_year}")

    _PAYMENTS_PAGE_SIZE = 8
    payment_rows = year_df.reset_index(drop=True).to_dict("records")
    total_items = len(payment_rows)
    total_pages = max(1, math.ceil(total_items / _PAYMENTS_PAGE_SIZE))
    current_page = int(st.session_state.get("view_payments_page", 1) or 1)
    current_page = max(1, min(current_page, total_pages))
    st.session_state["view_payments_page"] = current_page
    start_idx = (current_page - 1) * _PAYMENTS_PAGE_SIZE
    end_idx = min(start_idx + _PAYMENTS_PAGE_SIZE, total_items)
    page_rows = payment_rows[start_idx:end_idx]

    for row in page_rows:
        date_str = pd.to_datetime(row["payment_date"]).strftime("%d %b %Y")
        student_name = row["student"] or "—"
        lessons = int(row["number_of_lesson"])
        amount = float(row["paid_amount"])
        modality = row["modality"]
        subject = row["subject"] or "—"
        subject_custom = row.get("subject_custom", "") or ""
        if subject == "Other" and subject_custom.strip():
            subject = subject_custom.strip()
        cur = row["currency"]
        sym = currency_symbol(cur) if cur else ""

        modality_label = t("online") if modality == "Online" else t("offline")
        modality_color = "#0ea5e9" if modality == "Online" else "#f59e0b"
        amount_str = f"{sym} {amount:,.0f}" if sym else f"{amount:,.0f}"

        st.markdown(
            f"""
            <div style="
                background:linear-gradient(180deg, var(--panel), var(--panel-2));
                border:1px solid var(--border);
                border-left:4px solid var(--primary);
                border-radius:12px;
                padding:14px 16px 12px 16px;
                margin-bottom:10px;
                box-shadow:var(--shadow-md);
            ">
                <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:6px;">
                    <div style="font-weight:700;font-size:1rem;color:var(--text);">
                        {student_name}
                    </div>
                    <div style="font-size:1.05rem;font-weight:800;color:var(--primary-strong);">
                        {amount_str}
                    </div>
                </div>
                <div style="margin-top:6px;display:flex;flex-wrap:wrap;gap:6px;align-items:center;">
                    <span style="font-size:0.82rem;color:var(--muted);">📅 {date_str}</span>
                    <span style="font-size:0.82rem;color:var(--muted);">·</span>
                    <span style="font-size:0.82rem;color:var(--muted);">📚 {lessons} {t('lessons_paid')}</span>
                    <span style="font-size:0.82rem;color:var(--muted);">·</span>
                    <span style="font-size:0.82rem;padding:2px 8px;border-radius:10px;
                                 background:{modality_color}22;color:{modality_color};font-weight:600;">
                        {modality_label}
                    </span>
                    {f'<span style="font-size:0.82rem;color:var(--muted);">· 📖 {subject}</span>' if subject != "—" else ""}
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    if total_items > _PAYMENTS_PAGE_SIZE:
        prev_col, info_col, next_col = st.columns([1, 3, 1])
        with prev_col:
            if st.button("←", key="view_payments_page_prev", use_container_width=True, disabled=current_page <= 1):
                st.session_state["view_payments_page"] = max(1, current_page - 1)
                st.rerun()
        with info_col:
            st.caption(f"{start_idx + 1}-{end_idx} / {total_items} · {current_page}/{total_pages}")
        with next_col:
            if st.button("→", key="view_payments_page_next", use_container_width=True, disabled=current_page >= total_pages):
                st.session_state["view_payments_page"] = min(total_pages, current_page + 1)
                st.rerun()


# =========================
