import streamlit as st
from typing import Optional
from core.i18n import t
from core.timezone import _get_qp, detect_browser_timezone

PAGES = [
    ("dashboard", "dashboard", "📊"),
    ("students", "students", "👥"),
    ("add_lesson", "lesson", "🗓️"),
    ("add_payment", "payment", "💳"),
    ("calendar", "calendar", "📅"),
    ("smart_tools", "ai_tools", "🤖"),
    ("analytics", "analytics", "📈"),
    ("pricing", "pricing", "💎"),
    ("account", "account", "👤"),
    ("admin", "admin", "🛡️"),
    ("developer_workspace", "Developer Workspace", "🧪"),
    ("operational_diagnostics", "Operational Diagnostics", "🩺"),
]

STUDENT_PAGES = [
    ("student_home", "student_home_title", "🏠"),
    ("student_practice", "smart_practice", "🧠"),
    ("student_study_plan", "smart_study_plan", "📚"),
    ("student_assignments", "student_assignments_title", "🗂️"),
    ("student_find_teacher", "find_my_teacher", "🔍"),
]

PAGE_KEYS = {"home", "resources", "community"} | {key for key, _, _ in PAGES} | {key for key, _, _ in STUDENT_PAGES}


_RESOURCE_DIALOG_KEYS = {
    "_learning_program_assign_dialog",
    "_resource_bulk_assign_dialog",
}

_RESOURCE_PREVIEW_KEY_GROUPS = {
    "worksheet": {
    "files_selected_worksheet",
    "files_ws_subject",
    "files_ws_stage",
    "files_ws_level",
    "files_ws_type",
    "files_ws_topic",
    "files_ws_title",
    "files_selected_worksheet_id",
    "files_selected_worksheet_status",
    "files_selected_worksheet_assign_expanded",
    },
    "exam": {
    "files_selected_exam",
    "files_selected_exam_answer_key",
    "files_exam_subject",
    "files_exam_stage",
    "files_exam_level",
    "files_exam_topic",
    "files_exam_title",
    "files_selected_exam_id",
    "files_selected_exam_status",
    "files_selected_exam_assign_expanded",
    },
    "plan": {
    "files_selected_plan",
    "files_selected_subject",
    "files_selected_stage",
    "files_selected_level",
    "files_selected_purpose",
    "files_selected_topic",
    "files_selected_source_type",
    "files_selected_title",
    "files_selected_plan_id",
    "files_selected_plan_status",
    "files_selected_plan_assign_expanded",
    },
    "video": {
    "files_selected_video",
    "files_selected_video_id",
    "files_selected_video_status",
    "files_selected_video_assign_expanded",
    },
    "program": {
    "my_learning_programs_selected_program_id",
    "archived_learning_programs_selected_program_id",
    "public_learning_programs_selected_program_id",
    "home_public_learning_programs_selected_program_id",
    },
}

_RESOURCE_TRANSIENT_KEYS = set(_RESOURCE_DIALOG_KEYS)
for _resource_keys in _RESOURCE_PREVIEW_KEY_GROUPS.values():
    _RESOURCE_TRANSIENT_KEYS.update(_resource_keys)

_SMART_TOOL_RESULT_KEYS = {
    "worksheet_result",
    "worksheet_result_saved",
    "worksheet_record_id",
    "worksheet_kept",
    "worksheet_warning",
    "worksheet_assign_expanded",
    "ws_effective_topic",
    "worksheet_ab_debug_compare",
    "exam_result",
    "exam_answer_key",
    "exam_result_saved",
    "exam_record_id",
    "exam_kept",
    "exam_warning",
    "exam_assign_expanded",
    "quick_exam_effective_topic",
    "exam_ab_debug_compare",
    "quick_lesson_plan_result",
    "quick_lesson_plan_record_id",
    "quick_lesson_plan_kept",
    "quick_lesson_plan_mode_used",
    "quick_lesson_plan_warning",
    "quick_lesson_no_template",
    "quick_lesson_plan_assign_expanded",
    "quick_plan_effective_topic",
    "quick_plan_ab_debug_compare",
    "quick_learning_program_result",
    "quick_learning_program_mode_used",
    "quick_learning_program_warning",
    "quick_learning_program_meta",
    "quick_learning_program_payload",
    "quick_learning_program_pending_unit",
    "quick_learning_program_saved_program_id",
    "quick_learning_program_generate_requested",
    "quick_learning_program_editing_unit",
    "quick_cv_result",
    "quick_cv_title",
    "quick_cv_source_type",
    "quick_cv_ai_prompt",
    "quick_cv_record_id",
    "_quick_cv_auto_saved",
    "quick_cl_result",
    "quick_cl_title",
    "quick_cl_ai_prompt",
    "cv_import_applied",
}


def clear_resource_transient_state() -> None:
    for key in _RESOURCE_TRANSIENT_KEYS:
        st.session_state.pop(key, None)
    for key in list(st.session_state.keys()):
        if str(key).startswith("show_assign_learning_program_"):
            st.session_state.pop(key, None)


