import streamlit as st
import json
import logging
import math
from core.i18n import t
from core.navigation import go_to
from core.database import get_sb
from core.state import get_current_user_id
from helpers.practice_engine import (
    autosave_practice_draft_if_needed,
    worksheet_to_exercises,
    exam_to_exercises,
    normalize_exercise_data_for_web,
    render_practice_session,
    save_practice_session,
    save_practice_draft,
    save_practice_answers,
    update_practice_progress,
    update_practice_session,
    load_practice_history,
    load_practice_progress,
    load_in_progress_practice_session,
    load_practice_draft_answers,
    get_completed_source_ids,
    get_total_xp,
    get_global_best_streak,
    get_rank,
    calculate_session_xp,
    record_video_practice_interaction,
)
from helpers.teacher_student_integration import (
    _clean_teacher_feedback_text,
    create_teacher_review_request,
    get_reviewable_teacher_links_for_subject,
    load_assignment_state_map,
    load_practice_assignment_scope_map,
    load_student_assignment_by_id,
    load_student_assignments,
    load_student_teacher_links,
    load_student_review_requests_for_session,
    record_video_assignment_watch,
)
from helpers.exposure_telemetry import attach_student_recommendation_exposures
from helpers.student_recommendations import (
    build_recommended_materials,
    group_recommendations_for_subject_tabs,
    rank_recommended_materials,
)
from helpers.student_recommendation_ml import log_student_recommendation_impressions, log_student_recommendation_open
from helpers.empty_states import render_empty_state
from helpers.resource_gallery import (
    extract_gallery_language_label,
    extract_gallery_image_url,
    inject_resource_gallery_styles,
    render_gallery_card_html,
    normalize_resource_kind,
    resource_kind_accent,
    resource_kind_label,
)
from helpers.video_library import load_public_videos, load_video_record
from services.permissions_service import user_has_feature

_STUDENT_PRACTICE_PAGE_SIZE = 6
logger = logging.getLogger(__name__)


def _ui_text(key: str, fallback: str) -> str:
    value = t(key)
    return value if value != key else fallback


def _safe_int(value, default: int = 0) -> int:
    try:
        if value in (None, "", "None"):
            return default
        if isinstance(value, float) and math.isnan(value):
            return default
        return int(value)
    except Exception:
        return default


def _show_practice_resource_unavailable(exc: Exception | None = None) -> None:
    if exc:
        logger.exception("Student practice resource open failed: %s", exc)
    st.error(
        _ui_text(
            "student_practice_resource_unavailable",
            "We couldn't open this practice activity right now. Please try again in a moment or choose another resource.",
        )
    )


def _row_embedded_payload(row: dict, resource_type: str) -> dict:
    if resource_type == "exam":
        for key in ("exam_data", "answer_key"):
            payload = row.get(key)
            if isinstance(payload, dict):
                return payload
        return {}
    if resource_type == "worksheet":
        payload = row.get("worksheet_json")
        return payload if isinstance(payload, dict) else {}
    return dict(row or {})


def _load_card_gallery_payload(row: dict, resource_type: str) -> dict:
    combined_payload = {**dict(row or {}), **_row_embedded_payload(row, resource_type)}
    if extract_gallery_image_url(combined_payload) or not row.get("id"):
        return combined_payload
    if resource_type not in {"worksheet", "exam"}:
        return combined_payload

    try:
        table_name = "quick_exams" if resource_type == "exam" else "worksheets"
        rows = (
            get_sb()
            .table(table_name)
            .select("*")
            .eq("id", row.get("id"))
            .limit(1)
            .execute()
        ).data or []
        full_row = dict(rows[0]) if rows else {}
    except Exception as exc:
        logger.warning("Student practice card gallery payload unavailable: %s", exc)
        return combined_payload

    combined_payload = {**combined_payload, **full_row}
    nested_key = "exam_data" if resource_type == "exam" else "worksheet_json"
    nested_payload = full_row.get(nested_key) if isinstance(full_row.get(nested_key), dict) else {}
    return {**combined_payload, **nested_payload}


def _practice_resource_kind(row_or_kind) -> str:
    if isinstance(row_or_kind, dict):
        for key in ("source_type", "resource_type", "assignment_type", "kind"):
            kind = normalize_resource_kind(row_or_kind.get(key))
            if kind != "practice":
                return kind
        return "practice"
    return normalize_resource_kind(row_or_kind)


def _is_specific_resource_kind(kind: str) -> bool:
    return normalize_resource_kind(kind) in {"worksheet", "exam", "video", "lesson_plan", "program"}


def _resolve_exam_payload(row: dict) -> tuple[dict, dict, dict]:
    exam_data = row.get("exam_data") or {}
    answer_key = row.get("answer_key") or {}
    if row.get("id") and (not exam_data or not answer_key):
        from helpers.quick_exam_storage import load_exam_record

        full_row = load_exam_record(row.get("id"))
        if full_row:
            row = {**row, **full_row}
            exam_data = row.get("exam_data") or {}
            answer_key = row.get("answer_key") or {}
    if isinstance(exam_data, str):
        try:
            exam_data = json.loads(exam_data)
        except Exception:
            exam_data = {}
    if isinstance(answer_key, str):
        try:
            answer_key = json.loads(answer_key)
        except Exception:
            answer_key = {}
    return exam_data if isinstance(exam_data, dict) else {}, answer_key if isinstance(answer_key, dict) else {}, row


def _resolve_worksheet_payload(row: dict) -> tuple[dict, dict]:
    worksheet_json = row.get("worksheet_json") or {}
    if row.get("id") and not worksheet_json:
        from helpers.worksheet_storage import load_worksheet_record

        full_row = load_worksheet_record(row.get("id"))
        if full_row:
            row = {**row, **full_row}
            worksheet_json = row.get("worksheet_json") or {}
    if isinstance(worksheet_json, str):
        try:
            worksheet_json = json.loads(worksheet_json)
        except Exception:
            worksheet_json = {}
    return worksheet_json if isinstance(worksheet_json, dict) else {}, row


def _slice_practice_page(rows: list[dict], state_key: str, *, page_size: int = _STUDENT_PRACTICE_PAGE_SIZE):
    total_items = len(rows or [])
    total_pages = max(1, math.ceil(total_items / page_size)) if total_items else 1
    current_page = int(st.session_state.get(state_key, 1) or 1)
    current_page = max(1, min(current_page, total_pages))
    st.session_state[state_key] = current_page
    start_idx = (current_page - 1) * page_size
    end_idx = min(start_idx + page_size, total_items)
    return list((rows or [])[start_idx:end_idx]), current_page, total_pages, start_idx, end_idx, total_items


def _render_practice_pagination(rows: list[dict], state_key: str, *, page_size: int = _STUDENT_PRACTICE_PAGE_SIZE) -> None:
    _, current_page, total_pages, start_idx, end_idx, total_items = _slice_practice_page(
        rows,
        state_key,
        page_size=page_size,
    )
    if total_items <= page_size:
        return
    prev_col, info_col, next_col = st.columns([1, 3, 1])
    with prev_col:
        if st.button("←", key=f"{state_key}_prev", use_container_width=True, disabled=current_page <= 1):
            st.session_state[state_key] = max(1, current_page - 1)
            st.rerun()
    with info_col:
        st.caption(f"{start_idx + 1}-{end_idx} / {total_items} · {current_page}/{total_pages}")
    with next_col:
        if st.button("→", key=f"{state_key}_next", use_container_width=True, disabled=current_page >= total_pages):
            st.session_state[state_key] = min(total_pages, current_page + 1)
            st.rerun()


def _open_practice_item(exercise_data: dict, meta: dict | None = None, *, demo_id: str | None = None) -> bool:
    """Open a practice item only if it contains runnable exercises."""
    exercise_data = normalize_exercise_data_for_web(exercise_data or {})
    exercises = (exercise_data or {}).get("exercises") or []
    if not exercises:
        st.warning(t("no_exercises_available"))
        return False

    draft = load_in_progress_practice_session(
        str((exercise_data or {}).get("source_type") or ""),
        (exercise_data or {}).get("source_id"),
    )
    if draft:
        draft_exercise_data = exercise_data
        if isinstance(draft_exercise_data, str):
            try:
                draft_exercise_data = json.loads(draft_exercise_data)
            except Exception:
                draft_exercise_data = exercise_data
        draft_exercise_data = normalize_exercise_data_for_web(draft_exercise_data or exercise_data)
        st.session_state["practice_exercise_data"] = draft_exercise_data
        st.session_state["practice_meta"] = meta or {}
        st.session_state["_practice_resume_session_id"] = draft.get("id")
        st.session_state["_practice_resume_answers"] = load_practice_draft_answers(int(draft.get("id")))
        st.session_state["_practice_resume_notice"] = True
    else:
        st.session_state["practice_exercise_data"] = exercise_data
        st.session_state["practice_meta"] = meta or {}
        st.session_state.pop("_practice_resume_session_id", None)
        st.session_state.pop("_practice_resume_answers", None)
        st.session_state.pop("_practice_resume_notice", None)

    if demo_id:
        st.session_state["_practice_demo_id"] = demo_id
    else:
        st.session_state.pop("_practice_demo_id", None)
    return True


def _open_worksheet_practice_from_row(row: dict) -> bool:
    try:
        ws_json, resolved_row = _resolve_worksheet_payload(dict(row or {}))
        if not ws_json:
            _show_practice_resource_unavailable()
            return False
        from helpers.worksheet_builder import normalize_worksheet_output

        ws_json = normalize_worksheet_output(ws_json)
        ex_data = worksheet_to_exercises(ws_json, row_id=resolved_row.get("id"))
        return _open_practice_item(
            ex_data,
            {
                "subject": resolved_row.get("subject", ""),
                "topic": resolved_row.get("topic", ""),
                "learner_stage": resolved_row.get("learner_stage", ""),
                "level": resolved_row.get("level_or_band", ""),
            },
        )
    except Exception as exc:
        _show_practice_resource_unavailable(exc)
        return False


