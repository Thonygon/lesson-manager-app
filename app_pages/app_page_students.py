import streamlit as st
import datetime
import html as _html
import re
import urllib.parse
import pandas as pd
from core.i18n import t
from core.navigation import page_header
from core.database import load_table, load_students, get_sb
from core.database import (
    ensure_student,
    clear_app_caches,
    norm_student,
    update_student_profile,
    rename_student_everywhere
)
from core.state import get_current_user_id
from helpers.student_meta import load_students_df
from helpers.history import show_student_history
from helpers.ui_components import translate_df_headers, render_styled_dataframe
from helpers.whatsapp import _digits_only, normalize_phone_for_whatsapp, build_whatsapp_url
from helpers.student_report import (
    build_student_report_pdf,
    build_report_whatsapp_url,
    build_report_email_url,
)
from helpers.dashboard import rebuild_dashboard
from helpers.teacher_student_integration import (
    archive_teacher_student_link,
    get_teacher_request_resolution,
    load_active_linked_students_for_teacher,
    load_incoming_teacher_requests,
    load_teacher_assignment_progress,
    respond_to_teacher_request,
)

# 12.2) PAGE: STUDENTS
# =========================
def render_students():
    page_header(t("students"))
    st.caption(t("add_and_manage_students"))

    students = load_students()
    students_df = load_students_df()

    with st.expander(t("home_find_students"), expanded=False):
        st.markdown(
            f"""
            <details style="margin-bottom:14px">
              <summary style="cursor:pointer;font-weight:600;color:#f1f5f9;font-size:14px;
                              padding:8px 12px;background:#1e3a5f;border:1px solid #2d5a9e;
                              border-radius:8px;list-style:none;display:flex;align-items:center;gap:6px">
                💡 {t('find_students_rec_title')}
              </summary>
              <div style="background:#162844;border:1px solid #2d5a9e;border-top:none;
                          border-radius:0 0 8px 8px;padding:10px 14px">
                <ol style="margin:0;padding-left:18px;color:#e2e8f0;font-size:14px;line-height:1.8">
                  <li>{t('find_students_step_1')}</li>
                  <li>{t('find_students_step_2')}</li>
                  <li>{t('find_students_step_3')}</li>
                  <li>{t('find_students_step_4')}</li>
                  <li>{t('find_students_step_5')}</li>
                </ol>
              </div>
            </details>
            <style>
              .platform-grid {{
                display: grid;
                grid-template-columns: repeat(3, 1fr);
                gap: 10px;
                padding: 4px 0 6px 0;
              }}
              .platform-card {{
                display: flex;
                flex-direction: column;
                align-items: center;
                justify-content: center;
                gap: 7px;
                padding: 12px 8px 10px 8px;
                background: var(--platform-card-bg);
                border: 1px solid var(--platform-card-border);
                border-radius: 12px;
                text-decoration: none;
                color: var(--text);
                font-size: 0.78rem;
                font-weight: 600;
                letter-spacing: 0.01em;
                transition: background 0.18s, border-color 0.18s, color 0.18s, transform 0.15s;
                cursor: pointer;
              }}
              .platform-card:hover {{
                background: var(--platform-card-hover-bg);
                border-color: var(--platform-card-hover-border);
                color: var(--text);
                transform: translateY(-2px);
              }}
              .platform-card svg {{
                flex-shrink: 0;
              }}
            </style>
            <div class="platform-grid">
              <a class="platform-card" href="https://www.armut.com" target="_blank" rel="noopener noreferrer">
                <svg xmlns="http://www.w3.org/2000/svg" width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round">
                  <!-- pear shape -->
                  <path d="M12 2 C10 2 8.5 3.5 8.5 5.5 C8.5 7 9.2 8.3 10.3 9.2 C8.2 10.1 6.5 12.3 6.5 15 C6.5 18.6 9 21.5 12 21.5 C15 21.5 17.5 18.6 17.5 15 C17.5 12.3 15.8 10.1 13.7 9.2 C14.8 8.3 15.5 7 15.5 5.5 C15.5 3.5 14 2 12 2 Z"/>
                  <line x1="12" y1="2" x2="13.5" y2="0.5"/>
                </svg>
                Armut
              </a>
              <a class="platform-card" href="https://www.apprentus.com" target="_blank" rel="noopener noreferrer">
                <svg xmlns="http://www.w3.org/2000/svg" width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round">
                  <path d="M22 10v6M2 10l10-5 10 5-10 5z"/>
                  <path d="M6 12v5c3 3 9 3 12 0v-5"/>
                </svg>
                Apprentus
              </a>
              <a class="platform-card" href="https://www.superprof.com" target="_blank" rel="noopener noreferrer">
                <svg xmlns="http://www.w3.org/2000/svg" width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round">
                  <circle cx="12" cy="7" r="3"/>
                  <path d="M5 21v-2a7 7 0 0 1 14 0v2"/>
                  <line x1="9" y1="11" x2="15" y2="11"/>
                  <line x1="12" y1="11" x2="12" y2="17"/>
                </svg>
                Superprof
              </a>
              <a class="platform-card" href="https://www.ozelders.com" target="_blank" rel="noopener noreferrer">
                <svg xmlns="http://www.w3.org/2000/svg" width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round">
                  <path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z"/>
                  <path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z"/>
                </svg>
                ÖzelDers
              </a>
              <a class="platform-card" href="https://preply.com" target="_blank" rel="noopener noreferrer">
                <svg xmlns="http://www.w3.org/2000/svg" width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round">
                  <circle cx="12" cy="12" r="10"/>
                  <line x1="2" y1="12" x2="22" y2="12"/>
                  <path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/>
                </svg>
                Preply
              </a>
              <a class="platform-card" href="https://www.italki.com" target="_blank" rel="noopener noreferrer">
                <svg xmlns="http://www.w3.org/2000/svg" width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round">
                  <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
                  <line x1="9" y1="10" x2="15" y2="10"/>
                  <line x1="12" y1="7" x2="12" y2="13"/>
                </svg>
                italki
              </a>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown(f"### {t('add_new')}")
    new_student = st.text_input(t("new_student_name"), key="new_student_name")

    if st.button(f"{t('add')} {t('student')}", key="add_student"):
        name = new_student.strip()
        if not name:
            st.error(t("no_data"))
        elif any(norm_student(name) == norm_student(s) for s in students):
            st.warning(t("student_name_exists"))
        else:
            ensure_student(name)
            st.success(t("done_ok"))
            st.rerun()

    st.markdown(f"### {t('manage_students')}")
    st.markdown(
        """
        <style>
        .classio-student-link-card {
            position: relative;
            overflow: hidden;
            background:
              radial-gradient(circle at top right, rgba(59,130,246,.08), transparent 34%),
              linear-gradient(180deg, var(--panel), color-mix(in srgb, var(--panel) 82%, white 18%));
            border: 1px solid color-mix(in srgb, var(--border) 78%, rgba(59,130,246,.18) 22%);
            border-radius: 22px;
            padding: 18px 20px;
            box-shadow: 0 14px 32px rgba(15,23,42,.08);
            margin-bottom: 0.5rem;
        }
        .classio-student-link-card::before {
            content: "";
            position: absolute;
            inset: 0 auto 0 0;
            width: 5px;
            background: linear-gradient(180deg, #38bdf8, #6366f1 58%, #14b8a6);
        }
        .classio-student-link-name {
            font-size: 1.08rem;
            font-weight: 800;
            color: var(--text);
            line-height: 1.2;
        }
        .classio-student-link-meta {
            margin-top: 0.65rem;
            color: var(--muted);
            font-size: 0.9rem;
            line-height: 1.45;
        }
        .classio-student-link-note {
            margin-top: 0.75rem;
            padding: 0.75rem 0.9rem;
            border-radius: 14px;
            background: rgba(148,163,184,.08);
            border: 1px solid rgba(148,163,184,.16);
            color: var(--muted);
            font-size: 0.9rem;
        }
        .classio-student-link-action-label {
            font-size: 0.76rem;
            font-weight: 800;
            text-transform: uppercase;
            letter-spacing: 0.06em;
            color: var(--muted);
            margin: 0.25rem 0 0.55rem 0.1rem;
        }
        .classio-inline-chip {
            display: inline-flex;
            align-items: center;
            gap: 0.35rem;
            padding: 0.45rem 0.78rem;
            border-radius: 999px;
            background: rgba(59,130,246,.08);
            border: 1px solid rgba(59,130,246,.14);
            color: #2563eb;
            font-size: 0.78rem;
            font-weight: 700;
            margin: 0 0.45rem 0.45rem 0;
        }
        .classio-progress-card {
            position: relative;
            overflow: hidden;
            background:
              radial-gradient(circle at top right, rgba(139,92,246,.10), transparent 34%),
              linear-gradient(180deg, var(--panel), color-mix(in srgb, var(--panel) 82%, white 18%));
            border: 1px solid color-mix(in srgb, var(--border) 78%, rgba(139,92,246,.18) 22%);
            border-radius: 22px;
            padding: 18px 20px;
            box-shadow: 0 14px 32px rgba(15,23,42,.08);
            margin-bottom: 0.9rem;
        }
        .classio-progress-card::before {
            content: "";
            position: absolute;
            inset: 0 auto 0 0;
            width: 5px;
            background: linear-gradient(180deg, #8b5cf6, #6366f1 52%, #38bdf8);
        }
        .classio-progress-title {
            font-size: 1.08rem;
            font-weight: 800;
            color: var(--text);
            line-height: 1.25;
        }
        .classio-progress-meta {
            margin-top: 0.55rem;
            color: var(--muted);
            font-size: 0.9rem;
            line-height: 1.45;
        }
        .classio-progress-stats {
            display: flex;
            gap: 0.75rem;
            flex-wrap: wrap;
            margin-top: 0.95rem;
        }
        .classio-progress-stat {
            min-width: 110px;
            padding: 0.78rem 0.9rem;
            border-radius: 16px;
            background: rgba(148,163,184,.08);
            border: 1px solid rgba(148,163,184,.16);
        }
        .classio-progress-stat-label {
            font-size: 0.74rem;
            font-weight: 800;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            color: var(--muted);
        }
        .classio-progress-stat-value {
            margin-top: 0.25rem;
            font-size: 1.05rem;
            font-weight: 800;
            color: var(--text);
        }
        div[data-testid="stButton"] > button[kind="primary"] {
            border-radius: 16px;
            min-height: 3rem;
            font-weight: 800;
            box-shadow: 0 14px 28px rgba(37,99,235,.18);
        }
        div[data-testid="stButton"] > button[kind="secondary"] {
            border-radius: 16px;
            min-height: 3rem;
            font-weight: 700;
            border-color: rgba(148,163,184,.28);
            box-shadow: 0 8px 18px rgba(15,23,42,.06);
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
    if students_df.empty:
        st.info(t("no_students"))
    else:
        tab_list, tab_profile, tab_history, tab_requests, tab_progress, tab_delete = st.tabs([
            f"👩‍🎓 {t('student_list')}",
            f"📋 {t('student_profile')}",
            f"📊 {t('student_history')}",
            f"🤝 {t('teacher_requests_title')}",
            f"📈 {t('student_progress_title')}",
            f"🗑️ {t('delete_student')}",
        ])

        # ── TAB: Student List ──
        with tab_list:
            s_col1, s_col2 = st.columns([2, 1])
            with s_col1:
                q = st.text_input(
                    t("search"),
                    value="",
                    placeholder=t("search_name_placeholder"),
                    key="students_list_search"
                )
            with s_col2:
                st.caption(f"Total: **{len(students)}**")

            shown = students
            if q.strip():
                shown = [s for s in students if q.strip().lower() in s.lower()]

            if not shown:
                st.info(t("no_students"))
            else:
                for name in shown:
                    row = students_df.loc[students_df["student"] == name]
                    s_email = str(row.iloc[0].get("email", "")).strip() if not row.empty else ""
                    s_phone = str(row.iloc[0].get("phone", "")).strip() if not row.empty else ""
                    s_zoom  = str(row.iloc[0].get("zoom_link", "")).strip() if not row.empty else ""
                    s_color = str(row.iloc[0].get("color", "#3B82F6")).strip() if not row.empty else "#3B82F6"
                    s_notes = str(row.iloc[0].get("notes", "")).strip() if not row.empty else ""
                    s_address = str(row.iloc[0].get("address", "")).strip() if not row.empty else ""

                    has_profile = bool(s_email or s_phone or s_zoom or s_notes or s_address)

                    if not has_profile:
                        st.markdown(
                            f"""
                            <div style="
                                background:var(--panel, #fff);
                                border:1px solid var(--border-strong, rgba(17,24,39,0.08));
                                border-left:4px solid {s_color};
                                border-radius:12px;
                                padding:14px 16px;
                                margin-bottom:10px;
                                box-shadow:0 1px 4px rgba(0,0,0,0.06);
                            ">
                                <div style="font-weight:700;font-size:1rem;color:var(--text,#0f172a);margin-bottom:4px;">
                                    {name}
                                </div>
                                <div style="font-size:13px;color:var(--muted,#94a3b8);font-style:italic;">
                                    {t("no_profile_data")}
                                </div>
                            </div>
                            """,
                            unsafe_allow_html=True,
                        )
                        continue

                    chips = []
                    email_chip_style = (
                        "display:inline-flex;align-items:center;gap:4px;padding:4px 12px;"
                        "border-radius:20px;background:rgba(59,130,246,0.12);color:var(--text);font-size:13px;"
                        "text-decoration:none;border:1px solid rgba(59,130,246,0.28);"
                    )

                    whatsapp_chip_style = (
                        "display:inline-flex;align-items:center;gap:4px;padding:4px 12px;"
                        "border-radius:20px;background:rgba(16,185,129,0.12);color:var(--text);font-size:13px;"
                        "text-decoration:none;border:1px solid rgba(16,185,129,0.28);"
                    )

                    zoom_chip_style = (
                        "display:inline-flex;align-items:center;gap:4px;padding:4px 12px;"
                        "border-radius:20px;background:rgba(139,92,246,0.12);color:var(--text);font-size:13px;"
                        "text-decoration:none;border:1px solid rgba(139,92,246,0.28);"
                    )

                    if s_email:
                        mail_href = f"mailto:{urllib.parse.quote(s_email)}"
                        chips.append(
                            f'<a href="{mail_href}" target="_blank" rel="noopener noreferrer" '
                            f'style="{email_chip_style}">📧 {t("send_email")}</a>'
                        )
                    if s_phone:
                        wa_phone = normalize_phone_for_whatsapp(s_phone)
                        wa_url = f"https://wa.me/{wa_phone}" if wa_phone else ""
                        if wa_url:
                            chips.append(
                                f'<a href="{wa_url}" target="_blank" rel="noopener noreferrer" '
                                f'style="{whatsapp_chip_style}">💬 {t("send_whatsapp")}</a>'
                            )
                    if s_zoom:
                        chips.append(
                            f'<a href="{s_zoom}" target="_blank" rel="noopener noreferrer" '
                            f'style="{zoom_chip_style}">🎥 {t("open_zoom")}</a>'
                        )
                    if s_address:
                        maps_chip_style = (
                            "display:inline-flex;align-items:center;gap:4px;padding:4px 12px;"
                            "border-radius:20px;background:rgba(234,88,12,0.12);color:var(--text);font-size:13px;"
                            "text-decoration:none;border:1px solid rgba(234,88,12,0.28);"
                        )
                        maps_href = f"https://www.google.com/maps/search/{urllib.parse.quote(s_address)}"
                        chips.append(
                            f'<a href="{maps_href}" target="_blank" rel="noopener noreferrer" '
                            f'style="{maps_chip_style}">📍 {t("open_maps")}</a>'
                        )
                    contact_html = " ".join(chips) if chips else f'<span style="font-size:12px;color:#94a3b8;">{t("no_contact_info")}</span>'

                    info_parts = []
                    if s_email:
                        info_parts.append(f"📧 {s_email}")
                    if s_phone:
                        info_parts.append(f"📱 {s_phone}")
                    info_line = " &nbsp;·&nbsp; ".join(info_parts)

                    notes_html = ""
                    if s_notes:
                        safe_notes = s_notes.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace("\n", "<br>")
                        notes_html = f'<div style="font-size:12px;color:var(--muted,#64748b);margin-top:6px;padding:6px 8px;background:var(--bg-3,#f8fafc);border-radius:6px;">{safe_notes}</div>'

                    st.markdown(
                        f"""
                        <div style="
                            background:var(--panel, #fff);
                            border:1px solid var(--border-strong, rgba(17,24,39,0.08));
                            border-left:4px solid {s_color};
                            border-radius:12px;
                            padding:14px 16px;
                            margin-bottom:10px;
                            box-shadow:0 1px 4px rgba(0,0,0,0.06);
                        ">
                            <div style="font-weight:700;font-size:1rem;color:var(--text,#0f172a);margin-bottom:2px;">
                                {name}
                            </div>
                            <div style="font-size:13px;color:var(--muted,#475569);margin-bottom:8px;">
                                {info_line if info_line else ""}
                            </div>
                            <div style="display:flex;flex-wrap:wrap;gap:6px;margin-bottom:2px;">
                                {contact_html}
                            </div>
                            {notes_html}
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )

        # ── TAB: Student Profile ──
        with tab_profile:
            student_list = sorted(students_df["student"].unique().tolist())
            selected_student = st.selectbox(t("select_student"), student_list, key="edit_student_select")

            student_row = students_df.loc[students_df["student"] == selected_student].iloc[0]
            sid = norm_student(selected_student)

            with st.popover(f"✏️ {t('edit_name')}", use_container_width=False):
                new_name = st.text_input(t("new_name"), value=selected_student, key=f"rename_{sid}")
                if st.button(t("save"), key=f"btn_rename_{sid}"):
                    stripped = new_name.strip()
                    if not stripped:
                        st.error(t("no_data"))
                    elif norm_student(stripped) != norm_student(selected_student) and any(
                        norm_student(stripped) == norm_student(s) for s in student_list
                    ):
                        st.warning(t("student_name_exists"))
                    else:
                        try:
                            rename_student_everywhere(selected_student, stripped)
                            st.success(t("done_ok"))
                            st.rerun()
                        except ValueError as e:
                            st.error(t(str(e)))
                        except Exception as e:
                           st.error(f"{t('rename_student_failed')}\n\n{e}")

            col1, col2 = st.columns(2)
            with col1:
                email = st.text_input(t("email"), value=student_row.get("email", ""), key=f"student_email_{sid}")
                zoom_link = st.text_input(t("zoom_link"), value=student_row.get("zoom_link", ""), key=f"student_zoom_{sid}")
                _raw_phone = st.text_input(t("whatsapp_phone"), value=student_row.get("phone", ""), key=f"student_phone_{sid}")
                import re as _re_phone
                phone = _re_phone.sub(r"[^0-9+]", "", _raw_phone)
                if phone != _raw_phone:
                    st.info(t("examples_phone"))
                st.caption(t("examples_phone"))
            with col2:
                color = st.color_picker(t("calendar_color"), value=student_row.get("color", "#3B82F6"), key=f"student_color_{sid}")
                address = st.text_input(t("address"), value=student_row.get("address", ""), key=f"student_address_{sid}")
                notes = st.text_area(t("notes"), value=student_row.get("notes", ""), key=f"student_notes_{sid}")

            if phone and not normalize_phone_for_whatsapp(phone) and len(_digits_only(phone)) < 11:
                st.warning(t("examples_phone"))

            if st.button(t("save"), key=f"btn_save_student_profile_{sid}"):
                update_student_profile(selected_student, email, zoom_link, notes, color, phone, address)
                st.success(t("done_ok"))
                st.rerun()

        # ── TAB: Student History ──
        with tab_history:
            if not students:
                st.info(t("no_students"))
            else:
                hist_student = st.selectbox(t("select_student"), students, key="students_history_student")
                lessons_df, payments_df = show_student_history(hist_student)

                colA, colB = st.columns(2)
                with colA:
                    st.markdown(f"### {t('lessons')}")
                    render_styled_dataframe(translate_df_headers(lessons_df))
                with colB:
                    st.markdown(f"### {t('payments')}")
                    render_styled_dataframe(translate_df_headers(payments_df))

                st.markdown(f"#### {t('report_actions')}")

                _dash = rebuild_dashboard()
                _pkg_df = _dash[_dash["Student"] == hist_student].copy() if not _dash.empty else pd.DataFrame()

                pdf_bytes = build_student_report_pdf(hist_student, lessons_df, payments_df, _pkg_df)
                safe_name = re.sub(r"[^A-Za-z0-9._-]+", "_", hist_student.strip()) or "student"
                file_name = f"report_{safe_name}.pdf"

                _sdf = students_df
                _row = _sdf.loc[_sdf["student"] == hist_student]
                _email = str(_row.iloc[0].get("email", "")).strip() if not _row.empty else ""
                _phone = str(_row.iloc[0].get("phone", "")).strip() if not _row.empty else ""

                btn_cols = st.columns(3)
                with btn_cols[0]:
                    st.download_button(
                        label=f"📄 {t('download_pdf')}",
                        data=pdf_bytes,
                        file_name=file_name,
                        mime="application/pdf",
                        key="btn_download_student_report",
                        use_container_width=True,
                    )
                with btn_cols[1]:
                    if _phone:
                        wa_url = build_report_whatsapp_url(hist_student, _phone)
                        st.link_button(
                            f"💬 {t('send_whatsapp')}",
                            url=wa_url,
                            use_container_width=True,
                        )
                    else:
                        st.button(
                            f"💬 {t('send_whatsapp')}",
                            disabled=True,
                            help=t("no_phone_on_file"),
                            key="btn_wa_report_disabled",
                            use_container_width=True,
                        )
                with btn_cols[2]:
                    if _email:
                        mail_url = build_report_email_url(hist_student, _email)
                        st.link_button(
                            f"📧 {t('send_email')}",
                            url=mail_url,
                            use_container_width=True,
                        )
                    else:
                        st.button(
                            f"📧 {t('send_email')}",
                            disabled=True,
                            help=t("no_email_on_file"),
                            key="btn_email_report_disabled",
                            use_container_width=True,
                        )
                if _phone or _email:
                    st.caption(t("share_report_hint"))

        # ── TAB: Delete Student ──
        with tab_delete:
            st.caption(t("delete_student_warning"))
            if not students:
                st.info(t("no_students"))
            else:
                del_student = st.selectbox(t("select_student"), students, key="delete_student_select")
                confirm = st.checkbox(t("confirm_delete_student"), key="delete_student_confirm")
                if st.button(t("delete"), type="primary", disabled=not confirm, key="btn_delete_student"):
                    try:
                        get_sb().table("students").delete().eq("student", del_student).eq("user_id", get_current_user_id()).execute()
                        clear_app_caches()
                        st.success(t("done_ok"))
                        st.rerun()
                    except Exception as e:
                        st.error(f"{t('delete_student_failed')}\n\n{e}")

        with tab_requests:
            st.markdown(f"### {t('teacher_requests_title')}")
            incoming = load_incoming_teacher_requests()
            if not incoming:
                st.info(t("no_teacher_requests"))
            else:
                for row in incoming:
                    left_col, right_col = st.columns([6, 2], gap="medium")
                    requested = row.get("requested_subjects") or []
                    requested_labels = [s.get("subject_label", "") for s in requested if s.get("subject_label")]
                    with left_col:
                        chips = "".join(
                            f"<span class='classio-inline-chip'>📚 {str(label)}</span>"
                            for label in requested_labels
                        )
                        note_html = ""
                        if row.get("request_note"):
                            note_html = (
                                f"<div class='classio-student-link-note'><strong>{t('teacher_note')}:</strong> "
                                f"{row.get('request_note')}</div>"
                            )
                        st.markdown(
                            f"""
                            <div class="classio-student-link-card">
                                <div class="classio-student-link-name">{row.get('student_name', '—')}</div>
                                <div class="classio-student-link-meta">{t('requested_subjects')}</div>
                                <div style="margin-top:0.5rem;">{chips or f"<span class='classio-inline-chip'>{t('no_active_subjects')}</span>"}</div>
                                {note_html}
                            </div>
                            """,
                            unsafe_allow_html=True,
                        )

                    req_options = [
                        s.get("subject_label", "")
                        for s in requested
                        if s.get("subject_label")
                    ]
                    with right_col:
                        st.markdown(
                            f"<div class='classio-student-link-action-label'>{t('active_subjects')}</div>",
                            unsafe_allow_html=True,
                        )
                        resolution = get_teacher_request_resolution(int(row.get("id")))
                        selected_record_id = None
                        accept_disabled = not req_options
                        chosen = []
                        if req_options:
                            chosen = st.multiselect(
                                t("active_subjects"),
                                options=req_options,
                                default=req_options,
                                key=f"teacher_request_subjects_{row.get('id')}",
                                label_visibility="collapsed",
                            )
                        else:
                            st.warning(t("select_active_subjects"))
                        if resolution.get("mode") in {"linked_existing", "auto_email"} and resolution.get("selected_row"):
                            st.info(
                                f"{t(resolution.get('summary_key', 'teacher_request_auto_link_existing'))} "
                                f"{_html.escape(str(resolution['selected_row'].get('student') or ''))}"
                            )
                        elif resolution.get("mode") == "review":
                            st.warning(t("teacher_request_review_match"))
                            option_values = ["__choose__", "__create_new__"] + [
                                str(candidate.get("id")) for candidate in resolution.get("candidates", [])
                            ]
                            selected_option = st.selectbox(
                                t("teacher_request_select_student_record"),
                                options=option_values,
                                format_func=lambda value: (
                                    t("teacher_request_choose_resolution")
                                    if value == "__choose__"
                                    else t("teacher_request_create_new_record")
                                    if value == "__create_new__"
                                    else next(
                                        (
                                            f"{candidate.get('student', '—')}"
                                            + (
                                                f" · {candidate.get('email')}"
                                                if str(candidate.get('email') or '').strip()
                                                else ""
                                            )
                                            for candidate in resolution.get("candidates", [])
                                            if str(candidate.get("id")) == str(value)
                                        ),
                                        "—",
                                    )
                                ),
                                key=f"teacher_request_resolution_{row.get('id')}",
                            )
                            if selected_option == "__choose__":
                                accept_disabled = True
                            elif selected_option != "__create_new__":
                                selected_record_id = int(selected_option)
                        else:
                            st.caption(t("teacher_request_new_record_will_be_created"))
                        if st.button(
                            t("accept"),
                            key=f"teacher_request_accept_{row.get('id')}",
                            use_container_width=True,
                            disabled=accept_disabled,
                            type="primary",
                        ):
                            if resolution.get("mode") in {"linked_existing", "auto_email"} and resolution.get("selected_row"):
                                selected_record_id = int(resolution["selected_row"].get("id"))
                            ok, msg = respond_to_teacher_request(
                                int(row.get("id")),
                                True,
                                chosen,
                                selected_record_id,
                            )
                            if ok:
                                st.success(t(msg))
                                st.rerun()
                            st.error(t(msg))
                        st.markdown("<div style='height:0.45rem;'></div>", unsafe_allow_html=True)
                        if st.button(t("reject"), key=f"teacher_request_reject_{row.get('id')}", use_container_width=True):
                            ok, msg = respond_to_teacher_request(int(row.get("id")), False, [])
                            if ok:
                                st.success(t(msg))
                                st.rerun()
                            st.error(t(msg))
                    st.markdown("<div style='height:0.75rem;'></div>", unsafe_allow_html=True)

            st.markdown(f"### {t('my_linked_students')}")
            linked = load_active_linked_students_for_teacher()
            if not linked:
                st.info(t("no_linked_students"))
            else:
                for row in linked:
                    left_col, right_col = st.columns([6, 2], gap="medium")
                    subjects = ", ".join(
                        s.get("subject_label", "")
                        for s in row.get("subjects", [])
                        if s.get("subject_label")
                    )
                    with left_col:
                        chips = "".join(
                            f"<span class='classio-inline-chip'>📚 {label}</span>"
                            for label in [s.strip() for s in subjects.split(",") if s.strip()]
                        )
                        st.markdown(
                            f"""
                            <div class="classio-student-link-card">
                                <div class="classio-student-link-name">{row.get('student_name', '—')}</div>
                                <div class="classio-student-link-meta">{t('active_subjects')}</div>
                                <div style="margin-top:0.55rem;">{chips or f"<span class='classio-inline-chip'>{t('no_active_subjects')}</span>"}</div>
                            </div>
                            """,
                            unsafe_allow_html=True,
                        )
                    with right_col:
                        st.markdown(
                            f"<div class='classio-student-link-action-label'>{t('end_relationship')}</div>",
                            unsafe_allow_html=True,
                        )
                        if st.button(t("end_relationship"), key=f"archive_link_{row.get('id')}", use_container_width=True, type="primary"):
                            ok, msg = archive_teacher_student_link(int(row.get("id")))
                            if ok:
                                st.success(t(msg))
                                st.rerun()
                            st.error(t(msg))
                    st.markdown("<div style='height:0.75rem;'></div>", unsafe_allow_html=True)

        with tab_progress:
            st.markdown(f"### {t('student_progress_title')}")
            linked = load_active_linked_students_for_teacher()
            if not linked:
                st.info(t("no_linked_students"))
            else:
                student_options = {row.get("student_name", "—"): row for row in linked}
                selected_student_name = st.selectbox(
                    t("select_student"),
                    options=list(student_options.keys()),
                    key="assignment_progress_student",
                )
                selected_link = student_options[selected_student_name]
                subject_options = ["__all__"] + [s.get("subject_key", "") for s in selected_link.get("subjects", [])]
                selected_subject = st.selectbox(
                    t("subject_filter"),
                    options=subject_options,
                    format_func=lambda x: t("all_subjects") if x == "__all__" else next(
                        (
                            s.get("subject_label", x)
                            for s in selected_link.get("subjects", [])
                            if s.get("subject_key") == x
                        ),
                        x,
                    ),
                    key="assignment_progress_subject",
                )
                rows = load_teacher_assignment_progress(
                    student_id=str(selected_link.get("student_id") or ""),
                    subject_key=None if selected_subject == "__all__" else selected_subject,
                )
                if not rows:
                    st.info(t("no_assignments"))
                else:
                    for row in rows:
                        latest = row.get("latest_attempt") or {}
                        score = latest.get("score_pct", row.get("score_pct"))
                        title = _html.escape(str(row.get("title") or "—"))
                        subject_display = _html.escape(str(row.get("subject_display") or "—"))
                        status_label = _html.escape(t(f"assignment_status_{row.get('status')}"))
                        attempts_value = int(row.get("attempt_count") or 0)
                        score_value = f"{score}%" if score not in (None, "") else "—"
                        student_name_safe = _html.escape(str(row.get("student_name") or selected_student_name or "—"))

                        st.markdown(
                            f"""
                            <div class="classio-progress-card">
                                <div style="display:flex;justify-content:space-between;gap:12px;align-items:flex-start;flex-wrap:wrap;">
                                    <div>
                                        <div class="classio-progress-title">{title}</div>
                                        <div class="classio-progress-meta">{student_name_safe} · {subject_display}</div>
                                    </div>
                                    <div><span class="classio-inline-chip">📌 {status_label}</span></div>
                                </div>
                                <div class="classio-progress-stats">
                                    <div class="classio-progress-stat">
                                        <div class="classio-progress-stat-label">{_html.escape(t('attempts_label'))}</div>
                                        <div class="classio-progress-stat-value">{attempts_value}</div>
                                    </div>
                                    <div class="classio-progress-stat">
                                        <div class="classio-progress-stat-label">{_html.escape(t('score_label'))}</div>
                                        <div class="classio-progress-stat-value">{_html.escape(score_value)}</div>
                                    </div>
                                    <div class="classio-progress-stat">
                                        <div class="classio-progress-stat-label">{_html.escape(t('created_at_label'))}</div>
                                        <div class="classio-progress-stat-value">{_html.escape(str(row.get('created_at') or '')[:10] or '—')}</div>
                                    </div>
                                </div>
                            </div>
                            """,
                            unsafe_allow_html=True,
                        )

# =========================
