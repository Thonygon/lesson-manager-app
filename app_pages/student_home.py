import html as _html
import logging

import streamlit as st
from core.i18n import t
from core.navigation import go_to, STUDENT_PAGES
from core.state import get_current_user_id
from core.database import load_profile_row
from helpers.practice_engine import exam_to_exercises, worksheet_to_exercises
from helpers.notifications import (
    get_student_notifications,
    render_lazy_notification_panel,
)
from helpers.empty_states import render_empty_state
from helpers.quick_exam_storage import load_exam_record, load_public_exams
from helpers.student_recommendation_ml import log_student_recommendation_open
from helpers.student_recommendations import build_recommended_materials
from helpers.teacher_student_integration import load_student_assignment_by_id, record_video_assignment_watch
from helpers.video_library import load_public_videos
from helpers.worksheet_builder import normalize_worksheet_output
from helpers.worksheet_storage import load_public_worksheets, load_worksheet_record
from helpers.resource_gallery import (
    extract_gallery_language_label,
    extract_gallery_image_url,
    inject_resource_gallery_styles,
    render_gallery_card_html,
)
from services.permissions_service import user_has_feature

logger = logging.getLogger(__name__)


def _ui_text(key: str, fallback: str) -> str:
    value = t(key)
    return value if value != key else fallback


def _render_student_nav_card(card: dict) -> None:
    label = f"**{card['title']}**  \n{card['desc']}"
    clicked = st.button(label, key=f"student_card_{card['key']}", use_container_width=True)
    if clicked: go_to(str(card.get("key") or "student_home")); st.rerun()


def _open_home_recommendation_practice(item: dict) -> None:
    resource_type = str(item.get("resource_type") or "").strip()
    if resource_type not in {"worksheet", "exam"}:
        return

    assignment_id = int(item.get("assignment_id") or 0)
    if assignment_id > 0:
        assignment_row = load_student_assignment_by_id(assignment_id)
        if assignment_row:
            from app_pages.student_assignments import _open_assignment_practice

            log_student_recommendation_open(item, surface="student_home")
            _open_assignment_practice(assignment_row)
            return

    row = dict(item.get("row") or {})
    if resource_type == "worksheet":
        full_row = load_worksheet_record(row.get("id")) if row.get("id") else row
        worksheet_json = normalize_worksheet_output(dict((full_row or {}).get("worksheet_json") or {}))
        exercise_data = worksheet_to_exercises(worksheet_json, row_id=(full_row or row).get("id"))
    else:
        full_row = load_exam_record(row.get("id")) if row.get("id") else row
        exam_data = dict((full_row or {}).get("exam_data") or {})
        answer_key = dict((full_row or {}).get("answer_key") or {})
        exercise_data = exam_to_exercises(exam_data, answer_key, row_id=(full_row or row).get("id"))

    if not exercise_data.get("exercises"):
        st.warning(t("no_exercises_available"))
        return

    from app_pages.student_practice import _open_practice_item

    opened = _open_practice_item(
        exercise_data,
        {
            "subject": row.get("subject", ""),
            "topic": row.get("topic", ""),
            "learner_stage": row.get("learner_stage", ""),
            "level": row.get("level_or_band", "") or row.get("level", ""),
        },
    )
    if not opened:
        return
    log_student_recommendation_open(item, surface="student_home")
    go_to("student_practice")
    st.rerun()


def _load_student_home_recommendations(user_id: str) -> list[dict]:
    safe_user_id = str(user_id or "").strip()
    try:
        video_feature_enabled = user_has_feature(safe_user_id, "videos_access")
    except Exception:
        logger.exception("Failed to resolve student video feature access", extra={"user_id": safe_user_id})
        video_feature_enabled = False

    try:
        worksheets_df = load_public_worksheets(show_errors=False)
    except Exception:
        logger.exception("Failed to load public worksheets for student home", extra={"user_id": safe_user_id})
        worksheets_df = None

    try:
        exams_df = load_public_exams(show_errors=False)
    except Exception:
        logger.exception("Failed to load public exams for student home", extra={"user_id": safe_user_id})
        exams_df = None

    try:
        videos_df = load_public_videos() if video_feature_enabled else None
    except Exception:
        logger.exception("Failed to load public videos for student home", extra={"user_id": safe_user_id})
        videos_df = None

    try:
        return build_recommended_materials(
            worksheets_df,
            exams_df,
            videos_df,
            limit=3,
        )
    except Exception:
        logger.exception("Failed to build student home recommendations", extra={"user_id": safe_user_id})
        return []