def clear_smart_tool_result_state(*, clear_selection: bool = False) -> None:
    for key in _SMART_TOOL_RESULT_KEYS:
        st.session_state.pop(key, None)
    if clear_selection:
        st.session_state.pop("_home_smart_tool_dialog", None)
        st.session_state["home_smart_tool_selected"] = ""
        for key in (
            "open_quick_learning_program_expander",
            "open_quick_plan_expander",
            "open_quick_ws_expander",
            "open_quick_exam_expander",
            "open_quick_cv_expander",
            "open_income_goal_expander",
        ):
            st.session_state.pop(key, None)
    st.session_state.pop("_home_smart_tool_scroll_toast", None)


def clear_open_resource_previews(*, except_kind: str | None = None, clear_dialogs: bool = True) -> None:
    keep = str(except_kind or "").strip().lower()
    aliases = {"lesson_plan": "plan", "lesson": "plan", "quick_exam": "exam", "learning_program": "program"}
    keep = aliases.get(keep, keep)
    for kind, keys in _RESOURCE_PREVIEW_KEY_GROUPS.items():
        if keep and kind == keep:
            continue
        for key in keys:
            st.session_state.pop(key, None)
    if keep != "program":
        for key in list(st.session_state.keys()):
            if str(key).startswith("show_assign_learning_program_"):
                st.session_state.pop(key, None)
    if clear_dialogs:
        for key in _RESOURCE_DIALOG_KEYS:
            st.session_state.pop(key, None)


def _clear_page_transient_state(next_page: str) -> None:
    current_page = str(st.session_state.get("page") or "")
    if next_page != "resources":
        clear_resource_transient_state()
    if next_page == "resources":
        clear_smart_tool_result_state(clear_selection=True)
    keys: set[str] = set()
    if current_page == "smart_tools" and next_page != "smart_tools":
        keys.update(_SMART_TOOL_RESULT_KEYS)
    for key in keys:
        st.session_state.pop(key, None)


def _set_query(page: Optional[str] = None, lang: Optional[str] = None, panel: Optional[str] = None) -> None:
    new_page = page if page is not None else st.session_state.get("page", "home")
    new_lang = lang if lang is not None else st.session_state.get("ui_lang", "en")
    params = {"page": new_page, "lang": new_lang}
    current_browser_tz = str(st.session_state.get("browser_tz") or _get_qp("browser_tz", "") or "").strip()
    if current_browser_tz:
        params["browser_tz"] = current_browser_tz
    if panel is not None:
        params["panel"] = panel
    try:
        st.query_params.clear()
        for k, v in params.items():
            st.query_params[k] = v
    except Exception:
        st.experimental_set_query_params(**params)


def go_to(page_name: str):
    if page_name not in PAGE_KEYS:
        page_name = "home"
    current_page = str(st.session_state.get("page") or "")
    _clear_page_transient_state(page_name)
    st.session_state["_page_loading_transition_pending"] = current_page != page_name
    st.session_state["page"] = page_name
    _set_query(page=page_name, lang=st.session_state.get("ui_lang", "en"))


def home_go(page_name: str = "home", panel: Optional[str] = None):
    if page_name not in PAGE_KEYS:
        page_name = "home"
    current_page = str(st.session_state.get("page") or "")
    _clear_page_transient_state(page_name)
    if panel != "ai_tools":
        clear_smart_tool_result_state(clear_selection=True)
    st.session_state["_page_loading_transition_pending"] = current_page != page_name
    st.session_state["page"] = page_name
    _set_query(page=page_name, lang=st.session_state.get("ui_lang", "en"), panel=panel)


def page_header(title: str):
    st.markdown(f"## {title}")


def init_navigation_defaults():
    """Initialize all navigation-related session state and sync from URL."""
    if "page" not in st.session_state:
        st.session_state["page"] = "home"
    if "_page_loading_transition_pending" not in st.session_state:
        st.session_state["_page_loading_transition_pending"] = False
    if "ui_lang" not in st.session_state:
        st.session_state["ui_lang"] = "en"
    if "show_profile_dialog" not in st.session_state:
        st.session_state["show_profile_dialog"] = False
    if "home_action_menu_prev" not in st.session_state:
        st.session_state["home_action_menu_prev"] = t("sign_out")
    if "home_action_menu_nonce" not in st.session_state:
        st.session_state["home_action_menu_nonce"] = 0
    if "top_nav_prev" not in st.session_state:
        st.session_state["top_nav_prev"] = "home"

    # Sync from URL
    lang_qp = _get_qp("lang", None)
    if lang_qp in ("en", "es", "tr"):
        st.session_state["ui_lang"] = lang_qp

    qp_page = str(_get_qp("page", "home") or "home")
    if qp_page in PAGE_KEYS:
        st.session_state["page"] = qp_page
    else:
        st.session_state["page"] = "home"
        _set_query(page="home", lang=st.session_state["ui_lang"])

    detect_browser_timezone()
