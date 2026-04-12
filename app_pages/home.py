import streamlit as st
import datetime
from core.i18n import t
from core.state import get_current_user_id
from core.navigation import go_to, home_go, PAGES
from core.timezone import _get_qp
from core.database import load_table, load_students, clear_app_caches, profile_can_teach
from auth.auth import render_logout_button, render_profile_dialog, render_choose_username_dialog, render_choose_role_dialog
from styles.theme import load_css_home
from styles.theme import load_css_home
from streamlit_option_menu import option_menu
from core.database import get_profile_avatar_url
from auth.auth import sign_out_user
from core.database import load_profile_row
from helpers.lesson_planner import normalize_planner_output, subject_label as _subject_label_fn, normalize_subject as _normalize_subject
from helpers.planner_storage import load_my_lesson_plans, load_public_lesson_plans, render_plan_library_cards, render_quick_lesson_plan_result, render_quick_lesson_planner_expander
from helpers.cv_storage import load_my_cvs, load_my_cover_letters, render_cv_library_cards, render_cv_result, render_quick_cv_builder_expander, build_cv_pdf_bytes, build_cover_letter_pdf_bytes
from helpers.worksheet_storage import load_my_worksheets, load_public_worksheets, render_worksheet_library_cards, render_worksheet_result, render_quick_worksheet_maker_expander
from helpers.worksheet_builder import normalize_worksheet_output
from helpers.goal_explorer import render_income_goal_calculator
from helpers.quick_exam_storage import render_quick_exam_builder_expander, load_my_exams, load_public_exams, render_exam_library_cards, render_exam_result
from helpers.learning_programs import (
    load_learning_program,
    load_my_learning_programs,
    load_public_learning_programs,
    update_learning_program_visibility,
    render_learning_program_assignment_panel,
    render_learning_program_library_cards,
    render_quick_learning_program_builder_expander,
    render_saved_learning_program_workspace,
    render_teacher_program_view,
)
from core.database import load_community_profiles
from helpers.goal_explorer import _rank_search
import streamlit as st
import streamlit.components.v1 as components

