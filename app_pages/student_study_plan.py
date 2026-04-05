import streamlit as st
from core.i18n import t
from core.state import get_current_user_id


def render_student_study_plan():
    st.markdown(f"## 📚 {t('smart_study_plan')}")
    st.info(t("smart_study_plan_coming_soon"))

    st.markdown(f"### {t('study_plan_preview_title')}")

    col1, col2 = st.columns(2)
    with col1:
        st.markdown(
            f"""
            <div style="
                background: rgba(16,185,129,0.08);
                border-radius: 14px;
                padding: 18px;
                border: 1px solid var(--border);
            ">
                <h4 style="margin:0 0 8px 0;">🎯 {t("study_plan_goals")}</h4>
                <p style="margin:0; opacity:0.75; font-size:0.9rem;">{t("study_plan_goals_desc")}</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with col2:
        st.markdown(
            f"""
            <div style="
                background: rgba(168,85,247,0.08);
                border-radius: 14px;
                padding: 18px;
                border: 1px solid var(--border);
            ">
                <h4 style="margin:0 0 8px 0;">📅 {t("study_plan_schedule")}</h4>
                <p style="margin:0; opacity:0.75; font-size:0.9rem;">{t("study_plan_schedule_desc")}</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
