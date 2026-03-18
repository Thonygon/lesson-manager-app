import streamlit as st
import datetime
from datetime import datetime as _dt, timezone
import pandas as pd
from core.i18n import t
from core.state import get_current_user_id
from core.timezone import now_local, today_local
from core.navigation import go_to, page_header
from core.database import load_table, load_students
from core.database import norm_student, update_payment_row, clear_app_caches
from helpers.dashboard import rebuild_dashboard
from helpers.student_meta import student_meta_maps
from helpers.goals import load_app_settings_map, save_app_setting
from helpers.kpi_bubbles import kpi_stat_cards
from helpers.ui_components import pretty_df, translate_df_headers, translate_df
from helpers.language import translate_status, translate_modality_value, translate_language_value
from helpers.calendar_helpers import build_calendar_events
from helpers.whatsapp import build_whatsapp_url, build_msg_confirm, build_msg_cancel, build_msg_package_header, build_pricing_block, _msg_lang_label

# 12.1) PAGE: DASHBOARD
# =========================

def render_dashboard():
    page_header(t("dashboard"))
    st.caption(t("manage_current_students"))

    dash = rebuild_dashboard(active_window_days=183, expiry_days=365, grace_days=35)
    if dash is None or dash.empty:
        st.info(t("no_data"))
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
    # TODAY'S LESSONS (row: done | student+time | link)
    # ---------------------------------------
    st.subheader("📅 " + t("todays_lessons"))

    st.markdown(
        """
        <style>
          .tl-row{ display:flex; align-items:center; justify-content:space-between; gap:10px; flex-wrap:wrap; }
          .tl-left{ display:flex; align-items:center; gap:10px; flex-wrap:wrap; }
        </style>
        """,
        unsafe_allow_html=True,
    )

    today = today_local()
    today_events = build_calendar_events(today, today)

    # Keep a DF for WhatsApp templates (confirm/cancel)
    today_df = pd.DataFrame()

    if today_events is None or today_events.empty:
        st.caption(t("no_events_today"))
    else:
        df = today_events.copy()
        df["Student"] = df["Student"].astype(str).str.strip()
        df["Time"] = df["Time"].astype(str).str.strip()
        df["Zoom_Link"] = df.get("Zoom_Link", "").fillna("").astype(str).str.strip()
        df["Source"] = df.get("Source", "").fillna("").astype(str).str.strip().str.lower()
        df = df.sort_values("Time").reset_index(drop=True)

        # Save for WhatsApp Templates
        today_df = df.copy()
        settings_map = load_app_settings_map()

        for _, r in df.iterrows():
            student = str(r.get("Student", "")).strip()
            when = str(r.get("Time", "")).strip()
            link = str(r.get("Zoom_Link", "")).strip()

            # Stable unique lesson key per event
            lesson_id = f"{today.isoformat()}_{student}_{when}"
            key_done = f"today_done_{lesson_id}"

            # Load persisted value once per run
            saved_done_raw = settings_map.get(key_done, "0")
            saved_done = str(saved_done_raw).strip().lower() in ("1", "true", "yes", "y", "on")

            if key_done not in st.session_state:
                st.session_state[key_done] = saved_done

            # ✅ Row layout: Done | Info | Link
            c_done, c_info, c_link = st.columns([0.55, 2.2, 1.3], vertical_alignment="center")

            with c_done:
                old_done = saved_done
                done_now = st.toggle(
                    t("mark_done"),
                    value=bool(st.session_state.get(key_done, saved_done)),
                    key=f"{key_done}_widget",
                )

                if done_now != old_done:
                    ok = save_app_setting(key_done, "1" if done_now else "0")
                    if ok:
                        st.session_state[key_done] = done_now
                    else:
                       st.session_state[key_done] = old_done
                       st.error("Could not save lesson completion status.")

            # Styling AFTER the toggle value is known
            done_effective = bool(st.session_state.get(key_done, saved_done))

            name_style = "font-weight:900;"
            time_style = "font-weight:900;"
            if done_effective:
                name_style += "text-decoration:line-through; opacity:0.55;"
                time_style += "text-decoration:line-through; opacity:0.55;"

            with c_info:
                st.markdown(
                    f"""
                    <div class='tl-row'>
                      <div class='tl-left'>
                        <span style="{name_style}">{student}</span>
                        <span style="{time_style}">{when}</span>
                      </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

            with c_link:
                # Link disappears when done (keeps dashboard clean)
                if (not done_effective) and link.startswith("http"):
                    try:
                        st.link_button(
                            t("open_link"),
                            link,
                            use_container_width=True,
                            key=f"today_link_{lesson_id}",
                        )
                    except Exception:
                        st.markdown(
                            f"<a href='{link}' target='_blank' style='text-decoration:none;'>"
                            f"<button style='width:100%;padding:0.62rem 1.0rem;border-radius:14px;"
                            f"border:1px solid rgba(17,24,39,0.12);background:white;font-weight:700;cursor:pointer;'>"
                            f"{t('open_link')}</button></a>",
                            unsafe_allow_html=True,
                        )
                else:
                    st.markdown("<div style='height:38px;'></div>", unsafe_allow_html=True)

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
        cols_due = ["Student", "Lessons_Left", "Status", "Modality", "Subject", "Payment_Date", "Last_Lesson_Date"]
        cols_due = [c for c in cols_due if c in due_df.columns]

        show_due = due_df[cols_due].copy()
        show_due["Status"] = show_due["Status"].apply(translate_status)
        show_due["Modality"] = show_due.get("Modality", "").apply(translate_modality_value)

        st.dataframe(translate_df(pretty_df(show_due)), use_container_width=True, hide_index=True)

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
          <button style="width:100%;padding:0.7rem 1rem;border-radius:14px;border:1px solid rgba(17,24,39,0.12);background:white;font-weight:700;cursor:pointer;">
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

    with st.expander(t("current_packages"), expanded=False):
        d_display = d.copy()
        d_display["Status"] = d_display["Status"].apply(translate_status)
        d_display["Modality"] = d_display.get("Modality", "").apply(translate_modality_value)

        st.dataframe(
            translate_df(pretty_df(d_display)),
            use_container_width=True,
            hide_index=True,
        )

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

        st.dataframe(translate_df(pretty_df(mm_show)), use_container_width=True, hide_index=True)

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
