import html as _html
import re as _re_comm

import streamlit as st

from core.database import load_community_profiles, profile_can_teach
from core.i18n import t
from core.state import get_current_user_id
from helpers.lesson_planner import subject_label as _subj_label_fn


def render_community() -> None:
    user_id = str(get_current_user_id() or "").strip()

    st.markdown(f"### 🌐 {t('community_tab_title')}")
    st.caption(t("community_subtitle"))

    all_profiles = load_community_profiles()

    tab_teachers, tab_students = st.tabs([
        f"👩‍🏫 {t('teacher_role')}",
        f"🎓 {t('student_role')}",
    ])

    with tab_students:
        from app_pages.student_find_teacher import render_community_member_cards

        render_community_member_cards(all_profiles, role_filter="student")

    with tab_teachers:
        visible = [
            profile for profile in all_profiles
            if (profile.get("show_community_profile") or profile.get("user_id") == user_id)
            and profile_can_teach(profile)
        ]

        if not visible:
            st.info(t("community_empty"))
            return

        visible_ranked = sorted(
            visible,
            key=lambda profile: int(profile.get("active_student_count") or 0),
            reverse=True,
        )
        rank_map = {profile.get("user_id"): idx + 1 for idx, profile in enumerate(visible_ranked)}

        all_subjects: list[str] = []
        all_countries: list[str] = []
        all_edu: list[str] = []
        for profile in visible_ranked:
            for subject in (profile.get("primary_subjects") or []):
                if subject and subject != "other" and subject not in all_subjects:
                    all_subjects.append(subject)
            for subject in (profile.get("custom_subjects") or []):
                if subject and subject not in all_subjects:
                    all_subjects.append(subject)
            country = str(profile.get("country") or "").strip()
            if country and country not in all_countries:
                all_countries.append(country)
            education = str(profile.get("education_level") or "").strip()
            if education and education not in all_edu:
                all_edu.append(education)

        all_subjects = sorted(all_subjects)
        all_countries = sorted(all_countries)
        all_edu = sorted(all_edu)

        col_subject, col_country, col_edu = st.columns(3)
        with col_subject:
            selected_subject = st.selectbox(
                t("community_filter_subject"),
                [t("all")] + all_subjects,
                format_func=lambda value: _subj_label_fn(value) if value != t("all") else t("all"),
                key="community_subject_filter",
            )
        with col_country:
            selected_country = st.selectbox(
                t("country_label"),
                [t("all")] + all_countries,
                key="community_country_filter",
            )
        with col_edu:
            selected_edu = st.selectbox(
                t("education_level"),
                [t("all")] + all_edu,
                format_func=lambda value: t(value) if value != t("all") else t("all"),
                key="community_edu_filter",
            )

        any_filter = (
            selected_subject != t("all")
            or selected_country != t("all")
            or selected_edu != t("all")
        )
        filtered = visible_ranked
        if selected_subject != t("all"):
            filtered = [
                profile for profile in filtered
                if selected_subject in (profile.get("primary_subjects") or [])
                or selected_subject in (profile.get("custom_subjects") or [])
            ]
        if selected_country != t("all"):
            filtered = [
                profile for profile in filtered
                if str(profile.get("country") or "").strip() == selected_country
            ]
        if selected_edu != t("all"):
            filtered = [
                profile for profile in filtered
                if str(profile.get("education_level") or "").strip() == selected_edu
            ]

        display_profiles = filtered if any_filter else filtered[:10]

        if not display_profiles:
            st.info(t("community_empty"))
            return

        if not any_filter:
            st.caption(t("community_top10_hint"))
        else:
            st.caption(f"{len(display_profiles)} teachers")

        def _contact_btn(href: str, svg_path: str, color: str, label: str) -> str:
            return (
                f"<a href='{href}' target='_blank' rel='noopener noreferrer' "
                f"title='{label}' style='display:inline-flex;align-items:center;justify-content:center;"
                f"width:30px;height:30px;border-radius:50%;background:{color};text-decoration:none;'>"
                f"<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='white' width='15' height='15'>{svg_path}</svg>"
                f"</a>"
            )

        wa_svg = "<path d='M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347z'/><path d='M12 0C5.373 0 0 5.373 0 12c0 2.127.558 4.126 1.535 5.857L0 24l6.335-1.506A11.955 11.955 0 0012 24c6.627 0 12-5.373 12-12S18.627 0 12 0zm0 21.818a9.777 9.777 0 01-4.988-1.365l-.358-.214-3.761.894.952-3.653-.233-.374A9.772 9.772 0 012.182 12C2.182 6.57 6.57 2.182 12 2.182S21.818 6.57 21.818 12 17.43 21.818 12 21.818z'/>"
        email_svg = "<path d='M20 4H4c-1.1 0-2 .9-2 2v12c0 1.1.9 2 2 2h16c1.1 0 2-.9 2-2V6c0-1.1-.9-2-2-2zm0 4l-8 5-8-5V6l8 5 8-5v2z'/>"

        for profile in display_profiles:
            is_self = profile.get("user_id") == user_id
            show_full = bool(profile.get("show_community_profile")) or is_self
            show_contact = bool(profile.get("show_community_contact")) or is_self

            rank = rank_map.get(profile.get("user_id"), "")
            display_name = str(profile.get("display_name") or "").strip() or "—"
            username = str(profile.get("username") or "").strip()
            private_name = f"@{username}" if username else t("community_private_user")
            active_count = int(profile.get("active_student_count") or 0)
            subjects = profile.get("primary_subjects") or []
            custom_subjects = profile.get("custom_subjects") or []
            display_subjects = [_subj_label_fn(subject) for subject in subjects if subject != "other"] + [
                subject.title() for subject in custom_subjects if subject
            ]
            subject_labels = ", ".join(display_subjects) if display_subjects else "—"
            country = str(profile.get("country") or "").strip()
            education = str(profile.get("education_level") or "").strip()
            raw_phone = str(profile.get("phone_number") or "").strip()
            whatsapp_number = _re_comm.sub(r"[^\d+]", "", raw_phone)
            email = str(profile.get("email") or "").strip()
            avatar = str(profile.get("avatar_url") or "").strip()

            education_display = t(education) if education else ""
            self_badge = (
                "<span style='background:#3B82F6;color:#fff;border-radius:6px;padding:2px 8px;font-size:0.72rem;margin-left:6px;'>You</span>"
                if is_self
                else ""
            )
            rank_html = (
                f"<div style='font-size:0.85rem;font-weight:800;color:#f59e0b;min-width:26px;text-align:center;padding-top:16px;align-self:flex-start;'>#{rank}</div>"
                if rank
                else ""
            )

            if not show_full:
                st.caption(t("community_profile_empty"))
                continue

            safe_display_name = _html.escape(display_name)
            safe_subject_labels = _html.escape(subject_labels)
            safe_country = _html.escape(country)
            safe_education_display = _html.escape(education_display)

            avatar_html = (
                f"<img src='{avatar}' style='width:52px;height:52px;border-radius:50%;object-fit:cover;flex-shrink:0;' referrerpolicy='no-referrer' />"
                if avatar
                else "<div style='width:52px;height:52px;border-radius:50%;flex-shrink:0;background:linear-gradient(135deg,#60A5FA,#A78BFA);'></div>"
            )

            contact_parts: list[str] = []
            if country:
                contact_parts.append(
                    f"<span style='font-size:0.82rem;color:#64748b;'>🌍 {safe_country}</span>"
                )
            if show_contact:
                buttons = ""
                if whatsapp_number:
                    buttons += _contact_btn(
                        f"https://wa.me/{whatsapp_number.lstrip('+')}",
                        wa_svg,
                        "#25D366",
                        "WhatsApp",
                    )
                if email:
                    buttons += _contact_btn(
                        f"mailto:{email}",
                        email_svg,
                        "#3B82F6",
                        "Email",
                    )
                if buttons:
                    contact_parts.append(
                        f"<span style='margin-left:8px;display:inline-flex;gap:6px;vertical-align:middle;'>{buttons}</span>"
                    )

            if contact_parts:
                contact_html = (
                    "<div style='margin-top:5px;display:flex;align-items:center;flex-wrap:wrap;gap:4px;'>"
                    + "".join(contact_parts)
                    + "</div>"
                )
            else:
                contact_html = (
                    f"<div style='margin-top:5px;font-size:0.8rem;color:#64748b;opacity:0.8;'>{t('community_profile_empty')}</div>"
                )

            education_html = (
                f"<div style='font-size:0.82rem;color:#a78bfa;'>🎓 {safe_education_display}</div>"
                if education_display
                else ""
            )

            card_html = (
                "<div style='display:flex;align-items:flex-start;gap:10px;background:#1e293b;border-radius:12px;padding:14px 16px;margin-bottom:10px;border:1px solid #334155;'>"
                f"{rank_html}"
                f"{avatar_html}"
                "<div style='flex:1;min-width:0;'>"
                f"<div style='font-weight:700;font-size:1rem;color:#f1f5f9;'>{safe_display_name}{self_badge}</div>"
                f"<div style='font-size:0.82rem;color:#94a3b8;margin-top:2px;'>{safe_subject_labels}</div>"
                "<div style='display:flex;gap:14px;margin-top:6px;flex-wrap:wrap;'>"
                f"<div style='font-size:0.82rem;color:#38bdf8;'>👥 {active_count} {t('community_active_students')}</div>"
                f"{education_html}"
                "</div>"
                f"{contact_html}"
                "</div>"
                "</div>"
            )

            st.markdown(card_html, unsafe_allow_html=True)

