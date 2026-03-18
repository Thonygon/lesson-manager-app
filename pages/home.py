import streamlit as st
import datetime
from core.i18n import t
from core.timezone import now_local
from core.navigation import go_to, home_go, PAGES
from core.timezone import _get_qp
from core.database import load_table, load_students, clear_app_caches
from auth.auth import render_logout_button, render_profile_dialog
from styles.theme import load_css_home
from streamlit_option_menu import option_menu
from streamlit_extras.stylable_container import stylable_container
from core.database import get_profile_avatar_url
from auth.auth import sign_out_user
from helpers.dashboard import rebuild_dashboard
from helpers.analytics import build_income_analytics
from helpers.home_helpers import neon_button_css
from helpers.pricing import money_try
from helpers.ui_components import ts_today_naive
from helpers.goals import render_home_indicator, YEAR_GOAL_SCOPE, get_next_lesson_display
from helpers.year_goals import get_year_goal
from helpers.currency import format_currency, get_preferred_currency, get_exchange_rate
from core.database import load_profile_row
from helpers.lesson_planner import normalize_planner_output
from helpers.planner_storage import load_my_lesson_plans, load_public_lesson_plans, render_plan_library_cards, render_quick_lesson_plan_result, render_quick_lesson_planner_expander
from helpers.cv_storage import load_my_cvs, load_my_cover_letters, render_cv_library_cards, render_cv_result, render_quick_cv_builder_expander, build_cv_pdf_bytes, build_cover_letter_pdf_bytes

