import html as _html

import streamlit as st
from core.i18n import t
from core.navigation import go_to, STUDENT_PAGES
from core.state import get_current_user_id
from core.database import load_profile_row
from helpers.notifications import (
    get_student_notifications,
    render_notification_cloud,
    render_notification_heading,
    render_notification_panel,
)
from helpers.empty_states import render_empty_state
from helpers.quick_exam_storage import load_exam_record, load_public_exams
from helpers.student_recommendations import build_recommended_materials
from helpers.worksheet_storage import load_public_worksheets, load_worksheet_record
from helpers.resource_gallery import (
    extract_gallery_language_label,
    extract_gallery_image_url,
    inject_resource_gallery_styles,
    render_gallery_card_html,
)


def _ui_text(key: str, fallback: str) -> str:
    value = t(key)
    return value if value != key else fallback


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

    student_notifications = get_student_notifications()
    render_notification_cloud(student_notifications, scope="student")

    # ── Feature cards ──
    st.markdown(
        """
        <style>
        .classio-student-home-grid-card {
            position: relative;
            overflow: hidden;
            min-height: 228px;
            padding: 24px 20px 22px;
            border-radius: 24px;
            border: 1px solid color-mix(in srgb, var(--border-strong, rgba(15,23,42,.16)) 72%, var(--student-accent) 28%);
            background:
                radial-gradient(circle at 50% -18%, rgba(var(--student-rgb), .24), transparent 42%),
                linear-gradient(180deg, color-mix(in srgb, var(--panel, #fff) 90%, white 10%), color-mix(in srgb, var(--panel-2, #f8fafc) 82%, var(--student-accent) 18%));
            box-shadow:
                0 24px 58px rgba(15,23,42,.12),
                inset 0 1px 0 rgba(255,255,255,.78);
            text-align: center;
            color: var(--text, #0f172a);
        }
        .classio-student-home-grid-card::before {
            content: "";
            position: absolute;
            inset: 0;
            background:
                linear-gradient(135deg, rgba(255,255,255,.55), transparent 42%),
                radial-gradient(circle at 18% 86%, rgba(var(--student-rgb), .14), transparent 34%);
            pointer-events: none;
        }
        .classio-student-home-grid-card::after {
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
        .classio-student-home-card-inner {
            position: relative;
            z-index: 1;
            height: 100%;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
        }
        .classio-student-home-card-icon {
            width: 62px;
            height: 62px;
            display: flex;
            align-items: center;
            justify-content: center;
            margin-bottom: 16px;
            border-radius: 20px;
            background:
                linear-gradient(180deg, rgba(255,255,255,.74), rgba(255,255,255,.28)),
                color-mix(in srgb, var(--student-accent) 15%, transparent);
            border: 1px solid color-mix(in srgb, var(--student-accent) 28%, rgba(255,255,255,.72));
            box-shadow: 0 14px 28px rgba(var(--student-rgb), .16);
            font-size: 2rem;
        }
        .classio-student-home-card-title {
            margin: 0;
            font-size: 1.1rem;
            line-height: 1.18;
            font-weight: 900;
            color: var(--text, #0f172a);
        }
        .classio-student-home-card-desc {
            margin: 12px auto 0;
            max-width: 260px;
            color: var(--muted, #64748b);
            font-size: .88rem;
            line-height: 1.48;
            font-weight: 650;
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
            st.markdown(
                f"""
                <div class="classio-student-home-grid-card" style="--student-accent:{card['accent']};--student-rgb:{card['rgb']};">
                    <div class="classio-student-home-card-inner">
                        <div class="classio-student-home-card-icon">{_html.escape(card['icon'])}</div>
                        <h4 class="classio-student-home-card-title">{_html.escape(card['title'])}</h4>
                        <p class="classio-student-home-card-desc">{_html.escape(card['desc'])}</p>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            if st.button(
                card["title"],
                key=f"student_card_{card['key']}",
                use_container_width=True,
            ):
                go_to(card["key"])
                st.rerun()

    recommended = build_recommended_materials(
        load_public_worksheets(),
        load_public_exams(),
        limit=3,
    )
    if recommended:
        inject_resource_gallery_styles()
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
            resource_label = _ui_text("worksheet_label", "Worksheet") if resource_type == "worksheet" else _ui_text("exam_label", "Exam")
            payload = dict(row or {})
            if not extract_gallery_image_url(payload) and row.get("id"):
                full_row = load_worksheet_record(row.get("id")) if resource_type == "worksheet" else load_exam_record(row.get("id"))
                payload = full_row or payload
            hero_image = extract_gallery_image_url(payload)
            language_label = extract_gallery_language_label(payload)
            chips = "".join(
                [
                    f'<span class="cm-resource-chip">{_html.escape(resource_label)}</span>',
                    f'<span class="cm-resource-chip">🌐 {_html.escape(language_label)}</span>' if language_label else "",
                    f'<span class="cm-resource-chip">🏷️ {_html.escape(str(item.get("level") or ""))}</span>' if item.get("level") else "",
                    f'<span class="cm-resource-chip">⚙️ {_html.escape(t("mode_ai"))}</span>',
                ]
            )
            meta = f'<div class="cm-resource-meta">✨ {_html.escape((item.get("reasons") or [""])[0])}</div>'
            with rec_cols[idx]:
                st.markdown(
                    render_gallery_card_html(
                        kind="exam" if resource_type == "exam" else "worksheet",
                        title=str(item.get("title") or "—"),
                        chips_html=chips,
                        description=str(item.get("topic") or t("no_description_available")),
                        meta_html=meta,
                        image_url=hero_image,
                        placeholder_label=resource_label,
                    ),
                    unsafe_allow_html=True,
                )
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

    render_notification_heading(student_notifications, scope="student", title_text=t("notifications"))
    render_notification_panel(
        student_notifications,
        scope="student",
        toggle_key="student_home_notifications_toggle",
    )
