import streamlit as st
import datetime
from datetime import datetime as _dt, timezone
import pandas as pd
from core.i18n import t
from core.timezone import today_local, now_local
from core.navigation import page_header, go_to
from core.database import norm_student, update_payment_row, clear_app_caches
from helpers.dashboard import rebuild_dashboard
from helpers.student_meta import student_meta_maps
from helpers.goals import render_home_indicator, YEAR_GOAL_SCOPE, get_next_lesson_display
from helpers.kpi_bubbles import kpi_stat_cards
from helpers.ui_components import pretty_df, translate_df_headers, translate_df, ts_today_naive, render_styled_dataframe
from helpers.analytics import build_income_analytics
from helpers.year_goals import get_year_goal
from helpers.currency import format_currency, get_preferred_currency, get_exchange_rate
from helpers.language import translate_status, translate_modality_value, translate_language_value
from helpers.calendar_helpers import build_calendar_events
from helpers.whatsapp import build_whatsapp_url, build_msg_confirm, build_msg_cancel, build_msg_package_header, build_pricing_block, _msg_lang_label
from helpers.history import show_student_history
from helpers.student_meta import load_students_df
from helpers.student_report import (
    build_student_report_pdf,
    build_report_whatsapp_url,
    build_report_email_url,
)
import re as _re
import html as _html

# 12.1) PAGE: DASHBOARD
# =========================
def _svg_zoom_icon() -> str:
    return """
    <svg viewBox="0 0 24 24" width="18" height="18" fill="none" aria-hidden="true">
      <path d="M15 8.5V6.8c0-.86 0-1.29-.17-1.62a1.5 1.5 0 0 0-.66-.66C13.84 4.35 13.41 4.35 12.55 4.35H6.45c-.86 0-1.29 0-1.62.17a1.5 1.5 0 0 0-.66.66C4 5.51 4 5.94 4 6.8v6.4c0 .86 0 1.29.17 1.62.15.29.37.51.66.66.33.17.76.17 1.62.17h6.1c.86 0 1.29 0 1.62-.17.29-.15.51-.37.66-.66.17-.33.17-.76.17-1.62V11.5l3.2 2.4c.45.34.68.51.87.52a.75.75 0 0 0 .55-.19c.16-.14.16-.43.16-1V7.77c0-.57 0-.86-.16-1a.75.75 0 0 0-.55-.19c-.19.01-.42.18-.87.52L15 8.5Z" fill="currentColor"/>
    </svg>
    """

def _svg_whatsapp_icon() -> str:
    return """
    <svg viewBox="0 0 24 24" width="18" height="18" fill="none" aria-hidden="true">
      <path d="M12 4a8 8 0 0 0-6.93 12l-.82 3.02 3.1-.8A8 8 0 1 0 12 4Zm4.27 11.24c-.18.5-.9.92-1.25.97-.32.05-.72.08-1.16-.06-.27-.09-.62-.2-1.07-.39-1.88-.82-3.1-2.73-3.2-2.86-.1-.13-.76-1.01-.76-1.93 0-.92.48-1.37.65-1.56.17-.18.37-.23.5-.23h.36c.11 0 .26-.04.4.3.15.35.5 1.2.54 1.29.05.09.08.2.02.33-.06.13-.09.21-.18.32-.09.1-.19.24-.27.32-.09.09-.18.18-.08.35.1.17.45.74.96 1.2.66.59 1.22.78 1.39.87.17.08.27.07.37-.04.1-.11.42-.49.53-.66.11-.17.22-.14.37-.08.15.05.96.45 1.12.53.16.08.27.12.31.19.04.07.04.42-.14.92Z" fill="currentColor"/>
    </svg>
    """