# 10) HOME SCREEN UI (DARK)
# =========================
def render_home():
    current_lang = st.session_state.get("ui_lang", "en")
    if current_lang not in ("en", "es"):
        current_lang = "en"

    user = st.session_state.get("auth_user") or {}
    user_id = st.session_state.get("user_id", "") or ""
    panel = _get_qp("panel", "")

    if isinstance(user, dict):
        user_id = user.get("id") or user_id

    user_metadata = user.get("user_metadata", {}) if isinstance(user, dict) else {}

    user_name = (
        st.session_state.get("user_name")
        or user_metadata.get("full_name")
        or user_metadata.get("name")
        or st.session_state.get("user_email")
        or "User"
    )

    # Load avatar from DB once per session
    if user_id and not st.session_state.get("avatar_url"):
        st.session_state["avatar_url"] = get_profile_avatar_url(user_id)

    avatar_url = st.session_state.get("avatar_url", "")
    avatar_style = (
        f"background-image:url('{avatar_url}'); background-size:cover; background-position:center;"
        if avatar_url
        else "background: linear-gradient(135deg, #60A5FA, #A78BFA);"
    )

    # ---------- HOME SHELL ----------
    st.markdown('<div class="home-shell">', unsafe_allow_html=True)

    # ---------- TOP ACTION BUTTONS ----------
    left, right = st.columns([6, 4], vertical_alignment="center")

    with right:
        if "home_action_menu_nonce" not in st.session_state:
            st.session_state["home_action_menu_nonce"] = 0

        default_action_index = 1 if panel == "files" else 0

        # Keep prev in sync with whatever the menu is currently showing
        if "home_action_menu_prev" not in st.session_state:
            st.session_state["home_action_menu_prev"] = t("files") if panel == "files" else t("profile")

        action = option_menu(
            menu_title=None,
            options=[t("profile"), t("files"), t("sign_out")],
            icons=["person-circle", "folder2-open", "box-arrow-right"],
            orientation="horizontal",
            default_index=default_action_index,
            key=f"home_action_menu_{st.session_state.get('home_action_menu_nonce', 0)}",
            styles={
                "container": {
                    "padding": "0 !important",
                    "margin": "0 !important",
                    "background": "transparent",
                },
                "nav-link": {
                    "font-size": "14px",
                    "text-align": "center",
                    "padding": "6px 8px",
                    "--hover-color": "rgba(59,130,246,0.15)",
                },
                "nav-link-selected": {
                    "background-color": "#3B82F6",
                    "color": "white",
                },
                "icon": {
                    "font-size": "16px",
                },
            },
        )

        # The "default" item is effectively deselected/neutral – treat it as a no-op baseline
        default_label = t("files") if panel == "files" else t("profile")

    with left:
        st.markdown(
            f"""
            <div class="home-topbar home-topbar-main">
                <div class="home-topbar-left">
                    <div class="home-avatar home-avatar-sm" style="{avatar_style}"></div>
                    <div class="home-topbar-usertext">
                        <div class="home-topbar-sub">{t("welcome").strip()}</div>
                        <div class="home-topbar-name">{user_name}</div>
                    </div>
                <div class="home-topbar-brand">CLASSIO</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        previous_action = st.session_state.get("home_action_menu_prev", t("profile"))

        if action != default_label:
            if action == t("profile"):
                st.session_state["show_profile_dialog"] = True
                st.session_state["home_action_menu_prev"] = t("profile")
                st.session_state["home_action_menu_nonce"] += 1
                st.rerun()

            elif action == t("files"):
                st.session_state["home_action_menu_prev"] = t("files")
                home_go("home", panel="files")

            elif action == t("sign_out"):
                sign_out_user()     
        
    # ---------- PROFILE DIALOG ----------
    if st.session_state.get("show_profile_dialog"):
        st.session_state["show_profile_dialog"] = False
        render_profile_dialog(user_id)

    if panel == "files":
        top_a, top_b = st.columns([6, 1])

        with top_a:
            st.markdown(f"### {t('files')}")

        with top_b:
            if st.button(t("close_files"), key="close_files_panel", use_container_width=True):
                st.session_state["home_action_menu_prev"] = t("profile")
                st.session_state["home_action_menu_nonce"] += 1
                home_go("home", panel=None)
                st.rerun()

        tab1, tab2, tab3, tab4 = st.tabs([t("my_plans"), t("community_library"), t("my_cvs"), t("my_cover_letters")])

        with tab1:
            my_df = load_my_lesson_plans()

            if my_df.empty:
                st.info(t("no_saved_lesson_plans"))
            else:
                topic_q = st.text_input(
                    t("search_by_topic"),
                    key="my_plans_topic_q"
                ).strip().lower()

                subject_options = (
                    sorted(my_df["subject"].dropna().astype(str).unique().tolist())
                    if "subject" in my_df.columns
                    else []
                )

                subject_filter = st.selectbox(
                    t("subject_label"),
                    [t("all")] + subject_options,
                    format_func=lambda x: t(f"subject_{str(x).strip().lower().replace(' ', '_')}") if x != t("all") else t("all"),
                    key="my_plans_subject_filter",
                )

                filtered = my_df.copy()

                if topic_q and "topic" in filtered.columns:
                    filtered = filtered[
                        filtered["topic"].fillna("").astype(str).str.lower().str.contains(topic_q, na=False)
                    ]

                if subject_filter != t("all") and "subject" in filtered.columns:
                    filtered = filtered[filtered["subject"].astype(str) == subject_filter]

                render_plan_library_cards(
                    filtered,
                    prefix="my_plans",
                    show_author=False,
                )

        with tab2:
            public_df = load_public_lesson_plans()

            if public_df.empty:
                st.info(t("community_library_empty"))
            else:
                topic_q_public = st.text_input(
                    t("search_community_topic"),
                    key="public_plans_topic_q"
                ).strip().lower()

                public_subject_options = (
                    sorted(public_df["subject"].dropna().astype(str).unique().tolist())
                    if "subject" in public_df.columns
                    else []
                )

                subject_filter_public = st.selectbox(
                    t("community_subject"),
                    [t("all")] + public_subject_options,
                    format_func=lambda x: t(f"subject_{str(x).strip().lower().replace(' ', '_')}") if x != t("all") else t("all"),
                    key="public_plans_subject_filter",
                )

                filtered_public = public_df.copy()

                if topic_q_public and "topic" in filtered_public.columns:
                    filtered_public = filtered_public[
                        filtered_public["topic"].fillna("").astype(str).str.lower().str.contains(topic_q_public, na=False)
                    ]

                if subject_filter_public != t("all") and "subject" in filtered_public.columns:
                    filtered_public = filtered_public[
                        filtered_public["subject"].astype(str) == subject_filter_public
                    ]

                render_plan_library_cards(
                    filtered_public,
                    prefix="community_plans",
                    show_author=True,
                )

        with tab3:
            cv_df = load_my_cvs()
            if cv_df.empty:
                st.info(t("no_saved_cvs"))
            else:
                render_cv_library_cards(cv_df, prefix="files_cv")

        with tab4:
            cl_df = load_my_cover_letters()
            if cl_df.empty:
                st.info(t("no_saved_cover_letters"))
            else:
                render_cv_library_cards(cl_df, prefix="files_cl")

        selected_plan = st.session_state.get("files_selected_plan")

        if selected_plan:
            st.markdown("---")
            detail_l, detail_r = st.columns([6, 1])

            with detail_l:
                st.markdown(f"### {t('plan_preview')}")

            with detail_r:
                if st.button(t("close_plan"), key="close_selected_plan", use_container_width=True):
                    st.session_state.pop("files_selected_plan", None)
                    st.session_state.pop("files_selected_subject", None)
                    st.session_state.pop("files_selected_stage", None)
                    st.session_state.pop("files_selected_level", None)
                    st.session_state.pop("files_selected_purpose", None)
                    st.session_state.pop("files_selected_topic", None)
                    st.session_state.pop("files_selected_source_type", None)
                    st.session_state.pop("files_selected_title", None)
                    st.rerun()

            st.session_state["quick_lesson_plan_mode_used"] = st.session_state.get("files_selected_source_type", "template")
            st.session_state["quick_lesson_plan_warning"] = None

            render_quick_lesson_plan_result(
                normalize_planner_output(selected_plan),
                subject=st.session_state.get("files_selected_subject", ""),
                learner_stage=st.session_state.get("files_selected_stage", ""),
                level_or_band=st.session_state.get("files_selected_level", ""),
                lesson_purpose=st.session_state.get("files_selected_purpose", ""),
                topic=st.session_state.get("files_selected_topic", ""),
                read_only= True,
            )

        # ── Selected CV detail ────────────────────────────────────────────
        selected_cv = st.session_state.get("files_cv_selected")
        if selected_cv:
            import json
            st.markdown("---")
            cv_det_l, cv_det_r = st.columns([6, 1])
            with cv_det_l:
                st.markdown(f"### {t('cv')}")
            with cv_det_r:
                if st.button(t("close_plan"), key="close_selected_cv", use_container_width=True):
                    st.session_state.pop("files_cv_selected", None)
                    st.rerun()
            cv_data = selected_cv.get("cv_json") or {}
            if isinstance(cv_data, str):
                try:
                    cv_data = json.loads(cv_data)
                except Exception:
                    cv_data = {}
            if cv_data:
                render_cv_result(
                    cv=cv_data,
                    read_only=True,
                    source_type=str(selected_cv.get("source_type") or "template"),
                    title=str(selected_cv.get("title") or ""),
                )

        # ── Selected cover letter detail ─────────────────────────────────
        selected_cl = st.session_state.get("files_cl_selected")
        if selected_cl:
            st.markdown("---")
            cl_det_l, cl_det_r = st.columns([6, 1])
            with cl_det_l:
                st.markdown(f"### {t('cover_letter')}")
            with cl_det_r:
                if st.button(t("close_plan"), key="close_selected_cl", use_container_width=True):
                    st.session_state.pop("files_cl_selected", None)
                    st.rerun()
            cl_content = str(selected_cl.get("content") or "")
            cl_title   = str(selected_cl.get("title") or t("cover_letter"))
            st.text_area(t("cover_letter_content"), value=cl_content, height=300, disabled=True, key="files_cl_preview")
            if cl_content:
                import re as _re
                cl_pdf = build_cover_letter_pdf_bytes(cl_content, cl_title)
                _safe = _re.sub(r"[^A-Za-z0-9._-]+", "_", cl_title) or "cover_letter"
                st.download_button(
                    label=t("download_cl_pdf"),
                    data=cl_pdf,
                    file_name=f"{_safe}.pdf",
                    mime="application/pdf",
                    key="dl_cl_files",
                    use_container_width=True,
                )

        st.markdown("</div>", unsafe_allow_html=True)
        return
    # ---------- REAL VALUES ----------
    # Load preferred currency from profile (once per session)
    if "preferred_currency" not in st.session_state and user_id:
        _prof = load_profile_row(user_id)
        st.session_state["preferred_currency"] = str(_prof.get("preferred_currency") or "TRY")

    dash = rebuild_dashboard(active_window_days=183, expiry_days=365, grace_days=35)

    active_students = 0
    if dash is not None and not dash.empty and "Status" in dash.columns:
        active_students = int(
            dash["Status"]
            .astype(str)
            .str.strip()
            .str.casefold()
            .isin(["active", "almost_finished", "mismatch"])
            .sum()
        )

    next_lesson = get_next_lesson_display()

    kpis, *_ = build_income_analytics(group="monthly")
    income_this_year = float(kpis.get("income_this_year", 0.0))

    scope = YEAR_GOAL_SCOPE
    current_year = int(ts_today_naive().year)
    goal_val = float(get_year_goal(current_year, scope=scope, default=0.0) or 0.0)

    # Convert from base currency (TRY) to user's preferred currency
    pref_cur = get_preferred_currency()
    fx_rate = get_exchange_rate("TRY", pref_cur)
    goal_display = goal_val * fx_rate
    income_display = income_this_year * fx_rate

    goal_progress = 0.0
    if goal_val > 0:
        goal_progress = max(0.0, min(1.0, income_this_year / goal_val))

    render_home_indicator(
        status=t("online"),
        badge=now_local().strftime("%d %b %Y"),
        items=[
            (t("goal"), format_currency(goal_display) if goal_val > 0 else "—"),
            (t("ytd_income"), format_currency(income_display)),
            (t("students"), str(active_students)),
            (t("next"), next_lesson),
        ],
        progress=goal_progress,
        accent="#3B82F6",
    )

    # --- Quick lesson planner expander ---
    render_quick_lesson_planner_expander()

    # --- Quick CV builder expander ---
    render_quick_cv_builder_expander()

    # --- Section title between links and menu capsules ---
    # ---------- MENU ----------
    st.markdown(
        f"""
        <div class="home-section-line">
          <span>{t("home_menu_title")}</span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    menu_items = [
        ("dashboard", t("dashboard"), "rgba(59,130,246,0.55)"),
        ("students", t("students"), "rgba(16,185,129,0.55)"),
        ("add_lesson", t("lesson"), "rgba(245,158,11,0.55)"),
        ("add_payment", t("payment"), "rgba(239,68,68,0.55)"),
        ("calendar", t("calendar"), "rgba(6,182,212,0.55)"),
        ("analytics", t("analytics"), "rgba(168,85,247,0.55)"),
    ]

    menu_rows = [
        menu_items[0:2],
        menu_items[2:4],
        menu_items[4:6],
    ]

    for row in menu_rows:
        col1, col2 = st.columns(2, gap="medium")

        for col, (key, label, glow) in zip((col1, col2), row):
            with col:
                with stylable_container(
                    key=f"menu_glow_{key}",
                    css_styles=neon_button_css(
                        glow_rgba=glow,
                        text_color="#0B1220",
                        min_height=42,
                        radius=16,
                    ),
                ):
                    if st.button(label, key=f"home_menu_{key}", use_container_width=True):
                        go_to(key)
                        st.rerun()

        st.markdown("<div style='height:8px;'></div>", unsafe_allow_html=True)

    st.markdown('<div class="home-bottom-space"></div>', unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

# =========================