def _open_exam_practice_from_row(row: dict) -> bool:
    try:
        exam_data, answer_key, resolved_row = _resolve_exam_payload(dict(row or {}))
        if not exam_data:
            _show_practice_resource_unavailable()
            return False
        if isinstance(exam_data, dict):
            exam_data.setdefault("subject", resolved_row.get("subject", ""))
            exam_data.setdefault("topic", resolved_row.get("topic", ""))
            exam_data.setdefault("learner_stage", resolved_row.get("learner_stage", ""))
        ex_data = exam_to_exercises(exam_data, answer_key, row_id=resolved_row.get("id"))
        return _open_practice_item(
            ex_data,
            {
                "subject": resolved_row.get("subject", ""),
                "topic": resolved_row.get("topic", ""),
                "learner_stage": resolved_row.get("learner_stage", ""),
                "level": resolved_row.get("level", ""),
            },
        )
    except Exception as exc:
        _show_practice_resource_unavailable(exc)
        return False


def _open_video_item(video_payload: dict, meta: dict | None = None, *, assignment_id: int = 0) -> bool:
    combined_payload = dict(video_payload or {})
    video_id = combined_payload.get("id")
    if video_id:
        full_row = load_video_record(video_id) or {}
        combined_payload = {**combined_payload, **full_row}
    watch_url = str(combined_payload.get("watch_url") or combined_payload.get("youtube_url") or "").strip()
    if not watch_url:
        st.info(_ui_text("video_unavailable", "This video is not available right now."))
        return False
    st.session_state["practice_video_payload"] = combined_payload
    st.session_state["practice_meta"] = meta or {}
    st.session_state["_practice_video_assignment_id"] = int(assignment_id or 0)
    st.session_state["_practice_video_logged"] = False
    st.session_state.pop("practice_exercise_data", None)
    st.session_state.pop("_practice_resume_session_id", None)
    st.session_state.pop("_practice_resume_answers", None)
    st.session_state.pop("_practice_resume_notice", None)
    return True


def _open_history_practice_row(row: dict, *, assignment_state: dict | None = None) -> bool:
    assignment_state = assignment_state or {}
    source_type = str(row.get("source_type") or "").strip()
    source_id = _safe_int(row.get("source_id"))
    if source_type in {"worksheet", "exam"} and assignment_state and source_id > 0:
        assignment_row = load_student_assignment_by_id(source_id)
        if assignment_row:
            from app_pages.student_assignments import _open_assignment_practice

            _open_assignment_practice(assignment_row)
            return True
    if source_type == "worksheet":
        return _open_worksheet_practice_from_row({"id": source_id} if source_id > 0 else row)
    if source_type == "exam":
        return _open_exam_practice_from_row({"id": source_id} if source_id > 0 else row)
    exercise_data = row.get("exercise_data")
    if isinstance(exercise_data, str):
        try:
            exercise_data = json.loads(exercise_data)
        except Exception:
            exercise_data = None
    if not exercise_data:
        return False
    return _open_practice_item(
        exercise_data,
        {
            "subject": str(row.get("subject") or ""),
            "topic": str(row.get("topic") or ""),
            "learner_stage": str(row.get("learner_stage") or ""),
            "level": str(row.get("level") or ""),
        },
    )


def render_student_practice():
    st.markdown(f"## 🧠 {t('smart_practice')}")
    _inject_student_practice_styles()
    inject_resource_gallery_styles()

    # ── Active practice session ─────────────────────────────────
    video_payload = st.session_state.get("practice_video_payload")
    if video_payload:
        _render_active_video_session(video_payload)
        return

    exercise_data = st.session_state.get("practice_exercise_data")
    if exercise_data:
        _render_active_session(exercise_data)
        return

    # ── Gamification dashboard ──────────────────────────────────
    _render_xp_dashboard()

    # ── Main menu ───────────────────────────────────────────────
    tab_browse, tab_history, tab_progress = st.tabs([
        f"🎯 {t('start_practice')}",
        f"📊 {t('practice_history')}",
        f"📈 {t('my_progress')}",
    ])

    with tab_browse:
        _render_browse_tab()
    with tab_history:
        _render_history_tab()
    with tab_progress:
        _render_progress_tab()


# ── XP Dashboard ────────────────────────────────────────────────

