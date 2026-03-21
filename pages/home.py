import streamlit as st
import datetime
from core.i18n import t
from core.navigation import go_to, home_go, PAGES
from core.timezone import _get_qp
from core.database import load_table, load_students, clear_app_caches
from auth.auth import render_logout_button, render_profile_dialog
from styles.theme import load_css_home
from styles.theme import _is_dark
from streamlit_option_menu import option_menu
from core.database import get_profile_avatar_url
from auth.auth import sign_out_user
from core.database import load_profile_row
from helpers.lesson_planner import normalize_planner_output
from helpers.planner_storage import load_my_lesson_plans, load_public_lesson_plans, render_plan_library_cards, render_quick_lesson_plan_result, render_quick_lesson_planner_expander
from helpers.cv_storage import load_my_cvs, load_my_cover_letters, render_cv_library_cards, render_cv_result, render_quick_cv_builder_expander, build_cv_pdf_bytes, build_cover_letter_pdf_bytes
from helpers.worksheet_storage import load_my_worksheets, load_public_worksheets, render_worksheet_library_cards, render_worksheet_result, render_quick_worksheet_maker_expander
from helpers.worksheet_builder import normalize_worksheet_output
from helpers.goal_explorer import render_income_goal_calculator
from core.database import load_community_profiles