def _render_today_lessons_cards(df: pd.DataFrame, phone_map: dict) -> None:
    st.markdown(
        """
        <style>
          .dash-today-list{
            display:flex;
            flex-direction:column;
            gap:12px;
            margin-top:8px;
          }

          .dash-today-card{
            display:flex;
            align-items:center;
            justify-content:space-between;
            gap:14px;
            padding:14px 16px;
            border-radius:18px;
            background:linear-gradient(180deg, var(--panel), var(--panel-2));
            border:1px solid var(--border);
            box-shadow:var(--shadow-sm);
          }

          .dash-today-main{
            min-width:0;
            flex:1 1 auto;
          }

          .dash-today-top{
            display:flex;
            align-items:center;
            flex-wrap:wrap;
            gap:8px;
            margin-bottom:8px;
          }

          .dash-today-name{
            font-size:1rem;
            font-weight:800;
            color:var(--text);
            line-height:1.2;
          }

          .dash-today-time{
            display:inline-flex;
            align-items:center;
            padding:4px 10px;
            border-radius:999px;
            font-size:0.78rem;
            font-weight:800;
            color:var(--primary-strong);
            background:rgba(59,130,246,0.10);
            border:1px solid rgba(59,130,246,0.20);
            white-space:nowrap;
          }

          .dash-today-meta{
            display:flex;
            flex-wrap:wrap;
            gap:8px;
          }

          .dash-today-chip{
            display:inline-flex;
            align-items:center;
            gap:6px;
            padding:4px 10px;
            border-radius:999px;
            font-size:0.78rem;
            font-weight:700;
            color:var(--muted);
            background:rgba(148,163,184,0.08);
            border:1px solid var(--border);
            white-space:nowrap;
          }

          .dash-today-actions{
            display:flex;
            align-items:center;
            justify-content:flex-end;
            gap:8px;
            flex:0 0 auto;
          }

          .dash-today-icon-btn{
            width:42px;
            height:42px;
            border-radius:14px;
            display:inline-flex;
            align-items:center;
            justify-content:center;
            text-decoration:none !important;
            border:1px solid var(--border);
            background:linear-gradient(180deg, var(--panel-soft), var(--panel));
            color:var(--text) !important;
            box-shadow:var(--shadow-sm);
            transition:transform 160ms ease, box-shadow 160ms ease, border-color 160ms ease;
          }

          .dash-today-icon-btn:hover{
            transform:translateY(-1px);
            border-color:rgba(59,130,246,0.28);
            box-shadow:var(--shadow-md);
          }

          .dash-today-icon-btn--zoom{
            color:#2563EB !important;
          }

          .dash-today-icon-btn--wa{
            color:#22C55E !important;
          }

          @media (max-width: 768px){
            .dash-today-card{
              align-items:flex-start;
              flex-direction:column;
            }

            .dash-today-actions{
              width:100%;
              justify-content:flex-start;
            }
          }
        </style>
        """,
        unsafe_allow_html=True,
    )

    cards = []

    for _, r in df.iterrows():
        student = str(r.get("Student", "") or "").strip()
        when = str(r.get("Time", "") or "").strip()
        zoom_link = str(r.get("Zoom_Link", "") or "").strip()
        subject = str(r.get("Subject", "") or "").strip()
        modality_raw = str(r.get("Modality", "") or "").strip()
        source = str(r.get("Source", "") or "").strip().lower()

        phone_raw = str(phone_map.get(norm_student(student), "") or "").strip()
        wa_url = build_whatsapp_url("", raw_phone=phone_raw) if phone_raw else ""

        meta_bits = []
        if subject:
            meta_bits.append(
                f"<span class='dash-today-chip'>📚 {_html.escape(subject)}</span>"
            )
        if modality_raw:
            meta_bits.append(
                f"<span class='dash-today-chip'>📍 {_html.escape(translate_modality_value(modality_raw))}</span>"
            )

        actions = []
        if zoom_link.startswith("http"):
            actions.append(
                f"<a class='dash-today-icon-btn dash-today-icon-btn--zoom' "
                f"href='{_html.escape(zoom_link, quote=True)}' target='_blank' rel='noopener noreferrer' "
                f"title='Zoom'>{_svg_zoom_icon()}</a>"
            )
        if wa_url and phone_raw:
            actions.append(
                f"<a class='dash-today-icon-btn dash-today-icon-btn--wa' "
                f"href='{_html.escape(wa_url, quote=True)}' target='_blank' rel='noopener noreferrer' "
                f"title='WhatsApp'>{_svg_whatsapp_icon()}</a>"
            )

        card_html = (
            f'<div class="dash-today-card">'
            f'  <div class="dash-today-main">'
            f'    <div class="dash-today-top">'
            f'      <span class="dash-today-name">{_html.escape(student or "—")}</span>'
            f'      {"<span class=\"dash-today-time\">🕒 " + _html.escape(when) + "</span>" if when else ""}'
            f'    </div>'
            f'    {"<div class=\"dash-today-meta\">" + "".join(meta_bits) + "</div>" if meta_bits else ""}'
            f'  </div>'
            f'  {"<div class=\"dash-today-actions\">" + "".join(actions) + "</div>" if actions else ""}'
            f'</div>'
        )
        cards.append(card_html)

    if cards:
        st.markdown(
            "<div class='dash-today-list'>" + "".join(cards) + "</div>",
            unsafe_allow_html=True,
        )