def _render_xp_dashboard():
    """Compact XP / rank / streak bar at the top."""
    total_xp    = get_total_xp()
    best_streak = get_global_best_streak()
    rank_key, rank_emoji, xp_into, xp_span = get_rank(total_xp)
    rank_label = t(f"rank_{rank_key}") if t(f"rank_{rank_key}") != f"rank_{rank_key}" else rank_key.replace("_", " ").title()

    pct = min(round(xp_into / xp_span * 100), 100) if xp_span else 100

    # Find next rank name
    from helpers.practice_engine import RANKS
    next_rank_label = ""
    for i, (thr, key, _em) in enumerate(RANKS):
        if total_xp >= thr and i < len(RANKS) - 1:
            nk = RANKS[i + 1][1]
            next_rank_label = t(f"rank_{nk}") if t(f"rank_{nk}") != f"rank_{nk}" else nk.replace("_", " ").title()

    progress_label = f"{xp_into}/{xp_span} XP" if xp_span else "MAX"

    st.markdown(
        f"""
        <div style="
            display:flex; align-items:center; gap:14px;
            padding:10px 16px; border-radius:14px;
            background:var(--panel); border:1px solid var(--border);
            margin-bottom:14px; flex-wrap:wrap;
        ">
            <div style="font-size:1.6rem;">{rank_emoji}</div>
            <div style="flex:1;min-width:140px;">
                <div style="font-weight:800;font-size:0.92rem;">{rank_label}</div>
                <div style="background:var(--border);border-radius:6px;height:8px;overflow:hidden;margin-top:4px;">
                    <div style="width:{pct}%;height:100%;background:linear-gradient(90deg,#8B5CF6,#6D28D9);border-radius:6px;transition:width 0.4s;"></div>
                </div>
                <div style="font-size:0.7rem;color:var(--muted);margin-top:2px;">
                    {progress_label}{(' → ' + next_rank_label) if next_rank_label else ''}
                </div>
            </div>
            <div style="text-align:center;min-width:70px;">
                <div style="font-size:1.1rem;font-weight:800;color:#8B5CF6;">{total_xp}</div>
                <div style="font-size:0.68rem;color:var(--muted);">XP</div>
            </div>
            <div style="text-align:center;min-width:70px;">
                <div style="font-size:1.1rem;font-weight:800;color:#F59E0B;">🔥 {best_streak}</div>
                <div style="font-size:0.68rem;color:var(--muted);">{t('best_streak')}</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _inject_student_practice_styles() -> None:
    st.markdown(
        """
        <style>
                div[class*="st-key-sp_cat_"] {
                        height: 100%;
                }
                div[class*="st-key-sp_cat_"] div[data-testid="stButton"] > button {
                        position: relative;
                        overflow: hidden;
                        min-height: 98px;
                        height: 98px;
                        padding: 14px 12px 12px !important;
                        border-radius: 18px !important;
                        border: 1px solid color-mix(in srgb, var(--border-strong, rgba(17,24,39,.08)) 68%, rgba(var(--practice-cat-rgb), .42) 32%) !important;
                        background:
                            radial-gradient(circle at 50% -12%, rgba(var(--practice-cat-rgb), .16), transparent 42%),
                            linear-gradient(180deg, var(--panel, rgba(255,255,255,0.92)), var(--panel-2, rgba(248,250,255,0.85))) !important;
                        box-shadow:
                            0 8px 24px rgba(var(--practice-cat-rgb), .26),
                            0 0 14px rgba(var(--practice-cat-rgb), .18),
                            inset 0 1px 0 rgba(255,255,255,.78) !important;
                        color: var(--text, #0f172a) !important;
                        text-align: center;
                        transition: transform .18s ease, box-shadow .18s ease, border-color .18s ease !important;
                        white-space: normal !important;
                }
                div[class*="st-key-sp_cat_"] div[data-testid="stButton"] > button:hover,
                div[class*="st-key-sp_cat_"] div[data-testid="stButton"] > button:focus {
                        transform: translateY(-2px);
                        border-color: rgba(var(--practice-cat-rgb), .72) !important;
                        box-shadow:
                            0 12px 28px rgba(var(--practice-cat-rgb), .34),
                            0 0 18px rgba(var(--practice-cat-rgb), .24),
                            inset 0 1px 0 rgba(255,255,255,.84) !important;
                }
                div[class*="st-key-sp_cat_"] div[data-testid="stButton"] > button::before {
                        position: absolute;
                        top: 14px;
                        left: 50%;
                        width: 30px;
                        height: 30px;
                        transform: translateX(-50%);
                        display: flex;
                        align-items: center;
                        justify-content: center;
                        border-radius: 999px;
                        background: rgba(255,255,255,.86);
                        border: 1px solid rgba(var(--practice-cat-rgb), .34);
                        box-shadow: 0 10px 18px rgba(var(--practice-cat-rgb), .18);
                        font-size: 1rem;
                        pointer-events: none;
                }
                div[class*="st-key-sp_cat_"] div[data-testid="stButton"] > button p {
                        position: relative;
                        z-index: 1;
                        margin: 38px auto 0;
                        max-width: 240px;
                        text-align: center;
                        white-space: pre-line !important;
                }
                div[class*="st-key-sp_cat_"] div[data-testid="stButton"] > button p strong {
                        display: block;
                        font-size: .96rem;
                        line-height: 1.2;
                        font-weight: 800;
                        color: var(--text, #0f172a) !important;
                }
                div[class*="st-key-sp_cat_active_"] div[data-testid="stButton"] > button {
                        border: 2px solid rgba(234,179,8,.85) !important;
                        background:
                            radial-gradient(circle at 50% -10%, rgba(var(--practice-cat-rgb), .20), transparent 42%),
                            linear-gradient(180deg, rgba(var(--practice-cat-rgb), .10), rgba(var(--practice-cat-rgb), .04)) !important;
                        box-shadow:
                            0 12px 30px rgba(var(--practice-cat-rgb), .34),
                            0 0 18px rgba(var(--practice-cat-rgb), .22),
                            0 0 0 1px rgba(234,179,8,.24),
                            inset 0 1px 0 rgba(255,255,255,.78) !important;
                }
                .st-key-sp_cat___all__, .st-key-sp_cat_active___all__ { --practice-cat-rgb: 59,130,246; }
                .st-key-sp_cat_multiple_choice, .st-key-sp_cat_active_multiple_choice { --practice-cat-rgb: 168,85,247; }
                .st-key-sp_cat_true_false, .st-key-sp_cat_active_true_false { --practice-cat-rgb: 16,185,129; }
                .st-key-sp_cat_fill_in_the_blanks, .st-key-sp_cat_active_fill_in_the_blanks { --practice-cat-rgb: 245,158,11; }
                .st-key-sp_cat_short_answer, .st-key-sp_cat_active_short_answer { --practice-cat-rgb: 239,68,68; }
                .st-key-sp_cat_matching, .st-key-sp_cat_active_matching { --practice-cat-rgb: 6,182,212; }
                .st-key-sp_cat_reading_comprehension, .st-key-sp_cat_active_reading_comprehension { --practice-cat-rgb: 234,179,8; }
                .st-key-sp_cat_error_correction, .st-key-sp_cat_active_error_correction { --practice-cat-rgb: 20,184,166; }
                .st-key-sp_cat_word_search_vocab, .st-key-sp_cat_active_word_search_vocab { --practice-cat-rgb: 99,102,241; }
                .st-key-sp_cat___all__ div[data-testid="stButton"] > button::before,
                .st-key-sp_cat_active___all__ div[data-testid="stButton"] > button::before { content: "🎯"; }
                .st-key-sp_cat_multiple_choice div[data-testid="stButton"] > button::before,
                .st-key-sp_cat_active_multiple_choice div[data-testid="stButton"] > button::before { content: "🔘"; }
                .st-key-sp_cat_true_false div[data-testid="stButton"] > button::before,
                .st-key-sp_cat_active_true_false div[data-testid="stButton"] > button::before { content: "✅"; }
                .st-key-sp_cat_fill_in_the_blanks div[data-testid="stButton"] > button::before,
                .st-key-sp_cat_active_fill_in_the_blanks div[data-testid="stButton"] > button::before { content: "✏️"; }
                .st-key-sp_cat_short_answer div[data-testid="stButton"] > button::before,
                .st-key-sp_cat_active_short_answer div[data-testid="stButton"] > button::before { content: "📝"; }
                .st-key-sp_cat_matching div[data-testid="stButton"] > button::before,
                .st-key-sp_cat_active_matching div[data-testid="stButton"] > button::before { content: "🔗"; }
                .st-key-sp_cat_reading_comprehension div[data-testid="stButton"] > button::before,
                .st-key-sp_cat_active_reading_comprehension div[data-testid="stButton"] > button::before { content: "📖"; }
                .st-key-sp_cat_error_correction div[data-testid="stButton"] > button::before,
                .st-key-sp_cat_active_error_correction div[data-testid="stButton"] > button::before { content: "🔍"; }
                .st-key-sp_cat_word_search_vocab div[data-testid="stButton"] > button::before,
                .st-key-sp_cat_active_word_search_vocab div[data-testid="stButton"] > button::before { content: "🔠"; }
        .classio-practice-card {
            --practice-resource-accent: #60a5fa;
            position: relative;
            overflow: hidden;
            background:
              radial-gradient(circle at top right, color-mix(in srgb, var(--practice-resource-accent) 12%, transparent), transparent 38%),
              linear-gradient(90deg, color-mix(in srgb, var(--practice-resource-accent) 5%, transparent), transparent 30%),
              linear-gradient(180deg, var(--panel), color-mix(in srgb, var(--panel) 84%, white 16%));
            border: 1px solid color-mix(in srgb, var(--border) 78%, var(--practice-resource-accent) 22%);
            border-radius: 22px;
            padding: 18px 20px 18px 26px;
            box-shadow:
              0 18px 42px rgba(15,23,42,.08),
              inset 0 1px 0 rgba(255,255,255,.70);
            margin-bottom: 0.55rem;
        }
        .classio-practice-card::before {
            content: "";
            position: absolute;
            inset: 12px auto 12px 10px;
            width: 7px;
            border-radius: 999px;
            background: linear-gradient(
              180deg,
              color-mix(in srgb, var(--practice-resource-accent) 78%, white 22%),
              var(--practice-resource-accent)
            );
            box-shadow:
              0 0 0 1px color-mix(in srgb, var(--practice-resource-accent) 28%, transparent),
              0 12px 28px color-mix(in srgb, var(--practice-resource-accent) 24%, transparent);
        }
        .classio-practice-title {
            font-size: 1.06rem;
            font-weight: 800;
            line-height: 1.25;
            color: var(--text);
        }
        .classio-practice-meta {
            margin-top: 0.65rem;
            color: var(--muted);
            font-size: 0.9rem;
            line-height: 1.45;
        }
        .classio-practice-kind-chip {
            display:inline-flex;
            align-items:center;
            gap:5px;
            width:max-content;
            margin-top:0.55rem;
            border-radius:999px;
            padding:5px 10px;
            font-size:.76rem;
            font-weight:850;
            color:var(--text);
            background:color-mix(in srgb, var(--practice-resource-accent) 14%, var(--panel));
            border:1px solid color-mix(in srgb, var(--practice-resource-accent) 34%, var(--border));
        }
        .classio-practice-statgrid {
            display: flex;
            gap: 0.7rem;
            flex-wrap: wrap;
            margin-top: 0.95rem;
        }
        .classio-practice-stat {
            min-width: 96px;
            padding: 0.72rem 0.85rem;
            border-radius: 15px;
            background: rgba(148,163,184,.08);
            border: 1px solid rgba(148,163,184,.16);
        }
        .classio-practice-stat-label {
            font-size: 0.72rem;
            font-weight: 800;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            color: var(--muted);
        }
        .classio-practice-stat-value {
            margin-top: 0.22rem;
            font-size: 1rem;
            font-weight: 800;
            color: var(--text);
        }
        .classio-practice-action-label {
            font-size: 0.76rem;
            font-weight: 800;
            text-transform: uppercase;
            letter-spacing: 0.06em;
            color: var(--muted);
            margin: 0.2rem 0 0.55rem 0.1rem;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


# ── Browse & start ──────────────────────────────────────────────

def _render_browse_tab():
    st.caption(t("choose_practice_source"))
    video_feature_enabled = user_has_feature(get_current_user_id(), "videos_access")

    # Supported worksheet types for interactive practice
    _PRACTICE_WS_TYPES = {
        "multiple_choice", "true_false", "fill_in_the_blanks",
        "short_answer", "matching", "reading_comprehension", "error_correction",
        "word_search_vocab",
    }

    # Use the same subject / level / stage lists as teacher pages
    from helpers.lesson_planner import (
        QUICK_SUBJECTS, LEARNER_STAGES, LANGUAGE_LEVELS, ACADEMIC_BANDS,
        subject_label as _subject_label, get_level_options,
    )

    _sp_options = ["__all__"] + QUICK_SUBJECTS

    def _format_subject(x):
        if x == "__all__":
            return t("all_subjects")
        return _subject_label(x)

    def _render_resource_controls(panel_key: str) -> tuple[str, str, str, str]:
        search_query = st.text_input(
            t("explore_resource_search"),
            key=f"sp_resource_search_{panel_key}",
            placeholder=t("explore_resource_search_placeholder"),
        ).strip().lower()
        st.markdown("<div style='height:0.2rem;'></div>", unsafe_allow_html=True)

        f_col1, f_col2, f_col3 = st.columns(3)
        with f_col1:
            sp_subject_local = st.selectbox(
                t("filter_by_subject"),
                options=_sp_options,
                format_func=_format_subject,
                key=f"sp_filter_subject_{panel_key}",
            )

        sp_other_subject_local = ""
        if sp_subject_local == "other":
            sp_other_subject_local = st.text_input(
                t("other_subject_label"),
                key=f"sp_other_subject_{panel_key}",
            ).strip()

        if sp_subject_local in ("__all__", "other"):
            _all_levels = sorted(set(LANGUAGE_LEVELS + ACADEMIC_BANDS), key=lambda x: (LANGUAGE_LEVELS + ACADEMIC_BANDS).index(x))
        else:
            _all_levels = get_level_options(sp_subject_local)

        def _format_level(x):
            if x == "__all__":
                return t("all_levels")
            translated = t(x)
            return translated if translated != x else x

        with f_col2:
            sp_level_local = st.selectbox(
                t("level_cefr"),
                options=["__all__"] + _all_levels,
                format_func=_format_level,
                key=f"sp_filter_level_{panel_key}",
            )

        _stage_options = ["__all__"] + LEARNER_STAGES
        with f_col3:
            sp_stage_local = st.selectbox(
                t("learner_stage"),
                options=_stage_options,
                format_func=lambda x: t("all_stages") if x == "__all__" else t(x),
                key=f"sp_filter_stage_{panel_key}",
            )

        effective_subject_local = sp_other_subject_local if sp_subject_local == "other" else sp_subject_local
        st.markdown("<div style='height:0.35rem;'></div>", unsafe_allow_html=True)
        return search_query, effective_subject_local, sp_level_local, sp_stage_local

    # ── Pre-load data ────────────────────────────────────────────
    from helpers.worksheet_storage import load_public_worksheets
    from helpers.quick_exam_storage import load_public_exams
    pub_ws = load_public_worksheets()
    pub_ex = load_public_exams()
    pub_videos = load_public_videos() if video_feature_enabled else pub_ws.head(0).copy()

    if not pub_ws.empty and "worksheet_type" in pub_ws.columns:
        pub_ws = pub_ws[pub_ws["worksheet_type"].isin(_PRACTICE_WS_TYPES)].reset_index(drop=True)

    # Hide worksheets/exams already completed by this student
    _done = get_completed_source_ids()
    if not pub_ws.empty and _done["worksheet"] and "id" in pub_ws.columns:
        pub_ws = pub_ws[~pub_ws["id"].isin(_done["worksheet"])].reset_index(drop=True)
    if not pub_ex.empty and _done["exam"] and "id" in pub_ex.columns:
        pub_ex = pub_ex[~pub_ex["id"].isin(_done["exam"])].reset_index(drop=True)

    _render_recommended_materials(pub_ws, pub_ex, pub_videos if video_feature_enabled else None)

    practice_source_options = [
        ("worksheets", f"📋 {t('community_worksheets')}"),
        ("exams", f"📄 {t('community_exams')}"),
    ]
    if video_feature_enabled:
        practice_source_options.append(("videos", f"🎬 {_ui_text('videos_label', 'Videos')}"))
    practice_source_tabs = st.tabs([label for _key, label in practice_source_options])

    with practice_source_tabs[0]:
        practice_search_query, _effective_subject, sp_level, sp_stage = _render_resource_controls("ws")

        # Apply subject/level/stage filters
        if not pub_ws.empty and _effective_subject and _effective_subject != "__all__" and "subject" in pub_ws.columns:
            pub_ws = pub_ws[pub_ws["subject"].str.lower() == _effective_subject.lower()].reset_index(drop=True)
        if not pub_ws.empty and sp_level != "__all__" and "level_or_band" in pub_ws.columns:
            pub_ws = pub_ws[pub_ws["level_or_band"] == sp_level].reset_index(drop=True)
        if not pub_ws.empty and sp_stage != "__all__" and "learner_stage" in pub_ws.columns:
            pub_ws = pub_ws[pub_ws["learner_stage"] == sp_stage].reset_index(drop=True)
        if pub_ws.empty:
            render_empty_state(
                title_key="student_practice_empty_worksheets_title",
                body_key="student_practice_empty_worksheets_body",
                steps=[
                    "student_practice_empty_step_filters",
                    "student_practice_empty_step_assignments",
                    "student_practice_empty_step_return",
                ],
                icon="📋",
            )
        else:
            # ── Neon category filter cards ───────────────────────
            _CATEGORY_CARDS = [
                ("__all__",                  "🎯", t("all"),                    "59,130,246"),   # blue
                ("multiple_choice",          "🔘", t("multiple_choice"),        "168,85,247"),   # purple
                ("true_false",               "✅", t("true_false"),             "16,185,129"),   # green
                ("fill_in_the_blanks",       "✏️", t("fill_in_the_blanks"),    "245,158,11"),   # amber
                ("short_answer",             "📝", t("short_answer"),           "239,68,68"),    # red
                ("matching",                 "🔗", t("matching"),               "6,182,212"),    # cyan
                ("reading_comprehension",    "📖", t("reading_comprehension"),  "234,179,8"),    # gold
                ("error_correction",         "🔍", t("error_correction"),       "20,184,166"),   # teal
                ("word_search_vocab",        "🔠", t("word_search_vocab"),      "99,102,241"),   # indigo
            ]

            active_cat = st.session_state.get("sp_filter_ws_type")

            # Pre-filter worksheets once
            _ws_base = pub_ws.copy()
            if practice_search_query and not _ws_base.empty:
                from helpers.goal_explorer import _rank_search
                _ws_base = _rank_search(_ws_base, practice_search_query, weights={
                    "title": 5, "topic": 4, "subject": 3,
                    "worksheet_type": 3, "learner_stage": 2,
                    "level_or_band": 2, "author_name": 1,
                })
            else:
                _ws_base = _ws_base.head(24)

            if practice_search_query:
                st.caption(t("search_results"))
                ws_search_rows = _ws_base.reset_index(drop=True).to_dict("records")
                ws_search_page_rows, *_ = _slice_practice_page(ws_search_rows, "student_practice_ws_search_page")
                if not ws_search_page_rows:
                    st.info(t("no_data"))
                else:
                    for idx in range(0, len(ws_search_page_rows), 3):
                        pair = ws_search_page_rows[idx:idx + 3]
                        _ws_cols = st.columns(3, gap="medium")
                        for col_i, row in enumerate(pair):
                            with _ws_cols[col_i]:
                                _render_practice_card(
                                    title=str(row.get("title") or t("untitled_worksheet")),
                                    subject=str(row.get("subject") or ""),
                                    topic=str(row.get("topic") or ""),
                                    level=str(row.get("level_or_band") or ""),
                                    ws_type=str(row.get("worksheet_type") or ""),
                                    btn_key=f"sp_ws_search_{row.get('id', idx)}_{idx}_{col_i}",
                                    color=resource_kind_accent("worksheet"),
                                    row=row,
                                    resource_type="worksheet",
                                )
                                if st.session_state.pop(f"_start_sp_ws_search_{row.get('id', idx)}_{idx}_{col_i}", False):
                                    if _open_worksheet_practice_from_row(row):
                                        st.rerun()
                    _render_practice_pagination(ws_search_rows, "student_practice_ws_search_page")
                return

            # Expander-like behaviour:
            # - No category open -> show all category cards in a 2-col grid
            # - Category open -> show only that card + its worksheets below
            if active_cat is not None:
                # ── Expanded: show active category + worksheets ──
                _active_info = next(
                    (c for c in _CATEGORY_CARDS if c[0] == active_cat),
                    _CATEGORY_CARDS[0],
                )
                cat_key, _emoji, label, _rgb = _active_info
                if st.button(f"**{label}**", key=f"sp_cat_active_{cat_key}", use_container_width=True):
                    st.session_state["sp_filter_ws_type"] = None
                    st.rerun()

                st.markdown("---")

                # Show worksheets for this category
                _ws_cat = _ws_base.copy()
                if active_cat != "__all__" and not _ws_cat.empty and "worksheet_type" in _ws_cat.columns:
                    _ws_cat = _ws_cat[_ws_cat["worksheet_type"] == active_cat].reset_index(drop=True)

                if _ws_cat.empty:
                    st.info(t("no_data"))
                else:
                    _ws_rows = _ws_cat.reset_index(drop=True).to_dict("records")
                    _ws_page_rows, *_ = _slice_practice_page(_ws_rows, f"student_practice_ws_cat_{active_cat}")
                    for idx in range(0, len(_ws_page_rows), 3):
                        pair = _ws_page_rows[idx:idx + 3]
                        _ws_cols = st.columns(3, gap="medium")
                        for col_i, row in enumerate(pair):
                            with _ws_cols[col_i]:
                                _render_practice_card(
                                    title=str(row.get("title") or t("untitled_worksheet")),
                                    subject=str(row.get("subject") or ""),
                                    topic=str(row.get("topic") or ""),
                                    level=str(row.get("level_or_band") or ""),
                                    ws_type=str(row.get("worksheet_type") or ""),
                                    btn_key=f"sp_ws_{row.get('id', idx)}_{idx}_{col_i}",
                                    color=resource_kind_accent("worksheet"),
                                    row=row,
                                    resource_type="worksheet",
                                )
                                if st.session_state.pop(f"_start_sp_ws_{row.get('id', idx)}_{idx}_{col_i}", False):
                                    if _open_worksheet_practice_from_row(row):
                                        st.rerun()
                    _render_practice_pagination(_ws_rows, f"student_practice_ws_cat_{active_cat}")
            else:
                # ── Collapsed: show all category cards in 3-col grid ─
                for row_start in range(0, len(_CATEGORY_CARDS), 3):
                    pair = _CATEGORY_CARDS[row_start:row_start + 3]
                    _cat_cols = st.columns(3, gap="medium")
                    for ci, (cat_key, _emoji, label, _rgb) in enumerate(pair):
                        with _cat_cols[ci]:
                            if st.button(f"**{label}**", key=f"sp_cat_{cat_key}", use_container_width=True):
                                st.session_state["sp_filter_ws_type"] = cat_key
                                st.rerun()

    with practice_source_tabs[1]:
        practice_search_query, _effective_subject, sp_level, sp_stage = _render_resource_controls("exam")

        # Apply subject/level/stage filters
        if not pub_ex.empty and _effective_subject and _effective_subject != "__all__" and "subject" in pub_ex.columns:
            pub_ex = pub_ex[pub_ex["subject"].str.lower() == _effective_subject.lower()].reset_index(drop=True)
        if not pub_ex.empty and sp_level != "__all__" and "level" in pub_ex.columns:
            pub_ex = pub_ex[pub_ex["level"] == sp_level].reset_index(drop=True)
        if not pub_ex.empty and sp_stage != "__all__" and "learner_stage" in pub_ex.columns:
            pub_ex = pub_ex[pub_ex["learner_stage"] == sp_stage].reset_index(drop=True)
        if pub_ex.empty:
            render_empty_state(
                title_key="student_practice_empty_exams_title",
                body_key="student_practice_empty_exams_body",
                steps=[
                    "student_practice_empty_step_filters",
                    "student_practice_empty_step_assignments",
                    "student_practice_empty_step_return",
                ],
                icon="📄",
            )
        else:
            filtered = pub_ex.copy()
            if practice_search_query:
                from helpers.goal_explorer import _rank_search
                filtered = _rank_search(filtered, practice_search_query, weights={
                    "title": 5, "topic": 4, "subject": 3,
                    "learner_stage": 2, "level": 2, "author_name": 1,
                })
            else:
                filtered = filtered.head(24)

            if filtered.empty:
                st.info(t("no_data"))
            else:
                rows = filtered.reset_index(drop=True).to_dict("records")
                page_rows, *_ = _slice_practice_page(rows, "student_practice_exams_page")
                for idx in range(0, len(page_rows), 3):
                    pair = page_rows[idx:idx + 3]
                    cols = st.columns(3, gap="medium")
                    for col_i, row in enumerate(pair):
                        with cols[col_i]:
                            _render_practice_card(
                                title=str(row.get("title") or t("untitled_plan")),
                                subject=str(row.get("subject") or ""),
                                topic=str(row.get("topic") or ""),
                                level=str(row.get("level") or ""),
                                ws_type=str(row.get("exam_length") or ""),
                                btn_key=f"sp_ex_{row.get('id', idx)}_{idx}_{col_i}",
                                color=resource_kind_accent("exam"),
                                row=row,
                                resource_type="exam",
                            )
                            if st.session_state.pop(f"_start_sp_ex_{row.get('id', idx)}_{idx}_{col_i}", False):
                                if _open_exam_practice_from_row(row):
                                    st.rerun()
                _render_practice_pagination(rows, "student_practice_exams_page")

    if video_feature_enabled and len(practice_source_tabs) > 2:
        with practice_source_tabs[2]:
            practice_search_query, _effective_subject, sp_level, sp_stage = _render_resource_controls("videos")

            filtered_videos = pub_videos.copy()
            if not filtered_videos.empty and _effective_subject and _effective_subject != "__all__" and "subject" in filtered_videos.columns:
                filtered_videos = filtered_videos[
                    filtered_videos["subject"].astype(str).str.lower() == _effective_subject.lower()
                ].reset_index(drop=True)
            if not filtered_videos.empty and sp_level != "__all__" and "level_or_band" in filtered_videos.columns:
                filtered_videos = filtered_videos[
                    filtered_videos["level_or_band"].astype(str) == sp_level
                ].reset_index(drop=True)
            if not filtered_videos.empty and sp_stage != "__all__" and "learner_stage" in filtered_videos.columns:
                filtered_videos = filtered_videos[
                    filtered_videos["learner_stage"].astype(str) == sp_stage
                ].reset_index(drop=True)
            if filtered_videos.empty:
                render_empty_state(
                    title_key="student_practice_recommendations_empty_title",
                    body_key="student_practice_recommendations_empty_body",
                    steps=[
                        "student_practice_empty_step_filters",
                        "student_practice_empty_step_assignments",
                        "student_practice_empty_step_return",
                    ],
                    icon="🎬",
                )
            else:
                if practice_search_query:
                    from helpers.goal_explorer import _rank_search

                    filtered_videos = _rank_search(
                        filtered_videos,
                        practice_search_query,
                        weights={
                            "title": 5,
                            "topic": 4,
                            "subject": 3,
                            "learner_stage": 2,
                            "level_or_band": 2,
                            "author_name": 1,
                        },
                    )
                ranked_videos = rank_recommended_materials(videos_df=filtered_videos)
                rows = [item.get("row") or {} for item in ranked_videos] if ranked_videos else filtered_videos.head(24).to_dict("records")
                page_rows, *_ = _slice_practice_page(rows, "student_practice_videos_page")
                for idx in range(0, len(page_rows), 3):
                    trio = page_rows[idx:idx + 3]
                    cols = st.columns(3, gap="medium")
                    for col_i, row in enumerate(trio):
                        with cols[col_i]:
                            _render_practice_card(
                                title=str(row.get("title") or _ui_text("video_label", "Video")),
                                subject=str(row.get("subject") or ""),
                                topic=str(row.get("topic") or ""),
                                level=str(row.get("level_or_band") or ""),
                                ws_type=_ui_text("video_label", "Video"),
                                btn_key=f"sp_video_{row.get('id', idx)}_{idx}_{col_i}",
                                color=resource_kind_accent("video"),
                                row=row,
                                resource_type="video",
                            )
                _render_practice_pagination(rows, "student_practice_videos_page")


def _render_practice_card(
    title: str, subject: str, topic: str, level: str,
    ws_type: str, btn_key: str, color: str = "",
    row: dict | None = None,
    resource_type: str = "worksheet",
    recommendation_item: dict | None = None,
):
    """Render a gallery practice card matching the teacher resource bank."""
    import html as _html

    subject_label = t(f"subject_{subject.lower().replace(' ', '_')}") if subject else ""
    level_label = level if level in ("A1", "A2", "B1", "B2", "C1", "C2") else (t(level) if level else "")
    type_label = t(ws_type) if ws_type and t(ws_type) != ws_type else ws_type
    row = dict(row or {})
    combined_payload = _load_card_gallery_payload(row, resource_type)
    hero_image = extract_gallery_image_url(combined_payload)
    language_label = extract_gallery_language_label(combined_payload)

    chips = ""
    if language_label:
        chips += f'<span class="cm-resource-chip">🌐 {_html.escape(language_label)}</span>'
    if subject_label:
        chips += f'<span class="cm-resource-chip">📚 {_html.escape(subject_label)}</span>'
    if level_label:
        chips += f'<span class="cm-resource-chip">🏷️ {_html.escape(level_label)}</span>'
    if type_label:
        chips += f'<span class="cm-resource-chip">🧩 {_html.escape(type_label)}</span>'
    if row.get("_recommended_assignment_id"):
        chips += f'<span class="cm-resource-chip">📌 {_html.escape(t("assignment_status_assigned"))}</span>'
    if resource_type != "video":
        chips += f'<span class="cm-resource-chip">⚙️ {_html.escape(t("mode_ai"))}</span>'
    else:
        chips += f'<span class="cm-resource-chip">🎬 {_html.escape(_ui_text("video_label", "Video"))}</span>'

    meta_html = ""
    if row.get("author_name"):
        meta_html += f'<div class="cm-resource-meta">👤 {_html.escape(str(row.get("author_name") or ""))}</div>'
    if row.get("_recommended_assignment_teacher_name"):
        meta_html += f'<div class="cm-resource-meta">👩‍🏫 {_html.escape(str(row.get("_recommended_assignment_teacher_name") or ""))}</div>'
    if row.get("created_at"):
        meta_html += f'<div class="cm-resource-meta">🕒 {_html.escape(str(row.get("created_at") or "")[:16])}</div>'

    st.markdown(
        render_gallery_card_html(
            kind="video" if resource_type == "video" else "exam" if resource_type == "exam" else "worksheet",
            title=title,
            chips_html=chips,
            description=topic or t("no_description_available"),
            meta_html=meta_html,
            image_url=hero_image,
            placeholder_label=(
                _ui_text("video_label", "Video")
                if resource_type == "video"
                else t("quick_exam_builder") if resource_type == "exam" else t("worksheet_maker")
            ),
        ),
        unsafe_allow_html=True,
    )

    if resource_type == "video":
        if st.button(
            f"▶ {_ui_text('watch_video', 'Watch video')}",
            key=btn_key,
            use_container_width=True,
        ):
            assignment_id = int(row.get("_recommended_assignment_id") or 0)
            if _open_video_item(
                combined_payload,
                {
                    "subject": subject,
                    "topic": topic,
                    "learner_stage": str(row.get("learner_stage") or ""),
                    "level": level,
                },
                assignment_id=assignment_id,
            ):
                if recommendation_item:
                    log_student_recommendation_open(recommendation_item, surface="student_practice")
                st.rerun()
        return

    if st.button(f"▶ {t('start_practice')}", key=btn_key, use_container_width=True):
        if recommendation_item:
            log_student_recommendation_open(recommendation_item, surface="student_practice")
        st.session_state[f"_start_{btn_key}"] = True
        st.rerun()


# ── Active session ──────────────────────────────────────────────

def _render_active_session(exercise_data: dict):
    """Render the interactive practice and handle completion."""
    if st.button(f"← {t('back')}", key="practice_back"):
        autosave_practice_draft_if_needed(
            exercise_data,
            session_key="sp",
            meta=st.session_state.get("practice_meta") or {},
            force=True,
        )
        # Clear all practice-related session state
        for key in list(st.session_state.keys()):
            if key.startswith("_start_sp_") or key.startswith("_practice_") or key.startswith("sp_"):
                del st.session_state[key]
        st.session_state.pop("practice_exercise_data", None)
        st.session_state.pop("practice_meta", None)
        st.session_state.pop("_practice_retry_session_id", None)
        st.session_state.pop("_practice_assignment_id", None)
        st.session_state.pop("_practice_assignment_type", None)
        st.session_state.pop("_practice_resume_session_id", None)
        st.session_state.pop("_practice_resume_answers", None)
        st.session_state.pop("_practice_resume_notice", None)
        st.session_state.pop("_practice_last_autosave_payload_sp", None)
        st.session_state.pop("_practice_last_autosave_at_sp", None)
        st.session_state.pop("_practice_last_autosave_failed_sp", None)
        st.rerun()

    if st.session_state.pop("_practice_resume_notice", False):
        st.info(t("practice_resumed_notice"))

    result = render_practice_session(exercise_data, session_key="sp")
    review_mode = bool(st.session_state.get("_practice_review_mode"))

    # When submitted, save results ONCE (guard against duplicate saves on rerender)
    if result and review_mode:
        st.info(_ui_text("review_mode_notice", "Review mode — your previous answers are shown without creating a new attempt."))
    elif result and not st.session_state.get("_practice_saved_sp"):
        st.session_state["_practice_saved_sp"] = True

        if str(exercise_data.get("source_type") or "").strip() != "demo":
            # Real exercise: save to DB
            meta = st.session_state.get("practice_meta") or {}
            xp   = result.get("xp_earned", 0)
            strk = result.get("best_streak", 0)

            retry_id = st.session_state.get("_practice_retry_session_id")
            if retry_id:
                update_practice_session(
                    retry_id,
                    exercise_data,
                    total=result["total"],
                    correct=result["correct"],
                    score_pct=result["score_pct"],
                    xp_earned=xp,
                    best_streak=strk,
                )
                session_id = retry_id
            elif st.session_state.get("_practice_resume_session_id"):
                resumed_id = _safe_int(st.session_state["_practice_resume_session_id"])
                update_practice_session(
                    resumed_id,
                    exercise_data,
                    total=result["total"],
                    correct=result["correct"],
                    score_pct=result["score_pct"],
                    xp_earned=xp,
                    best_streak=strk,
                )
                session_id = resumed_id
            else:
                session_id = save_practice_session(
                    exercise_data,
                    total=result["total"],
                    correct=result["correct"],
                    score_pct=result["score_pct"],
                    xp_earned=xp,
                    best_streak=strk,
                    meta=meta,
                )
            if session_id:
                st.session_state["_practice_last_session_id"] = session_id
                save_practice_answers(
                    session_id, exercise_data, result["answers"], session_key="sp",
                    replace_existing=bool(retry_id or st.session_state.get("_practice_resume_session_id")),
                )
            assignment_id = st.session_state.get("_practice_assignment_id")
            assignment_scope = (
                load_student_assignment_by_id(_safe_int(assignment_id))
                if assignment_id
                else {}
            )
            if assignment_id:
                try:
                    from helpers.teacher_student_integration import record_assignment_attempt_from_practice

                    record_assignment_attempt_from_practice(
                        _safe_int(assignment_id),
                        session_id,
                        result,
                        exercise_data,
                    )
                except Exception:
                    pass
            # Always save progress (even if session save failed)
            update_practice_progress(
                exercise_data, result["answers"],
                meta={
                    **meta,
                    "assignment_id": _safe_int(assignment_id),
                    "teacher_id": str(assignment_scope.get("teacher_id") or ""),
                    "learning_program_assignment_id": int(
                        assignment_scope.get("learning_program_assignment_id") or 0
                    ),
                },
                session_key="sp",
                xp_earned=xp, best_streak=strk,
            )
            st.session_state.pop("_practice_resume_session_id", None)
            st.session_state.pop("_practice_resume_answers", None)

    if result and not review_mode and str(exercise_data.get("source_type") or "").strip() != "demo":
        _render_teacher_review_request_panel(exercise_data)


def _render_teacher_review_request_panel(exercise_data: dict) -> None:
    session_id = st.session_state.get("_practice_last_session_id")
    if not session_id:
        return

    source_type = str(exercise_data.get("source_type") or "").strip()
    if source_type not in {"worksheet", "exam"}:
        return

    meta = st.session_state.get("practice_meta") or {}
    subject_key = str(meta.get("subject") or "").strip()
    links = get_reviewable_teacher_links_for_subject(subject_key)
    requests = load_student_review_requests_for_session(_safe_int(session_id))

    st.markdown(
        """
        <div style="
            margin-top:1rem;
            padding:20px 22px;
            border-radius:22px;
            background:
              radial-gradient(circle at top right, rgba(16,185,129,.10), transparent 36%),
              linear-gradient(180deg, var(--panel), color-mix(in srgb, var(--panel) 84%, white 16%));
            border:1px solid color-mix(in srgb, var(--border) 78%, rgba(16,185,129,.20) 22%);
            box-shadow:0 14px 32px rgba(15,23,42,.08);
            margin-bottom:0.85rem;
        ">
            <div style="font-size:1.1rem;font-weight:800;color:var(--text);">🧑‍🏫 """
        + t("request_teacher_review")
        + """</div>
            <div style="margin-top:0.35rem;color:var(--muted);font-size:0.92rem;">"""
        + t("teacher_review_note_placeholder")
        + """</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if requests:
        latest = requests[0]
        teacher_name = latest.get("teacher_name") or "—"
        status_key = f"teacher_review_status_{latest.get('status')}"
        st.success(t("teacher_review_requested_with_name", teacher=teacher_name))
        st.caption(f"{t('teacher_review_current_status')}: {t(status_key)}")
        feedback = _clean_teacher_feedback_text(latest.get("teacher_feedback"))
        if feedback:
            st.info(f"{t('teacher_review_feedback')}: {feedback}")
        return

    if not links:
        st.info(t("teacher_review_not_connected"))
        if st.button(t("teacher_review_find_teacher"), key=f"find_teacher_review_{session_id}", type="primary"):
            go_to("student_find_teacher")
            st.rerun()
        return

    selected_teacher_idx = st.selectbox(
        t("teacher_review_select_teacher"),
        options=list(range(len(links))),
        format_func=lambda idx: f"{links[idx].get('teacher_name', '—')} · {', '.join(s.get('subject_label', '') for s in links[idx].get('active_subjects', []) if s.get('subject_label'))}",
        key=f"teacher_review_teacher_{session_id}",
    )
    review_note = st.text_area(
        t("teacher_review_note"),
        key=f"teacher_review_note_{session_id}",
        height=90,
        placeholder=t("teacher_review_note_placeholder"),
    )
    if st.button(t("request_teacher_review"), key=f"teacher_review_request_btn_{session_id}", use_container_width=True, type="primary"):
        selected = links[selected_teacher_idx]
        ok, msg = create_teacher_review_request(
            practice_session_id=_safe_int(session_id),
            teacher_id=str(selected.get("teacher_id") or ""),
            assignment_id=st.session_state.get("_practice_assignment_id"),
            request_note=review_note,
        )
        if ok:
            st.success(t(msg))
            st.rerun()
        st.error(t(msg))


# ── History tab ─────────────────────────────────────────────────

def _practice_subject_groups(frame) -> list[tuple[str, str, object]]:
    if frame is None or frame.empty or "subject" not in frame.columns:
        return []
    grouped: dict[tuple[str, str], dict] = {}
    for _, row in frame.iterrows():
        subject = str(row.get("subject") or "").strip()
        if not subject:
            continue
        subject_key = subject.lower()
        teacher_id = str(row.get("_scope_teacher_id") or "").strip()
        teacher_name = str(row.get("_scope_teacher_name") or "").strip()
        bucket = grouped.setdefault(
            (subject_key, teacher_id),
            {
                "subject": subject,
                "teacher_name": teacher_name,
                "indexes": [],
            },
        )
        bucket["indexes"].append(row.name)

    subject_counts: dict[str, int] = {}
    for subject_key, _teacher_id in grouped:
        subject_counts[subject_key] = subject_counts.get(subject_key, 0) + 1

    groups = []
    for (subject_key, teacher_id), payload in sorted(grouped.items()):
        subject = str(payload.get("subject") or subject_key)
        translation_key = f"subject_{subject_key.replace(' ', '_')}"
        label = t(translation_key)
        if label == translation_key:
            label = subject
        teacher_name = str(payload.get("teacher_name") or "").strip()
        if subject_counts.get(subject_key, 0) > 1 and teacher_name:
            label = f"{label} · {teacher_name}"
        scope_key = f"{subject_key}_{teacher_id or 'independent'}"
        scoped = frame.loc[payload.get("indexes") or []].reset_index(drop=True)
        groups.append((scope_key, label, scoped))
    return groups


def _render_history_tab(history_override=None, *, scope_key: str = ""):
    history = history_override if history_override is not None else load_practice_history()
    if history.empty:
        render_empty_state(
            title_key="student_practice_history_empty_title",
            body_key="student_practice_history_empty_body",
            steps=[
                "student_practice_history_empty_step_start",
                "student_practice_history_empty_step_save",
                "student_practice_history_empty_step_review",
            ],
            icon="📊",
        )
        return

    if history_override is None:
        history = history.copy()
        session_ids = (
            [
                _safe_int(value)
                for value in history["id"].tolist()
                if _safe_int(value) > 0
            ]
            if "id" in history.columns
            else []
        )
        assignment_scopes = load_practice_assignment_scope_map(session_ids)
        if "id" in history.columns:
            history["_scope_teacher_id"] = history["id"].apply(
                lambda value: str(assignment_scopes.get(_safe_int(value), {}).get("teacher_id") or "")
            )
            history["_scope_teacher_name"] = history["id"].apply(
                lambda value: str(assignment_scopes.get(_safe_int(value), {}).get("teacher_name") or "")
            )
        subject_groups = _practice_subject_groups(history)
        if len(subject_groups) > 1:
            tabs = st.tabs([f"📚 {label}" for subject_key, label, _frame in subject_groups])
            for tab, (subject_key, _label, scoped_history) in zip(tabs, subject_groups):
                with tab:
                    _render_history_tab(scoped_history, scope_key=subject_key)
            return

    history_rows = history.reset_index(drop=True).to_dict("records")
    page_state_key = f"student_practice_history_page_{scope_key or 'all'}"
    history_page_rows, *_ = _slice_practice_page(history_rows, page_state_key)

    assignment_ids = []
    for row in history_page_rows:
        source_type = str(row.get("source_type") or "").strip()
        source_id = _safe_int(row.get("source_id"))
        if source_type in {"worksheet", "exam"} and source_id > 0:
            assignment_ids.append(source_id)
    assignment_state_map = load_assignment_state_map(assignment_ids)

    for h_idx, row in enumerate(history_page_rows):
        title   = str(row.get("title") or t("smart_practice"))
        score   = row.get("score_pct", 0)
        total   = row.get("total_questions", 0)
        correct = row.get("correct_count", 0)
        xp      = row.get("xp_earned", 0)
        streak  = row.get("best_streak", 0)
        created = str(row.get("created_at") or "")[:16]
        session_id = row.get("id")
        subject = str(row.get("subject") or "").strip()
        topic = str(row.get("topic") or "").strip()
        assignment_state = assignment_state_map.get(_safe_int(row.get("source_id")), {})
        assignment_removed = str(assignment_state.get("status") or "").strip() == "archived"
        source_archived = bool(assignment_state.get("source_archived"))

        resource_kind = _practice_resource_kind(row)
        card_accent = resource_kind_accent(resource_kind)
        material_label = resource_kind_label(resource_kind)
        is_video_history = resource_kind == "video"

        if is_video_history:
            color = card_accent
            result_label = _ui_text("watched_label", "Watched")
        elif score >= 80:
            color = "#10B981"
            result_label = f"{round(score)}%"
        elif score >= 60:
            color = "#F59E0B"
            result_label = f"{round(score)}%"
        else:
            color = "#EF4444"
            result_label = f"{round(score)}%"
        subject_label = t(f"subject_{subject.lower().replace(' ', '_')}") if subject else ""
        if subject_label == f"subject_{subject.lower().replace(' ', '_')}":
            subject_label = subject

        left_col, right_col = st.columns([6, 2], gap="medium")
        with left_col:
            meta_bits = [bit for bit in [subject_label, topic, created] if bit]
            if is_video_history:
                stat_blocks = [
                    (
                        f"<div class='classio-practice-stat'>"
                        f"<div class='classio-practice-stat-label'>{_escape_html(_ui_text('views_label', 'Views'))}</div>"
                        f"<div class='classio-practice-stat-value'>{max(1, _safe_int(row.get('total_questions'), 1))}</div>"
                        f"</div>"
                    )
                ]
            else:
                stat_blocks = [
                    (
                        f"<div class='classio-practice-stat'>"
                        f"<div class='classio-practice-stat-label'>{t('correct')}</div>"
                        f"<div class='classio-practice-stat-value'>{correct}/{total}</div>"
                        f"</div>"
                    )
                ]
            if streak >= 2:
                stat_blocks.append(
                    f"<div class='classio-practice-stat'><div class='classio-practice-stat-label'>{t('best_streak')}</div>"
                    f"<div class='classio-practice-stat-value'>🔥 {streak}</div></div>"
                )
            if xp:
                stat_blocks.append(
                    f"<div class='classio-practice-stat'><div class='classio-practice-stat-label'>XP</div>"
                    f"<div class='classio-practice-stat-value'>+{xp}</div></div>"
                )
            st.markdown(
                f"""
                <div class="classio-practice-card" style="--practice-resource-accent:{card_accent};">
                    <div style="display:flex;justify-content:space-between;gap:12px;align-items:flex-start;flex-wrap:wrap;">
                        <div>
                            <div class="classio-practice-title">{_escape_html(title)}</div>
                            <div class="classio-practice-kind-chip">🧩 {_escape_html(material_label)}</div>
                            <div class="classio-practice-meta">{_escape_html(' · '.join(meta_bits))}</div>
                        </div>
                        <div style="font-size:1.05rem;font-weight:800;color:{color};background:{color}15;padding:8px 14px;border-radius:999px;border:1px solid {color}33;">
                            {_escape_html(result_label)}
                        </div>
                    </div>
                    <div class="classio-practice-statgrid">
                        {''.join(stat_blocks)}
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

        # Try Again button — reload the exercise data from the saved session
        exercise_data = row.get("exercise_data")
        with right_col:
            if assignment_removed or source_archived:
                if st.button(
                    t("archived_label"),
                    key=f"hist_archived_{session_id}_{h_idx}",
                    use_container_width=True,
                ):
                    st.info(t("assignment_source_archived_notice"))
            elif is_video_history:
                if st.button(
                    f"▶ {_ui_text('watch_again', 'Watch again')}",
                    key=f"hist_watch_again_{session_id}_{h_idx}",
                    use_container_width=True,
                    type="primary",
                ):
                    st.session_state[f"_history_watch_video_{session_id}_{h_idx}"] = True
                    st.rerun()
                if st.session_state.get(f"_history_watch_video_{session_id}_{h_idx}"):
                    video_payload = exercise_data or {}
                    if isinstance(video_payload, str):
                        try:
                            video_payload = json.loads(video_payload)
                        except Exception:
                            video_payload = {}
                    watch_url = str(
                        (video_payload or {}).get("watch_url")
                        or (video_payload or {}).get("youtube_url")
                        or ""
                    )
                    if not watch_url and _safe_int(row.get("source_id")) > 0:
                        video_row = load_video_record(_safe_int(row.get("source_id"))) or {}
                        watch_url = str(video_row.get("watch_url") or video_row.get("youtube_url") or "")
                    if watch_url:
                        st.video(watch_url)
                    else:
                        st.info(_ui_text("video_unavailable", "This video is not available right now."))
            elif (exercise_data or str(row.get("source_type") or "").strip() in {"worksheet", "exam"}) and st.button(
                    t("try_again"),
                    key=f"hist_retry_{session_id}_{h_idx}",
                    use_container_width=True,
                    type="primary",
                ):
                    if _open_history_practice_row(row, assignment_state=assignment_state):
                        st.session_state["_practice_retry_session_id"] = session_id
                        st.rerun()

        st.markdown("<div style='height:0.8rem;'></div>", unsafe_allow_html=True)
    _render_practice_pagination(history_rows, page_state_key)


def _render_active_video_session(video_payload: dict) -> None:
    watch_url = str(video_payload.get("watch_url") or video_payload.get("youtube_url") or "").strip()
    if st.button(f"← {t('back')}", key="practice_video_back"):
        st.session_state.pop("practice_video_payload", None)
        st.session_state.pop("practice_meta", None)
        st.session_state.pop("_practice_video_assignment_id", None)
        st.session_state.pop("_practice_video_logged", None)
        st.rerun()

    title = str(video_payload.get("title") or _ui_text("video_label", "Video")).strip()
    topic = str(video_payload.get("topic") or "").strip()
    subject = str(video_payload.get("subject") or "").strip()
    level = str(video_payload.get("level_or_band") or video_payload.get("level") or "").strip()
    meta_bits = []
    if subject:
        meta_bits.append(t(f"subject_{subject.lower().replace(' ', '_')}") if t(f"subject_{subject.lower().replace(' ', '_')}") != f"subject_{subject.lower().replace(' ', '_')}" else subject)
    if topic:
        meta_bits.append(topic)
    if level:
        meta_bits.append(level)

    st.markdown(f"### {title}")
    if meta_bits:
        st.caption(" · ".join(meta_bits))
    if watch_url:
        st.video(watch_url)
        st.link_button(t("open_on_youtube"), watch_url, use_container_width=True)
    else:
        st.info(_ui_text("video_unavailable", "This video is not available right now."))
    description = str(video_payload.get("description") or "").strip()
    if description:
        st.caption(description)

    if not st.session_state.get("_practice_video_logged"):
        st.session_state["_practice_video_logged"] = True
        assignment_id = _safe_int(st.session_state.get("_practice_video_assignment_id"))
        meta = st.session_state.get("practice_meta") or {}
        try:
            if assignment_id > 0:
                record_video_assignment_watch(assignment_id)
            else:
                record_video_practice_interaction(video_payload, meta=meta)
        except Exception:
            pass


# ── Progress tab ────────────────────────────────────────────────

def _render_progress_tab(progress_override=None, *, scope_key: str = ""):
    progress = progress_override if progress_override is not None else load_practice_progress()
    if progress.empty:
        render_empty_state(
            title_key="student_practice_progress_empty_title",
            body_key="student_practice_progress_empty_body",
            steps=[
                "student_practice_progress_empty_step_complete",
                "student_practice_progress_empty_step_patterns",
                "student_practice_progress_empty_step_recommend",
            ],
            icon="📈",
        )
        return

    if progress_override is None:
        progress = progress.copy()
        assignments_by_id = {
            _safe_int(row.get("id")): row
            for row in load_student_assignments()
            if _safe_int(row.get("id")) > 0
        }
        history_source_by_assignment: dict[int, str] = {}
        history_source_by_topic: dict[tuple[str, str, str], str] = {}
        try:
            history_for_kind = load_practice_history(limit=160)
        except Exception:
            history_for_kind = None
        if history_for_kind is not None and not history_for_kind.empty:
            for hist_row in history_for_kind.to_dict("records"):
                hist_kind = _practice_resource_kind(hist_row)
                if not _is_specific_resource_kind(hist_kind):
                    continue
                hist_assignment_id = _safe_int(hist_row.get("assignment_id"))
                if hist_assignment_id > 0:
                    history_source_by_assignment.setdefault(hist_assignment_id, hist_kind)
                hist_key = (
                    str(hist_row.get("subject") or "").strip().lower(),
                    str(hist_row.get("topic") or "").strip().lower(),
                    str(hist_row.get("level") or "").strip().lower(),
                )
                if hist_key[0] or hist_key[1] or hist_key[2]:
                    history_source_by_topic.setdefault(hist_key, hist_kind)

        def _progress_display_kind(row) -> str:
            current_kind = _practice_resource_kind(row.to_dict() if hasattr(row, "to_dict") else dict(row))
            if _is_specific_resource_kind(current_kind):
                return current_kind
            assignment_id = _safe_int(row.get("assignment_id"))
            assignment_row = assignments_by_id.get(assignment_id, {})
            assignment_kind = _practice_resource_kind(assignment_row)
            if _is_specific_resource_kind(assignment_kind):
                return assignment_kind
            if assignment_id > 0 and assignment_id in history_source_by_assignment:
                return history_source_by_assignment[assignment_id]
            hist_key = (
                str(row.get("subject") or "").strip().lower(),
                str(row.get("topic") or "").strip().lower(),
                str(row.get("level") or "").strip().lower(),
            )
            return history_source_by_topic.get(hist_key, current_kind)

        progress["_display_resource_kind"] = progress.apply(_progress_display_kind, axis=1)
        progress["_scope_teacher_id"] = progress.apply(
            lambda row: str(
                row.get("teacher_id")
                or assignments_by_id.get(_safe_int(row.get("assignment_id")), {}).get("teacher_id")
                or ""
            ),
            axis=1,
        )
        progress["_scope_teacher_name"] = progress.apply(
            lambda row: str(
                assignments_by_id.get(_safe_int(row.get("assignment_id")), {}).get("teacher_name")
                or ""
            ),
            axis=1,
        )
        subject_groups = _practice_subject_groups(progress)
        if len(subject_groups) > 1:
            tabs = st.tabs([f"📚 {label}" for subject_key, label, _frame in subject_groups])
            for tab, (subject_key, _label, scoped_progress) in zip(tabs, subject_groups):
                with tab:
                    _render_progress_tab(scoped_progress, scope_key=subject_key)
            return

    # ── Aggregate XP + rank banner ──────────────────────────────
    total_xp = int(progress["total_xp"].sum()) if "total_xp" in progress.columns else 0
    total_attempted = int(progress["total_attempted"].sum()) if "total_attempted" in progress.columns else 0
    total_correct   = int(progress["total_correct"].sum()) if "total_correct" in progress.columns else 0
    overall_pct     = round(total_correct / total_attempted * 100) if total_attempted else 0

    st.markdown(
        f"""
        <div style="
            display:flex; gap:12px; margin-bottom:14px; flex-wrap:wrap;
        ">
            <div style="flex:1;min-width:100px;text-align:center;padding:12px;border-radius:12px;background:var(--panel);border:1px solid var(--border);">
                <div style="font-size:1.3rem;font-weight:800;color:#8B5CF6;">{total_xp}</div>
                <div style="font-size:0.72rem;color:var(--muted);">{t('total_xp')}</div>
            </div>
            <div style="flex:1;min-width:100px;text-align:center;padding:12px;border-radius:12px;background:var(--panel);border:1px solid var(--border);">
                <div style="font-size:1.3rem;font-weight:800;color:#10B981;">{overall_pct}%</div>
                <div style="font-size:0.72rem;color:var(--muted);">{t('overall_accuracy')}</div>
            </div>
            <div style="flex:1;min-width:100px;text-align:center;padding:12px;border-radius:12px;background:var(--panel);border:1px solid var(--border);">
                <div style="font-size:1.3rem;font-weight:800;">{total_attempted}</div>
                <div style="font-size:0.72rem;color:var(--muted);">{t('questions_attempted')}</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # ── Per-topic breakdown ─────────────────────────────────────
    progress_rows = progress.reset_index(drop=True).to_dict("records")
    page_state_key = f"student_practice_progress_page_{scope_key or 'all'}"
    progress_page_rows, *_ = _slice_practice_page(progress_rows, page_state_key)

    for row in progress_page_rows:
        subject  = str(row.get("subject") or "").strip()
        topic    = str(row.get("topic") or "").strip()
        ex_type  = str(row.get("exercise_type") or "").strip()
        accuracy = row.get("accuracy_pct", 0)
        attempted = row.get("total_attempted", 0)
        row_xp   = row.get("total_xp", 0)
        resource_kind = _practice_resource_kind(row.get("_display_resource_kind") or row)
        card_accent = resource_kind_accent(resource_kind)
        is_video_progress = resource_kind == "video"

        label = " · ".join(filter(None, [
            t(f"subject_{subject.lower().replace(' ', '_')}") if subject else "",
            topic,
            _ui_text("video_label", "Video") if resource_kind == "video" else (t(ex_type) if t(ex_type) != ex_type else ex_type),
        ]))

        if is_video_progress:
            bar_color = card_accent
            top_badge = _ui_text("watched_label", "Watched")
        elif accuracy >= 80:
            bar_color = "#10B981"
            top_badge = f"{round(accuracy)}%"
        elif accuracy >= 60:
            bar_color = "#F59E0B"
            top_badge = f"{round(accuracy)}%"
        else:
            bar_color = "#EF4444"
            top_badge = f"{round(accuracy)}%"

        if is_video_progress:
            progress_width = 100
            stat_blocks = [
                (
                    f"<div class='classio-practice-stat'>"
                    f"<div class='classio-practice-stat-label'>{_escape_html(_ui_text('views_label', 'Views'))}</div>"
                    f"<div class='classio-practice-stat-value'>{attempted}</div>"
                    f"</div>"
                )
            ]
            if row_xp:
                stat_blocks.append(
                    f"<div class='classio-practice-stat'><div class='classio-practice-stat-label'>XP</div>"
                    f"<div class='classio-practice-stat-value'>{row_xp}</div></div>"
                )
        else:
            progress_width = min(accuracy, 100)
            stat_blocks = [
                (
                    f"<div class='classio-practice-stat'>"
                    f"<div class='classio-practice-stat-label'>{t('score_label')}</div>"
                    f"<div class='classio-practice-stat-value'>{round(accuracy)}%</div>"
                    f"</div>"
                ),
                (
                    f"<div class='classio-practice-stat'>"
                    f"<div class='classio-practice-stat-label'>{t('questions_attempted')}</div>"
                    f"<div class='classio-practice-stat-value'>{attempted}</div>"
                    f"</div>"
                ),
                (
                    f"<div class='classio-practice-stat'>"
                    f"<div class='classio-practice-stat-label'>XP</div>"
                    f"<div class='classio-practice-stat-value'>{row_xp}</div>"
                    f"</div>"
                ),
            ]

        st.markdown(
            f"""
            <div class="classio-practice-card" style="--practice-resource-accent:{card_accent};margin-bottom:0.75rem;">
                <div style="display:flex;justify-content:space-between;gap:12px;align-items:flex-start;flex-wrap:wrap;">
                    <div>
                        <div class="classio-practice-title">{_escape_html(label)}</div>
                    </div>
                    <div style="font-size:1.05rem;font-weight:800;color:{bar_color};background:{bar_color}15;padding:8px 14px;border-radius:999px;border:1px solid {bar_color}33;">
                        {_escape_html(top_badge)}
                    </div>
                </div>
                <div style="background:var(--border);border-radius:999px;height:10px;overflow:hidden;margin-top:0.95rem;">
                    <div style="width:{progress_width}%;height:100%;background:{bar_color};border-radius:999px;"></div>
                </div>
                <div class="classio-practice-statgrid">
                    {''.join(stat_blocks)}
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    _render_practice_pagination(progress_rows, page_state_key)


def _render_recommendation_subject_group(
    recommendations: list[dict],
    *,
    group_key: str,
) -> None:
    for idx in range(0, len(recommendations), 3):
        pair = recommendations[idx:idx + 3]
        cols = st.columns(3, gap="medium")
        for col_idx, item in enumerate(pair):
            row = {
                **(item.get("row") or {}),
                "_recommended_assignment_id": item.get("assignment_id"),
                "_recommended_assignment_status": item.get("assignment_status"),
                "_recommended_assignment_attempt_count": item.get("assignment_attempt_count"),
                "_recommended_assignment_teacher_name": (
                    item.get("assignment_teacher_name")
                    or item.get("program_teacher_name")
                ),
            }
            resource_type = str(item.get("resource_type") or "")
            item_key = f"{group_key}_{resource_type}_{row.get('id', idx)}_{idx}_{col_idx}"
            with cols[col_idx]:
                _render_practice_card(
                    title=str(item.get("title") or t("untitled_worksheet")),
                    subject=str(item.get("subject") or ""),
                    topic=str(item.get("topic") or ""),
                    level=str(item.get("level") or ""),
                    ws_type=str(item.get("exercise_type") or resource_type),
                    btn_key=f"sp_reco_{item_key}",
                    color=resource_kind_accent(resource_type),
                    row=row,
                    resource_type=resource_type,
                    recommendation_item=item,
                )
                for reason in item.get("reasons") or []:
                    st.caption(f"- {reason}")

                trigger_key = f"_start_sp_reco_{item_key}"
                if st.session_state.pop(trigger_key, False):
                    try:
                        assignment_id = _safe_int(item.get("assignment_id"))
                        if assignment_id > 0 and resource_type in {"worksheet", "exam"}:
                            assignment_row = load_student_assignment_by_id(assignment_id)
                            if assignment_row:
                                from app_pages.student_assignments import _open_assignment_practice

                                _open_assignment_practice(assignment_row)
                                st.rerun()
                        if resource_type == "worksheet":
                            if _open_worksheet_practice_from_row(row):
                                st.rerun()
                        elif resource_type == "exam":
                            if _open_exam_practice_from_row(row):
                                st.rerun()
                    except Exception as exc:
                        _show_practice_resource_unavailable(exc)


def _render_recommended_materials(pub_ws, pub_ex, pub_videos) -> None:
    recommendations = build_recommended_materials(
        pub_ws,
        pub_ex,
        pub_videos,
        limit=6,
    )
    if not recommendations:
        videos_empty = pub_videos is None or getattr(pub_videos, "empty", True)
        if pub_ws.empty and pub_ex.empty and videos_empty:
            return
        render_empty_state(
            title_key="student_practice_recommendations_empty_title",
            body_key="student_practice_recommendations_empty_body",
            steps=[
                "student_practice_recommendations_empty_step_practice",
                "student_practice_recommendations_empty_step_history",
                "student_practice_recommendations_empty_step_return",
            ],
            icon="✨",
        )
        return

    st.markdown(
        f"### {_ui_text('recommended_materials', 'Recommended for you')}"
    )
    st.caption(
        _ui_text(
            "recommended_materials_caption",
            "Start with these materials to strengthen weak areas, revisit past topics, and keep moving toward the next level.",
        )
    )
    recommendations = attach_student_recommendation_exposures(recommendations, surface="student_practice")
    log_student_recommendation_impressions(recommendations, surface="student_practice")

    recommendation_groups = group_recommendations_for_subject_tabs(recommendations)
    if len(recommendation_groups) > 1:
        tabs = st.tabs([str(group.get("label") or "") for group in recommendation_groups])
        for tab, group in zip(tabs, recommendation_groups):
            with tab:
                _render_recommendation_subject_group(
                    group.get("recommendations") or [],
                    group_key=str(group.get("key") or "subject"),
                )
    elif recommendation_groups:
        group = recommendation_groups[0]
        _render_recommendation_subject_group(
            group.get("recommendations") or [],
            group_key=str(group.get("key") or "subject"),
        )
    st.markdown("<div style='height:0.5rem;'></div>", unsafe_allow_html=True)


def _escape_html(value: str) -> str:
    import html as _html
    return _html.escape(str(value or ""))
