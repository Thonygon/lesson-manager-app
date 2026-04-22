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
            background: linear-gradient(135deg, rgba(59,130,246,0.12), rgba(16,185,129,0.08));
            border-radius: 18px;
            padding: 28px 24px 20px;
            margin-bottom: 24px;
            border: 1px solid var(--border);
        ">
            <h2 style="margin:0 0 4px 0;">👋 {t("student_welcome_title").format(name=first_name)}</h2>
            <p style="margin:0; opacity:0.8; font-size:1.05rem;">{t("student_welcome_subtitle")}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    student_notifications = get_student_notifications()
    render_notification_cloud(student_notifications, scope="student")

    # ── Feature cards ──
    cards = [
        {
            "key": "student_practice",
            "icon": "🧠",
            "title": t("smart_practice"),
            "desc": t("smart_practice_desc"),
            "color": "rgba(59,130,246,0.12)",
        },
        {
            "key": "student_study_plan",
            "icon": "📚",
            "title": t("smart_study_plan"),
            "desc": t("smart_study_plan_desc"),
            "color": "rgba(16,185,129,0.12)",
        },
        {
            "key": "student_assignments",
            "icon": "🗂️",
            "title": t("student_assignments_title"),
            "desc": t("student_assignments_desc"),
            "color": "rgba(245,158,11,0.12)",
        },
        {
            "key": "student_find_teacher",
            "icon": "🔍",
            "title": t("find_my_teacher"),
            "desc": t("find_my_teacher_desc"),
            "color": "rgba(168,85,247,0.12)",
        },
    ]

    cols = st.columns(len(cards))
    for col, card in zip(cols, cards):
        with col:
            st.markdown(
                f"""
                <div style="
                    background: {card['color']};
                    border-radius: 16px;
                    padding: 22px 18px;
                    text-align: center;
                    border: 1px solid var(--border);
                    min-height: 160px;
                    display: flex;
                    flex-direction: column;
                    justify-content: center;
                ">
                    <div style="font-size: 2.2rem; margin-bottom: 8px;">{card['icon']}</div>
                    <h4 style="margin: 0 0 6px 0;">{card['title']}</h4>
                    <p style="margin: 0; opacity: 0.75; font-size: 0.9rem;">{card['desc']}</p>
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

    render_notification_heading(student_notifications, scope="student", title_text=t("notifications"))
    render_notification_panel(
        student_notifications,
        scope="student",
        toggle_key="student_home_notifications_toggle",
    )