def render_dashboard():
    page_header(t("dashboard"))
    st.caption(t("manage_current_students"))

    dash = rebuild_dashboard(active_window_days=183, expiry_days=365, grace_days=35)
    if dash is None or dash.empty:
        st.info(t("no_dashboard_data"))
        st.stop()

    d = dash.copy()

    # --- IMPORTANT: treat status as INTERNAL CODES (lowercase) ---
    d["Status"] = d.get("Status", "").fillna("").astype(str).str.strip().str.casefold()
    d["Is_Active_6m"] = pd.Series(d.get("Is_Active_6m", False)).fillna(False).astype(bool)

    d = d[
        (d["Status"].isin(["active", "almost_finished", "mismatch"])) |
        ((d["Status"] == "finished") & (d["Is_Active_6m"] == True))
    ].copy()

    # ---------------------------------------
    # GOAL INDICATOR
    # ---------------------------------------
    active_students = int(
        d["Status"]
        .isin(["active", "almost_finished", "mismatch"])
        .sum()
    )

    next_lesson = get_next_lesson_display()

    kpis, *_ = build_income_analytics(group="monthly")
    income_this_year = float(kpis.get("income_this_year", 0.0))

    current_year = int(ts_today_naive().year)
    goal_val = float(get_year_goal(current_year, scope=YEAR_GOAL_SCOPE, default=0.0) or 0.0)

    pref_cur = get_preferred_currency()
    fx_rate = get_exchange_rate("TRY", pref_cur)
    goal_display = goal_val * fx_rate
    income_display = income_this_year * fx_rate

    goal_progress = 0.0
    if goal_val > 0:
        goal_progress = max(0.0, min(1.0, income_this_year / goal_val))

    if goal_val > 0:
        render_home_indicator(
            status=t("online"),
            badge=now_local().strftime("%d %b %Y"),
            items=[
                (t("goal"), format_currency(goal_display)),
                (t("ytd_income"), format_currency(income_display)),
                (t("students"), str(active_students)),
                (t("next"), next_lesson),
            ],
            progress=goal_progress,
            accent="#3B82F6",
        )
    else:
        st.info(t("goal_not_set_invite"))
        if st.button(t("analytics"), key="dash_go_analytics"):
            go_to("analytics")
            st.rerun()

    # ---------------------------------------
    # TODAY'S LESSONS
    # ---------------------------------------
    st.subheader("📅 " + t("todays_lessons"))

    today = today_local()
    today_events = build_calendar_events(today, today)

    # Keep a DF for WhatsApp templates (confirm/cancel)
    today_df = pd.DataFrame()

    if today_events is None or today_events.empty:
        st.caption(t("no_events_today"))
    else:
        df = today_events.copy()

        for col in ["Student", "Time", "Zoom_Link", "Source", "Subject", "Modality"]:
            if col not in df.columns:
                df[col] = ""

        df["Student"] = df["Student"].fillna("").astype(str).str.strip()
        df["Time"] = df["Time"].fillna("").astype(str).str.strip()
        df["Zoom_Link"] = df["Zoom_Link"].fillna("").astype(str).str.strip()
        df["Source"] = df["Source"].fillna("").astype(str).str.strip().str.lower()
        df["Subject"] = df["Subject"].fillna("").astype(str).str.strip()
        df["Modality"] = df["Modality"].fillna("").astype(str).str.strip()

        df = df.sort_values("Time").reset_index(drop=True)

        today_df = df.copy()

        _, _, _, phone_map = student_meta_maps()
        _render_today_lessons_cards(df, phone_map)

    # ---------------------------------------
    # TAKE ACTION
    # ---------------------------------------
    st.subheader(t("take_action"))

    due_df = d[d["Status"] == "almost_finished"].copy()
    due_df["Lessons_Left"] = pd.to_numeric(due_df.get("Lessons_Left_Units"), errors="coerce").fillna(0).astype(int)
    due_df = due_df.sort_values(["Lessons_Left", "Student"])

    if due_df.empty:
        st.caption(t("no_data"))
    else:
        color_map, _, _, _ = student_meta_maps()
        for _, row in due_df.iterrows():
            student = str(row.get("Student", ""))
            lessons_left = int(row.get("Lessons_Left", 0))
            modality = translate_modality_value(str(row.get("Modality", "")))
            subject = str(row.get("Subject", ""))
            payment_date = str(row.get("Payment_Date", ""))[:10]
            last_lesson = str(row.get("Last_Lesson_Date", ""))[:10]
            s_color = color_map.get(norm_student(student), "#3B82F6")

            # Urgency styling
            if lessons_left <= 1:
                badge_bg = "#FEE2E2"; badge_color = "#991B1B"; badge_border = "#FECACA"
            elif lessons_left <= 2:
                badge_bg = "#FEF3C7"; badge_color = "#92400E"; badge_border = "#FDE68A"
            else:
                badge_bg = "#DBEAFE"; badge_color = "#1E40AF"; badge_border = "#BFDBFE"

            st.markdown(
                f"""
                <div style="
                    background:var(--panel, #fff);
                    border:1px solid var(--border-strong, rgba(17,24,39,0.08));
                    border-left:4px solid {s_color};
                    border-radius:12px;
                    padding:14px 16px;
                    margin-bottom:10px;
                    box-shadow:0 1px 4px rgba(0,0,0,0.08);
                ">
                    <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:6px;">
                        <span style="font-weight:700;font-size:1rem;color:var(--text, #0f172a);">{student}</span>
                        <span style="
                            display:inline-block;padding:3px 10px;border-radius:12px;font-size:12px;font-weight:700;
                            background:{badge_bg};color:{badge_color};border:1px solid {badge_border};
                        ">{lessons_left} {t('lessons_left')}</span>
                    </div>
                    <div style="display:flex;flex-wrap:wrap;gap:12px;margin-top:8px;font-size:13px;color:var(--muted, #475569);">
                        <span>📚 {subject}</span>
                        <span>📍 {modality}</span>
                        <span>💳 {payment_date}</span>
                        <span>📅 {last_lesson}</span>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    # ---------------------------------------
    # WHATSAPP TEMPLATES (PACKAGE / CONFIRM / CANCEL)
    # ---------------------------------------
    st.subheader(t("whatsapp_templates_title"))

    # IMPORTANT: Streamlit widgets keep value by key.
    # To ensure the message updates when user changes template/student/lang,
    # we overwrite st.session_state["wa_msg_box_visible"] when signature changes.

    # Language picker controls MESSAGE language
    ui_lang = st.session_state.get("ui_lang", "en")
    if ui_lang not in ("en", "es", "tr"):
        ui_lang = "en"

    wa_lang = st.selectbox(
        t("whatsapp_message_language"),
        ["en", "es", "tr"],
        format_func=_msg_lang_label,
        index=["en", "es", "tr"].index(ui_lang),
        key="wa_lang_pick",
    )

    template_type = st.radio(
        t("whatsapp_choose_template"),
        ["package", "confirm_today", "cancel_today"],
        format_func=lambda x: {
            "package": t("whatsapp_tpl_package"),
            "confirm_today": t("whatsapp_tpl_confirm"),
            "cancel_today": t("whatsapp_tpl_cancel"),
        }.get(x, x),
        horizontal=True,
        key="wa_template_type",
    )

    # Phone map
    _, _, _, phone_map = student_meta_maps()

    # Decide eligible list + pick student
    pick = ""
    default_msg = ""

    if template_type == "package":
        eligible = due_df.copy()
        if eligible is None or eligible.empty or ("Student" not in eligible.columns):
            st.info(t("whatsapp_no_students_for_template"))
            # Ensure textbox doesn't keep stale content when nothing is eligible
            st.session_state["wa_msg_box_visible"] = ""
            st.stop()

        pick = st.selectbox(
            t("contact_student"),
            eligible["Student"].tolist(),
            key="wa_pick_student_package",
        )

        st_row = eligible[eligible["Student"] == pick].iloc[0]
        status_val = st_row.get("Status", "almost_finished")

        default_msg = (
            build_msg_package_header(pick, wa_lang, status_val)
            + "\n"
            + build_pricing_block(wa_lang)
        )

    else:
        eligible = today_df.copy()
        if eligible is None or eligible.empty or ("Student" not in eligible.columns):
            st.info(t("whatsapp_no_students_for_template"))
            st.session_state["wa_msg_box_visible"] = ""
            st.stop()

        pick = st.selectbox(
            t("contact_student"),
            eligible["Student"].tolist(),
            key="wa_pick_student_today",
        )

        st_row = eligible[eligible["Student"] == pick].iloc[0]
        time_text = str(st_row.get("Time", "") or "").strip()

        if template_type == "confirm_today":
            default_msg = build_msg_confirm(pick, wa_lang, time_text=time_text)
        else:
            default_msg = build_msg_cancel(pick, wa_lang)

    raw_phone = phone_map.get(norm_student(pick), "")

    # -------------------------------------------------
    # Force refresh of textbox when selection changes
    # -------------------------------------------------
    sig_key = "wa_signature"
    signature = f"{template_type}||{wa_lang}||{pick}"

    if st.session_state.get(sig_key) != signature:
        st.session_state[sig_key] = signature
        st.session_state["wa_msg_box_visible"] = default_msg

    # Editable message (bound to state key)
    msg = st.text_area(
        t("whatsapp_message"),
        height=260,
        key="wa_msg_box_visible",
    )

    wa_url = build_whatsapp_url(msg, raw_phone=raw_phone)

    st.markdown(
        f"""
        <a href="{wa_url}" target="_blank" style="text-decoration:none;">
          <button style="width:100%;padding:0.7rem 1rem;border-radius:14px;border:1px solid var(--border-strong,rgba(17,24,39,0.12));background:var(--panel,white);color:var(--text,#0f172a);font-weight:700;cursor:pointer;">
            {t("open_whatsapp")}
          </button>
        </a>
        """,
        unsafe_allow_html=True,
    )

    # ---------------------------------------
    # CURRENT STUDENTS AND PACKAGES (BUBBLES)
    # ---------------------------------------
    st.subheader(t("academic_status"))

    total_students = int(len(d))
    active_count = int((d["Status"] == "active").sum())
    finish_soon_count = int((d["Status"] == "almost_finished").sum())
    finished_recent_count = int((d["Status"] == "finished").sum())
    mismatch_count = int((d["Status"] == "mismatch").sum())

    kpi_stat_cards(
        values=[
            (t("students"), str(total_students)),
            (t("active"), str(active_count)),
            (t("action_finish_soon"), str(finish_soon_count)),
            (t("finished"), str(finished_recent_count)),
            (t("mismatch"), str(mismatch_count)),
        ],
        accent_colors=[
            "#3B82F6",  # blue
            "#10B981",  # green
            "#F59E0B",  # amber
            "#8B5CF6",  # purple
            "#EF4444",  # red
        ],
    )

    with st.expander(t("view_student_reports"), expanded=False):
        _dash_students = sorted(d["Student"].dropna().unique().tolist())
        if not _dash_students:
            st.info(t("no_students"))
        else:
            _rpt_student = st.selectbox(t("select_student"), _dash_students, key="dash_report_student")
            _rpt_lessons, _rpt_payments = show_student_history(_rpt_student)

            _rptA, _rptB = st.columns(2)
            with _rptA:
                st.markdown(f"### {t('lessons')}")
                render_styled_dataframe(translate_df_headers(_rpt_lessons))
            with _rptB:
                st.markdown(f"### {t('payments')}")
                render_styled_dataframe(translate_df_headers(_rpt_payments))

            st.markdown(f"#### {t('report_actions')}")
            _pkg_df = d[d["Student"] == _rpt_student].copy()
            _rpt_pdf = build_student_report_pdf(_rpt_student, _rpt_lessons, _rpt_payments, _pkg_df)
            _safe_name = _re.sub(r"[^A-Za-z0-9._-]+", "_", _rpt_student.strip()) or "student"
            _rpt_file = f"report_{_safe_name}.pdf"

            _sdf = load_students_df()
            _srow = _sdf.loc[_sdf["student"] == _rpt_student]
            _s_email = str(_srow.iloc[0].get("email", "")).strip() if not _srow.empty else ""
            _s_phone = str(_srow.iloc[0].get("phone", "")).strip() if not _srow.empty else ""

            _rpt_cols = st.columns(3)
            with _rpt_cols[0]:
                st.download_button(
                    label=f"\U0001f4c4 {t('download_pdf')}",
                    data=_rpt_pdf,
                    file_name=_rpt_file,
                    mime="application/pdf",
                    key="dash_btn_download_report",
                    use_container_width=True,
                )
            with _rpt_cols[1]:
                if _s_phone:
                    _wa_url = build_report_whatsapp_url(_rpt_student, _s_phone)
                    st.link_button(
                        f"\U0001f4ac {t('send_whatsapp')}",
                        url=_wa_url,
                        use_container_width=True,
                    )
                else:
                    st.button(
                        f"\U0001f4ac {t('send_whatsapp')}",
                        disabled=True,
                        help=t("no_phone_on_file"),
                        key="dash_btn_wa_report_disabled",
                        use_container_width=True,
                    )
            with _rpt_cols[2]:
                if _s_email:
                    _mail_url = build_report_email_url(_rpt_student, _s_email)
                    st.link_button(
                        f"\U0001f4e7 {t('send_email')}",
                        url=_mail_url,
                        use_container_width=True,
                    )
                else:
                    st.button(
                        f"\U0001f4e7 {t('send_email')}",
                        disabled=True,
                        help=t("no_email_on_file"),
                        key="dash_btn_email_report_disabled",
                        use_container_width=True,
                    )
            if _s_phone or _s_email:
                st.caption(t("share_report_hint"))

    _show_raw = st.toggle(t("show_raw_data"), value=False, key="dash_show_raw_packages")
    if _show_raw:
        d_display = d.copy()
        d_display["Status"] = d_display["Status"].apply(translate_status)
        d_display["Modality"] = d_display.get("Modality", "").apply(translate_modality_value)

        render_styled_dataframe(translate_df(pretty_df(d_display)))

    # ---------------------------------------
    # MISMATCHES
    # ---------------------------------------
    st.subheader(t("mismatches"))
    mismatch_df = d[d["Status"] == "mismatch"].copy()

    if mismatch_df.empty:
        st.caption(t("all_good_no_action_required"))
    else:
        cols_mm = [
            "Student",
            "Overused_Units",
            "Lessons_Left_Units",
            "Lessons_Taken_Units",
            "Lessons_Paid_Total",
            "Payment_Date",
            "Package_Start_Date",
            "Modality",
            "Subject",
            "Payment_ID",
            "Normalize_Allowed",
        ]
        cols_mm = [c for c in cols_mm if c in mismatch_df.columns]

        mm_show = mismatch_df[cols_mm].copy()
        if "Modality" in mm_show.columns:
            mm_show["Modality"] = mm_show["Modality"].apply(translate_modality_value)

        render_styled_dataframe(translate_df(pretty_df(mm_show)))

        st.markdown(f"### {t('normalize')}")

        pick_m = st.selectbox(
            t("select_student"),
            mismatch_df["Student"].tolist(),
            key="dash_norm_pick_student",
        )

        rowm = mismatch_df[mismatch_df["Student"] == pick_m].iloc[0]
        pid = int(rowm.get("Payment_ID", 0))
        can_norm = bool(rowm.get("Normalize_Allowed", False))

        st.caption(t("normalized_note"))

        adj_units = st.number_input(
            t("adjust_units"),
            min_value=-1000,
            max_value=1000,
            value=0,
            step=1,
            key="dash_norm_adj_units",
        )
        norm_note = st.text_input(
            t("normalized_note"),
            value=t("normalized_default_note"),
            key="dash_norm_note",
        )

        if st.button(t("normalize"), disabled=not can_norm, key="dash_norm_save_btn"):
            try:
                updates = {
                    "lesson_adjustment_units": int(adj_units),
                    "package_normalized": True,
                    "normalized_note": str(norm_note or "").strip(),
                    "normalized_at": _dt.now(timezone.utc).isoformat(),
                }
                ok = update_payment_row(pid, updates)
                if ok:
                    st.success(t("done_ok"))
                    st.rerun()
                else:
                    st.error(t("normalize_failed"))
            except Exception as e:
                st.error(f"{t('normalize_failed')}\n\n{e}")

# =========================
