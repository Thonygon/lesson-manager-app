import streamlit as st
import datetime
from datetime import datetime as _dt, timezone
import pandas as pd
from core.i18n import t
from core.navigation import go_to, page_header
from core.database import get_sb, load_table, load_students, add_payment, clear_app_caches
from helpers.language import LANG_EN, LANG_ES, LANG_BOTH, ALLOWED_LANGS, DEFAULT_PACKAGE_LANGS, pack_languages, allowed_lesson_language_from_package, translate_language_value
from core.database import delete_row, update_payment_row, update_class_row
from helpers.pricing import render_pricing_editor
from helpers.package_lang_lookups import latest_payment_languages_for_student
from helpers.currency import CURRENCIES, CURRENCY_CODES, get_preferred_currency, currency_symbol, guess_currency_from_timezone
from helpers.lesson_planner import QUICK_SUBJECTS

# 12.4) PAGE: ADD PAYMENT
# =========================
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
        _subj_options = QUICK_SUBJECTS + [t("other")]
        pay_subject_choice = st.selectbox(
            t("subject"),
            _subj_options,
            key="pay_subject_select",
        )
        if pay_subject_choice == t("other"):
            pay_subject = st.text_input(t("subject_other"), key="pay_subject_other").strip()
        else:
            pay_subject = pay_subject_choice

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
            if not pay_currency:
                st.error("Please select a currency.")
                st.stop()
            add_payment(
                student=student_p,
                number_of_lesson=int(lessons_paid),
                payment_date=payment_date.isoformat(),
                paid_amount=float(paid_amount),
                modality=str(modality_p),
                subject=pay_subject,
                package_start_date=pkg_start.isoformat() if pkg_start else payment_date.isoformat(),
                package_expiry_date=pkg_expiry.isoformat() if pkg_expiry else None,
                lesson_adjustment_units=0,
                package_normalized=False,
                normalized_note="",
                currency=pay_currency,
            )
            st.success(t("saved"))
            st.rerun()

        # ----------------------------
        # PAYMENT EDITOR (BULK + DELETE BY ID INSIDE)
        # ----------------------------
        with st.expander(t("payment_editor"), expanded=False):
            st.caption(t("warning_apply"))

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
                    payments["number_of_lesson"] = pd.to_numeric(payments["number_of_lesson"], errors="coerce").fillna(0).astype(int)
                    payments["paid_amount"] = pd.to_numeric(payments["paid_amount"], errors="coerce").fillna(0.0)
                    payments["lesson_adjustment_units"] = pd.to_numeric(payments["lesson_adjustment_units"], errors="coerce").fillna(0).astype(int)
                    payments["package_normalized"] = payments["package_normalized"].fillna(False).astype(bool)
                    payments["subject"] = payments["subject"].fillna("").astype(str).str.strip()
                    payments["modality"] = payments["modality"].fillna("Online").astype(str).str.strip()

                    show_cols = [
                        "id",
                        "payment_date",
                        "number_of_lesson",
                        "paid_amount",
                        "modality",
                        "subject",
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
                                options=QUICK_SUBJECTS + [t("other"), ""],
                            ),
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

                            subject_val = str(r.get("subject") or "").strip()

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
                                "subject": subject_val,
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
    for col in ["payment_date", "paid_amount", "number_of_lesson", "student", "modality", "subject", "currency"]:
        if col not in payments.columns:
            payments[col] = None

    payments["payment_date"] = pd.to_datetime(payments["payment_date"], errors="coerce")
    payments["paid_amount"] = pd.to_numeric(payments["paid_amount"], errors="coerce").fillna(0.0)
    payments["number_of_lesson"] = pd.to_numeric(payments["number_of_lesson"], errors="coerce").fillna(0).astype(int)
    payments["student"] = payments["student"].fillna("").astype(str).str.strip()
    payments["modality"] = payments["modality"].fillna("Online").astype(str).str.strip()
    payments["subject"] = payments["subject"].fillna("").astype(str).str.strip()
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

    st.caption(f"**{len(year_df)}** payments · {selected_year}")

    for _, row in year_df.iterrows():
        date_str = row["payment_date"].strftime("%d %b %Y")
        student_name = row["student"] or "—"
        lessons = int(row["number_of_lesson"])
        amount = float(row["paid_amount"])
        modality = row["modality"]
        subject = row["subject"] or "—"
        cur = row["currency"]
        sym = currency_symbol(cur) if cur else ""

        modality_label = t("online") if modality == "Online" else t("offline")
        modality_color = "#0ea5e9" if modality == "Online" else "#f59e0b"
        amount_str = f"{sym} {amount:,.0f}" if sym else f"{amount:,.0f}"

        st.markdown(
            f"""
            <div style="
                background:#fff;
                border:1px solid rgba(17,24,39,0.08);
                border-left:4px solid #3B82F6;
                border-radius:12px;
                padding:14px 16px 12px 16px;
                margin-bottom:10px;
                box-shadow:0 1px 4px rgba(0,0,0,0.04);
            ">
                <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:6px;">
                    <div style="font-weight:700;font-size:1rem;color:#0f172a;">
                        {student_name}
                    </div>
                    <div style="font-size:1.05rem;font-weight:800;color:#1e40af;">
                        {amount_str}
                    </div>
                </div>
                <div style="margin-top:6px;display:flex;flex-wrap:wrap;gap:6px;align-items:center;">
                    <span style="font-size:0.82rem;color:#64748b;">📅 {date_str}</span>
                    <span style="font-size:0.82rem;color:#64748b;">·</span>
                    <span style="font-size:0.82rem;color:#64748b;">📚 {lessons} {t('lessons_paid')}</span>
                    <span style="font-size:0.82rem;color:#64748b;">·</span>
                    <span style="font-size:0.82rem;padding:2px 8px;border-radius:10px;
                                 background:{modality_color}22;color:{modality_color};font-weight:600;">
                        {modality_label}
                    </span>
                    {f'<span style="font-size:0.82rem;color:#64748b;">· 📖 {subject}</span>' if subject != "—" else ""}
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )


# =========================