def inject_loading_screen():
    st.markdown(
        """
        <style>
        /* Full-screen splash */
        #app-preloader {
            position: fixed;
            inset: 0;
            z-index: 999999;
            display: flex;
            align-items: center;
            justify-content: center;
            flex-direction: column;
            gap: 14px;
            background:
                radial-gradient(circle at top left, rgba(59,130,246,0.16), transparent 35%),
                radial-gradient(circle at top right, rgba(16,185,129,0.10), transparent 30%),
                linear-gradient(180deg, #0f172a 0%, #111827 100%);
            color: #f8fafc;
            transition: opacity 0.35s ease, visibility 0.35s ease;
        }

        #app-preloader.hide {
            opacity: 0;
            visibility: hidden;
            pointer-events: none;
        }

        .preloader-logo {
            font-size: 1.6rem;
            font-weight: 800;
            letter-spacing: 0.04em;
        }

        .preloader-sub {
            font-size: 0.95rem;
            color: rgba(241,245,249,0.78);
        }

        .preloader-spinner {
            width: 56px;
            height: 56px;
            border-radius: 50%;
            border: 4px solid rgba(255,255,255,0.12);
            border-top-color: #60A5FA;
            animation: app-spin 0.9s linear infinite;
            box-shadow: 0 0 30px rgba(96,165,250,0.18);
        }

        @keyframes app-spin {
            to { transform: rotate(360deg); }
        }
        </style>

        <div id="app-preloader">
            <div class="preloader-spinner"></div>
            <div class="preloader-logo">Classio</div>
            <div class="preloader-sub">Loading your workspace...</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    components.html(
        """
        <script>
        function hidePreloader() {
            const p = window.parent.document.getElementById("app-preloader");
            if (p) p.classList.add("hide");
        }

        // Hide after page settles a bit
        window.addEventListener("load", () => {
            setTimeout(hidePreloader, 500);
        });

        // Fallback in case load fires earlier/later in Streamlit
        setTimeout(hidePreloader, 1200);
        </script>
        """,
        height=0,
    )

def _render_restore_dialog(user_id: str) -> None:
    """Show a dialog for users whose account was soft-deleted within 90 days."""
    from core.database import check_deleted_account, restore_deleted_account

    info = check_deleted_account(user_id)
    if not info:
        return

    deleted_at_raw = str(info.get("deleted_at") or "")
    try:
        from datetime import datetime as _dt, timezone as _tz
        deleted_dt = _dt.fromisoformat(deleted_at_raw.replace("Z", "+00:00"))
        days_elapsed = (_dt.now(_tz.utc) - deleted_dt).days
        days_left = max(90 - days_elapsed, 0)
        deleted_date_str = deleted_dt.strftime("%Y-%m-%d")
    except Exception:
        days_left = 90
        deleted_date_str = "—"

    if days_left <= 0:
        # Past 90 days — wipe old profile and start fresh
        restore_deleted_account(user_id)
        return

    @st.dialog(t("restore_account_title"))
    def _restore_dlg():
        msg = t("restore_account_msg").format(date=deleted_date_str, days=days_left)
        st.info(msg)

        col1, col2 = st.columns(2)
        with col1:
            if st.button(t("restore_account_btn"), key="btn_restore_yes", use_container_width=True, type="primary"):
                restore_deleted_account(user_id)
                st.success(t("account_restored"))
                st.session_state["show_profile_dialog"] = True
                import time; time.sleep(1)
                st.rerun()
        with col2:
            if st.button(t("restore_account_cancel"), key="btn_restore_no", use_container_width=True):
                sign_out_user()

    _restore_dlg()

# TEACHING RESOURCES PREVIEW 
# =========================
def render_home_teaching_resources_preview():
    st.markdown(
        f"""
        <div class="home-section-line">
          <span>{t("teaching_resources")}</span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    res_tab0, res_tab1, res_tab2, res_tab3 = st.tabs([
        "📚 Learning Programs",
        f"📝 {t('community_plans')}",
        f"📋 {t('community_worksheets')}",
        f"📄 {t('community_exams')}",
    ])

    with res_tab0:
        public_program_df = load_public_learning_programs()

        if public_program_df.empty:
            st.info(t("community_library_empty"))
        else:
            program_q = st.text_input(
                t("explore_resource_search"),
                key="home_public_learning_programs_q",
                placeholder=t("explore_resource_search_placeholder"),
            ).strip().lower()

            filtered_programs = public_program_df.copy()
            if program_q:
                for col in ["title", "subject", "custom_subject_name", "learner_stage", "level_or_band", "program_overview"]:
                    if col not in filtered_programs.columns:
                        filtered_programs[col] = ""
                mask = (
                    filtered_programs["title"].fillna("").astype(str).str.lower().str.contains(program_q, na=False)
                    | filtered_programs["subject"].fillna("").astype(str).str.lower().str.contains(program_q, na=False)
                    | filtered_programs["custom_subject_name"].fillna("").astype(str).str.lower().str.contains(program_q, na=False)
                    | filtered_programs["learner_stage"].fillna("").astype(str).str.lower().str.contains(program_q, na=False)
                    | filtered_programs["level_or_band"].fillna("").astype(str).str.lower().str.contains(program_q, na=False)
                    | filtered_programs["program_overview"].fillna("").astype(str).str.lower().str.contains(program_q, na=False)
                )
                filtered_programs = filtered_programs[mask]

            if "updated_at" in filtered_programs.columns:
                filtered_programs = filtered_programs.sort_values("updated_at", ascending=False)

            programs_to_show = filtered_programs if program_q else filtered_programs.head(4)

            if programs_to_show.empty:
                st.info(t("be_the_first_to_share"))
            else:
                if program_q:
                    st.caption(t("learning_programs_count", count=len(programs_to_show)))
                else:
                    st.caption(t("explore_latest_resources_note").format(count=4))
                render_learning_program_library_cards(
                    programs_to_show,
                    prefix="home_public_learning_programs",
                    show_author=True,
                    allow_visibility_toggle=False,
                )

            if st.button(t("see_all_learning_programs"), key="home_see_all_learning_programs", use_container_width=True):
                home_go("home", panel="files")
                st.rerun()

    # =========================
    # LESSON PLANS
    # =========================
    with res_tab1:
        public_df = load_public_lesson_plans()

        if public_df.empty:
            st.info(t("community_library_empty"))
        else:
            plan_q = st.text_input(
                t("explore_resource_search"),
                key="home_public_plans_q",
                placeholder=t("explore_resource_search_placeholder"),
            ).strip()

            if plan_q:
                filtered_plans = _rank_search(
                    public_df,
                    plan_q,
                    weights={
                        "title": 5,
                        "topic": 4,
                        "subject": 3,
                        "lesson_purpose": 3,
                        "learner_stage": 2,
                        "level_or_band": 2,
                        "author_name": 1,
                    },
                )
            else:
                filtered_plans = public_df.copy()

            if "created_at" in filtered_plans.columns:
                filtered_plans = filtered_plans.sort_values("created_at", ascending=False)

            plans_to_show = filtered_plans if plan_q else filtered_plans.head(4)

            if plans_to_show.empty:
                st.info(t("be_the_first_to_share"))
            else:
                if plan_q:
                    st.caption(f"{len(plans_to_show)} {t('community_plans').lower()}")
                else:
                    st.caption(t("explore_latest_resources_note").format(count=4))

                render_plan_library_cards(
                    plans_to_show,
                    prefix="home_public_plans",
                    show_author=True,
                    open_in_files=True,
                )

            if st.button(t("see_all_lesson_plans"), key="home_see_all_plans", use_container_width=True):
                home_go("home", panel="files")
                st.rerun()

    # =========================
    # WORKSHEETS
    # =========================
    with res_tab2:
        public_ws_df = load_public_worksheets()

        if public_ws_df.empty:
            st.info(t("community_library_empty"))
        else:
            ws_q = st.text_input(
                t("explore_resource_search"),
                key="home_public_ws_q",
                placeholder=t("explore_resource_search_placeholder"),
            ).strip()

            if ws_q:
                filtered_ws = _rank_search(
                    public_ws_df,
                    ws_q,
                    weights={
                        "title": 5,
                        "topic": 4,
                        "subject": 3,
                        "worksheet_type": 3,
                        "learner_stage": 2,
                        "level_or_band": 2,
                        "author_name": 1,
                    },
                )
            else:
                filtered_ws = public_ws_df.copy()

            if "created_at" in filtered_ws.columns:
                filtered_ws = filtered_ws.sort_values("created_at", ascending=False)

            ws_to_show = filtered_ws if ws_q else filtered_ws.head(4)

            if ws_to_show.empty:
                st.info(t("be_the_first_to_share"))
            else:
                if ws_q:
                    st.caption(f"{len(ws_to_show)} {t('community_worksheets').lower()}")
                else:
                    st.caption(t("explore_latest_resources_note").format(count=4))

                render_worksheet_library_cards(
                    ws_to_show,
                    prefix="home_public_ws",
                    show_author=True,
                    open_in_files=True,
                )

            if st.button(t("see_all_worksheets"), key="home_see_all_ws", use_container_width=True):
                home_go("home", panel="files")
                st.rerun()

    # =========================
    # EXAMS
    # =========================
    with res_tab3:
        public_exam_df = load_public_exams()

        if public_exam_df.empty:
            st.info(t("community_library_empty"))
        else:
            exam_q = st.text_input(
                t("explore_resource_search"),
                key="home_public_exam_q",
                placeholder=t("explore_resource_search_placeholder"),
            ).strip()

            if exam_q:
                filtered_exams = _rank_search(
                    public_exam_df,
                    exam_q,
                    weights={
                        "title": 5,
                        "topic": 4,
                        "subject": 3,
                        "learner_stage": 2,
                        "level": 2,
                        "author_name": 1,
                    },
                )
            else:
                filtered_exams = public_exam_df.copy()

            if "created_at" in filtered_exams.columns:
                filtered_exams = filtered_exams.sort_values("created_at", ascending=False)

            exams_to_show = filtered_exams if exam_q else filtered_exams.head(4)

            if exams_to_show.empty:
                st.info(t("be_the_first_to_share"))
            else:
                if exam_q:
                    st.caption(f"{len(exams_to_show)} {t('community_exams').lower()}")
                else:
                    st.caption(t("explore_latest_resources_note").format(count=4))

                render_exam_library_cards(
                    exams_to_show,
                    prefix="home_public_exams",
                    show_author=True,
                    open_in_files=True,
                )

            if st.button(t("see_all_exams"), key="home_see_all_exams", use_container_width=True):
                home_go("home", panel="files")
                st.rerun()

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

    # ---------- CHOOSE ROLE DIALOG (new users — must run BEFORE welcome page) ----------
    if st.session_state.get("show_choose_role_dialog"):
        st.session_state["show_choose_role_dialog"] = False
        render_choose_role_dialog(user_id)
        return

    # ---------- WELCOME PAGE ----------
    from app_pages.render_home_welcome import render_home_welcome

    if panel in ("", None):
        if render_home_welcome(user_name):
            return
    
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

        default_action_index = 2 if panel == "files" else 1

        if "home_action_menu_prev" not in st.session_state:
            st.session_state["home_action_menu_prev"] = t("files") if panel == "files" else t("home")

        default_label = t("files") if panel == "files" else t("home")

        action = option_menu(
            menu_title=None,
            options=[t("profile"), t("home"), t("files"), t("sign_out")],
            icons=["person-circle", "house", "folder2-open", "box-arrow-right"],
            orientation="horizontal",
            default_index=default_action_index,
            key=f"home_action_menu_{st.session_state.get('home_action_menu_nonce', 0)}",
            styles={
                "container": {
                    "padding": "0 !important",
                    "margin": "0 !important",
                    "background": "var(--panel)",
                    "border": "1px solid var(--border)",
                    "border-radius": "14px",
                },
                "nav-link": {
                    "font-size": "14px",
                    "text-align": "center",
                    "padding": "6px 8px",
                    "color": "var(--muted)",
                    "--hover-color": "var(--panel-soft)",
                },
                "nav-link-selected": {
                    "background": "var(--primary)",
                    "color": "#f1f5f9",
                },
                "icon": {
                    "font-size": "16px",
                    "color": "var(--primary-light)",
                },
            },
        )


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

            elif action == t("home"):
                st.session_state["home_action_menu_prev"] = t("home")
                st.session_state.pop("confirm_sign_out", None)
                home_go("home", panel=None)
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

    # ---------- CHOOSE USERNAME DIALOG ----------
    if st.session_state.get("show_choose_username_dialog"):
        st.session_state["show_choose_username_dialog"] = False
        render_choose_username_dialog(user_id)

    # ---------- PROFILE DIALOG ----------
    if st.session_state.get("show_profile_dialog"):
        st.session_state["show_profile_dialog"] = False
        render_profile_dialog(user_id)

    # ---------- RESTORE ACCOUNT DIALOG ----------
    if st.session_state.get("_show_restore_dialog"):
        st.session_state["_show_restore_dialog"] = False
        _render_restore_dialog(user_id)

    if panel != "files" and st.session_state.get("home_public_learning_programs_selected_program_id"):
        home_go("home", panel="files")
        st.rerun()

    if panel == "files":

        head_left, head_right = st.columns([6, 1], vertical_alignment="center")

        with head_left:
            st.markdown (f"### 📁 {t('files')}")
        with head_right:
            if st.button(t("close"), key="close_files_panel_top", help=t("close_files"), use_container_width=True):
                st.session_state["home_action_menu_prev"] = t("home")
                st.session_state["home_action_menu_nonce"] += 1
                home_go("home", panel=None)
                st.rerun()

        tab_prog, tab1, tab2, tab_exams, tab3, tab4 = st.tabs([t("my_programs"), t("my_plans"), t("my_worksheets"), t("my_exams"), t("community_library"), t("professional")])

        with tab_prog:
            prog_df = load_my_learning_programs()
            if prog_df.empty:
                st.info(t("no_my_learning_programs"))
            else:
                prog_q = st.text_input(t("search_learning_programs"), key="my_programs_q").strip().lower()
                prog_subj_opts = (
                    sorted(
                        set(_normalize_subject(s) for s in prog_df["subject"].dropna().astype(str) if _normalize_subject(s))
                    )
                    if "subject" in prog_df.columns
                    else []
                )
                prog_subj_filter = st.selectbox(
                    t("subject_label"),
                    [t("all")] + prog_subj_opts,
                    format_func=lambda x: _subject_label_fn(x) if x != t("all") else t("all"),
                    key="my_programs_subject_filter",
                )
                p_col1, p_col2 = st.columns(2)
                with p_col1:
                    prog_stage_opts = sorted(prog_df["learner_stage"].dropna().astype(str).unique().tolist()) if "learner_stage" in prog_df.columns else []
                    prog_stage_filter = st.selectbox(
                        t("learner_stage"),
                        [t("all")] + prog_stage_opts,
                        format_func=lambda x: t(x) if x != t("all") else t("all"),
                        key="my_programs_stage_filter",
                    )
                with p_col2:
                    prog_level_opts = sorted(prog_df["level_or_band"].dropna().astype(str).unique().tolist()) if "level_or_band" in prog_df.columns else []
                    prog_level_filter = st.selectbox(
                        t("level_or_band"),
                        [t("all")] + prog_level_opts,
                        format_func=lambda x: x if x in ("A1", "A2", "B1", "B2", "C1", "C2") else t(x) if x != t("all") else t("all"),
                        key="my_programs_level_filter",
                    )
                prog_filtered = prog_df.copy()
                if prog_q:
                    for col in ["title", "program_overview", "custom_subject_name", "subject", "learner_stage", "level_or_band"]:
                        if col not in prog_filtered.columns:
                            prog_filtered[col] = ""
                    prog_filtered = prog_filtered[
                        prog_filtered["title"].fillna("").astype(str).str.lower().str.contains(prog_q, na=False)
                        | prog_filtered["program_overview"].fillna("").astype(str).str.lower().str.contains(prog_q, na=False)
                        | prog_filtered["custom_subject_name"].fillna("").astype(str).str.lower().str.contains(prog_q, na=False)
                        | prog_filtered["subject"].fillna("").astype(str).str.lower().str.contains(prog_q, na=False)
                        | prog_filtered["learner_stage"].fillna("").astype(str).str.lower().str.contains(prog_q, na=False)
                        | prog_filtered["level_or_band"].fillna("").astype(str).str.lower().str.contains(prog_q, na=False)
                    ]
                if prog_subj_filter != t("all") and "subject" in prog_filtered.columns:
                    prog_filtered = prog_filtered[prog_filtered["subject"].astype(str).apply(_normalize_subject) == prog_subj_filter]
                if prog_stage_filter != t("all") and "learner_stage" in prog_filtered.columns:
                    prog_filtered = prog_filtered[prog_filtered["learner_stage"].astype(str) == prog_stage_filter]
                if prog_level_filter != t("all") and "level_or_band" in prog_filtered.columns:
                    prog_filtered = prog_filtered[prog_filtered["level_or_band"].astype(str) == prog_level_filter]
                render_learning_program_library_cards(prog_filtered, prefix="my_learning_programs", show_author=False, allow_visibility_toggle=True)

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
                    sorted(set(_normalize_subject(s) for s in my_df["subject"].dropna().astype(str) if _normalize_subject(s)))
                    if "subject" in my_df.columns
                    else []
                )

                subject_filter = st.selectbox(
                    t("subject_label"),
                    [t("all")] + subject_options,
                    format_func=lambda x: _subject_label_fn(x) if x != t("all") else t("all"),
                    key="my_plans_subject_filter",
                )

                filtered = my_df.copy()

                if topic_q and "topic" in filtered.columns:
                    filtered = filtered[
                        filtered["topic"].fillna("").astype(str).str.lower().str.contains(topic_q, na=False)
                    ]

                if subject_filter != t("all") and "subject" in filtered.columns:
                    filtered = filtered[filtered["subject"].astype(str).apply(_normalize_subject) == subject_filter]

                if filtered.empty:
                    st.info(t("no_data"))
                else:
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
                ws_subj_opts = sorted(set(_normalize_subject(s) for s in ws_df["subject"].dropna().astype(str) if _normalize_subject(s))) if "subject" in ws_df.columns else []
                ws_subj_filter = st.selectbox(
                    t("subject_label"),
                    [t("all")] + ws_subj_opts,
                    format_func=lambda x: _subject_label_fn(x) if x != t("all") else t("all"),
                    key="my_ws_subject_filter",
                )
                ws_filtered = ws_df.copy()
                if ws_topic_q and "topic" in ws_filtered.columns:
                    ws_filtered = ws_filtered[ws_filtered["topic"].fillna("").astype(str).str.lower().str.contains(ws_topic_q, na=False)]
                if ws_subj_filter != t("all") and "subject" in ws_filtered.columns:
                    ws_filtered = ws_filtered[ws_filtered["subject"].astype(str).apply(_normalize_subject) == ws_subj_filter]
                render_worksheet_library_cards(ws_filtered, prefix="my_ws", show_author=False)

        with tab_exams:
            exam_df = load_my_exams()
            if exam_df.empty:
                st.info(t("no_saved_exams"))
            else:
                exam_topic_q = st.text_input(t("search_by_topic"), key="my_exam_topic_q").strip().lower()
                exam_subj_opts = sorted(set(_normalize_subject(s) for s in exam_df["subject"].dropna().astype(str) if _normalize_subject(s))) if "subject" in exam_df.columns else []
                exam_subj_filter = st.selectbox(
                    t("subject_label"),
                    [t("all")] + exam_subj_opts,
                    format_func=lambda x: _subject_label_fn(x) if x != t("all") else t("all"),
                    key="my_exam_subject_filter",
                )
                exam_filtered = exam_df.copy()
                if exam_topic_q and "topic" in exam_filtered.columns:
                    exam_filtered = exam_filtered[exam_filtered["topic"].fillna("").astype(str).str.lower().str.contains(exam_topic_q, na=False)]
                if exam_subj_filter != t("all") and "subject" in exam_filtered.columns:
                    exam_filtered = exam_filtered[exam_filtered["subject"].astype(str).apply(_normalize_subject) == exam_subj_filter]
                render_exam_library_cards(exam_filtered, prefix="my_exams", show_author=False)

        with tab3:
            comm_tab_programs, comm_tab_plans, comm_tab_ws, comm_tab_exams = st.tabs([
                f"📚 {t('learning_programs')}",
                f"📝 {t('community_plans')}",
                f"📋 {t('community_worksheets')}",
                f"📄 {t('community_exams')}",
            ])

            with comm_tab_programs:
                public_program_df = load_public_learning_programs()
                if public_program_df.empty:
                    st.info(t("community_library_empty"))
                else:
                    pf_col1, pf_col2 = st.columns([3, 1])
                    with pf_col1:
                        public_program_q = st.text_input(
                            t("search_learning_programs"),
                            key="public_learning_program_q",
                            placeholder=t("learning_program_search_placeholder"),
                        ).strip().lower()
                    with pf_col2:
                        public_program_subj_opts = sorted(
                            set(_normalize_subject(s) for s in public_program_df["subject"].dropna().astype(str) if _normalize_subject(s))
                        ) if "subject" in public_program_df.columns else []
                        public_program_subj_filter = st.selectbox(
                            t("subject_label"),
                            [t("all")] + public_program_subj_opts,
                            format_func=lambda x: _subject_label_fn(x) if x != t("all") else t("all"),
                            key="public_learning_program_subject_filter",
                        )
                    pf_col3, pf_col4 = st.columns(2)
                    with pf_col3:
                        public_program_stage_opts = sorted(public_program_df["learner_stage"].dropna().astype(str).unique().tolist()) if "learner_stage" in public_program_df.columns else []
                        public_program_stage_filter = st.selectbox(
                            t("learner_stage"),
                            [t("all")] + public_program_stage_opts,
                            format_func=lambda x: t(x) if x != t("all") else t("all"),
                            key="public_learning_program_stage_filter",
                        )
                    with pf_col4:
                        public_program_level_opts = sorted(public_program_df["level_or_band"].dropna().astype(str).unique().tolist()) if "level_or_band" in public_program_df.columns else []
                        public_program_level_filter = st.selectbox(
                            t("level_or_band"),
                            [t("all")] + public_program_level_opts,
                            format_func=lambda x: x if x in ("A1", "A2", "B1", "B2", "C1", "C2") else t(x) if x != t("all") else t("all"),
                            key="public_learning_program_level_filter",
                        )

                    public_program_filtered = public_program_df.copy()
                    if public_program_q:
                        for col in ["title", "program_overview", "custom_subject_name", "subject", "learner_stage", "level_or_band"]:
                            if col not in public_program_filtered.columns:
                                public_program_filtered[col] = ""
                        public_program_filtered = public_program_filtered[
                            public_program_filtered["title"].fillna("").astype(str).str.lower().str.contains(public_program_q, na=False)
                            | public_program_filtered["program_overview"].fillna("").astype(str).str.lower().str.contains(public_program_q, na=False)
                            | public_program_filtered["custom_subject_name"].fillna("").astype(str).str.lower().str.contains(public_program_q, na=False)
                            | public_program_filtered["subject"].fillna("").astype(str).str.lower().str.contains(public_program_q, na=False)
                            | public_program_filtered["learner_stage"].fillna("").astype(str).str.lower().str.contains(public_program_q, na=False)
                            | public_program_filtered["level_or_band"].fillna("").astype(str).str.lower().str.contains(public_program_q, na=False)
                        ]
                    if public_program_subj_filter != t("all") and "subject" in public_program_filtered.columns:
                        public_program_filtered = public_program_filtered[public_program_filtered["subject"].astype(str).apply(_normalize_subject) == public_program_subj_filter]
                    if public_program_stage_filter != t("all") and "learner_stage" in public_program_filtered.columns:
                        public_program_filtered = public_program_filtered[public_program_filtered["learner_stage"].astype(str) == public_program_stage_filter]
                    if public_program_level_filter != t("all") and "level_or_band" in public_program_filtered.columns:
                        public_program_filtered = public_program_filtered[public_program_filtered["level_or_band"].astype(str) == public_program_level_filter]

                    if public_program_filtered.empty:
                        st.info(t("be_the_first_to_share"))
                    else:
                        st.caption(t("learning_programs_count", count=len(public_program_filtered)))
                        render_learning_program_library_cards(public_program_filtered, prefix="public_learning_programs", show_author=True, allow_visibility_toggle=False)

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
                        _pub_subj_opts = sorted(set(_normalize_subject(s) for s in public_df["subject"].dropna().astype(str) if _normalize_subject(s))) if "subject" in public_df.columns else []
                        subject_filter_public = st.selectbox(
                            t("subject_label"),
                            [t("all")] + _pub_subj_opts,
                            format_func=lambda x: _subject_label_fn(x) if x != t("all") else t("all"),
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
                        filtered_public = filtered_public[filtered_public["subject"].astype(str).apply(_normalize_subject) == subject_filter_public]
                    if stage_filter_public != t("all") and "learner_stage" in filtered_public.columns:
                        filtered_public = filtered_public[filtered_public["learner_stage"].astype(str) == stage_filter_public]
                    if level_filter_public != t("all") and "level_or_band" in filtered_public.columns:
                        filtered_public = filtered_public[filtered_public["level_or_band"].astype(str) == level_filter_public]
                    if purpose_filter_public != t("all") and "lesson_purpose" in filtered_public.columns:
                        filtered_public = filtered_public[filtered_public["lesson_purpose"].astype(str) == purpose_filter_public]
                    if source_filter_public != t("all") and "source_type" in filtered_public.columns:
                        filtered_public = filtered_public[filtered_public["source_type"].astype(str) == source_filter_public]

                    if filtered_public.empty:
                        st.info(t("be_the_first_to_share"))
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
                        pub_ws_subj_opts = sorted(set(_normalize_subject(s) for s in pub_ws_df["subject"].dropna().astype(str) if _normalize_subject(s))) if "subject" in pub_ws_df.columns else []
                        pub_ws_subj_filter = st.selectbox(
                            t("subject_label"),
                            [t("all")] + pub_ws_subj_opts,
                            format_func=lambda x: _subject_label_fn(x) if x != t("all") else t("all"),
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
                        pub_ws_filtered = pub_ws_filtered[pub_ws_filtered["subject"].astype(str).apply(_normalize_subject) == pub_ws_subj_filter]
                    if pub_ws_stage_filter != t("all") and "learner_stage" in pub_ws_filtered.columns:
                        pub_ws_filtered = pub_ws_filtered[pub_ws_filtered["learner_stage"].astype(str) == pub_ws_stage_filter]
                    if pub_ws_level_filter != t("all") and "level_or_band" in pub_ws_filtered.columns:
                        pub_ws_filtered = pub_ws_filtered[pub_ws_filtered["level_or_band"].astype(str) == pub_ws_level_filter]
                    if pub_ws_type_filter != t("all") and "worksheet_type" in pub_ws_filtered.columns:
                        pub_ws_filtered = pub_ws_filtered[pub_ws_filtered["worksheet_type"].astype(str) == pub_ws_type_filter]
                    if pub_ws_src_filter != t("all") and "source_type" in pub_ws_filtered.columns:
                        pub_ws_filtered = pub_ws_filtered[pub_ws_filtered["source_type"].astype(str) == pub_ws_src_filter]

                    if pub_ws_filtered.empty:
                        st.info(t("be_the_first_to_share"))
                    else:
                        st.caption(f"{len(pub_ws_filtered)} {t('community_worksheets').lower()}")
                        render_worksheet_library_cards(pub_ws_filtered, prefix="pub_ws", show_author=True)

            with comm_tab_exams:
                pub_exam_df = load_public_exams()

                if pub_exam_df.empty:
                    st.info(t("community_library_empty"))
                else:
                    import helpers.lesson_planner as _lp_mod3
                    ef_col1, ef_col2 = st.columns([3, 1])
                    with ef_col1:
                        pub_exam_topic_q = st.text_input(
                            t("search_by_topic"),
                            key="pub_exam_topic_q",
                            placeholder="e.g. grammar, fractions…",
                        ).strip().lower()
                    with ef_col2:
                        pub_exam_subj_opts = sorted(set(_normalize_subject(s) for s in pub_exam_df["subject"].dropna().astype(str) if _normalize_subject(s))) if "subject" in pub_exam_df.columns else []
                        pub_exam_subj_filter = st.selectbox(
                            t("subject_label"),
                            [t("all")] + pub_exam_subj_opts,
                            format_func=lambda x: _subject_label_fn(x) if x != t("all") else t("all"),
                            key="pub_exam_subject_filter",
                        )

                    ef_col3, ef_col4 = st.columns(2)
                    with ef_col3:
                        _exam_stage_opts = sorted(pub_exam_df["learner_stage"].dropna().astype(str).unique().tolist()) if "learner_stage" in pub_exam_df.columns else []
                        pub_exam_stage_filter = st.selectbox(
                            t("learner_stage"),
                            [t("all")] + _exam_stage_opts,
                            format_func=lambda x: _lp_mod3._stage_label(x) if x != t("all") else t("all"),
                            key="pub_exam_stage_filter",
                        )
                    with ef_col4:
                        _exam_level_opts = sorted(pub_exam_df["level"].dropna().astype(str).unique().tolist()) if "level" in pub_exam_df.columns else []
                        pub_exam_level_filter = st.selectbox(
                            t("level_or_band"),
                            [t("all")] + _exam_level_opts,
                            format_func=lambda x: _lp_mod3._level_label(x) if x != t("all") else t("all"),
                            key="pub_exam_level_filter",
                        )

                    pub_exam_filtered = pub_exam_df.copy()
                    if pub_exam_topic_q and "topic" in pub_exam_filtered.columns:
                        pub_exam_filtered = pub_exam_filtered[pub_exam_filtered["topic"].fillna("").astype(str).str.lower().str.contains(pub_exam_topic_q, na=False)]
                    if pub_exam_subj_filter != t("all") and "subject" in pub_exam_filtered.columns:
                        pub_exam_filtered = pub_exam_filtered[pub_exam_filtered["subject"].astype(str).apply(_normalize_subject) == pub_exam_subj_filter]
                    if pub_exam_stage_filter != t("all") and "learner_stage" in pub_exam_filtered.columns:
                        pub_exam_filtered = pub_exam_filtered[pub_exam_filtered["learner_stage"].astype(str) == pub_exam_stage_filter]
                    if pub_exam_level_filter != t("all") and "level" in pub_exam_filtered.columns:
                        pub_exam_filtered = pub_exam_filtered[pub_exam_filtered["level"].astype(str) == pub_exam_level_filter]

                    if pub_exam_filtered.empty:
                        st.info(t("be_the_first_to_share"))
                    else:
                        st.caption(f"{len(pub_exam_filtered)} {t('community_exams').lower()}")
                        render_exam_library_cards(pub_exam_filtered, prefix="pub_exams", show_author=True)

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
        selected_program_id = (
            st.session_state.get("my_learning_programs_selected_program_id")
            or st.session_state.get("public_learning_programs_selected_program_id")
            or st.session_state.get("home_public_learning_programs_selected_program_id")
        )

        if selected_program_id:
            selected_program = load_learning_program(int(selected_program_id))
            st.markdown("---")
            st.markdown(f"### {t('learning_program_preview')}")
            if st.session_state.get("my_learning_programs_selected_program_id") and str(selected_program.get("user_id") or "") == str(get_current_user_id() or ""):
                render_saved_learning_program_workspace(
                    selected_program,
                    int(selected_program_id),
                    ns=f"saved_learning_program_{int(selected_program_id)}",
                )
            else:
                render_teacher_program_view(selected_program)

            program_complete = bool(selected_program) and all(unit.get("unit_objectives") or unit.get("delivery_notes") or any(topic.get("learning_objectives") for topic in (unit.get("topics") or [])) for unit in (selected_program.get("units") or []))
            if program_complete and st.session_state.get(f"show_assign_learning_program_{selected_program_id}", False):
                render_learning_program_assignment_panel(selected_program, prefix=f"learning_program_assign_{selected_program_id}")
            close_cols = st.columns([1, 4])
            with close_cols[0]:
                if st.button(t("close_program"), key="close_selected_learning_program"):
                    for _k in [
                        "my_learning_programs_selected_program_id",
                        "public_learning_programs_selected_program_id",
                        "home_public_learning_programs_selected_program_id",
                    ]:
                        st.session_state.pop(_k, None)
                    st.rerun()

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
                    allow_assign=True,
                    subject=st.session_state.get("files_ws_subject", ""),
                    learner_stage=st.session_state.get("files_ws_stage", ""),
                    level_or_band=st.session_state.get("files_ws_level", ""),
                    worksheet_type=st.session_state.get("files_ws_type", ""),
                    topic=st.session_state.get("files_ws_topic", ""),
                )

        # ── Selected exam detail ──────────────────────────────────────────
        selected_exam = st.session_state.get("files_selected_exam")
        if selected_exam:
            import json as _json_exam
            if isinstance(selected_exam, str):
                try:
                    selected_exam = _json_exam.loads(selected_exam)
                except Exception:
                    selected_exam = {}
            selected_exam_ak = st.session_state.get("files_selected_exam_answer_key") or {}
            if isinstance(selected_exam_ak, str):
                try:
                    selected_exam_ak = _json_exam.loads(selected_exam_ak)
                except Exception:
                    selected_exam_ak = {}
            if selected_exam:
                st.markdown("---")
                exam_det_l, exam_det_r = st.columns([6, 1])
                with exam_det_l:
                    st.markdown(f"### {t('exam_preview')}")
                with exam_det_r:
                    if st.button(t("close_exam"), key="close_selected_exam", use_container_width=True):
                        for _k in ["files_selected_exam", "files_selected_exam_answer_key", "files_exam_subject", "files_exam_stage", "files_exam_level", "files_exam_topic", "files_exam_title"]:
                            st.session_state.pop(_k, None)
                        st.rerun()
                render_exam_result(
                    selected_exam,
                    selected_exam_ak,
                    show_ready_banner=False,
                    allow_assign=True,
                    subject=st.session_state.get("files_exam_subject", ""),
                    learner_stage=st.session_state.get("files_exam_stage", ""),
                    level_or_band=st.session_state.get("files_exam_level", ""),
                    topic=st.session_state.get("files_exam_topic", ""),
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

        return

    # ---------- COMMUNITY PANEL ----------
    if panel == "community":
        import re as _re_comm
        from helpers.lesson_planner import subject_label as _subj_label_fn

        head_left, head_right = st.columns([6, 1], vertical_alignment="center")

        with head_left:
            st.markdown(f"### 🌐 {t('community_tab_title')}")
            st.caption(t("community_subtitle"))

        with head_right:
            if st.button(f"{t('close')}", key="close_community_top", help=t("close_community"), use_container_width=True):
               st.session_state["home_action_menu_prev"] = t("home")
               st.session_state["home_action_menu_nonce"] += 1
               home_go("home", panel=None)
               st.rerun()

        _all_profiles_raw = load_community_profiles()

        # Tabs: Teachers / Students
        _comm_tab_teachers, _comm_tab_students = st.tabs([
            f"👩‍🏫 {t('teacher_role')}",
            f"🎓 {t('student_role')}",
        ])

        with _comm_tab_students:
            from app_pages.student_find_teacher import render_community_member_cards
            render_community_member_cards(_all_profiles_raw, role_filter="student")

        with _comm_tab_teachers:

            # All opted-in profiles + own entry for self-preview
            _visible = [
                p for p in _all_profiles_raw
                if (p.get("show_community_profile") or p.get("user_id") == user_id)
                and profile_can_teach(p)
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
                        if s and s != "other" and s not in _all_subjects:
                            _all_subjects.append(s)
                    for s in (_fp.get("custom_subjects") or []):
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
                    _filtered = [
                        p for p in _filtered
                        if _subj_sel in (p.get("primary_subjects") or [])
                        or _subj_sel in (p.get("custom_subjects") or [])
                    ]
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
                        _username = str(_p.get("username") or "").strip()
                        _private_name = f"@{_username}" if _username else t("community_private_user")
                        _active_count = int(_p.get("active_student_count") or 0)
                        _subjects = _p.get("primary_subjects") or []
                        _custom_subjects = _p.get("custom_subjects") or []
                        _display_subjects = [_subj_label_fn(s) for s in _subjects if s != "other"] + [s.title() for s in _custom_subjects if s]
                        _subj_labels = ", ".join(_display_subjects) if _display_subjects else "—"
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
                            import html as _html

                            _safe_display_name = _html.escape(_display_name)
                            _safe_subj_labels = _html.escape(_subj_labels)
                            _safe_country = _html.escape(_country)
                            _safe_edu_display = _html.escape(_edu_display)

                            _avatar_html = (
                                f"<img src='{_avatar}' style='width:52px;height:52px;border-radius:50%;object-fit:cover;flex-shrink:0;' referrerpolicy='no-referrer' />"
                                if _avatar
                                else "<div style='width:52px;height:52px;border-radius:50%;flex-shrink:0;background:linear-gradient(135deg,#60A5FA,#A78BFA);'></div>"
                            )

                            _contact_parts = []

                            if _country:
                                _contact_parts.append(
                                    f"<span style='font-size:0.82rem;color:#64748b;'>🌍 {_safe_country}</span>"
                                )

                            if _show_contact:
                                _btns = ""
                                if _wa_num:
                                    _btns += _contact_btn(
                                        f"https://wa.me/{_wa_num.lstrip('+')}",
                                        _wa_svg,
                                        "#25D366",
                                        "WhatsApp",
                                    )
                                if _email:
                                    _btns += _contact_btn(
                                        f"mailto:{_email}",
                                        _email_svg,
                                        "#3B82F6",
                                        "Email",
                                    )

                                if _btns:
                                    _contact_parts.append(
                                        f"<span style='margin-left:8px;display:inline-flex;gap:6px;vertical-align:middle;'>{_btns}</span>"
                                    )

                            if _contact_parts:
                                _contact_html = (
                                    "<div style='margin-top:5px;display:flex;align-items:center;flex-wrap:wrap;gap:4px;'>"
                                    + "".join(_contact_parts)
                                    + "</div>"
                                )
                            else:
                                _contact_html = (
                                    f"<div style='margin-top:5px;font-size:0.8rem;color:#64748b;opacity:0.8;'>"
                                    f"{t('community_profile_empty')}"
                                    f"</div>"
                                )

                            _edu_html = (
                                f"<div style='font-size:0.82rem;color:#a78bfa;'>🎓 {_safe_edu_display}</div>"
                                if _edu_display
                                else ""
                            )

                            _card_html = (
                                "<div style='display:flex;align-items:flex-start;gap:10px;background:#1e293b;border-radius:12px;padding:14px 16px;margin-bottom:10px;border:1px solid #334155;'>"
                                f"{_rank_html}"
                                f"{_avatar_html}"
                                "<div style='flex:1;min-width:0;'>"
                                f"<div style='font-weight:700;font-size:1rem;color:#f1f5f9;'>{_safe_display_name}{_badge_self}</div>"
                                f"<div style='font-size:0.82rem;color:#94a3b8;margin-top:2px;'>{_safe_subj_labels}</div>"
                                "<div style='display:flex;gap:14px;margin-top:6px;flex-wrap:wrap;'>"
                                f"<div style='font-size:0.82rem;color:#38bdf8;'>👥 {_active_count} {t('community_active_students')}</div>"
                                f"{_edu_html}"
                                "</div>"
                                f"{_contact_html}"
                                "</div>"
                                "</div>"
                            )

                            st.markdown(_card_html, unsafe_allow_html=True)

    # ---------- AI TOOLS PANEL ----------
    if panel == "ai_tools":
        st.markdown(f"### 🤖 {t('ai_tools')}")

        # --- Learning Program Maker ---
        render_quick_learning_program_builder_expander()

        # --- Lesson Planner ---
        render_quick_lesson_planner_expander()

        # --- Worksheet Maker ---
        render_quick_worksheet_maker_expander()

        # --- Quick Exam Builder ---
        render_quick_exam_builder_expander()

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

    render_home_teaching_resources_preview()

    st.markdown('<div class="home-bottom-space"></div>', unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

# =========================