# 10) HOME SCREEN UI (DARK)
# =========================
def render_home():
    current_lang = st.session_state.get("ui_lang", "en")
    if current_lang not in ("en", "es", "tr"):
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

        default_action_index = 1 if panel == "community" else (2 if panel == "files" else 3)

        # Keep prev in sync with whatever the menu is currently showing
        if "home_action_menu_prev" not in st.session_state:
            st.session_state["home_action_menu_prev"] = t("files") if panel == "files" else (t("community") if panel == "community" else t("sign_out"))

        action = option_menu(
            menu_title=None,
            options=[t("profile"), t("community"), t("files"), t("sign_out")],
            icons=["person-circle", "people-fill", "folder2-open", "box-arrow-right"],
            orientation="horizontal",
            default_index=default_action_index,
            key=f"home_action_menu_{st.session_state.get('home_action_menu_nonce', 0)}",
            styles={
                "container": {
                    "padding": "0 !important",
                    "margin": "0 !important",
                    "background": "#0f172a" if _is_dark() else "transparent",
                },
                "nav-link": {
                    "font-size": "14px",
                    "text-align": "center",
                    "padding": "6px 8px",
                    "color": "#94a3b8" if _is_dark() else "#475569",
                    "--hover-color": "rgba(96,165,250,0.18)" if _is_dark() else "rgba(59,130,246,0.15)",
                },
                "nav-link-selected": {
                    "background": "linear-gradient(180deg, #1e3a5f, #162844)" if _is_dark() else "#3B82F6",
                    "color": "#f1f5f9",
                },
                "icon": {
                    "font-size": "16px",
                    "color": "#60A5FA" if _is_dark() else "inherit",
                },
            },
        )

        # The "default" item is effectively deselected/neutral – treat it as a no-op baseline
        default_label = t("community") if panel == "community" else (t("files") if panel == "files" else t("sign_out"))

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

        previous_action = st.session_state.get("home_action_menu_prev", t("sign_out"))

        if action != default_label:
            if action == t("profile"):
                st.session_state["show_profile_dialog"] = True
                st.session_state["home_action_menu_prev"] = t("profile")
                st.session_state["home_action_menu_nonce"] += 1
                st.session_state.pop("confirm_sign_out", None)
                st.rerun()

            elif action == t("files"):
                st.session_state["home_action_menu_prev"] = t("files")
                st.session_state.pop("confirm_sign_out", None)
                home_go("home", panel="files")
                st.rerun()

            elif action == t("community"):
                st.session_state["home_action_menu_prev"] = t("community")
                st.session_state.pop("confirm_sign_out", None)
                home_go("home", panel="community")
                st.rerun()

            elif action == t("sign_out"):
                if st.session_state.get("confirm_sign_out"):
                    st.session_state.pop("confirm_sign_out", None)
                    sign_out_user()
                else:
                    st.session_state["confirm_sign_out"] = True
                    st.session_state["home_action_menu_nonce"] += 1
                    st.rerun()     
        
    # ---------- SIGN OUT CONFIRMATION ----------
    if st.session_state.get("confirm_sign_out"):
        st.warning(t("confirm_sign_out_msg"))

    # ---------- PROFILE DIALOG ----------
    if st.session_state.get("show_profile_dialog"):
        st.session_state["show_profile_dialog"] = False
        render_profile_dialog(user_id)

    if panel == "files":
        st.markdown(f"### {t('files')}")

        tab1, tab2, tab3, tab4 = st.tabs([t("my_plans"), t("my_worksheets"), t("community_library"), t("professional")])

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
            ws_df = load_my_worksheets()
            if ws_df.empty:
                st.info(t("no_saved_worksheets"))
            else:
                ws_topic_q = st.text_input(t("search_by_topic"), key="my_ws_topic_q").strip().lower()
                ws_subj_opts = sorted(ws_df["subject"].dropna().astype(str).unique().tolist()) if "subject" in ws_df.columns else []
                ws_subj_filter = st.selectbox(
                    t("subject_label"),
                    [t("all")] + ws_subj_opts,
                    format_func=lambda x: t(f"subject_{str(x).strip().lower().replace(' ', '_')}") if x != t("all") else t("all"),
                    key="my_ws_subject_filter",
                )
                ws_filtered = ws_df.copy()
                if ws_topic_q and "topic" in ws_filtered.columns:
                    ws_filtered = ws_filtered[ws_filtered["topic"].fillna("").astype(str).str.lower().str.contains(ws_topic_q, na=False)]
                if ws_subj_filter != t("all") and "subject" in ws_filtered.columns:
                    ws_filtered = ws_filtered[ws_filtered["subject"].astype(str) == ws_subj_filter]
                render_worksheet_library_cards(ws_filtered, prefix="my_ws", show_author=False)

        with tab3:
            comm_tab_plans, comm_tab_ws = st.tabs([
                f"📝 {t('community_plans')}",
                f"📋 {t('community_worksheets')}",
            ])

            with comm_tab_plans:
                public_df = load_public_lesson_plans()

                if public_df.empty:
                    st.info(t("community_library_empty"))
                else:
                    import helpers.lesson_planner as _lp_mod
                    f_col1, f_col2 = st.columns([3, 1])
                    with f_col1:
                        topic_q_public = st.text_input(
                            t("search_by_topic"),
                            key="public_plans_topic_q",
                            placeholder="e.g. fractions, photosynthesis…",
                        ).strip().lower()
                    with f_col2:
                        _pub_subj_opts = sorted(public_df["subject"].dropna().astype(str).unique().tolist()) if "subject" in public_df.columns else []
                        subject_filter_public = st.selectbox(
                            t("subject_label"),
                            [t("all")] + _pub_subj_opts,
                            format_func=lambda x: t(f"subject_{str(x).strip().lower().replace(' ', '_')}") if x != t("all") else t("all"),
                            key="public_plans_subject_filter",
                        )

                    f_col3, f_col4, f_col5, f_col6 = st.columns(4)
                    with f_col3:
                        _stage_opts = sorted(public_df["learner_stage"].dropna().astype(str).unique().tolist()) if "learner_stage" in public_df.columns else []
                        stage_filter_public = st.selectbox(
                            t("learner_stage"),
                            [t("all")] + _stage_opts,
                            format_func=lambda x: _lp_mod._stage_label(x) if x != t("all") else t("all"),
                            key="public_plans_stage_filter",
                        )
                    with f_col4:
                        _level_opts = sorted(public_df["level_or_band"].dropna().astype(str).unique().tolist()) if "level_or_band" in public_df.columns else []
                        level_filter_public = st.selectbox(
                            t("level_or_band"),
                            [t("all")] + _level_opts,
                            format_func=lambda x: _lp_mod._level_label(x) if x != t("all") else t("all"),
                            key="public_plans_level_filter",
                        )
                    with f_col5:
                        _purpose_opts = sorted(public_df["lesson_purpose"].dropna().astype(str).unique().tolist()) if "lesson_purpose" in public_df.columns else []
                        purpose_filter_public = st.selectbox(
                            t("lesson_purpose"),
                            [t("all")] + _purpose_opts,
                            format_func=lambda x: _lp_mod._purpose_label(x) if x != t("all") else t("all"),
                            key="public_plans_purpose_filter",
                        )
                    with f_col6:
                        _src_opts = sorted(public_df["source_type"].dropna().astype(str).unique().tolist()) if "source_type" in public_df.columns else []
                        _src_label_map = {"ai": t("mode_ai"), "template": t("mode_template")}
                        source_filter_public = st.selectbox(
                            t("source_type"),
                            [t("all")] + _src_opts,
                            format_func=lambda x: _src_label_map.get(x, x) if x != t("all") else t("all"),
                            key="public_plans_source_filter",
                        )

                    filtered_public = public_df.copy()
                    if topic_q_public and "topic" in filtered_public.columns:
                        filtered_public = filtered_public[filtered_public["topic"].fillna("").astype(str).str.lower().str.contains(topic_q_public, na=False)]
                    if subject_filter_public != t("all") and "subject" in filtered_public.columns:
                        filtered_public = filtered_public[filtered_public["subject"].astype(str) == subject_filter_public]
                    if stage_filter_public != t("all") and "learner_stage" in filtered_public.columns:
                        filtered_public = filtered_public[filtered_public["learner_stage"].astype(str) == stage_filter_public]
                    if level_filter_public != t("all") and "level_or_band" in filtered_public.columns:
                        filtered_public = filtered_public[filtered_public["level_or_band"].astype(str) == level_filter_public]
                    if purpose_filter_public != t("all") and "lesson_purpose" in filtered_public.columns:
                        filtered_public = filtered_public[filtered_public["lesson_purpose"].astype(str) == purpose_filter_public]
                    if source_filter_public != t("all") and "source_type" in filtered_public.columns:
                        filtered_public = filtered_public[filtered_public["source_type"].astype(str) == source_filter_public]

                    if filtered_public.empty:
                        st.info(t("no_data"))
                    else:
                        st.caption(f"{len(filtered_public)} {t('community_plans').lower()}")
                        render_plan_library_cards(filtered_public, prefix="community_plans", show_author=True)

            with comm_tab_ws:
                pub_ws_df = load_public_worksheets()

                if pub_ws_df.empty:
                    st.info(t("community_library_empty"))
                else:
                    from helpers.worksheet_builder import WORKSHEET_TYPES as _WS_TYPES
                    import helpers.lesson_planner as _lp_mod2
                    wf_col1, wf_col2 = st.columns([3, 1])
                    with wf_col1:
                        pub_ws_topic_q = st.text_input(
                            t("search_by_topic"),
                            key="pub_ws_topic_q",
                            placeholder="e.g. fractions, vocabulary…",
                        ).strip().lower()
                    with wf_col2:
                        pub_ws_subj_opts = sorted(pub_ws_df["subject"].dropna().astype(str).unique().tolist()) if "subject" in pub_ws_df.columns else []
                        pub_ws_subj_filter = st.selectbox(
                            t("subject_label"),
                            [t("all")] + pub_ws_subj_opts,
                            format_func=lambda x: t(f"subject_{str(x).strip().lower().replace(' ', '_')}") if x != t("all") else t("all"),
                            key="pub_ws_subject_filter",
                        )

                    wf_col3, wf_col4, wf_col5, wf_col6 = st.columns(4)
                    with wf_col3:
                        _ws_stage_opts = sorted(pub_ws_df["learner_stage"].dropna().astype(str).unique().tolist()) if "learner_stage" in pub_ws_df.columns else []
                        pub_ws_stage_filter = st.selectbox(
                            t("learner_stage"),
                            [t("all")] + _ws_stage_opts,
                            format_func=lambda x: _lp_mod2._stage_label(x) if x != t("all") else t("all"),
                            key="pub_ws_stage_filter",
                        )
                    with wf_col4:
                        _ws_level_opts = sorted(pub_ws_df["level_or_band"].dropna().astype(str).unique().tolist()) if "level_or_band" in pub_ws_df.columns else []
                        pub_ws_level_filter = st.selectbox(
                            t("level_or_band"),
                            [t("all")] + _ws_level_opts,
                            format_func=lambda x: _lp_mod2._level_label(x) if x != t("all") else t("all"),
                            key="pub_ws_level_filter",
                        )
                    with wf_col5:
                        _ws_type_opts = sorted(pub_ws_df["worksheet_type"].dropna().astype(str).unique().tolist()) if "worksheet_type" in pub_ws_df.columns else []
                        pub_ws_type_filter = st.selectbox(
                            t("worksheet_type_label"),
                            [t("all")] + _ws_type_opts,
                            format_func=lambda x: t(x) if x != t("all") else t("all"),
                            key="pub_ws_type_filter",
                        )
                    with wf_col6:
                        _ws_src_opts = sorted(pub_ws_df["source_type"].dropna().astype(str).unique().tolist()) if "source_type" in pub_ws_df.columns else []
                        _ws_src_label_map = {"ai": t("mode_ai"), "template": t("mode_template")}
                        pub_ws_src_filter = st.selectbox(
                            t("source_type"),
                            [t("all")] + _ws_src_opts,
                            format_func=lambda x: _ws_src_label_map.get(x, x) if x != t("all") else t("all"),
                            key="pub_ws_src_filter",
                        )

                    pub_ws_filtered = pub_ws_df.copy()
                    if pub_ws_topic_q and "topic" in pub_ws_filtered.columns:
                        pub_ws_filtered = pub_ws_filtered[pub_ws_filtered["topic"].fillna("").astype(str).str.lower().str.contains(pub_ws_topic_q, na=False)]
                    if pub_ws_subj_filter != t("all") and "subject" in pub_ws_filtered.columns:
                        pub_ws_filtered = pub_ws_filtered[pub_ws_filtered["subject"].astype(str) == pub_ws_subj_filter]
                    if pub_ws_stage_filter != t("all") and "learner_stage" in pub_ws_filtered.columns:
                        pub_ws_filtered = pub_ws_filtered[pub_ws_filtered["learner_stage"].astype(str) == pub_ws_stage_filter]
                    if pub_ws_level_filter != t("all") and "level_or_band" in pub_ws_filtered.columns:
                        pub_ws_filtered = pub_ws_filtered[pub_ws_filtered["level_or_band"].astype(str) == pub_ws_level_filter]
                    if pub_ws_type_filter != t("all") and "worksheet_type" in pub_ws_filtered.columns:
                        pub_ws_filtered = pub_ws_filtered[pub_ws_filtered["worksheet_type"].astype(str) == pub_ws_type_filter]
                    if pub_ws_src_filter != t("all") and "source_type" in pub_ws_filtered.columns:
                        pub_ws_filtered = pub_ws_filtered[pub_ws_filtered["source_type"].astype(str) == pub_ws_src_filter]

                    if pub_ws_filtered.empty:
                        st.info(t("no_data"))
                    else:
                        st.caption(f"{len(pub_ws_filtered)} {t('community_worksheets').lower()}")
                        render_worksheet_library_cards(pub_ws_filtered, prefix="pub_ws", show_author=True)

        with tab4:
            pro_tab_cv, pro_tab_cl = st.tabs([
                f"📄 {t('my_cvs')}",
                f"✉️ {t('my_cover_letters')}",
            ])

            with pro_tab_cv:
                cv_df = load_my_cvs()
                if cv_df.empty:
                    st.info(t("no_saved_cvs"))
                else:
                    render_cv_library_cards(cv_df, prefix="files_cv")

            with pro_tab_cl:
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

        # ── Selected worksheet detail ─────────────────────────────────────
        selected_ws = st.session_state.get("files_selected_worksheet")
        if selected_ws:
            import json as _json_ws
            if isinstance(selected_ws, str):
                try:
                    selected_ws = _json_ws.loads(selected_ws)
                except Exception:
                    selected_ws = {}
            if selected_ws:
                st.markdown("---")
                ws_det_l, ws_det_r = st.columns([6, 1])
                with ws_det_l:
                    st.markdown(f"### {t('worksheet_preview')}")
                with ws_det_r:
                    if st.button(t("close_worksheet"), key="close_selected_ws", use_container_width=True):
                        for _k in ["files_selected_worksheet", "files_ws_subject", "files_ws_stage", "files_ws_level", "files_ws_type", "files_ws_topic", "files_ws_title"]:
                            st.session_state.pop(_k, None)
                        st.rerun()
                render_worksheet_result(
                    normalize_worksheet_output(selected_ws),
                    read_only=True,
                    subject=st.session_state.get("files_ws_subject", ""),
                    learner_stage=st.session_state.get("files_ws_stage", ""),
                    level_or_band=st.session_state.get("files_ws_level", ""),
                    worksheet_type=st.session_state.get("files_ws_type", ""),
                    topic=st.session_state.get("files_ws_topic", ""),
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
                _cv_close, _cv_del = st.columns(2)
                with _cv_close:
                    if st.button(t("close_cv"), key="close_selected_cv", use_container_width=True):
                        st.session_state.pop("files_cv_selected", None)
                        st.rerun()
                with _cv_del:
                    if st.button("🗑️", key="del_selected_cv", use_container_width=True, help=t("delete_cv")):
                        from helpers.cv_storage import delete_cv_record
                        _cv_id = selected_cv.get("id")
                        if _cv_id and delete_cv_record(str(_cv_id)):
                            st.session_state.pop("files_cv_selected", None)
                            st.rerun()
                        else:
                            st.error(t("delete_failed"))
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
                _cl_close, _cl_del = st.columns(2)
                with _cl_close:
                    if st.button(t("close_cover_letter"), key="close_selected_cl", use_container_width=True):
                        st.session_state.pop("files_cl_selected", None)
                        st.rerun()
                with _cl_del:
                    if st.button("🗑️", key="del_selected_cl", use_container_width=True, help=t("delete_cover_letter")):
                        from helpers.cv_storage import delete_cv_record
                        _cl_id = selected_cl.get("id")
                        if _cl_id and delete_cv_record(str(_cl_id)):
                            st.session_state.pop("files_cl_selected", None)
                            st.rerun()
                        else:
                            st.error(t("delete_failed"))
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

        st.divider()
        if st.button(t("close_files"), key="close_files_panel", use_container_width=True):
            st.session_state["home_action_menu_prev"] = t("profile")
            st.session_state["home_action_menu_nonce"] += 1
            home_go("home", panel=None)
            st.rerun()

        return

    # ---------- COMMUNITY PANEL ----------
    if panel == "community":
        import re as _re_comm
        from auth.auth import _profile_subject_label as _subj_label_fn

        st.markdown(f"### 🌐 {t('community_tab_title')}")
        st.caption(t("community_subtitle"))

        _all_profiles_raw = load_community_profiles()

        # All opted-in profiles + own entry for self-preview
        _visible = [
            p for p in _all_profiles_raw
            if p.get("show_community_profile") or p.get("user_id") == user_id
        ]

        if not _visible:
            st.info(t("community_empty"))
        else:
            # Global ranking — always sorted by active students descending
            _visible_ranked = sorted(
                _visible,
                key=lambda p: int(p.get("active_student_count") or 0),
                reverse=True,
            )
            _rank_map = {p.get("user_id"): i + 1 for i, p in enumerate(_visible_ranked)}

            # ---- build filter option lists ----
            _all_subjects: list = []
            _all_countries: list = []
            _all_edu: list = []
            for _fp in _visible_ranked:
                for s in (_fp.get("primary_subjects") or []):
                    if s and s not in _all_subjects:
                        _all_subjects.append(s)
                _fc = str(_fp.get("country") or "").strip()
                if _fc and _fc not in _all_countries:
                    _all_countries.append(_fc)
                _fe = str(_fp.get("education_level") or "").strip()
                if _fe and _fe not in _all_edu:
                    _all_edu.append(_fe)
            _all_subjects = sorted(_all_subjects)
            _all_countries = sorted(_all_countries)
            _all_edu = sorted(_all_edu)

            # ---- filter widgets ----
            fc1, fc2, fc3 = st.columns(3)
            with fc1:
                _subj_sel = st.selectbox(
                    t("community_filter_subject"),
                    [t("all")] + _all_subjects,
                    format_func=lambda x: _subj_label_fn(x) if x != t("all") else t("all"),
                    key="community_subject_filter",
                )
            with fc2:
                _country_sel = st.selectbox(
                    t("country_label"),
                    [t("all")] + _all_countries,
                    key="community_country_filter",
                )
            with fc3:
                _edu_sel = st.selectbox(
                    t("education_level"),
                    [t("all")] + _all_edu,
                    format_func=lambda x: t(x) if x != t("all") else t("all"),
                    key="community_edu_filter",
                )

            # ---- apply filters (retain ranking order) ----
            _any_filter = (
                _subj_sel != t("all")
                or _country_sel != t("all")
                or _edu_sel != t("all")
            )
            _filtered = _visible_ranked
            if _subj_sel != t("all"):
                _filtered = [p for p in _filtered if _subj_sel in (p.get("primary_subjects") or [])]
            if _country_sel != t("all"):
                _filtered = [p for p in _filtered if str(p.get("country") or "").strip() == _country_sel]
            if _edu_sel != t("all"):
                _filtered = [p for p in _filtered if str(p.get("education_level") or "").strip() == _edu_sel]

            # Default (no filters): top 10; with filters: all results
            _display = _filtered if _any_filter else _filtered[:10]

            if not _display:
                st.info(t("community_empty"))
            else:
                if not _any_filter:
                    st.caption(t("community_top10_hint"))
                else:
                    st.caption(f"{len(_display)} teachers")

                # ---- contact button helper & SVG paths (defined once outside loop) ----
                def _contact_btn(href: str, svg_path: str, color: str, label: str) -> str:
                    return (
                        f"<a href='{href}' target='_blank' rel='noopener noreferrer' "
                        f"title='{label}' style='display:inline-flex;align-items:center;justify-content:center;"
                        f"width:30px;height:30px;border-radius:50%;background:{color};text-decoration:none;'>"
                        f"<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='white' width='15' height='15'>{svg_path}</svg>"
                        f"</a>"
                    )

                _wa_svg = "<path d='M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347z'/><path d='M12 0C5.373 0 0 5.373 0 12c0 2.127.558 4.126 1.535 5.857L0 24l6.335-1.506A11.955 11.955 0 0012 24c6.627 0 12-5.373 12-12S18.627 0 12 0zm0 21.818a9.777 9.777 0 01-4.988-1.365l-.358-.214-3.761.894.952-3.653-.233-.374A9.772 9.772 0 012.182 12C2.182 6.57 6.57 2.182 12 2.182S21.818 6.57 21.818 12 17.43 21.818 12 21.818z'/>"
                _email_svg = "<path d='M20 4H4c-1.1 0-2 .9-2 2v12c0 1.1.9 2 2 2h16c1.1 0 2-.9 2-2V6c0-1.1-.9-2-2-2zm0 4l-8 5-8-5V6l8 5 8-5v2z'/>"

                for _p in _display:
                    _is_self = _p.get("user_id") == user_id
                    _show_full = bool(_p.get("show_community_profile")) or _is_self
                    _show_contact = bool(_p.get("show_community_contact")) or _is_self

                    _rank = _rank_map.get(_p.get("user_id"), "")
                    _display_name = str(_p.get("display_name") or "").strip() or "—"
                    _active_count = int(_p.get("active_student_count") or 0)
                    _subjects = _p.get("primary_subjects") or []
                    _subj_labels = ", ".join([_subj_label_fn(s) for s in _subjects]) if _subjects else "—"
                    _country = str(_p.get("country") or "").strip()
                    _edu = str(_p.get("education_level") or "").strip()
                    _raw_phone = str(_p.get("phone_number") or "").strip()
                    _wa_num = _re_comm.sub(r"[^\d+]", "", _raw_phone)
                    _email = str(_p.get("email") or "").strip()
                    _avatar = str(_p.get("avatar_url") or "").strip()

                    _edu_display = t(_edu) if _edu else ""
                    _badge_self = f"<span style='background:#3B82F6;color:#fff;border-radius:6px;padding:2px 8px;font-size:0.72rem;margin-left:6px;'>You</span>" if _is_self else ""
                    _rank_html = f"<div style='font-size:0.85rem;font-weight:800;color:#f59e0b;min-width:26px;text-align:center;padding-top:16px;align-self:flex-start;'>#{_rank}</div>" if _rank else ""

                    if _show_full:
                        _avatar_html = (
                            f"<img src='{_avatar}' style='width:52px;height:52px;border-radius:50%;object-fit:cover;flex-shrink:0;' referrerpolicy='no-referrer' />"
                            if _avatar
                            else "<div style='width:52px;height:52px;border-radius:50%;flex-shrink:0;background:linear-gradient(135deg,#60A5FA,#A78BFA);'></div>"
                        )
                        _contact_html = ""
                        if _country:
                            _contact_html += f"<span style='font-size:0.82rem;color:#64748b;'>🌍 {_country}</span>"
                        if _show_contact:
                            _btns = ""
                            if _wa_num:
                                _btns += _contact_btn(f"https://wa.me/{_wa_num.lstrip('+')}", _wa_svg, "#25D366", "WhatsApp")
                            if _email:
                                _btns += _contact_btn(f"mailto:{_email}", _email_svg, "#3B82F6", "Email")
                            if _btns:
                                _contact_html += f"<span style='margin-left:8px;display:inline-flex;gap:6px;vertical-align:middle;'>{_btns}</span>"
                        if _contact_html:
                            _contact_html = f"<div style='margin-top:5px;display:flex;align-items:center;flex-wrap:wrap;gap:4px;'>{_contact_html}</div>"

                        st.markdown(
                            f"""
                            <div style='display:flex;align-items:flex-start;gap:10px;background:#1e293b;border-radius:12px;padding:14px 16px;margin-bottom:10px;border:1px solid #334155;'>
                                {_rank_html}
                                {_avatar_html}
                                <div style='flex:1;min-width:0;'>
                                    <div style='font-weight:700;font-size:1rem;color:#f1f5f9;'>{_display_name}{_badge_self}</div>
                                    <div style='font-size:0.82rem;color:#94a3b8;margin-top:2px;'>{_subj_labels}</div>
                                    <div style='display:flex;gap:14px;margin-top:6px;flex-wrap:wrap;'>
                                        <div style='font-size:0.82rem;color:#38bdf8;'>👥 {_active_count} {t('community_active_students')}</div>
                                        {(f"<div style='font-size:0.82rem;color:#a78bfa;'>🎓 {_edu_display}</div>") if _edu_display else ""}
                                    </div>
                                    {_contact_html}
                                </div>
                            </div>
                            """,
                            unsafe_allow_html=True,
                        )
                    else:
                        st.markdown(
                            f"""
                            <div style='display:flex;align-items:center;gap:10px;background:#1e293b;border-radius:12px;padding:12px 16px;margin-bottom:10px;border:1px solid #334155;opacity:0.75;'>
                                {_rank_html}
                                <div style='width:40px;height:40px;border-radius:50%;flex-shrink:0;background:linear-gradient(135deg,#334155,#475569);display:flex;align-items:center;justify-content:center;color:#94a3b8;font-size:1.1rem;'>👤</div>
                                <div style='flex:1;min-width:0;'>
                                    <div style='font-weight:600;font-size:0.93rem;color:#cbd5e1;'>{_display_name}</div>
                                    <div style='font-size:0.8rem;color:#64748b;'>{_subj_labels}</div>
                                    <div style='font-size:0.8rem;color:#38bdf8;margin-top:3px;'>👥 {_active_count} {t('community_active_students')}</div>
                                </div>
                                <div style='font-size:0.72rem;color:#475569;white-space:nowrap;'>{t('community_private_user')}</div>
                            </div>
                            """,
                            unsafe_allow_html=True,
                        )

        st.divider()
        if st.button(t("close_community"), key="close_community_panel", use_container_width=True):
            st.session_state["home_action_menu_prev"] = t("profile")
            st.session_state["home_action_menu_nonce"] += 1
            home_go("home", panel=None)
            st.rerun()

        return

    # ---------- AI TOOLS PANEL ----------
    if panel == "ai_tools":
        st.markdown(f"### 🤖 {t('ai_tools')}")

        # --- Lesson Planner ---
        render_quick_lesson_planner_expander()

        # --- Worksheet Maker ---
        render_quick_worksheet_maker_expander()

        # --- CV Builder ---
        render_quick_cv_builder_expander()

        # --- Income Goal Calculator ---
        render_income_goal_calculator()

        st.divider()
        if st.button(t("close"), key="close_ai_tools_panel", use_container_width=True):
            home_go("home", panel=None)
            st.rerun()

        return

    # ---------- REAL VALUES ----------
    # Load preferred currency from profile (once per session)
    if "preferred_currency" not in st.session_state and user_id:
        _prof = load_profile_row(user_id)
        st.session_state["preferred_currency"] = str(_prof.get("preferred_currency") or "TRY")

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
        ("dashboard",   "📊", t("dashboard"),  "rgba(59,130,246,0.55)", t("explore_feat_dashboard")),
        ("students",    "👩‍🎓", t("students"),   "rgba(16,185,129,0.55)", t("explore_feat_students")),
        ("add_lesson",  "📝", t("lesson"),     "rgba(245,158,11,0.55)", t("explore_feat_lesson")),
        ("add_payment", "💳", t("payment"),    "rgba(239,68,68,0.55)",  t("explore_feat_payment")),
        ("calendar",    "📅", t("calendar"),   "rgba(6,182,212,0.55)",  t("explore_feat_calendar")),
        ("analytics",   "📈", t("analytics"),  "rgba(168,85,247,0.55)", t("explore_feat_analytics")),
        ("ai_tools",    "🤖", t("ai_tools"),   "rgba(234,179,8,0.55)",  t("ai_tools")),
        ("community",   "🌐", t("community"),  "rgba(20,184,166,0.55)", t("community_subtitle")),
    ]

    menu_rows = [
        menu_items[0:2],
        menu_items[2:4],
        menu_items[4:6],
        menu_items[6:8],
    ]

    for row in menu_rows:
        cols = st.columns(len(row), gap="medium")
        for col, (key, icon, label, glow, desc) in zip(cols, row):
            with col:
                st.markdown(
                    f"""
                    <div style="
                        background: linear-gradient(180deg, var(--panel, rgba(255,255,255,0.92)), var(--panel-2, rgba(248,250,255,0.85)));
                        border: 1px solid var(--border-strong, rgba(17,24,39,0.08));
                        border-radius: 16px;
                        padding: 16px 12px 10px 12px;
                        text-align: center;
                        box-shadow: 0 4px 18px {glow};
                        min-height: 90px;
                    ">
                        <div style="font-size:1.6rem; margin-bottom:4px;">{icon}</div>
                        <div style="font-weight:700; font-size:0.95rem; color:var(--text, #0f172a);">{label}</div>
                        <div style="font-size:0.78rem; color:var(--muted, #64748b); margin-top:2px;">{desc}</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
                if key == "ai_tools":
                    if st.button(label, key="home_menu_ai_tools", use_container_width=True):
                        home_go("home", panel="ai_tools")
                        st.rerun()
                elif key == "community":
                    if st.button(label, key="home_menu_community", use_container_width=True):
                        home_go("home", panel="community")
                        st.rerun()
                else:
                    if st.button(label, key=f"home_menu_{key}", use_container_width=True):
                        go_to(key)
                        st.rerun()
        st.markdown("<div style='height:6px;'></div>", unsafe_allow_html=True)

    st.markdown('<div class="home-bottom-space"></div>', unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

# =========================