def render_student_home():
    user_id = get_current_user_id()
    profile = load_profile_row(user_id) if user_id else {}
    display_name = str(
        profile.get("display_name")
        or st.session_state.get("user_name")
        or ""
    ).strip()
    first_name = display_name.split()[0] if display_name else t("student_role")

    # ── Hero section ──
    st.markdown(
        f"""
        <div style="
            position:relative;
            overflow:hidden;
            background:
              radial-gradient(circle at top right, rgba(34,197,94,0.18), transparent 36%),
              linear-gradient(135deg, color-mix(in srgb, var(--panel) 88%, rgba(59,130,246,0.18) 12%), color-mix(in srgb, var(--panel) 88%, rgba(20,184,166,0.14) 12%));
            border-radius: 22px;
            padding: 30px 26px 22px;
            margin-bottom: 24px;
            border: 1px solid color-mix(in srgb, var(--border) 76%, rgba(59,130,246,.26) 24%);
            box-shadow: var(--shadow-md);
        ">
            <div style="font-size:.78rem;letter-spacing:.08em;text-transform:uppercase;color:var(--muted);font-weight:800;margin-bottom:8px;">{t('student_home_command_center')}</div>
            <h2 style="margin:0 0 6px 0;font-size:1.8rem;line-height:1.18;">👋 {t("student_welcome_title").format(name=first_name)}</h2>
            <p style="margin:0; color:var(--muted); font-size:1.03rem;max-width:680px;">{t("student_welcome_subtitle")}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # ── Feature cards ──
    st.markdown(
        """
        <style>
        .st-key-student_card_student_practice,
        .st-key-student_card_student_study_plan,
        .st-key-student_card_student_assignments,
        .st-key-student_card_student_find_teacher {
            height: 100%;
        }
        .st-key-student_card_student_practice div[data-testid="stButton"] > button,
        .st-key-student_card_student_study_plan div[data-testid="stButton"] > button,
        .st-key-student_card_student_assignments div[data-testid="stButton"] > button,
        .st-key-student_card_student_find_teacher div[data-testid="stButton"] > button {
            position: relative;
            overflow: hidden;
            min-height: 210px;
            height: 210px;
            padding: 22px 18px 18px !important;
            border-radius: 24px !important;
            border: 1px solid color-mix(in srgb, var(--border-strong, rgba(15,23,42,.16)) 72%, var(--student-accent) 28%) !important;
            background:
                radial-gradient(circle at 50% -18%, rgba(var(--student-rgb), .24), transparent 42%),
                linear-gradient(180deg, color-mix(in srgb, var(--panel, #fff) 90%, white 10%), color-mix(in srgb, var(--panel-2, #f8fafc) 82%, var(--student-accent) 18%)) !important;
            box-shadow:
                0 24px 58px rgba(15,23,42,.12),
                inset 0 1px 0 rgba(255,255,255,.78) !important;
            text-align: center;
            color: var(--text, #0f172a) !important;
            transition: transform .18s ease, box-shadow .18s ease, border-color .18s ease !important;
            white-space: normal !important;
        }
        .st-key-student_card_student_practice div[data-testid="stButton"] > button:hover,
        .st-key-student_card_student_practice div[data-testid="stButton"] > button:focus,
        .st-key-student_card_student_study_plan div[data-testid="stButton"] > button:hover,
        .st-key-student_card_student_study_plan div[data-testid="stButton"] > button:focus,
        .st-key-student_card_student_assignments div[data-testid="stButton"] > button:hover,
        .st-key-student_card_student_assignments div[data-testid="stButton"] > button:focus,
        .st-key-student_card_student_find_teacher div[data-testid="stButton"] > button:hover,
        .st-key-student_card_student_find_teacher div[data-testid="stButton"] > button:focus {
            transform: translateY(-3px);
            border-color: color-mix(in srgb, var(--student-accent) 48%, rgba(255,255,255,.44)) !important;
            box-shadow:
                0 30px 68px rgba(15,23,42,.16),
                inset 0 1px 0 rgba(255,255,255,.82) !important;
        }
        .st-key-student_card_student_practice div[data-testid="stButton"] > button::before,
        .st-key-student_card_student_study_plan div[data-testid="stButton"] > button::before,
        .st-key-student_card_student_assignments div[data-testid="stButton"] > button::before,
        .st-key-student_card_student_find_teacher div[data-testid="stButton"] > button::before {
            position: absolute;
            top: 22px;
            left: 50%;
            width: 62px;
            height: 62px;
            transform: translateX(-50%);
            display: flex;
            align-items: center;
            justify-content: center;
            border-radius: 20px;
            background:
                linear-gradient(180deg, rgba(255,255,255,.74), rgba(255,255,255,.28)),
                color-mix(in srgb, var(--student-accent) 15%, transparent);
            border: 1px solid color-mix(in srgb, var(--student-accent) 28%, rgba(255,255,255,.72));
            box-shadow: 0 14px 28px rgba(var(--student-rgb), .16);
            font-size: 2rem;
            pointer-events: none;
        }
        .st-key-student_card_student_practice div[data-testid="stButton"] > button::after,
        .st-key-student_card_student_study_plan div[data-testid="stButton"] > button::after,
        .st-key-student_card_student_assignments div[data-testid="stButton"] > button::after,
        .st-key-student_card_student_find_teacher div[data-testid="stButton"] > button::after {
            content: "";
            position: absolute;
            left: 18px;
            right: 18px;
            top: 0;
            height: 4px;
            border-radius: 0 0 999px 999px;
            background: linear-gradient(90deg, transparent, var(--student-accent), transparent);
            opacity: .72;
        }
        .st-key-student_card_student_practice div[data-testid="stButton"] > button p,
        .st-key-student_card_student_study_plan div[data-testid="stButton"] > button p,
        .st-key-student_card_student_assignments div[data-testid="stButton"] > button p,
        .st-key-student_card_student_find_teacher div[data-testid="stButton"] > button p {
            position: relative;
            z-index: 1;
            display: block;
            max-width: 250px;
            margin: 78px auto 0;
            white-space: pre-line !important;
            text-align: center;
            font-size: .9rem;
            line-height: 1.45;
            font-weight: 650;
            color: var(--muted, #64748b) !important;
        }
        .st-key-student_card_student_practice div[data-testid="stButton"] > button p strong,
        .st-key-student_card_student_study_plan div[data-testid="stButton"] > button p strong,
        .st-key-student_card_student_assignments div[data-testid="stButton"] > button p strong,
        .st-key-student_card_student_find_teacher div[data-testid="stButton"] > button p strong {
            display: block;
            margin: 0 0 10px;
            font-size: 1.16rem;
            line-height: 1.16;
            font-weight: 900;
            color: var(--text, #0f172a) !important;
        }
        .st-key-student_card_student_practice div[data-testid="stButton"] > button p:first-child,
        .st-key-student_card_student_study_plan div[data-testid="stButton"] > button p:first-child,
        .st-key-student_card_student_assignments div[data-testid="stButton"] > button p:first-child,
        .st-key-student_card_student_find_teacher div[data-testid="stButton"] > button p:first-child {
            margin-inline: auto;
        }
        .st-key-student_card_student_practice div[data-testid="stButton"] > button::before {
            content: "🧠";
        }
        .st-key-student_card_student_study_plan div[data-testid="stButton"] > button::before {
            content: "📚";
        }
        .st-key-student_card_student_assignments div[data-testid="stButton"] > button::before {
            content: "🗂️";
        }
        .st-key-student_card_student_find_teacher div[data-testid="stButton"] > button::before {
            content: "🔍";
        }
        .st-key-student_card_student_practice {
            --student-accent: #2563EB;
            --student-rgb: 37,99,235;
        }
        .st-key-student_card_student_study_plan {
            --student-accent: #059669;
            --student-rgb: 5,150,105;
        }
        .st-key-student_card_student_assignments {
            --student-accent: #D97706;
            --student-rgb: 217,119,6;
        }
        .st-key-student_card_student_find_teacher {
            --student-accent: #7C3AED;
            --student-rgb: 124,58,237;
        }
        div[data-testid="stButton"] > button {
            border-radius: 18px !important;
            min-height: 3.1rem !important;
            font-weight: 850 !important;
            border: 1px solid color-mix(in srgb, var(--border-strong, rgba(15,23,42,.16)) 74%, rgba(59,130,246,.24) 26%) !important;
            background:
                linear-gradient(180deg, color-mix(in srgb, var(--panel, #fff) 92%, white 8%), color-mix(in srgb, var(--panel-2, #f8fafc) 86%, rgba(59,130,246,.08) 14%)) !important;
            box-shadow: 0 12px 26px rgba(15,23,42,.09), inset 0 1px 0 rgba(255,255,255,.72) !important;
            color: var(--text, #0f172a) !important;
        }
        div[data-testid="stButton"] > button:hover {
            transform: translateY(-1px);
            border-color: color-mix(in srgb, var(--primary, #2563eb) 45%, var(--border-strong, rgba(15,23,42,.16)) 55%) !important;
            box-shadow: 0 16px 34px rgba(15,23,42,.13), inset 0 1px 0 rgba(255,255,255,.82) !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    cards = [
        {
            "key": "student_practice",
            "icon": "🧠",
            "title": t("smart_practice"),
            "desc": t("smart_practice_desc"),
            "accent": "#2563EB",
            "rgb": "37,99,235",
        },
        {
            "key": "student_study_plan",
            "icon": "📚",
            "title": t("smart_study_plan"),
            "desc": t("smart_study_plan_desc"),
            "accent": "#059669",
            "rgb": "5,150,105",
        },
        {
            "key": "student_assignments",
            "icon": "🗂️",
            "title": t("student_assignments_title"),
            "desc": t("student_assignments_desc"),
            "accent": "#D97706",
            "rgb": "217,119,6",
        },
        {
            "key": "student_find_teacher",
            "icon": "🔍",
            "title": t("find_my_teacher"),
            "desc": t("find_my_teacher_desc"),
            "accent": "#7C3AED",
            "rgb": "124,58,237",
        },
    ]

    cols = st.columns(len(cards))
    for col, card in zip(cols, cards):
        with col:
            _render_student_nav_card(card)

    recommended = _load_student_home_recommendations(str(user_id or ""))
    if recommended:
        inject_resource_gallery_styles()
        urgent_review_item = next(
            (
                item
                for item in recommended
                if item.get("assigned_resource")
            ),
            None,
        )
        if urgent_review_item:
            urgent_resource_type = str(urgent_review_item.get("resource_type") or "")
            urgent_placeholder = (
                _ui_text("worksheet_label", "Worksheet")
                if urgent_resource_type == "worksheet"
                else _ui_text("exam_label", "Exam")
                if urgent_resource_type == "exam"
                else _ui_text("video_label", "Video")
            )
            urgent_title = str(urgent_review_item.get("title") or urgent_placeholder)
            urgent_topic = str(urgent_review_item.get("topic") or "")
            urgent_teacher = str(urgent_review_item.get("assignment_teacher_name") or "")
            review_reason = (
                (urgent_review_item.get("reasons") or [])
                or [_ui_text("student_material_reason_balanced", "A balanced next step based on recent progress")]
            )[0]
            teacher_line = f"{urgent_teacher} · " if urgent_teacher else ""
            st.markdown(
                f"""
                <div style="
                    margin:0 0 18px 0;
                    padding:18px 20px;
                    border-radius:20px;
                    border:1px solid color-mix(in srgb, var(--border) 70%, rgba(239,68,68,.28) 30%);
                    background:
                      radial-gradient(circle at top right, rgba(239,68,68,.12), transparent 36%),
                      linear-gradient(135deg, color-mix(in srgb, var(--panel) 90%, rgba(251,191,36,.08) 10%), color-mix(in srgb, var(--panel) 88%, rgba(239,68,68,.10) 12%));
                    box-shadow: var(--shadow-md);
                ">
                    <div style="font-size:.78rem;letter-spacing:.08em;text-transform:uppercase;color:var(--muted);font-weight:800;margin-bottom:8px;">{_ui_text('student_home_review_now_eyebrow', 'Review now')}</div>
                    <div style="font-size:1.18rem;font-weight:900;line-height:1.25;margin-bottom:6px;">{_html.escape(urgent_title)}</div>
                    <div style="color:var(--muted);font-size:.96rem;line-height:1.5;">{_html.escape(teacher_line + review_reason)}</div>
                    <div style="margin-top:8px;color:var(--muted);font-size:.9rem;">{_html.escape(urgent_topic)}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            action_col1, action_col2 = st.columns(2)
            with action_col1:
                if st.button(_ui_text("student_home_review_now_button", "Open Smart Practice"), key="student_home_review_now_btn", use_container_width=True, type="primary"):
                    go_to("student_practice")
                    st.rerun()
            with action_col2:
                if st.button(_ui_text("student_home_view_assignments_button", "View my assignments"), key="student_home_view_assignments_btn", use_container_width=True):
                    go_to("student_assignments")
                    st.rerun()
        st.markdown(f"### {_ui_text('recommended_materials', 'Recommended for you')}")
        st.caption(
            _ui_text(
                "recommended_materials_home_caption",
                "These are the best next materials for this student right now based on recent progress and practice history.",
            )
        )
        rec_cols = st.columns(min(3, len(recommended)), gap="medium")
        for idx, item in enumerate(recommended[:3]):
            row = item.get("row") or {}
            resource_type = str(item.get("resource_type") or "worksheet")
            resource_label = (
                _ui_text("worksheet_label", "Worksheet")
                if resource_type == "worksheet"
                else _ui_text("exam_label", "Exam")
                if resource_type == "exam"
                else _ui_text("video_label", "Video")
            )
            payload = dict(row or {})
            if resource_type in {"worksheet", "exam"} and not extract_gallery_image_url(payload) and row.get("id"):
                full_row = load_worksheet_record(row.get("id")) if resource_type == "worksheet" else load_exam_record(row.get("id"))
                payload = full_row or payload
            hero_image = extract_gallery_image_url(payload)
            language_label = extract_gallery_language_label(payload)
            chips = "".join(
                [
                    f'<span class="cm-resource-chip">{_html.escape(resource_label)}</span>',
                    f'<span class="cm-resource-chip">🌐 {_html.escape(language_label)}</span>' if language_label else "",
                    f'<span class="cm-resource-chip">🏷️ {_html.escape(str(item.get("level") or ""))}</span>' if item.get("level") else "",
                    f'<span class="cm-resource-chip">📌 {_html.escape(t("assignment_status_assigned"))}</span>' if item.get("assigned_resource") else "",
                    f'<span class="cm-resource-chip">⚙️ {_html.escape(t("mode_ai"))}</span>' if resource_type != "video" else "",
                ]
            )
            meta = f'<div class="cm-resource-meta">✨ {_html.escape((item.get("reasons") or [""])[0])}</div>'
            with rec_cols[idx]:
                st.markdown(
                    render_gallery_card_html(
                        kind="video" if resource_type == "video" else "exam" if resource_type == "exam" else "worksheet",
                        title=str(item.get("title") or "—"),
                        chips_html=chips,
                        description=str(item.get("topic") or t("no_description_available")),
                        meta_html=meta,
                        image_url=hero_image,
                        placeholder_label=resource_label,
                    ),
                    unsafe_allow_html=True,
                )
                action_label = _ui_text("watch_video", "Watch video") if resource_type == "video" else t("start_practice")
                if st.button(
                    f"▶ {action_label}",
                    key=f"student_home_recommend_action_{resource_type}_{item.get('id', idx)}",
                    use_container_width=True,
                    type="primary",
                ):
                    if resource_type == "video":
                        if int(item.get("assignment_id") or 0) > 0:
                            record_video_assignment_watch(int(item.get("assignment_id") or 0))
                        log_student_recommendation_open(item, surface="student_home")
                        st.session_state[f"_student_home_watch_video_{item.get('id', idx)}"] = True
                        st.rerun()
                    else:
                        _open_home_recommendation_practice(item)
                if resource_type == "video" and st.session_state.get(f"_student_home_watch_video_{item.get('id', idx)}"):
                    watch_url = str(payload.get("watch_url") or payload.get("youtube_url") or row.get("watch_url") or row.get("youtube_url") or "")
                    if watch_url:
                        st.video(watch_url)
        if st.button(_ui_text("open_recommended_materials", "Open recommended materials"), key="student_home_open_recommended", use_container_width=True):
            go_to("student_practice")
            st.rerun()
    else:
        render_empty_state(
            title_key="student_home_recommendations_empty_title",
            body_key="student_home_recommendations_empty_body",
            steps=[
                "student_home_recommendations_empty_step_practice",
                "student_home_recommendations_empty_step_teacher",
                "student_home_recommendations_empty_step_return",
            ],
            icon="✨",
        )
        cta_col, teacher_col = st.columns(2)
        with cta_col:
            if st.button(t("start_practice"), key="student_home_empty_start_practice", use_container_width=True, type="primary"):
                go_to("student_practice")
                st.rerun()
        with teacher_col:
            if st.button(t("student_assignments_empty_find_teacher"), key="student_home_empty_find_teacher", use_container_width=True):
                go_to("student_find_teacher")
                st.rerun()

    render_lazy_notification_panel(
        scope="student",
        toggle_key="student_home_notifications_toggle",
        loader=get_student_notifications,
        title_text=t("notifications"),
    )
